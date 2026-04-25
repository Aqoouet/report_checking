from __future__ import annotations

import asyncio
from threading import Lock
from typing import Optional

from app import job_repo
from app.jobs import JobStatus

_pipeline_queue: asyncio.Queue[str] = asyncio.Queue()
_active_job_id: Optional[str] = None
_waiting: list[str] = []
_queue_lock = Lock()


def _sync_queue_positions_locked() -> None:
    if _active_job_id is not None:
        job_repo.patch_job(_active_job_id, queue_position=0)
    for idx, jid in enumerate(_waiting, start=1):
        job_repo.patch_job(jid, queue_position=idx)


async def enqueue_job(job_id: str) -> int:
    with _queue_lock:
        if job_id not in _waiting and job_id != _active_job_id:
            _waiting.append(job_id)
        _sync_queue_positions_locked()
        position = _waiting.index(job_id) + 1 if job_id in _waiting else 0
    await _pipeline_queue.put(job_id)
    return position


async def get_next_job_id() -> str:
    global _active_job_id
    while True:
        job_id = await _pipeline_queue.get()
        with _queue_lock:
            if job_id in _waiting:
                _waiting.remove(job_id)
            _active_job_id = job_id
            _sync_queue_positions_locked()

        job = job_repo.get_job(job_id)
        if job is None or job.status == JobStatus.CANCELLED or job.cancelled:
            complete_active_job()
            _pipeline_queue.task_done()
            continue
        return job_id


def cancel_queued_job(job_id: str) -> bool:
    with _queue_lock:
        if job_id not in _waiting:
            return False
        _waiting.remove(job_id)
        job_repo.patch_job(job_id, queue_position=0)
        _sync_queue_positions_locked()
        return True


def complete_active_job() -> None:
    global _active_job_id
    with _queue_lock:
        _active_job_id = None
        _sync_queue_positions_locked()


def task_done() -> None:
    _pipeline_queue.task_done()
