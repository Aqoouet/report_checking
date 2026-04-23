from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError, field_validator

import ai_client
import aggregator
import config_store
import jobs as job_store
import pipeline_orchestrator
from jobs import JobStatus, enqueue_job, list_jobs
from doc_parser import parse_document
from path_mapper import get_allowed_prefixes, map_path
from range_parser import parse_range_script

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RESULT_DIR = Path(tempfile.gettempdir()) / "report_checker"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CHECK_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "clarity.txt"
DEFAULT_VALIDATION_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "validation.txt"
DEFAULT_SUMMARY_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "summary.txt"
CHECK_PROMPT_MAX_BYTES = 256 * 1024

try:
    RESULT_TTL_SECONDS = int(os.getenv("RESULT_TTL_HOURS", "24")) * 3600
except ValueError:
    RESULT_TTL_SECONDS = 24 * 3600
MAX_PATH_LEN = 1024
MAX_RANGE_SPEC_LEN = 4096
ERROR_ID_LENGTH = 8
try:
    _RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_CHECK_PER_MINUTE", "10"))
except ValueError:
    _RATE_LIMIT_PER_MINUTE = 10

_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:80").split(",")
    if o.strip()
]

_OUTPUT_BASE_DIR_STR = os.getenv("OUTPUT_BASE_DIR", "").strip()

_DEFAULT_SERVERS = [
    {"url": "http://10.99.66.97:1234", "concurrency": 3},
    {"url": "http://10.99.66.212:1234", "concurrency": 3},
]

_rate_store: dict[str, list[float]] = defaultdict(list)
_rate_lock = Lock()


def _is_rate_limited(client_ip: str) -> bool:
    now = time.time()
    with _rate_lock:
        times = [t for t in _rate_store.get(client_ip, []) if now - t < 60]
        if len(times) >= _RATE_LIMIT_PER_MINUTE:
            _rate_store[client_ip] = times
            return True
        times.append(now)
        _rate_store[client_ip] = times
        return False


def _cleanup_rate_store() -> None:
    now = time.time()
    with _rate_lock:
        stale = [ip for ip, ts in _rate_store.items() if not ts or now - ts[-1] > 60]
        for ip in stale:
            del _rate_store[ip]


def _get_worker_servers() -> list[dict]:
    raw = os.getenv("WORKER_SERVERS", "").strip()
    if not raw:
        return _DEFAULT_SERVERS
    try:
        servers = json.loads(raw)
        if isinstance(servers, list) and servers:
            return servers
    except Exception:
        logger.warning("WORKER_SERVERS env var is not valid JSON, using defaults")
    return _DEFAULT_SERVERS


def _validate_output_dir(path: str) -> Path:
    p = Path(path).resolve()
    allowed_prefixes = get_allowed_prefixes()
    if allowed_prefixes:
        resolved_str = str(p)
        if not any(resolved_str.startswith(str(Path(pfx).resolve())) for pfx in allowed_prefixes):
            raise HTTPException(status_code=400, detail="Путь output_dir вне разрешённой директории")
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _pipeline_worker() -> None:
    while True:
        try:
            job_id = await job_store.get_next_job_id()
            job = job_store.get_job(job_id)
            if job is None:
                job_store.complete_active_job()
                job_store.task_done()
                continue
            cfg = job.config_snapshot or config_store.get_config()
            if cfg is None:
                job.status = JobStatus.ERROR
                job.error = "Конфигурация не задана"
                job_store.update_job(job)
                job_store.complete_active_job()
                job_store.task_done()
                continue
            servers = _get_worker_servers()
            try:
                await pipeline_orchestrator.run(job, cfg, servers)
            except Exception as exc:
                logger.error("_pipeline_worker unhandled error for job %s: %s", job_id, exc, exc_info=True)
                failed_job = job_store.get_job(job_id)
                if failed_job is not None and failed_job.status not in (JobStatus.DONE, JobStatus.CANCELLED):
                    failed_job.status = JobStatus.ERROR
                    failed_job.error = str(exc)
                    job_store.update_job(failed_job)
            finally:
                job_store.complete_active_job()
                job_store.task_done()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("_pipeline_worker loop error: %s", exc)


