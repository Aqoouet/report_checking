from __future__ import annotations

import asyncio
from threading import Lock
from typing import Optional

import job_repo

_pipeline_queue: asyncio.Queue[str] = asyncio.Queue()
_active_job_id: Optional[str] = None
_waiting: list[str] = []
_queue_lock = Lock()


async def enqueue_job(job_id: str) -> int:
    global _waiting
    with _queue_lock:
        _waiting.append(job_id)
        job_repo.set_queue_positions(_active_job_id, _waiting)
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
        job_repo.set_queue_positions(_active_job_id, _waiting)
    return job_id


def complete_active_job() -> None:
    global _active_job_id
    with _queue_lock:
        _active_job_id = None
        job_repo.set_queue_positions(None, _waiting)


def task_done() -> None:
    _pipeline_queue.task_done()
