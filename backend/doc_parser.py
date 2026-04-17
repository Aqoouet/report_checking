"""Unified document parser — public API.

Detects the file format and delegates to ``docx_parser`` or ``pdf_parser``.
All data-model classes are re-exported from ``doc_models`` so existing
importers (checkpoints, aggregator, main) continue to work without changes.
"""

from __future__ import annotations

from pathlib import Path

# Re-export data models so existing "from doc_parser import DocData, ..." still works.
from doc_models import DocData, FigTableEntry, FigTableMention, Section  # noqa: F401


def parse_document(
    file_path: str,
    range_spec: dict | None = None,
) -> DocData:
    """Detect format and parse *file_path* into a :class:`DocData`.

    *range_spec* is a dict produced by the range validator::

        {"type": "sections"|"pages",
         "items": [{"start": "3.1", "end": "3.4"}, ...]}

    If *range_spec* is None the full document is processed.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    ext = path.suffix.lower()
    if ext == ".docx":
        from docx_parser import parse_docx
        return parse_docx(file_path, range_spec)
    elif ext == ".pdf":
        from pdf_parser import parse_pdf
        return parse_pdf(file_path, range_spec)
    else:
        raise ValueError(f"Неподдерживаемый формат файла: {ext}. Ожидается .docx или .pdf")
