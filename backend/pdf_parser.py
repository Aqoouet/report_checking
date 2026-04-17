"""PDF document parser.

Produces a ``DocData`` object whose ``sections`` are individual pages and whose
``fig_table_dict`` contains figure/table captions found via text scan.
Cross-reference checking is intentionally not supported for PDF — only clarity
and units checkpoints run on PDF output.
"""

from __future__ import annotations

import re

import fitz  # PyMuPDF

from doc_models import (
    CAPTION_RE as _CAPTION_RE,
    MENTION_RE as _MENTION_RE,
    DocData,
    FigTableEntry,
    FigTableMention,
    Section,
    normalise_mention as _normalise_mention,
)


def parse_pdf(file_path: str, range_spec: dict | None) -> DocData:
    """Parse *file_path* (.pdf) into a :class:`DocData`."""
    pdf = fitz.open(file_path)
    sections: list[Section] = []

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        blocks = page.get_text("blocks")
        page_text = "\n".join(
            b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()
        )
        if not page_text:
            continue
        page_label = str(page_num + 1)
        sections.append(Section(
            number=page_label,
            title=f"Страница {page_label}",
            text=page_text,
            level=0,
        ))

    if range_spec and range_spec.get("type") == "pages":
        items = range_spec.get("items", [])
        if items:
            sections = [s for s in sections if _page_in_range(int(s.number), items)]

    fig_table_dict = _build_fig_table_dict_pdf(sections)

    if range_spec and range_spec.get("type") == "pages":
        items = range_spec.get("items", [])
        if items:
            fig_table_dict = [
                e for e in fig_table_dict
                if _page_in_range(int(e.section_number), items)
            ]

    return DocData(fmt="pdf", file_path=file_path,
                   sections=sections, fig_table_dict=fig_table_dict, raw_pdf=pdf)


def _page_in_range(page_num: int, items: list[dict]) -> bool:
    for item in items:
        try:
            s = int(re.sub(r"\D", "", str(item.get("start", page_num))))
            e = int(re.sub(r"\D", "", str(item.get("end", item.get("start", page_num)))))
            if s <= page_num <= e:
                return True
        except (ValueError, TypeError):
            pass
    return False


def _build_fig_table_dict_pdf(sections: list[Section]) -> list[FigTableEntry]:
    entries: dict[str, FigTableEntry] = {}

    for sec in sections:
        lines = sec.text.splitlines()
        for line in lines:
            m = _CAPTION_RE.match(line.strip())
            if m:
                label = m.group(0).strip()
                if label not in entries:
                    entries[label] = FigTableEntry(
                        label=label, caption=line.strip(), section_number=sec.number
                    )

    for sec in sections:
        lines = sec.text.splitlines()
        for line_idx, line in enumerate(lines):
            for m in _MENTION_RE.finditer(line):
                label_candidate = _normalise_mention(m.group(0))
                if label_candidate not in entries:
                    continue
                ctx_start = max(0, line_idx - 1)
                ctx_end = min(len(lines), line_idx + 2)
                context = "\n".join(lines[ctx_start:ctx_end])
                entries[label_candidate].mentions.append(
                    FigTableMention(context=context, section_number=sec.number)
                )

    return list(entries.values())
