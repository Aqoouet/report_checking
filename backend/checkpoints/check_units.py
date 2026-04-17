"""Checkpoint 2 — Physical quantities and units representation."""

from __future__ import annotations

from pathlib import Path

from checkpoints.base import PerSectionCheckpoint

_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "units.txt"


class CheckUnits(PerSectionCheckpoint):
    name = "Представление физических величин и единиц измерения"
    short_name = "Единицы измерения"
    supported_formats = ["docx", "pdf"]
    prompt_file = _PROMPT_FILE
