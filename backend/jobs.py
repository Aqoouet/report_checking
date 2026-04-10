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
    current_page: int = 0
    total_pages: int = 0
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
