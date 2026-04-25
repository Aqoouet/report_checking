from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request

import config_store
import job_repo
from error_codes import ERR_CONFIG_NOT_SET, ERR_JOB_NOT_FOUND, api_error
from jobs import JobStatus
from queue_service import enqueue_job
from job_repo import list_jobs
from settings import MSK_TZ
from utils import get_session_id

router = APIRouter()


@router.post("/check")
async def check(request: Request):
    session_id = get_session_id(request)
    cfg = config_store.get_config(session_id)
    if cfg is None:
        raise api_error(ERR_CONFIG_NOT_SET)

    job = job_repo.create_job()
    job.submitted_at = time.time()
    job.docx_name = Path(cfg.input_docx_path).name
    job.config_snapshot = cfg
    job_repo.update_job(job)

    queue_size = await enqueue_job(job.id)
    job.queue_position = queue_size
    job_repo.update_job(job)

    return {"job_id": job.id, "queue_position": queue_size}


@router.get("/jobs")
async def get_jobs():
    jobs = list_jobs()
    return [
        {
            "id": j.id,
            "status": j.status,
            "phase": j.phase,
            "docx_name": j.docx_name,
            "current_checkpoint_name": j.current_checkpoint_name,
            "checkpoint_sub_current": j.checkpoint_sub_current,
            "checkpoint_sub_total": j.checkpoint_sub_total,
            "queue_position": j.queue_position,
            "submitted_at": j.submitted_at or j.created_at,
            "finished_at": j.finished_at,
            "error": j.error,
            "artifact_dir": j.artifact_dir,
            "failed_sections_count": j.failed_sections_count,
        }
        for j in jobs
    ]


@router.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    job = job_repo.get_job(job_id)
    if not job:
        raise api_error(ERR_JOB_NOT_FOUND)
    fields: dict[str, object] = {"cancelled": True}
    if job.status == JobStatus.PENDING:
        fields["status"] = JobStatus.CANCELLED
        fields["finished_at"] = time.time()
    job_repo.patch_job(job.id, **fields)
    if job.log_path:
        try:
            ts = datetime.now(MSK_TZ).strftime("%Y-%m-%d %H:%M:%S")
            with open(job.log_path, "a", encoding="utf-8") as lf:
                lf.write(f"[{ts}] INFO  Cancel requested by user\n")
        except OSError:
            pass
    return {"ok": True}
