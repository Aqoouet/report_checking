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
from jobs import JobCancelledError, JobStatus
from checkpoints import load_checkpoints
from doc_parser import parse_document
from path_mapper import map_path
from range_parser import parse_range_script

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

DEFAULT_CHECK_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "clarity.txt"
CHECK_PROMPT_MAX_BYTES = 256 * 1024


def _normalize_check_prompt(raw: str) -> str | None:
    """Return stripped prompt or None to use the default file. Raises ValueError if too large."""
    s = raw.strip()
    if not s:
        return None
    if len(s.encode("utf-8")) > CHECK_PROMPT_MAX_BYTES:
        raise ValueError("Промпт слишком длинный")
    return s


def process_document(
    job_id: str,
    file_path: str,
    range_spec: dict | None,
    check_prompt: str | None = None,
) -> None:
    job = job_store.get_job(job_id)
    if not job:
        return

    try:
        job.status = JobStatus.PROCESSING
        job_store.update_job(job)

        doc_data = parse_document(file_path, range_spec=range_spec)

        checkpoints = load_checkpoints()
        job.total_checkpoints = len(checkpoints)
        job.current_checkpoint = 0
        job_store.update_job(job)

        all_errors: list[dict] = []
        was_cancelled = False

        for cp in checkpoints:
            job = job_store.get_job(job_id)
            if job is None:
                break
            if job.cancelled:
                was_cancelled = True
                break

            job.current_checkpoint_name = cp.name
            job.current_checkpoint_short_name = cp.short_name
            job.checkpoint_sub_current = 0
            job.checkpoint_sub_total = 0
            job.checkpoint_sub_location = ""
            job.checkpoint_sub_name = ""
            job_store.update_job(job)

            try:
                errors = cp.run(doc_data, job_id=job_id, prompt_override=check_prompt)
            except JobCancelledError:
                was_cancelled = True
                break

            for err in errors:
                all_errors.append({
                    "checkpoint": cp.name,
                    "location": err.get("location", ""),
                    "error": err.get("error", ""),
                })

            job.current_checkpoint += 1
            job_store.update_job(job)

        result_path = str(RESULT_DIR / f"{job_id}_result.txt")
        aggregator.aggregate(all_errors, result_path, doc_data=doc_data)

        job = job_store.get_job(job_id)
        if job is None:
            return
        job.result_path = result_path
        job.status = JobStatus.CANCELLED if was_cancelled else JobStatus.DONE
        job_store.update_job(job)

    except Exception as exc:
        job = job_store.get_job(job_id)
        if job:
            job.status = JobStatus.ERROR
            job.error = str(exc)
            job_store.update_job(job)


@app.post("/validate_range_quick")
async def validate_range_quick(range_text: str = Form(...)):
    return parse_range_script(range_text.strip())


@app.post("/validate_range")
async def validate_range(range_text: str = Form(...)):
    if not range_text.strip():
        return {"valid": True, "type": "sections", "items": [], "display": "", "suggestion": ""}
    return ai_client.validate_range(range_text.strip())


@app.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    job.cancelled = True
    job_store.update_job(job)
    return {"ok": True}


@app.get("/default_check_prompt")
async def default_check_prompt():
    if not DEFAULT_CHECK_PROMPT_PATH.is_file():
        raise HTTPException(status_code=500, detail="Файл промпта по умолчанию не найден")
    text = DEFAULT_CHECK_PROMPT_PATH.read_text(encoding="utf-8")
    return {"prompt": text}


@app.post("/check")
async def check(
    background_tasks: BackgroundTasks,
    file_path: str = Form(...),
    range_spec: str = Form(""),
    check_prompt: str = Form(""),
):
    linux_path = map_path(file_path)

    if not Path(linux_path).exists():
        raise HTTPException(status_code=400, detail=f"Файл не найден: {linux_path}")

    if not linux_path.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .docx")

    try:
        normalized_prompt = _normalize_check_prompt(check_prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    parsed_range: dict | None = None
    if range_spec.strip():
        try:
            parsed_range = json.loads(range_spec)
            if not isinstance(parsed_range, dict) or not parsed_range.get("valid"):
                parsed_range = None
        except (json.JSONDecodeError, ValueError):
            parsed_range = None

    job = job_store.create_job()
    background_tasks.add_task(
        process_document,
        job.id,
        linux_path,
        parsed_range,
        normalized_prompt,
    )
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
    if job.status not in (JobStatus.DONE, JobStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Результат ещё не готов")
    if not job.result_path or not os.path.exists(job.result_path):
        raise HTTPException(status_code=404, detail="Файл результата не найден")

    filename = (
        "report_errors_partial.txt"
        if job.status == JobStatus.CANCELLED
        else "report_errors.txt"
    )
    return FileResponse(
        path=job.result_path,
        media_type="text/plain; charset=utf-8",
        filename=filename,
    )
