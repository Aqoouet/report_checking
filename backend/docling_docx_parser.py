"""Map a DoclingDocument JSON dict (from docling-service) to DocData.

The DoclingDocument schema (v1.x) produced by ``docling``'s
``DocumentConverter`` provides:

- ``texts``    — list of TextItem dicts (paragraphs, section headers,
                 captions, list items, …)
- ``tables``   — list of TableItem dicts
- ``pictures`` — list of PictureItem dicts
- ``body``     — document tree whose ``children`` reference the above lists
                 via ``{"$ref": "#/texts/N"}`` etc.

The body tree encodes the true document order for DOCX files.  We do a
depth-first traversal to reconstruct it, then build the same ``DocData``
that the legacy ``docx_parser`` produces so that all existing checkpoints
continue to work unchanged.
"""

from __future__ import annotations

import re
from typing import Any

from doc_models import (
    CAPTION_RE,
    MENTION_RE,
    DocData,
    FigTableEntry,
    FigTableMention,
    Section,
    normalise_mention,
)

# ---------------------------------------------------------------------------
# Docling label constants (from docling_core.types.doc.labels)
# ---------------------------------------------------------------------------

_LABEL_SECTION_HEADER = "section_header"
_LABEL_PARAGRAPH = "paragraph"
_LABEL_CAPTION = "caption"
_LABEL_LIST_ITEM = "list_item"
_LABEL_TABLE = "table"
_LABEL_PICTURE = "picture"
_LABEL_TEXT_LABELS = {
    _LABEL_PARAGRAPH,
    _LABEL_CAPTION,
    _LABEL_LIST_ITEM,
    "text",
    "footnote",
    "formula",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_docx_from_docling(
    docling_doc: dict,
    file_path: str,
    range_spec: dict | None,
) -> DocData:
    """Map *docling_doc* (``export_to_dict()`` payload) to a :class:`DocData`.

    Parameters
    ----------
    docling_doc:
        Raw JSON dict from ``POST /convert`` on the docling-service.
    file_path:
        Original file path — stored in ``DocData.file_path`` for downstream
        use; not read here.
    range_spec:
        Optional section-range filter dict produced by the range validator.
    """
    # 1. Build a lookup {self_ref → item} for every item in the document.
    lookup = _build_lookup(docling_doc)

    # 2. Walk the body tree to get items in document order.
    ordered = _document_order(docling_doc.get("body", {}), lookup)

    # 3. Build sections + fig/table index in one linear pass.
    sections_raw, fig_table_dict = _extract_structure(ordered)

    # 4. Keep only leaf sections (no child headings beneath them).
    leaf_sections = _filter_leaf_sections(sections_raw)

    # 5. Optionally filter by section range.
    if range_spec and range_spec.get("type") == "sections" and range_spec.get("items"):
        leaf_sections = [
            s for s in leaf_sections
            if s.number and _section_in_range(s.number, range_spec["items"])
        ]

    return DocData(
        fmt="docx",
        file_path=file_path,
        sections=leaf_sections,
        fig_table_dict=fig_table_dict,
    )


# ---------------------------------------------------------------------------
# Lookup & document-order helpers
# ---------------------------------------------------------------------------

def _build_lookup(doc: dict) -> dict[str, dict]:
    """Return a map from ``self_ref`` string → item dict for all document items."""
    lookup: dict[str, dict] = {}
    for collection in ("texts", "tables", "pictures", "groups", "key_value_items"):
        for item in doc.get(collection, []):
            ref = item.get("self_ref")
            if ref:
                lookup[ref] = item
    return lookup


def _document_order(node: dict, lookup: dict[str, dict]) -> list[dict]:
    """DFS on the Docling body / group tree; returns items in document order."""
    result: list[dict] = []
    _dfs(node, lookup, result)
    return result


def _dfs(node: dict, lookup: dict[str, dict], result: list[dict]) -> None:
    """Recursive DFS helper."""
    # If the current node is an actual content item, record it.
    if "label" in node and node.get("self_ref"):
        result.append(node)

    for child_ptr in node.get("children", []):
        ref = child_ptr.get("$ref")
        if not ref:
            continue
        child = lookup.get(ref)
        if child:
            _dfs(child, lookup, result)


# ---------------------------------------------------------------------------
# Structure extraction
# ---------------------------------------------------------------------------

def _extract_structure(
    ordered_items: list[dict],
) -> tuple[list[_RawSection], list[FigTableEntry]]:
    """Single linear pass over *ordered_items*.

    Returns
    -------
    raw_sections:
        List of :class:`_RawSection` (one per heading).  Text is the
        accumulated body text of that heading including the heading title.
    fig_table_dict:
        List of :class:`FigTableEntry` with mentions filled in.
    """
    raw_sections: list[_RawSection] = []
    current: _RawSection | None = None

    # Map from canonical label (e.g. "Рисунок 3.1‑2") → FigTableEntry,
    # kept in insertion order so indices are stable.
    ft_entries: dict[str, FigTableEntry] = {}

    for item in ordered_items:
        label = item.get("label", "")
        text = (item.get("text") or item.get("orig") or "").strip()
        if not text:
            continue

        if label == _LABEL_SECTION_HEADER:
            level = int(item.get("level") or 1)
            number, title = _split_heading(text)
            current = _RawSection(number=number, title=title, level=level, parts=[title])
            raw_sections.append(current)

        elif label == _LABEL_CAPTION:
            if current:
                current.parts.append(text)
            cap_m = CAPTION_RE.match(text)
            if cap_m and current:
                kind_word = cap_m.group(1)
                raw_num = cap_m.group(2)
                # Build a preliminary label; renumbering happens below.
                entry_label = f"{kind_word} {raw_num}"
                if entry_label not in ft_entries:
                    ft_entries[entry_label] = FigTableEntry(
                        label=entry_label,
                        caption=text,
                        section_number=current.number if current else "",
                    )

        elif label in _LABEL_TEXT_LABELS or label == _LABEL_LIST_ITEM:
            if current:
                current.parts.append(text)
            # Scan for figure/table mentions.
            if current:
                for raw_mention in MENTION_RE.findall(text):
                    canon = normalise_mention(raw_mention)
                    if canon in ft_entries:
                        ft_entries[canon].mentions.append(
                            FigTableMention(context=text, section_number=current.number)
                        )

        # Tables contribute no direct text item in the body but their
        # caption (a separate texts item) is captured above.

    # Renumber entries: Docling may give "Рисунок 5" where the original
    # document uses SEQ fields.  Keep the label as-is; the checkpoints only
    # need structural consistency, not the original SEQ-counter value.
    fig_table_list = list(ft_entries.values())

    raw_sections_out = [
        _RawSection(
            number=s.number,
            title=s.title,
            level=s.level,
            parts=s.parts,
        )
        for s in raw_sections
    ]
    return raw_sections_out, fig_table_list


# ---------------------------------------------------------------------------
# Heading parsing
# ---------------------------------------------------------------------------

_HEADING_NUMBER_RE = re.compile(
    r"^((?:\d+[.\-–—])*\d+)\.?\s+(.*)"  # "3.2.1 Title" or "3.2.1. Title"
)


def _split_heading(text: str) -> tuple[str, str]:
    """Split '3.2 Введение' into ('3.2', 'Введение').

    Returns ('', text) if no numeric prefix is found.
    """
    m = _HEADING_NUMBER_RE.match(text.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return "", text.strip()


# ---------------------------------------------------------------------------
# Leaf-section filter
# ---------------------------------------------------------------------------

class _RawSection:
    """Lightweight mutable container used during parsing."""

    __slots__ = ("number", "title", "level", "parts")

    def __init__(self, number: str, title: str, level: int, parts: list[str]) -> None:
        self.number = number
        self.title = title
        self.level = level
        self.parts = parts

    def to_section(self) -> Section:
        return Section(
            number=self.number,
            title=self.title,
            text="\n".join(p for p in self.parts if p),
            level=self.level,
        )


def _filter_leaf_sections(raw: list[_RawSection]) -> list[Section]:
    """Keep only sections that have no deeper heading beneath them.

    Mirrors the logic in the legacy ``docx_parser._parse_docx_inner``.
    """
    if not raw:
        return []

    leaf: list[Section] = []
    for i, sec in enumerate(raw):
        is_leaf = True
        for j in range(i + 1, len(raw)):
            nxt_level = raw[j].level
            if nxt_level <= sec.level:
                break
            # A deeper heading exists → current section is not a leaf.
            is_leaf = False
            break
        if is_leaf:
            leaf.append(sec.to_section())
    return leaf


# ---------------------------------------------------------------------------
# Section range filter
# ---------------------------------------------------------------------------

def _section_in_range(number: str, items: list[dict]) -> bool:
    """Return True if *number* falls within any of the given section ranges.

    Copied logic from ``docx_parser._section_in_range`` to avoid circular
    imports — both modules are siblings with no shared helpers module.
    """

    def _key(s: str) -> tuple[int, ...]:
        parts = []
        for p in re.split(r"[.\-–—]", s):
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
