from __future__ import annotations

import asyncio
import copy
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
    docx_name: str = ""
    token_count: int = 0
    queue_position: int = 0
    phase: str = ""
    artifact_dir: Optional[str] = None
    log_path: Optional[str] = None
    submitted_at: float = field(default_factory=time.time)
    # Config frozen at job creation so worker uses original settings even if
    # the user changes config while the job is queued (bug #4).
    config_snapshot: Optional[object] = field(default=None, repr=False)


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
        job = _store.get(job_id)
        return copy.copy(job) if job is not None else None


def update_job(job: Job) -> None:
    with _store_lock:
        _store[job.id] = job


_pipeline_queue: asyncio.Queue[str] = asyncio.Queue()


def _get_queue() -> asyncio.Queue[str]:
    return _pipeline_queue
_active_job_id: Optional[str] = None
_waiting: list[str] = []
_queue_lock = Lock()


async def enqueue_job(job_id: str) -> int:
    with _queue_lock:
        _waiting.append(job_id)
        _sync_positions_locked()
        position = len(_waiting)
    await _pipeline_queue.put(job_id)
    return position


async def get_next_job_id() -> str:
    global _active_job_id
    job_id = await _pipeline_queue.get()
    with _queue_lock:
        if job_id in _waiting:
            _waiting.remove(job_id)
        _active_job_id = job_id
        _sync_positions_locked()
    return job_id


def complete_active_job() -> None:
    global _active_job_id
    with _queue_lock:
        _active_job_id = None
        _sync_positions_locked()


def task_done() -> None:
    _pipeline_queue.task_done()


def _sync_positions_locked() -> None:
    with _store_lock:
        if _active_job_id and _active_job_id in _store:
            _store[_active_job_id].queue_position = 0
        for idx, jid in enumerate(_waiting, start=1):
            if jid in _store:
                _store[jid].queue_position = idx


def list_jobs() -> list[Job]:
    with _store_lock:
        return sorted(
            _store.values(),
            key=lambda j: j.submitted_at or j.created_at,
            reverse=False,
        )


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
