import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import jobs as job_store
from ai_client import check_page
from annotation_writer import write_annotations
from pdf_parser import PageData, parse_page_range, parse_pages

load_dotenv()

app = FastAPI(title="Report Checker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(tempfile.gettempdir()) / "report_checker"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def process_report(job_id: str, pdf_path: str, pages_str: str) -> None:
    job = job_store.get_job(job_id)
    if not job:
        return

    try:
        job.status = job_store.JobStatus.PROCESSING
        job_store.update_job(job)

        pages_to_check = parse_page_range(pages_str)
        if not pages_to_check:
            raise ValueError("Не удалось распознать диапазон страниц")

        page_data_list: list[PageData] = parse_pages(pdf_path, pages_to_check)

        if not page_data_list:
            raise ValueError("На указанных страницах не найден текст")

        job.total_pages = len(page_data_list)
        job.current_page = 0
        job_store.update_job(job)

        page_comments: list[tuple[PageData, str]] = []

        for page_data in page_data_list:
            comment = check_page(page_data.text, page_data.page_label)
            page_comments.append((page_data, comment))

            job.current_page += 1
            job_store.update_job(job)

        result_path = str(UPLOAD_DIR / f"{job_id}_result.pdf")
        write_annotations(pdf_path, result_path, page_comments)

        job.result_path = result_path
        job.status = job_store.JobStatus.DONE
        job_store.update_job(job)

    except Exception as exc:
        job.status = job_store.JobStatus.ERROR
        job.error = str(exc)
        job_store.update_job(job)
    finally:
        try:
            os.remove(pdf_path)
        except OSError:
            pass


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pages: str = Form(...),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Допускаются только PDF-файлы")

    job = job_store.create_job()

    pdf_path = str(UPLOAD_DIR / f"{job.id}_input.pdf")
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    background_tasks.add_task(process_report, job.id, pdf_path, pages)

    return {"job_id": job.id}


@app.get("/status/{job_id}")
async def status(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    return {
        "status": job.status,
        "current_page": job.current_page,
        "total_pages": job.total_pages,
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
        media_type="application/pdf",
        filename="report_reviewed.pdf",
    )
