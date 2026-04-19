from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
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
from path_mapper import get_allowed_prefixes, map_path
from range_parser import parse_range_script

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RESULT_DIR = Path(tempfile.gettempdir()) / "report_checker"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CHECK_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "clarity.txt"
CHECK_PROMPT_MAX_BYTES = 256 * 1024

RESULT_TTL_SECONDS = int(os.getenv("RESULT_TTL_HOURS", "24")) * 3600
MAX_PATH_LEN = 1024
MAX_RANGE_SPEC_LEN = 4096

# Allowed CORS origins — comma-separated list in env (dev only; production uses same-origin nginx proxy).
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:80").split(",")
    if o.strip()
]


def _cleanup_old_results() -> None:
    now = time.time()
    for f in RESULT_DIR.glob("*_result.txt"):
        try:
            if now - f.stat().st_mtime > RESULT_TTL_SECONDS:
                f.unlink()
                logger.info("Cleaned up old result file: %s", f.name)
        except OSError:
            pass


async def _periodic_cleanup() -> None:
    while True:
        await asyncio.sleep(3600)
        _cleanup_old_results()
        job_store.cleanup_old_jobs()


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ARG001
    _cleanup_old_results()
    job_store.cleanup_old_jobs()
    task = asyncio.create_task(_periodic_cleanup())
    yield
    task.cancel()


app = FastAPI(title="Report Checker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _validate_file_path(file_path: str) -> Path:
    """Validate and resolve a user-supplied file path.

    Checks length, null bytes, symlinks, path traversal, allowlist, existence, and extension.
    Raises HTTPException on any violation.
    """
    if len(file_path) > MAX_PATH_LEN:
        raise HTTPException(status_code=400, detail="Путь к файлу слишком длинный")
    if "\x00" in file_path:
        raise HTTPException(status_code=400, detail="Недопустимый путь к файлу")

    linux_path = map_path(file_path)
    p = Path(linux_path)

    # Reject symlinks before resolving — prevents escaping the allowlist via a symlink
    # inside an allowed directory pointing to a file outside it.
    if p.is_symlink():
        raise HTTPException(status_code=403, detail="Доступ к файлу запрещён")

    resolved = p.resolve()

    allowed_prefixes = get_allowed_prefixes()
    if allowed_prefixes:
        resolved_str = str(resolved)
        if not any(resolved_str.startswith(str(Path(pfx).resolve())) for pfx in allowed_prefixes):
            logger.warning("Access denied for path (hash: %s)", resolved_str[:8])
            raise HTTPException(status_code=403, detail="Доступ к файлу запрещён")

    if not resolved.exists():
        raise HTTPException(status_code=400, detail="Файл не найден")

    if resolved.suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .docx")

    return resolved


def _safe_download_stem(raw: str, max_len: int = 80) -> str:
    t = (raw or "").strip()
    s = "".join(c if (c.isalnum() or c in "._-") else "_" for c in t)
    s = "_".join(p for p in s.split("_") if p)
    return (s or "report")[:max_len]


def _normalize_check_prompt(raw: str) -> str | None:
    """Return stripped prompt or None to use the default file. Raises ValueError if too large."""
    s = raw.strip()
    if not s:
        return None
    if len(s.encode("utf-8")) > CHECK_PROMPT_MAX_BYTES:
        raise ValueError("Промпт слишком длинный")
    return s


_CONTEXT_FIELD_KEYS = (
    "max_context_length",
    "context_length",
    "context_window",
    "max_model_len",
    "n_ctx",
)


def _openai_base_to_lm_root(openai_base: str) -> str:
    """OPENAI_BASE_URL usually ends with /v1; LM Studio native API is on the server root."""
    base = openai_base.rstrip("/")
    if base.lower().endswith("/v1"):
        return base[:-3] or base
    return base


def _context_from_model_entry(entry: dict) -> int | None:
    for key in _CONTEXT_FIELD_KEYS:
        v = entry.get(key)
        if isinstance(v, int) and v > 0:
            return v
    return None


def _model_id_matches_listing(eid: str, configured: str) -> bool:
    if not configured:
        return False
    return eid == configured or configured in eid or eid in configured


async def _resolve_context_tokens(
    client: httpx.AsyncClient,
    openai_base: str,
    model_id: str,
) -> int | None:
    """Read context from LM Studio GET /api/v0/models (OpenAI GET /v1/models has no such fields)."""
    if not model_id.strip():
        return None
    openai_base = openai_base.rstrip("/")
    root = _openai_base_to_lm_root(openai_base)

    def _from_entries(entries: list) -> int | None:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            eid = str(entry.get("id") or entry.get("model") or "")
            if not _model_id_matches_listing(eid, model_id):
                continue
            ctx = _context_from_model_entry(entry)
            if ctx is not None:
                return ctx
        return None

    try:
        r = await client.get(f"{root}/api/v0/models")
        if r.status_code == 200:
            payload = r.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list):
                found = _from_entries(data)
                if found is not None:
                    return found
    except Exception:
        pass

    try:
        r = await client.get(f"{root}/api/v0/models/{quote(model_id, safe='')}")
        if r.status_code == 200:
            payload = r.json()
            if isinstance(payload, dict):
                ctx = _context_from_model_entry(payload)
                if ctx is not None:
                    return ctx
    except Exception:
        pass

    try:
        r = await client.get(f"{openai_base}/models")
        if r.status_code == 200:
            payload = r.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list):
                return _from_entries(data)
    except Exception:
        pass

    return None


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

        doc_data, md_text = parse_document(file_path, range_spec=range_spec)
        md_path = str(RESULT_DIR / f"{job_id}.md")
        Path(md_path).write_text(md_text, encoding="utf-8")
        job = job_store.get_job(job_id)
        if job is None:
            return
        job.md_result_path = md_path
        job.source_doc_stem = Path(file_path).stem
        job_store.update_job(job)

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
            except JobCancelledError as cancelled:
                was_cancelled = True
                for err in cancelled.partial_issues:
                    all_errors.append({
                        "checkpoint": cp.name,
                        "location": err.get("location", ""),
                        "error": err.get("error", ""),
                    })
                for loc in cancelled.ok_locations:
                    all_errors.append({
                        "checkpoint": cp.name,
                        "location": loc,
                        "error": "Ошибок не найдено (раздел проверен).",
                    })
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
        aggregator.aggregate(
            all_errors,
            result_path,
            doc_data=doc_data,
            is_partial=was_cancelled,
        )

        job = job_store.get_job(job_id)
        if job is None:
            return
        job.result_path = result_path
        job.status = JobStatus.CANCELLED if was_cancelled else JobStatus.DONE
        job_store.update_job(job)

    except Exception as exc:
        error_id = uuid.uuid4().hex[:8]
        logger.error("process_document error [%s] for job %s: %s", error_id, job_id, exc, exc_info=True)
        job = job_store.get_job(job_id)
        if job:
            job.status = JobStatus.ERROR
            job.error = f"Внутренняя ошибка обработки [ID: {error_id}]."
            job_store.update_job(job)


