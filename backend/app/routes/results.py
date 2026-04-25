from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app import job_repo
from app.error_codes import (
    ERR_FILE_NOT_FOUND,
    ERR_JOB_NOT_FOUND,
    ERR_LOG_NOT_FOUND,
    ERR_RESULT_NOT_READY,
    api_error,
)
from app.jobs import JobStatus
from app.utils import safe_download_stem

router = APIRouter()


@router.get("/status/{job_id}")
async def status(job_id: str):
    job = job_repo.get_job(job_id)
    if not job:
        raise api_error(ERR_JOB_NOT_FOUND)
    return {
        "status": job.status,
        "current_checkpoint": job.current_checkpoint,
        "total_checkpoints": job.total_checkpoints,
        "current_checkpoint_name": job.current_checkpoint_name,
        "current_checkpoint_short_name": job.current_checkpoint_short_name,
        "checkpoint_sub_current": job.checkpoint_sub_current,
        "checkpoint_sub_total": job.checkpoint_sub_total,
        "checkpoint_sub_location": job.checkpoint_sub_location,
        "checkpoint_sub_name": job.checkpoint_sub_name,
        "previous_result": job.previous_result,
        "error": job.error,
        "phase": job.phase,
    }


@router.get("/result_log/{job_id}")
async def result_log(job_id: str):
    job = job_repo.get_job(job_id)
    if not job:
        raise api_error(ERR_JOB_NOT_FOUND)
    if not job.log_path:
        raise api_error(ERR_LOG_NOT_FOUND)
    try:
        text = Path(job.log_path).read_text(encoding="utf-8")
        return {"log": text}
    except OSError:
        raise api_error(ERR_LOG_NOT_FOUND)


@router.get("/result/{job_id}")
async def result(job_id: str):
    job = job_repo.get_job(job_id)
    if not job:
        raise api_error(ERR_JOB_NOT_FOUND)
    if job.status not in (JobStatus.DONE, JobStatus.CANCELLED):
        raise api_error(ERR_RESULT_NOT_READY)
    if not job.result_path:
        raise api_error(ERR_FILE_NOT_FOUND)

    stem = safe_download_stem(job.source_doc_stem)
    ts = datetime.fromtimestamp(job.created_at).strftime("%Y%m%d_%H%M%S")
    suffix = "_partial" if job.status == JobStatus.CANCELLED else ""
    filename = f"{stem}_{ts}_result{suffix}.txt"
    try:
        return FileResponse(
            path=job.result_path,
            media_type="text/plain; charset=utf-8",
            filename=filename,
        )
    except FileNotFoundError:
        raise api_error(ERR_FILE_NOT_FOUND)


@router.get("/result_md/{job_id}")
async def result_md(job_id: str):
    job = job_repo.get_job(job_id)
    if not job:
        raise api_error(ERR_JOB_NOT_FOUND)
    if job.status not in (JobStatus.DONE, JobStatus.CANCELLED):
        raise api_error(ERR_RESULT_NOT_READY)
    if not job.md_result_path:
        raise api_error(ERR_FILE_NOT_FOUND)

    stem = safe_download_stem(job.source_doc_stem)
    filename = f"{stem}_docling.md"
    try:
        return FileResponse(
            path=job.md_result_path,
            media_type="text/markdown; charset=utf-8",
            filename=filename,
        )
    except FileNotFoundError:
        raise api_error(ERR_FILE_NOT_FOUND)
