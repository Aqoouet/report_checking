"""Parse a Markdown document (produced by docling-serve) into Sections.

Docling emits ATX headings (``# Title``, ``## 3.2 Title``, etc.).
We split on headings, extract the numeric prefix as the section number,
and optionally filter by a range spec.
"""

from __future__ import annotations

import re

from doc_models import Section

# Matches ATX headings: captures (hashes, heading text)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Numeric section prefix: "3", "3.2", "3.2.1"
_NUMBER_RE = re.compile(r"^((?:\d+[.\-])*\d+)\.?\s+(.*)")


def parse_sections(md_text: str, range_spec: dict | None = None) -> list[Section]:
    """Split *md_text* on ATX headings and return a list of leaf :class:`Section`.

    Parameters
    ----------
    md_text:
        Full Markdown string from docling-serve.
    range_spec:
        Optional filter dict: ``{"type": "sections", "items": [{"start": "3.1", "end": "3.4"}]}``.
        When provided only sections whose number falls within the given ranges are kept.
    """
    sections = _split_into_sections(md_text)
    sections = _filter_leaf_sections(sections)

    if range_spec and range_spec.get("type") == "sections" and range_spec.get("items"):
        items = range_spec["items"]
        sections = [s for s in sections if s.number and _section_in_range(s.number, items)]

    return sections


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_into_sections(md_text: str) -> list[Section]:
    """Split on all ATX headings and collect body text per heading."""
    matches = list(_HEADING_RE.finditer(md_text))
    if not matches:
        # No headings — treat whole document as one section.
        return [Section(number="", title="Документ", text=md_text.strip(), level=1)]

    sections: list[Section] = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        heading_text = m.group(2).strip()
        number, title = _split_heading(heading_text)

        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        body = md_text[body_start:body_end].strip()

        full_text = (heading_text + "\n" + body).strip()
        sections.append(Section(number=number, title=title, text=full_text, level=level))

    return sections


def _split_heading(text: str) -> tuple[str, str]:
    """Return (number, title) from a heading string.

    '3.2 Методы исследования' → ('3.2', 'Методы исследования')
    'Введение' → ('', 'Введение')
    """
    m = _NUMBER_RE.match(text.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return "", text.strip()


def _filter_leaf_sections(sections: list[Section]) -> list[Section]:
    """Keep only sections with no deeper heading beneath them.

    A section is a leaf if the next heading at the same depth or shallower
    comes before any heading that is deeper.
    """
    if not sections:
        return []

    leaf: list[Section] = []
    for i, sec in enumerate(sections):
        is_leaf = True
        for j in range(i + 1, len(sections)):
            if sections[j].level <= sec.level:
                break
            # A deeper heading exists — not a leaf.
            is_leaf = False
            break
        if is_leaf:
            leaf.append(sec)
    return leaf


def _section_in_range(number: str, items: list[dict]) -> bool:
    """Return True if *number* falls within any of the given section ranges."""
    def _key(s: str) -> tuple[int, ...]:
        parts = []
        for p in re.split(r"[.\-]", s):
            try:
                parts.append(int(p))
            except ValueError:
                pass
        return tuple(parts)

    num_key = _key(number)
    if not num_key:
        return False
    for item in items:
        start_key = _key(item.get("start", ""))
        end_key = _key(item.get("end", item.get("start", "")))
        if not start_key:
            continue
        if start_key <= num_key <= end_key:
            return True
        prefix = num_key[: len(start_key)]
        if prefix and start_key <= prefix <= end_key:
            return True
    return False
