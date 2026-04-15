"""Checkpoint 3 — Cross-references to tables and figures.

Uses python-docx XML parsing to follow actual Word cross-reference fields
(REF field codes) rather than plain text search.  This correctly handles
declined forms of «Таблица» / «Рисунок» because the reference is encoded
as a bookmark ID, not as display text.

Algorithm:
1. Walk ``doc.element.body`` and collect ``w:bookmarkStart`` elements.
   Those that sit inside a paragraph whose text matches the caption pattern
   (e.g. «Таблица 3.1-2 — …» or «Рисунок 3.1-2 — …») are recorded as
   caption bookmarks.
2. Walk all paragraphs and locate ``w:instrText`` nodes containing
   ``REF <bookmark_name>``.  For every such field collect:
   - the visible text rendered by the field (text of sibling ``w:t`` nodes
     after the field begin mark),
   - surrounding context (the paragraph itself + one paragraph before/after).
3. Build a dict ``{bookmark_name: {caption, mentions}}``.
4. Send to AI for verification.  Captions with zero mentions are also errors.
"""

from __future__ import annotations

import json
import re
from typing import Any

import ai_client
from checkpoints.base import BaseCheckpoint
from doc_parser import DocData

# Namespace shorthand used in python-docx XML.
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_CAPTION_RE = re.compile(
    r"^(Таблица|Рисунок)\s+[\d\.]+[-–—][\d\.]+",
    re.IGNORECASE,
)

_AI_PROMPT = """Ты эксперт по проверке технических отчётов.
Тебе передан словарь перекрёстных ссылок в документе.
Каждый ключ — это ID закладки Word (bookmark), значение содержит:
  - "caption": текст подписи к таблице или рисунку
  - "mentions": список объектов с полями:
      "ref_text"  — отображаемый текст ссылки (может быть в любом падеже)
      "context"   — абзац, в котором стоит ссылка, с соседними абзацами

Твоя задача — проверить:
1. Есть ли у каждой подписи хотя бы одно упоминание; если нет — ошибка.
2. Соответствует ли контекст упоминания смыслу подписи;
   если ссылка явно не соответствует или бессмысленна — ошибка.

Формат ответа — строго JSON-массив объектов:
[
  {"caption": "...", "error": "...описание проблемы..."}
]
Если ошибок нет — верни пустой массив: []
Отвечай только JSON, без пояснений.
"""


def _para_text(para_elem: Any) -> str:
    """Return plain text of a paragraph XML element."""
    return "".join(
        node.text or ""
        for node in para_elem.iter(f"{{{_W}}}t")
    )


def _collect_caption_bookmarks(doc: Any) -> dict[str, str]:
    """Return {bookmark_name: caption_text} for table/figure captions."""
    captions: dict[str, str] = {}
    body = doc.element.body

    for para in body.iter(f"{{{_W}}}p"):
        text = _para_text(para).strip()
        if not _CAPTION_RE.match(text):
            continue
        for bm in para.iter(f"{{{_W}}}bookmarkStart"):
            name = bm.get(f"{{{_W}}}name", "")
            if name:
                captions[name] = text

    return captions


def _collect_ref_fields(
    doc: Any,
    caption_bookmarks: dict[str, str],
) -> dict[str, list[dict]]:
    """Return {bookmark_name: [mention, ...]} by walking REF field codes."""
    mentions: dict[str, list[dict]] = {k: [] for k in caption_bookmarks}
    body = doc.element.body
    paragraphs = list(body.iter(f"{{{_W}}}p"))

    for para_idx, para in enumerate(paragraphs):
        instr_texts = [
            node.text or ""
            for node in para.iter(f"{{{_W}}}instrText")
        ]
        for instr in instr_texts:
            instr = instr.strip()
            if not instr.upper().startswith("REF "):
                continue
            # REF _Ref123 \h  →  bookmark name is the second token
            parts = instr.split()
            if len(parts) < 2:
                continue
            bm_name = parts[1]
            if bm_name not in caption_bookmarks:
                continue

            # Visible text: collect w:t after fldChar type="begin" up to "end"
            ref_text = _extract_field_display_text(para)

            # Context: previous + current + next paragraph texts
            ctx_parts = []
            if para_idx > 0:
                ctx_parts.append(_para_text(paragraphs[para_idx - 1]).strip())
            ctx_parts.append(_para_text(para).strip())
            if para_idx < len(paragraphs) - 1:
                ctx_parts.append(_para_text(paragraphs[para_idx + 1]).strip())
            context = "\n".join(p for p in ctx_parts if p)

            mentions[bm_name].append({
                "ref_text": ref_text,
                "context": context,
            })

    return mentions


def _extract_field_display_text(para_elem: Any) -> str:
    """Extract the text that Word renders for the first REF field in *para_elem*.

    Collects ``w:t`` text between ``w:fldChar type=separate`` and
    ``w:fldChar type=end``.
    """
    collecting = False
    parts: list[str] = []

    for node in para_elem.iter():
        tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
        if tag == "fldChar":
            ftype = node.get(f"{{{_W}}}fldCharType", "")
            if ftype == "separate":
                collecting = True
            elif ftype == "end":
                collecting = False
        elif tag == "t" and collecting:
            parts.append(node.text or "")

    return "".join(parts).strip()


class CheckReferences(BaseCheckpoint):
    name = "Перекрёстные ссылки на таблицы и рисунки"
    supported_formats = ["docx"]

    def run(self, doc_data: DocData) -> list[dict]:
        doc = doc_data.raw_docx
        if doc is None:
            return []

        caption_bookmarks = _collect_caption_bookmarks(doc)
        if not caption_bookmarks:
            return []

        ref_mentions = _collect_ref_fields(doc, caption_bookmarks)

        # Build the dict to send to AI.
        payload: dict[str, dict] = {}
        for bm_name, caption in caption_bookmarks.items():
            payload[bm_name] = {
                "caption": caption,
                "mentions": ref_mentions.get(bm_name, []),
            }

        ai_response = ai_client.check_references(payload, _AI_PROMPT)

        errors: list[dict] = []
        for item in ai_response:
            errors.append({
                "location": item.get("caption", ""),
                "error": item.get("error", ""),
            })
        return errors
