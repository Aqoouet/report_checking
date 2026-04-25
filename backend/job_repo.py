from __future__ import annotations

import copy
import time
from pathlib import Path
from threading import Lock
from typing import Optional

from jobs import Job

_store: dict[str, Job] = {}
_store_lock = Lock()


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


def list_jobs() -> list[Job]:
    with _store_lock:
        return sorted(
            _store.values(),
            key=lambda j: j.submitted_at or j.created_at,
        )


def set_queue_positions(active_id: Optional[str], waiting: list[str]) -> None:
    with _store_lock:
        if active_id and active_id in _store:
            _store[active_id].queue_position = 0
        for idx, jid in enumerate(waiting, start=1):
            if jid in _store:
                _store[jid].queue_position = idx


def delete_expired_jobs(ttl_seconds: float) -> None:
    now = time.time()
    with _store_lock:
        expired = [jid for jid, job in _store.items() if now - job.created_at > ttl_seconds]
        for jid in expired:
            job = _store[jid]
            for attr in ("result_path", "md_result_path"):
                p = getattr(job, attr, None)
                if p:
                    try:
                        Path(p).unlink(missing_ok=True)
                    except OSError:
                        pass
            del _store[jid]
