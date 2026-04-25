from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Section:
    number: str   # "3.2" / "1.1.2"
    title: str    # section heading text
    text: str     # full section text (may be a token-limited chunk)
    level: int    # heading depth (1-based)


@dataclass
class DocData:
    fmt: str = "docx"
    file_path: str = ""
    sections: list[Section] = field(default_factory=list)
