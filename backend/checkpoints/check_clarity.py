"""Checkpoint 1 — Clarity, coherence and scientific-technical style.

Splits the document into text chunks and sends each one to the AI with
a prompt from ``prompts/clarity.txt``.  Works for both .docx and .pdf.
"""

from __future__ import annotations

from pathlib import Path

import ai_client
from checkpoints.base import BaseCheckpoint
from doc_parser import DocData

_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "clarity.txt"


class CheckClarity(BaseCheckpoint):
    name = "Ясность изложения и научно-технический стиль"
    supported_formats = ["docx", "pdf"]

    def run(self, doc_data: DocData) -> list[dict]:
        prompt = _PROMPT_FILE.read_text(encoding="utf-8").strip()
        errors: list[dict] = []

        for chunk in doc_data.chunks:
            result = ai_client.check_text_chunk(chunk.text, prompt)
            if result and "ошибок не найдено" not in result.lower():
                errors.append({
                    "location": chunk.location,
                    "error": result.strip(),
                })

        return errors
