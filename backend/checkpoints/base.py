from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from doc_parser import DocData

# ---------------------------------------------------------------------------
# Shared "no error" detection
# ---------------------------------------------------------------------------

_NO_ERROR_VARIANTS = (
    "ошибок не найдено",
    "ошибки не найдено",
    "ошибка не найдена",
    "нет ошибок",
    "ошибок нет",
    "без ошибок",
    "все в порядке",
    "всё в порядке",
    "all good",
    "no errors",
    "no issues",
)


def is_no_error(result: str) -> bool:
    """Return True if *result* is a model response indicating no errors were found."""
    r = result.lower().strip()
    return any(v in r for v in _NO_ERROR_VARIANTS)


class BaseCheckpoint(ABC):
    name: str
    short_name: str = ""
    supported_formats: list[str]  # e.g. ["docx", "pdf"] or ["docx"]

    def supports(self, fmt: str) -> bool:
        return fmt in self.supported_formats

    @abstractmethod
    def run(self, doc_data: "DocData", *, job_id: str | None = None) -> list[dict]:
        """Run the checkpoint and return a list of errors.

        *job_id* is set when the job should receive fine-grained progress updates.

        Each error is a dict with keys:
            location (str): human-readable location, e.g. "Параграф 12" or "Страница 5"
            error    (str): description of the found problem
        """


class PerSectionCheckpoint(BaseCheckpoint):
    """Base for checkpoints that send each section/page to the AI individually.

    Subclasses only need to declare ``name``, ``short_name``,
    ``supported_formats``, and ``prompt_file``.  The iteration, progress
    reporting, and cancellation detection are handled here.
    """

    prompt_file: Path

    def run(self, doc_data: "DocData", *, job_id: str | None = None) -> list[dict]:
        import ai_client
        import jobs as job_store
        from jobs import JobCancelledError

        prompt = self.prompt_file.read_text(encoding="utf-8").strip()
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
                    if job.cancelled:
                        raise JobCancelledError()

            if result and not is_no_error(result):
                errors.append({
                    "location": location,
                    "error": result.strip(),
                })

        return errors
