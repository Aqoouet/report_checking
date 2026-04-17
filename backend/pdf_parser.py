"""PDF document parser.

Produces a ``DocData`` object whose ``sections`` are individual pages (or groups
of pages when ``PDF_PAGES_PER_CHUNK`` > 1) and whose ``fig_table_dict`` contains
figure/table captions found via text scan.
Cross-reference checking is intentionally not supported for PDF — only clarity
and units checkpoints run on PDF output.
"""

from __future__ import annotations

import os
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

# Number of consecutive PDF pages merged into a single AI call (default 1).
# Increase only if you have a large-context model; small local models tend to
# perform *worse* with very large chunks (lost-in-the-middle).
_PDF_PAGES_PER_CHUNK: int = max(1, int(os.getenv("PDF_PAGES_PER_CHUNK", "1")))


def _build_repeating_fingerprints(pdf: fitz.Document, threshold: float = 0.4) -> set[str]:
    """Return normalised fingerprints of text blocks that repeat on many pages.

    Running headers/footers appear on almost every page, often varying only by
    the page number or date.  Stripping digits before comparison lets us match
    "Стр. 43 из 93" and "Стр. 44 из 93" as the same fingerprint.

    A fingerprint is considered repeating when it occurs on at least
    ``max(3, n_pages * threshold)`` distinct pages.
    """
    n_pages = len(pdf)
    if n_pages < 3:
        return set()
    counts: dict[str, int] = {}
    for page_num in range(n_pages):
        seen: set[str] = set()
        for b in pdf[page_num].get_text("blocks"):
            if b[6] != 0:
                continue
            text = b[4].strip()
            if not text:
                continue
            fp = re.sub(r"\d+", "", text).strip()
            if fp and fp not in seen:
                seen.add(fp)
                counts[fp] = counts.get(fp, 0) + 1
    min_count = max(3, int(n_pages * threshold))
    return {fp for fp, c in counts.items() if c >= min_count}


def _extract_page_text(page: fitz.Page, repeating: set[str]) -> str:
    """Extract text from *page*, using table detection for structured table content.

    Tables are rendered as pipe-separated rows (``cell1 | cell2 | …``) so the AI
    receives ``DAN6-8 (ремонтный) | 6.40 | 1,55`` on a single line instead of
    three separate lines — dramatically improving units-checking accuracy.
    Non-table blocks are extracted as plain text, with repeating header/footer
    fingerprints stripped.
    """
    try:
        tabs = page.find_tables()
        table_rects: list[fitz.Rect] = [fitz.Rect(tab.bbox) for tab in tabs]
    except Exception:
        tabs = []
        table_rects = []

    parts: list[tuple[float, str]] = []  # (y0, text)

    # Non-table text blocks
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        text = b[4].strip()
        if not text:
            continue
        fp = re.sub(r"\d+", "", text).strip()
        if fp in repeating:
            continue
        b_rect = fitz.Rect(b[:4])
        if any(b_rect.intersects(tr) for tr in table_rects):
            continue  # handled below as structured table rows
        parts.append((b[1], text))

    # Table content as pipe-separated rows
    for tab in tabs:
        rows = tab.extract()
        if not rows:
            continue
        lines: list[str] = []
        for row in rows:
            cells = [c.strip().replace("\n", " ") if c else "" for c in row]
            if any(cells):
                lines.append(" | ".join(cells))
        if lines:
            parts.append((tab.bbox[1], "\n".join(lines)))

    parts.sort(key=lambda x: x[0])
    return "\n".join(text for _, text in parts)


def _section_in_range(section_number: str, items: list[dict]) -> bool:
    """Return True if any page covered by *section_number* falls within *items*.

    *section_number* may be a single page ("43") or a range ("43-46").
    """
    try:
        parts = re.split(r"[-–]", section_number)
        first = int(re.sub(r"\D", "", parts[0]))
        last = int(re.sub(r"\D", "", parts[-1])) if len(parts) > 1 else first
    except (ValueError, IndexError):
        return False
    return any(_page_in_range(p, items) for p in range(first, last + 1))


def parse_pdf(file_path: str, range_spec: dict | None) -> DocData:
    """Parse *file_path* (.pdf) into a :class:`DocData`."""
    pdf = fitz.open(file_path)
    repeating = _build_repeating_fingerprints(pdf)

    # Collect non-empty per-page texts in order
    page_texts: list[tuple[int, str]] = []  # (1-based page num, cleaned text)
    for page_num in range(len(pdf)):
        page_text = _extract_page_text(pdf[page_num], repeating)
        if page_text:
            page_texts.append((page_num + 1, page_text))

    # Group consecutive pages into chunks (default: 1 page per chunk)
    sections: list[Section] = []
    for i in range(0, len(page_texts), _PDF_PAGES_PER_CHUNK):
        chunk = page_texts[i : i + _PDF_PAGES_PER_CHUNK]
        first_page = chunk[0][0]
        last_page = chunk[-1][0]
        combined_text = "\n\n".join(text for _, text in chunk)
        if first_page == last_page:
            label = str(first_page)
            title = f"Страница {first_page}"
        else:
            label = f"{first_page}-{last_page}"
            title = f"Страницы {first_page}–{last_page}"
        sections.append(Section(number=label, title=title, text=combined_text, level=0))

    if range_spec and range_spec.get("type") == "pages":
        items = range_spec.get("items", [])
        if items:
            sections = [s for s in sections if _section_in_range(s.number, items)]

    fig_table_dict = _build_fig_table_dict_pdf(sections)

    if range_spec and range_spec.get("type") == "pages":
        items = range_spec.get("items", [])
        if items:
            fig_table_dict = [
                e for e in fig_table_dict
                if _section_in_range(e.section_number, items)
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
