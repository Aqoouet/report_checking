"""Checkpoint 1 — Clarity, coherence and scientific-technical style."""

from __future__ import annotations

from pathlib import Path

from checkpoints.base import PerSectionCheckpoint

_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "clarity.txt"


class CheckClarity(PerSectionCheckpoint):
    name = "Ясность изложения и научно-технический стиль"
    short_name = "Ясность изложения"
    supported_formats = ["docx", "pdf"]
    prompt_file = _PROMPT_FILE
