"""Unified document parser — public API.

Detects the file format and delegates to the appropriate parser.
All data-model classes are re-exported from ``doc_models`` so existing
importers (checkpoints, aggregator, main) continue to work without changes.

DOCX parsing back-end
---------------------
Two back-ends are available for ``.docx`` files:

* **Legacy** (default) — ``docx_parser``, a hand-written python-docx /
  OOXML parser.  Always available; requires no extra services.

* **Docling** — ``docling_docx_parser``, which delegates OOXML→JSON
  conversion to the separate ``docling-service`` container and then maps
  the result to :class:`DocData`.  Enabled by setting ``USE_DOCLING=true``
  in the environment and pointing ``DOCLING_URL`` at the running service.

The Docling path keeps the LibreOffice field-refresh step (``field_updater``)
so STYLEREF/SEQ fields are resolved before the file is sent for conversion.
"""

from __future__ import annotations

import os
from pathlib import Path

# Re-export data models so existing "from doc_parser import DocData, ..." still works.
from doc_models import DocData, FigTableEntry, FigTableMention, Section  # noqa: F401

# Set USE_DOCLING=true to route .docx files through the docling-service.
_USE_DOCLING = os.getenv("USE_DOCLING", "false").strip().lower() in {"1", "true", "yes"}


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
        if _USE_DOCLING:
            return _parse_docx_docling(file_path, range_spec)
        from docx_parser import parse_docx
        return parse_docx(file_path, range_spec)

    elif ext == ".pdf":
        from pdf_parser import parse_pdf
        return parse_pdf(file_path, range_spec)

    else:
        raise ValueError(f"Неподдерживаемый формат файла: {ext}. Ожидается .docx или .pdf")


def _parse_docx_docling(file_path: str, range_spec: dict | None) -> DocData:
    """Parse *file_path* via the docling-service microservice.

    Steps:
    1. Run LibreOffice headless to refresh STYLEREF/SEQ/REF field caches
       (same as the legacy parser — Docling reads the field result values
       embedded in the file, which may be stale without this step).
    2. Upload the refreshed file to ``docling-service POST /convert``.
    3. Map the returned DoclingDocument JSON to :class:`DocData`.
    """
    from docling_client import convert_file
    from docling_docx_parser import parse_docx_from_docling
    from field_updater import cleanup_updated_docx, update_docx_fields

    updated_path = update_docx_fields(file_path)
    try:
        docling_json = convert_file(updated_path)
        return parse_docx_from_docling(docling_json, file_path, range_spec)
    finally:
        cleanup_updated_docx(file_path, updated_path)
