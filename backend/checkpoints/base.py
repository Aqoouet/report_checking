from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from doc_parser import DocData


class BaseCheckpoint(ABC):
    name: str
    short_name: str = ""
    supported_formats: list[str]  # e.g. ["docx", "pdf"] or ["docx"]

    def supports(self, fmt: str) -> bool:
        return fmt in self.supported_formats

    @abstractmethod
    def run(self, doc_data: DocData, *, job_id: str | None = None) -> list[dict]:
        """Run the checkpoint and return a list of errors.

        *job_id* is set when the job should receive fine-grained progress updates.

        Each error is a dict with keys:
            location (str): human-readable location, e.g. "Параграф 12" or "Страница 5"
            error    (str): description of the found problem
        """
