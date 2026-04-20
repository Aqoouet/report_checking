from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class JobCancelledError(Exception):
    """Raised by checkpoints when they detect job.cancelled == True.

    Carries checkpoint progress so a partial report can list finished sections.
    """

    def __init__(
        self,
        *,
        partial_issues: list[dict] | None = None,
        ok_locations: list[str] | None = None,
    ):
        super().__init__()
        self.partial_issues = partial_issues or []
        self.ok_locations = ok_locations or []


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    current_checkpoint: int = 0
    total_checkpoints: int = 0
    current_checkpoint_name: str = ""
    current_checkpoint_short_name: str = ""
    checkpoint_sub_current: int = 0
    checkpoint_sub_total: int = 0
    checkpoint_sub_location: str = ""
    checkpoint_sub_name: str = ""
    previous_result: str = ""
    cancelled: bool = False
    error: Optional[str] = None
    result_path: Optional[str] = None
    md_result_path: Optional[str] = None
    source_doc_stem: str = ""
    created_at: float = field(default_factory=time.time)


_store: dict[str, Job] = {}
_store_lock = Lock()

JOB_TTL_SECONDS = 86400  # 24 hours


def create_job() -> Job:
    job = Job()
    with _store_lock:
        _store[job.id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    with _store_lock:
        return _store.get(job_id)


def update_job(job: Job) -> None:
    with _store_lock:
        _store[job.id] = job


def cleanup_old_jobs() -> None:
    now = time.time()
    with _store_lock:
        expired = [jid for jid, job in _store.items() if now - job.created_at > JOB_TTL_SECONDS]
        for jid in expired:
            job = _store[jid]
            for attr in ("result_path", "md_result_path"):
                p = getattr(job, attr, None)
                if p:
                    from pathlib import Path as _Path
                    try:
                        _Path(p).unlink(missing_ok=True)
                    except OSError:
                        pass
            del _store[jid]
