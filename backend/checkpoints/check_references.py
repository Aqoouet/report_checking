"""Checkpoint 3 — Cross-references to tables and figures.

Uses the pre-built ``doc_data.fig_table_dict`` (populated by ``doc_parser``)
so that the dictionary is constructed once for the whole document regardless of
any range filter applied to sections.

For each table/figure entry the AI is asked to assess:
1. Whether there is at least one mention in the text.
2. Whether the context of each mention is semantically compatible with the caption.

Progress updates set ``checkpoint_sub_name`` to the current table/figure label so
the GUI can show it together with the AI response for the previous item.
"""

from __future__ import annotations

import re

import ai_client
import jobs as job_store
from jobs import JobCancelledError
from checkpoints.base import BaseCheckpoint
from doc_parser import DocData, FigTableEntry

_AI_PROMPT = """Ты проверяешь технический отчёт.

Тебе дана ТЕМА таблицы и список того, что написано об этой таблице в тексте.

ЗАДАЧА: для каждого пункта определи — совпадает ли его тема с ТЕМОЙ таблицы?
Явное несовпадение → ошибка.
Пункт без конкретной темы (просто ссылка) → ОК.
Если пунктов нет → ошибка: таблица не упомянута.

ПРИМЕР ОШИБКИ:
  ТЕМА таблицы: «Данные о крепежах»
  Пункт 1: «Данные об овощах» → ОШИБКА: «овощи» ≠ «крепежи»

Начни с «Ошибок не найдено.» если всё ОК.
Иначе — укажи номер пункта и в чём несоответствие. Максимум 150 токенов.
"""

# All natural-language variants of "no errors found" any model might output.
_NO_ERROR_VARIANTS = (
    "ошибок не найдено",
    "ошибки не найдено",
    "ошибка не найдена",
    "нет ошибок",
    "ошибок нет",
    "без ошибок",
    "все в порядке",
    "всё в порядке",
    "all good",
    "no errors",
    "no issues",
)


def _is_no_error(result: str) -> bool:
    r = result.lower().strip()
    return any(v in r for v in _NO_ERROR_VARIANTS)


class CheckReferences(BaseCheckpoint):
    name = "Перекрёстные ссылки на таблицы и рисунки"
    short_name = "Ссылки на таблицы и рисунки"
    supported_formats = ["docx", "pdf"]

    def run(self, doc_data: DocData, *, job_id: str | None = None) -> list[dict]:
        entries = doc_data.fig_table_dict
        if not entries:
            return []

        errors: list[dict] = []
        total = len(entries)

        for i, entry in enumerate(entries):
            sub_name = entry.label

            if job_id:
                job = job_store.get_job(job_id)
                if job:
                    job.checkpoint_sub_current = i + 1
                    job.checkpoint_sub_total = total
                    job.checkpoint_sub_location = entry.label
                    job.checkpoint_sub_name = sub_name
                    job_store.update_job(job)

            payload_text = _format_entry(entry)

            result = ai_client.check_text_chunk(payload_text, _AI_PROMPT)

            if job_id:
                job = job_store.get_job(job_id)
                if job:
                    job.previous_result = result.strip() if result else ""
                    job_store.update_job(job)
                    if job.cancelled:
                        raise JobCancelledError()

            if result and not _is_no_error(result):
                errors.append({
                    "location": entry.label,
                    "error": result.strip(),
                })

        return errors


_CLAIM_VERBS = re.compile(
    r"приведен|представлен|показан|содержит|включает|перечислен|указан",
    re.IGNORECASE,
)

# Match claim verbs plus everything after them (to strip the "в таблице X" tail).
_CLAIM_SPLIT = re.compile(
    r"\s*(?:приведен[аыо]?|представлен[аыо]?|показан[аыо]?|содержит(?:ся)?|"
    r"включает(?:ся)?|перечислен[аыо]?|указан[аыо]?)\b.*",
    re.IGNORECASE | re.DOTALL,
)


def _extract_claim(sentence: str) -> str:
    """Strip the 'приведены/представлено в таблице X' tail from a sentence.

    'Данные об овощах приведены в таблице T-3.' → 'Данные об овощах'
    Falls back to the full sentence if no verb is found.
    """
    shortened = _CLAIM_SPLIT.sub("", sentence).strip()
    return shortened if shortened else sentence.strip()

_CAPTION_SEP = re.compile(r"\s*[–—-]\s*")


def _caption_topic(caption: str) -> str:
    """Extract the descriptive part of a caption (after the dash separator)."""
    parts = _CAPTION_SEP.split(caption, maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return caption.strip()


def _key_sentence(context: str, label: str) -> str:
    """Return the sentence from *context* that directly references *label*.

    Prefers sentences that contain a claim verb (приведены/представлено/…) AND
    a word from *label*.  Falls back to the first non-empty sentence.
    """
    # Split on sentence-ending punctuation or newlines.
    parts = re.split(r"(?<=[.!?])\s+|\n+", context)
    label_words = {w.lower() for w in label.split() if len(w) > 3}

    # First pass: sentence with claim verb AND a label word.
    for part in parts:
        s = part.strip()
        if not s:
            continue
        s_lower = s.lower()
        if _CLAIM_VERBS.search(s) and any(w in s_lower for w in label_words):
            return s

    # Second pass: any sentence with a claim verb.
    for part in parts:
        s = part.strip()
        if s and _CLAIM_VERBS.search(s):
            return s

    # Fallback: first non-empty sentence.
    for part in parts:
        s = part.strip()
        if s:
            return s[:300]

    return context[:300]


def _format_entry(entry: FigTableEntry) -> str:
    topic = _caption_topic(entry.caption)
    lines = [
        f"ТЕМА таблицы/рисунка: «{topic}»",
        "",
        f"Что написано об этом объекте в тексте:",
    ]
    if not entry.mentions:
        lines.append("  (нет упоминаний)")
    for i, m in enumerate(entry.mentions, 1):
        key = _key_sentence(m.context, entry.label)
        claim = _extract_claim(key)
        lines.append(f"  {i}. «{claim}»")
    return "\n".join(lines)
