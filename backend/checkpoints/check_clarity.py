"""Checkpoint 1 — Clarity, coherence and scientific-technical style.

Iterates over leaf sections (docx) or pages (pdf) and sends each one to the
AI with a prompt from ``prompts/clarity.txt``.  Works for both .docx and .pdf.
"""

from __future__ import annotations

from pathlib import Path

import ai_client
import jobs as job_store
from checkpoints.base import BaseCheckpoint
from doc_parser import DocData

_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "clarity.txt"


class CheckClarity(BaseCheckpoint):
    name = "Ясность изложения и научно-технический стиль"
    short_name = "Ясность изложения"
    supported_formats = ["docx", "pdf"]

    def run(self, doc_data: DocData, *, job_id: str | None = None) -> list[dict]:
        prompt = _PROMPT_FILE.read_text(encoding="utf-8").strip()
        errors: list[dict] = []
        sections = doc_data.sections
        total = len(sections)

        for i, section in enumerate(sections):
            if doc_data.fmt == "pdf":
                location = f"Страница {section.number}"
                sub_name = location
            else:
                location = f"Раздел {section.number} — {section.title}".strip(" —")
                sub_name = f"{section.number} {section.title}".strip()

            if job_id:
                job = job_store.get_job(job_id)
                if job:
                    job.checkpoint_sub_current = i + 1
                    job.checkpoint_sub_total = total
                    job.checkpoint_sub_location = location
                    job.checkpoint_sub_name = sub_name
                    job_store.update_job(job)

            result = ai_client.check_text_chunk(section.text, prompt)

            if job_id:
                job = job_store.get_job(job_id)
                if job:
                    job.previous_result = result.strip() if result else ""
                    job_store.update_job(job)

            if result and "ошибок не найдено" not in result.lower():
                errors.append({
                    "location": location,
                    "error": result.strip(),
                })

        return errors
