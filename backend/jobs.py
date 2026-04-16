from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    current_checkpoint: int = 0
    total_checkpoints: int = 0
    current_checkpoint_name: str = ""
    current_checkpoint_short_name: str = ""
    # Progress inside the current checkpoint (section / figure / table index).
    checkpoint_sub_current: int = 0
    checkpoint_sub_total: int = 0
    checkpoint_sub_location: str = ""
    # Name of the current sub-item (section title or figure/table label).
    checkpoint_sub_name: str = ""
    # AI response for the previously completed sub-item.
    previous_result: str = ""
    error: Optional[str] = None
    result_path: Optional[str] = None


_store: dict[str, Job] = {}


def create_job() -> Job:
    job = Job()
    _store[job.id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _store.get(job_id)


def update_job(job: Job) -> None:
    _store[job.id] = job
