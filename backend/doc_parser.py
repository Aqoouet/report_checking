"""Unified document parser for Word (.docx) and PDF files.

Produces a ``DocData`` object that checkpoints consume regardless of the
original file format.  Text is split into chunks of roughly ``CHUNK_SIZE``
characters so that prompt-based checkpoints can process them uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF — used only for PDF
from docx import Document  # python-docx — used only for .docx

CHUNK_SIZE = 3000  # approximate target size in characters per chunk


@dataclass
class TextChunk:
    text: str
    location: str  # "Страница 5" | "Параграфы 12-15"


@dataclass
class DocData:
    fmt: str                          # "docx" | "pdf"
    file_path: str
    chunks: list[TextChunk] = field(default_factory=list)
    raw_docx: Optional[Document] = field(default=None, repr=False)
    raw_pdf: Optional[fitz.Document] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_document(file_path: str) -> DocData:
    """Detect format and parse *file_path* into a :class:`DocData`."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    ext = path.suffix.lower()
    if ext == ".docx":
        return _parse_docx(file_path)
    elif ext == ".pdf":
        return _parse_pdf(file_path)
    else:
        raise ValueError(f"Неподдерживаемый формат файла: {ext}. Ожидается .docx или .pdf")


# ---------------------------------------------------------------------------
# Word parser
# ---------------------------------------------------------------------------

def _parse_docx(file_path: str) -> DocData:
    doc = Document(file_path)
    chunks: list[TextChunk] = []

    buffer = ""
    start_idx = 0

    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue

        buffer += text + "\n"

        if len(buffer) >= CHUNK_SIZE:
            chunks.append(TextChunk(
                text=buffer.strip(),
                location=f"Параграфы {start_idx + 1}–{idx + 1}",
            ))
            buffer = ""
            start_idx = idx + 1

    if buffer.strip():
        end_idx = len(doc.paragraphs)
        chunks.append(TextChunk(
            text=buffer.strip(),
            location=f"Параграфы {start_idx + 1}–{end_idx}",
        ))

    return DocData(fmt="docx", file_path=file_path, chunks=chunks, raw_docx=doc)


# ---------------------------------------------------------------------------
# PDF parser
# ---------------------------------------------------------------------------

def _parse_pdf(file_path: str) -> DocData:
    pdf = fitz.open(file_path)
    chunks: list[TextChunk] = []

    buffer = ""
    start_page = 1

    for page_num in range(len(pdf)):
        page = pdf[page_num]
        blocks = page.get_text("blocks")
        page_text = "\n".join(
            b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()
        )
        if not page_text:
            continue

        buffer += page_text + "\n"

        if len(buffer) >= CHUNK_SIZE:
            label = (
                f"Страница {start_page}"
                if start_page == page_num + 1
                else f"Страницы {start_page}–{page_num + 1}"
            )
            chunks.append(TextChunk(text=buffer.strip(), location=label))
            buffer = ""
            start_page = page_num + 2

    if buffer.strip():
        end_page = len(pdf)
        label = (
            f"Страница {start_page}"
            if start_page == end_page
            else f"Страницы {start_page}–{end_page}"
        )
        chunks.append(TextChunk(text=buffer.strip(), location=label))

    return DocData(fmt="pdf", file_path=file_path, chunks=chunks, raw_pdf=pdf)