class _RangeItem(BaseModel):
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _validate_section(cls, v: str) -> str:
        import re
        if not re.match(r"^\d+(?:\.\d+)*$", v):
            raise ValueError(f"Неверный номер раздела: {v!r}")
        if len(v) > 50:
            raise ValueError("Номер раздела слишком длинный")
        return v


class _RangeSpec(BaseModel):
    valid: bool
    type: str
    items: list[_RangeItem]


def _cleanup_old_results() -> None:
    now = time.time()
    for f in RESULT_DIR.glob("*_result.txt"):
        try:
            if now - f.stat().st_mtime > RESULT_TTL_SECONDS:
                f.unlink()
                logger.info("Cleaned up old result file: %s", f.name)
        except OSError as exc:
            logger.warning("Failed to clean up result file %s: %s", f.name, exc)


async def _periodic_cleanup() -> None:
    while True:
        try:
            await asyncio.sleep(3600)
            _cleanup_old_results()
            job_store.cleanup_old_jobs()
            _cleanup_rate_store()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("_periodic_cleanup error: %s", exc)


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ARG001
    _cleanup_old_results()
    job_store.cleanup_old_jobs()
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    worker_task = asyncio.create_task(_pipeline_worker())
    yield
    worker_task.cancel()
    cleanup_task.cancel()
    for t in (worker_task, cleanup_task):
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Report Checker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def _validate_file_path(file_path: str) -> Path:
    if len(file_path) > MAX_PATH_LEN:
        raise HTTPException(status_code=400, detail="Путь к файлу слишком длинный")
    if "\x00" in file_path:
        raise HTTPException(status_code=400, detail="Недопустимый путь к файлу")

    linux_path = map_path(file_path)
    p = Path(linux_path)

    try:
        resolved = p.resolve()
        if p.is_symlink():
            raise HTTPException(status_code=403, detail="Доступ к файлу запрещён")
    except HTTPException:
        raise
    except OSError as e:
        logger.warning("OS error resolving path: %s", e)
        raise HTTPException(status_code=403, detail="Нет доступа к файлу или каталогу")

    allowed_prefixes = get_allowed_prefixes()
    if not allowed_prefixes:
        logger.warning("No path allowlist configured (path_mapping.json missing or empty) — all paths are accessible")
    else:
        resolved_str = str(resolved)
        if not any(resolved_str.startswith(str(Path(pfx).resolve())) for pfx in allowed_prefixes):
            logger.warning("Access denied for path (hash: %s)", resolved_str[:8])
            raise HTTPException(status_code=403, detail="Доступ к файлу запрещён")

    try:
        exists = resolved.exists()
        suffix = resolved.suffix.lower()
    except OSError as e:
        logger.warning("OS error checking path: %s", e)
        raise HTTPException(status_code=403, detail="Нет доступа к файлу или каталогу")

    if not exists:
        raise HTTPException(status_code=400, detail="Файл не найден")

    if suffix != ".docx":
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .docx")

    return resolved


def _safe_download_stem(raw: str, max_len: int = 80) -> str:
    t = (raw or "").strip()
    s = "".join(c if (c.isalnum() or c in "._-") else "_" for c in t)
    s = "_".join(p for p in s.split("_") if p)
    return (s or "report")[:max_len]


_CONTEXT_FIELD_KEYS = (
    "max_context_length",
    "context_length",
    "context_window",
    "max_model_len",
    "n_ctx",
)


def _openai_base_to_lm_root(openai_base: str) -> str:
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
    except Exception as exc:
        logger.debug("_resolve_context_tokens /api/v0/models list failed: %s", exc)

    try:
        r = await client.get(f"{root}/api/v0/models/{quote(model_id, safe='')}")
        if r.status_code == 200:
            payload = r.json()
            if isinstance(payload, dict):
                ctx = _context_from_model_entry(payload)
                if ctx is not None:
                    return ctx
    except Exception as exc:
        logger.debug("_resolve_context_tokens /api/v0/models/<id> failed: %s", exc)

    try:
        r = await client.get(f"{openai_base}/models")
        if r.status_code == 200:
            payload = r.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list):
                return _from_entries(data)
    except Exception as exc:
        logger.debug("_resolve_context_tokens /v1/models failed: %s", exc)

    return None


