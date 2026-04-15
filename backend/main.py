from __future__ import annotations

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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


def process_document(job_id: str, file_path: str) -> None:
    job = job_store.get_job(job_id)
    if not job:
        return

    try:
        job.status = job_store.JobStatus.PROCESSING
        job_store.update_job(job)

        doc_data = parse_document(file_path)

        checkpoints = [cp for cp in load_checkpoints() if cp.supports(doc_data.fmt)]

        job.total_checkpoints = len(checkpoints)
        job.current_checkpoint = 0
        job_store.update_job(job)

        all_errors: list[dict] = []

        for idx, cp in enumerate(checkpoints):
            job.current_checkpoint_name = cp.name
            job.checkpoint_sub_current = 0
            job.checkpoint_sub_total = 0
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


@app.post("/check")
async def check(
    background_tasks: BackgroundTasks,
    file_path: str = Form(...),
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

    job = job_store.create_job()
    background_tasks.add_task(process_document, job.id, linux_path)

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
        "checkpoint_sub_current": job.checkpoint_sub_current,
        "checkpoint_sub_total": job.checkpoint_sub_total,
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
