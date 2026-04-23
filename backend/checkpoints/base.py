# LEGACY — not called by pipeline_orchestrator.py or main.py.
# Active pipeline runs directly through pipeline_orchestrator.run().
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from doc_models import DocData

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
    r = result.lower().strip()
    return any(v in r for v in _NO_ERROR_VARIANTS)


class BaseCheckpoint(ABC):
    name: str
    short_name: str = ""
    supported_formats: list[str]

    def supports(self, fmt: str) -> bool:
        return fmt in self.supported_formats

    @abstractmethod
    def run(
        self,
        doc_data: "DocData",
        *,
        job_id: str | None = None,
        prompt_override: str | None = None,
        temperature: float | None = None,
    ) -> list[dict]:
        """Run the checkpoint and return a list of error dicts (location, error)."""


class PerSectionCheckpoint(BaseCheckpoint):
    """Sends each section chunk to the AI and collects errors."""

    prompt_file: Path

    def run(
        self,
        doc_data: "DocData",
        *,
        job_id: str | None = None,
        prompt_override: str | None = None,
        temperature: float | None = None,
    ) -> list[dict]:
        import ai_client
        import jobs as job_store
        from jobs import JobCancelledError

        override = (prompt_override or "").strip()
        prompt = (
            override
            if override
            else self.prompt_file.read_text(encoding="utf-8").strip()
        )
        errors: list[dict] = []
        ok_locations: list[str] = []
        sections = doc_data.sections
        total = len(sections)

        for i, section in enumerate(sections):
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

            result = ai_client.check_text_chunk(section.text, prompt, temperature=temperature)
            cleaned = (result or "").strip()
            had_issue = bool(cleaned and not is_no_error(cleaned))
            if had_issue:
                errors.append({
                    "location": location,
                    "error": cleaned,
                })
            else:
                ok_locations.append(location)

            if job_id:
                job = job_store.get_job(job_id)
                if job:
                    job.previous_result = cleaned
                    job_store.update_job(job)
                    if job.cancelled:
                        raise JobCancelledError(
                            partial_issues=list(errors),
                            ok_locations=list(ok_locations),
                        )

        return errors
