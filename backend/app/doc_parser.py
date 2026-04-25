"""Unified document parser — public API.

Pipeline: DOCX → docling-serve (Markdown) → md_parser (sections) → token_chunker (chunks)

Returns a :class:`DocData` with sections ready for AI checking.
"""

from __future__ import annotations

from pathlib import Path

from app.doc_models import DocData, Section  # noqa: F401


def parse_document(file_path: str, range_spec: dict | None = None, chunk_size_tokens: int | None = None) -> tuple[DocData, str]:
    """Parse *file_path* (.docx) into a :class:`DocData` and return raw Markdown from Docling.

    Parameters
    ----------
    file_path:
        Path to the .docx file accessible from the container.
    range_spec:
        Optional section-range filter: ``{"type": "sections", "items": [...]}``.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext != ".docx":
        raise ValueError(f"Unsupported format: {ext}. Expected .docx")

    from app.docling_client import convert_file_to_md
    from app.md_cache import get_or_convert_md
    from app.md_parser import parse_sections
    from app.token_chunker import chunk_sections

    md_text = get_or_convert_md(file_path, convert_file_to_md)
    sections = parse_sections(md_text, range_spec=range_spec)
    sections = chunk_sections(sections, max_tokens=chunk_size_tokens)

    return DocData(fmt="docx", file_path=file_path, sections=sections), md_text
