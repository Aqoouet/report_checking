from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import ai_client
import aggregator
import jobs as job_store

from checkpoints import load_checkpoints
from doc_parser import parse_document
from path_mapper import map_path

load_dotenv()

app = FastAPI(title="Report Checker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULT_DIR = Path(tempfile.gettempdir()) / "report_checker"
RESULT_DIR.mkdir(parents=True, exist_ok=True)


def process_document(job_id: str, file_path: str, range_spec: dict | None) -> None:
    job = job_store.get_job(job_id)
    if not job:
        return

    try:
        job.status = job_store.JobStatus.PROCESSING
        job_store.update_job(job)

        doc_data = parse_document(file_path, range_spec=range_spec)

        checkpoints = [cp for cp in load_checkpoints() if cp.supports(doc_data.fmt)]

        job.total_checkpoints = len(checkpoints)
        job.current_checkpoint = 0
        job_store.update_job(job)

        all_errors: list[dict] = []

        for idx, cp in enumerate(checkpoints):
            job.current_checkpoint_name = cp.name
            job.current_checkpoint_short_name = cp.short_name
            job.checkpoint_sub_current = 0
            job.checkpoint_sub_total = 0
            job.checkpoint_sub_location = ""
            job.checkpoint_sub_name = ""
            job_store.update_job(job)

            errors = cp.run(doc_data, job_id=job_id)

            for err in errors:
                all_errors.append({
                    "checkpoint": cp.name,
                    "location": err.get("location", ""),
                    "error": err.get("error", ""),
                })

            job.current_checkpoint += 1
            job_store.update_job(job)

        result_path = str(RESULT_DIR / f"{job_id}_result.txt")
        aggregator.aggregate(all_errors, result_path)

        job.result_path = result_path
        job.status = job_store.JobStatus.DONE
        job_store.update_job(job)

    except Exception as exc:
        job.status = job_store.JobStatus.ERROR
        job.error = str(exc)
        job_store.update_job(job)


@app.post("/validate_range")
async def validate_range(
    range_text: str = Form(...),
    file_type: str = Form(...),
):
    """Validate and normalise a free-form range string via AI.

    Returns ``{valid, type, items, display, suggestion}``.
    """
    if not range_text.strip():
        return {"valid": True, "type": "", "items": [], "display": "", "suggestion": ""}

    result = ai_client.validate_range(range_text.strip(), file_type)
    return result


@app.post("/check")
async def check(
    background_tasks: BackgroundTasks,
    file_path: str = Form(...),
    range_spec: str = Form(""),
):
    linux_path = map_path(file_path)

    if not Path(linux_path).exists():
        raise HTTPException(
            status_code=400,
            detail=f"Файл не найден: {linux_path}",
        )

    ext = Path(linux_path).suffix.lower()
    if ext not in (".docx", ".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только файлы .docx и .pdf",
        )

    parsed_range: dict | None = None
    if range_spec.strip():
        try:
            parsed_range = json.loads(range_spec)
            if not isinstance(parsed_range, dict) or not parsed_range.get("valid"):
                parsed_range = None
        except (json.JSONDecodeError, ValueError):
            parsed_range = None

    job = job_store.create_job()
    background_tasks.add_task(process_document, job.id, linux_path, parsed_range)

    return {"job_id": job.id}


@app.get("/status/{job_id}")
async def status(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")

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
    }


@app.get("/result/{job_id}")
async def result(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if job.status != job_store.JobStatus.DONE:
        raise HTTPException(status_code=400, detail="Результат ещё не готов")
    if not job.result_path or not os.path.exists(job.result_path):
        raise HTTPException(status_code=404, detail="Файл результата не найден")

    return FileResponse(
        path=job.result_path,
        media_type="text/plain; charset=utf-8",
        filename="report_errors.txt",
    )
