"""Shared data-model dataclasses and regex constants for the document parser.

Imported by ``doc_parser``, ``docx_parser``, ``pdf_parser``, checkpoints, and
the aggregator — keeping them in one place avoids circular imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Shared regex constants (used by both docx_parser and pdf_parser)
# ---------------------------------------------------------------------------

# Matches caption lines like "Таблица 3.1-2 — ..." or "Рисунок 5"
CAPTION_RE = re.compile(
    r"^(Таблица|Рисунок)\s+([\d\.]+[-–—‑][\d\.]+|[\d\.]+)(?=\s*[-–—‑]|\s*$)",
    re.IGNORECASE,
)

# Matches in-text references to figures/tables, e.g. "см. таблицу 3.1-2"
MENTION_RE = re.compile(
    r"(таблиц[еуией]?\s+[\d\.]+[-–—‑][\d\.]+|рисун[окке]+\s+[\d\.]+[-–—‑][\d\.]+|"
    r"таблиц[еуией]?\s+[\d\.]+|рисун[окке]+\s+[\d\.]+)",
    re.IGNORECASE,
)


def normalise_mention(raw: str) -> str:
    """Convert a loose mention like 'таблицу 3.1-2' to canonical 'Таблица 3.1-2'."""
    raw = raw.strip()
    kind = "Таблица" if re.match(r"таблиц", raw, re.IGNORECASE) else "Рисунок"
    num_m = re.search(r"[\d\.]+[-–—‑][\d\.]+|[\d\.]+", raw)
    if num_m:
        return f"{kind} {num_m.group(0)}"
    return raw


@dataclass
class Section:
    number: str   # "3.2" / "1.1.2" / "Страница 5"
    title: str    # заголовок раздела или ""
    text: str     # весь текст раздела
    level: int    # уровень заголовка (1-based); 0 для страниц PDF


@dataclass
class FigTableMention:
    context: str          # абзац(ы) где встречается ссылка
    section_number: str   # номер раздела где встречается ссылка


@dataclass
class FigTableEntry:
    label: str                       # "Таблица 3.1-2"
    caption: str                     # полный текст подписи
    section_number: str              # раздел где находится сама подпись
    mentions: list[FigTableMention] = field(default_factory=list)


@dataclass
class DocData:
    fmt: str                                    # "docx" | "pdf"
    file_path: str
    sections: list[Section] = field(default_factory=list)
    fig_table_dict: list[FigTableEntry] = field(default_factory=list)
    raw_docx: Optional[object] = field(default=None, repr=False)
    raw_pdf: Optional[object] = field(default=None, repr=False)