@app.post("/validate_path")
async def validate_path_endpoint(file_path: str = Form(...)):
    """Check that *file_path* maps to an existing .docx on the server (same rules as /check)."""
    raw = (file_path or "").strip()
    if not raw:
        return {"valid": False, "message": "Укажите путь к файлу", "mapped_path": ""}
    try:
        resolved = _validate_file_path(raw)
        return {"valid": True, "message": "Файл доступен", "mapped_path": str(resolved)}
    except HTTPException as exc:
        return {"valid": False, "message": exc.detail, "mapped_path": ""}


@app.post("/validate_range_quick")
async def validate_range_quick(range_text: str = Form(...)):
    return parse_range_script(range_text.strip())


@app.post("/validate_range")
async def validate_range(range_text: str = Form(...)):
    if not range_text.strip():
        return {"valid": True, "type": "sections", "items": [], "display": "", "suggestion": ""}
    result = ai_client.validate_range(range_text.strip())
    if not result.get("valid") and result.get("server_error"):
        logger.warning("AI range validation failed: %s", result.get("range_message", "unknown error"))
    return result


@app.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    job.cancelled = True
    job_store.update_job(job)
    return {"ok": True}


@app.get("/runtime_info")
async def runtime_info():
    """Public hints for the UI: model id, context from LM Studio /api/v0/models when available."""
    base = os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1").rstrip("/")
    model_id = os.getenv("OPENAI_MODEL", "").strip()
    context_tokens: int | None = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            context_tokens = await _resolve_context_tokens(client, base, model_id)
    except Exception:
        pass
    try:
        chunk = int(os.getenv("DOC_CHUNK_SIZE", "10000"))
    except ValueError:
        chunk = 10000
    return {
        "check_model": model_id or "—",
        "context_tokens": context_tokens,
        "doc_chunk_tokens": chunk,
    }


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
    if len(range_spec) > MAX_RANGE_SPEC_LEN:
        raise HTTPException(status_code=400, detail="Диапазон слишком длинный")

    resolved = _validate_file_path(file_path)

    try:
        normalized_prompt = _normalize_check_prompt(check_prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    parsed_range: dict | None = None
    if range_spec.strip():
        try:
            candidate = json.loads(range_spec)
            if (
                isinstance(candidate, dict)
                and candidate.get("valid")
                and isinstance(candidate.get("items"), list)
                and all(
                    isinstance(item, dict)
                    and isinstance(item.get("start"), str)
                    and isinstance(item.get("end"), str)
                    for item in candidate["items"]
                )
            ):
                parsed_range = candidate
        except (json.JSONDecodeError, ValueError):
            pass

    job = job_store.create_job()
    background_tasks.add_task(
        process_document,
        job.id,
        str(resolved),
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


@app.get("/result_md/{job_id}")
async def result_md(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if job.status not in (JobStatus.DONE, JobStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Результат ещё не готов")
    if not job.md_result_path or not os.path.exists(job.md_result_path):
        raise HTTPException(status_code=404, detail="Файл Markdown не найден")

    stem = _safe_download_stem(job.source_doc_stem)
    filename = f"{stem}_docling.md"
    return FileResponse(
        path=job.md_result_path,
        media_type="text/markdown; charset=utf-8",
        filename=filename,
    )