# ── Config endpoints ──────────────────────────────────────────────────────────

@app.post("/config")
async def set_config(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный JSON")

    raw_docx = (data.get("input_docx_path") or "").strip()
    raw_output = (data.get("output_dir") or "").strip()

    if not raw_docx:
        raise HTTPException(status_code=400, detail="input_docx_path обязателен")
    if not raw_output:
        raise HTTPException(status_code=400, detail="output_dir обязателен")

    try:
        resolved_docx = str(_validate_file_path(raw_docx))
    except HTTPException:
        raise

    try:
        resolved_output = str(_validate_output_dir(raw_output))
    except HTTPException:
        raise

    errors = config_store.validate_and_set(data, resolved_docx, resolved_output, validate_range_with_ai=ai_client.validate_range)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    return {"ok": True}


@app.get("/config")
async def get_config():
    cfg = config_store.to_dict()
    if cfg is None:
        return {}
    return cfg


# ── Check endpoint ────────────────────────────────────────────────────────────

@app.post("/check")
async def check(request: Request):
    client_ip = (request.client.host if request.client else "unknown")
    if _is_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Слишком много запросов. Подождите минуту.")

    cfg = config_store.get_config()
    if cfg is None:
        raise HTTPException(status_code=400, detail="Сначала сохраните конфигурацию через /config")

    job = job_store.create_job()
    job.submitted_at = time.time()
    job.docx_name = Path(cfg.input_docx_path).name
    job.config_snapshot = cfg
    job_store.update_job(job)

    queue_size = await enqueue_job(job.id)
    job.queue_position = queue_size
    job_store.update_job(job)

    return {"job_id": job.id, "queue_position": queue_size}


# ── Jobs list ─────────────────────────────────────────────────────────────────

@app.get("/jobs")
async def get_jobs():
    jobs = list_jobs()
    result = []
    for j in jobs:
        result.append({
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
        })
    return result


# ── Result log endpoint ───────────────────────────────────────────────────────

@app.get("/result_log/{job_id}")
async def result_log(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if not job.log_path:
        raise HTTPException(status_code=404, detail="Лог не найден")
    try:
        text = Path(job.log_path).read_text(encoding="utf-8")
        return {"log": text}
    except OSError:
        raise HTTPException(status_code=404, detail="Лог не найден")


# ── Existing endpoints (unchanged) ────────────────────────────────────────────

@app.post("/validate_path")
async def validate_path_endpoint(file_path: str = Form(...)):
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
    if len(range_text) > MAX_RANGE_SPEC_LEN:
        return {"valid": False, "range_message": "Текст диапазона слишком длинный", "server_error": False}
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
    if job.log_path:
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(job.log_path, "a", encoding="utf-8") as _lf:
                _lf.write(f"[{ts}] INFO  Cancel requested by user\n")
        except OSError:
            pass
    return {"ok": True}


@app.get("/runtime_info")
async def runtime_info():
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


def _read_prompt_file(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


@app.get("/default_prompts")
async def default_prompts():
    return {
        "check_prompt": _read_prompt_file(DEFAULT_CHECK_PROMPT_PATH),
        "validation_prompt": _read_prompt_file(DEFAULT_VALIDATION_PROMPT_PATH),
        "summary_prompt": _read_prompt_file(DEFAULT_SUMMARY_PROMPT_PATH),
    }


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
        "phase": job.phase,
    }


@app.get("/result/{job_id}")
async def result(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if job.status not in (JobStatus.DONE, JobStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Результат ещё не готов")
    if not job.result_path:
        raise HTTPException(status_code=404, detail="Файл результата не найден")

    stem = _safe_download_stem(job.source_doc_stem)
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
        raise HTTPException(status_code=404, detail="Файл результата не найден")


@app.get("/result_md/{job_id}")
async def result_md(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if job.status not in (JobStatus.DONE, JobStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Результат ещё не готов")
    if not job.md_result_path:
        raise HTTPException(status_code=404, detail="Файл Markdown не найден")

    stem = _safe_download_stem(job.source_doc_stem)
    filename = f"{stem}_docling.md"
    try:
        return FileResponse(
            path=job.md_result_path,
            media_type="text/markdown; charset=utf-8",
            filename=filename,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл Markdown не найден")
