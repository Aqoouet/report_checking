from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml  # type: ignore[import-untyped]

from app.job_repo import get_job, patch_job
from app.jobs import Job, JobStatus
from app.config_store import PipelineConfig
from app.worker_ai_client import call_worker_chat as call_async
from app.worker_servers import WorkerServer

logger = logging.getLogger(__name__)
MSK_TZ = ZoneInfo("Europe/Moscow")


class PipelineCancelledError(Exception):
    pass


def _ensure_not_cancelled(job_id: str, log: "ArtifactLogger | None" = None) -> None:
    fresh = get_job(job_id)
    if fresh and fresh.cancelled:
        if log:
            log.info("Cancelled by user")
        raise PipelineCancelledError()


class _ArtifactFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return datetime.fromtimestamp(record.created, MSK_TZ).strftime(
            datefmt or "%Y-%m-%d %H:%M:%S"
        )


class ArtifactLogger:
    def __init__(self, path: str, job_id: str) -> None:
        self._handler = logging.FileHandler(path, mode="w", encoding="utf-8")
        self._handler.setFormatter(
            _ArtifactFormatter("[%(asctime)s] %(levelname)-5s %(message)s")
        )
        self._logger = logging.getLogger(f"{__name__}.artifact.{job_id}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        for handler in list(self._logger.handlers):
            self._logger.removeHandler(handler)
            handler.close()
        self._logger.addHandler(self._handler)
        self._adapter = logging.LoggerAdapter(self._logger, {"job_id": job_id})

    def info(self, msg: str) -> None:
        self._adapter.info(msg)

    def error(self, msg: str) -> None:
        self._adapter.error(msg)

    def close(self) -> None:
        self._logger.removeHandler(self._handler)
        self._handler.close()


def _write_config_yaml(config: PipelineConfig, path: Path) -> None:
    payload = asdict(config)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _split_check_result_blocks(text: str) -> list[str]:
    sep = "=" * 40
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.strip() == sep and current:
            blocks.append("".join(current))
            current = []
        current.append(line)
    if current:
        blocks.append("".join(current))
    return [b for b in blocks if b.strip()]


async def _call_in_chunks(
    text: str,
    prompt: str,
    servers: list[WorkerServer],
    model: str,
    temperature: float | None,
    max_chunk_tokens: int = 8000,
    log: "ArtifactLogger | None" = None,
    job_id: str | None = None,
    job: "Job | None" = None,
) -> str:
    from app.token_chunker import count_tokens

    first_url = servers[0].url_str

    if count_tokens(text) <= max_chunk_tokens:
        return await call_async(text, prompt, first_url, model=model, temperature=temperature)

    blocks = _split_check_result_blocks(text)
    if not blocks:
        return await call_async(text, prompt, first_url, model=model, temperature=temperature)

    chunks: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0
    for block in blocks:
        bt = count_tokens(block)
        if current_tokens + bt > max_chunk_tokens and current_parts:
            chunks.append("".join(current_parts))
            current_parts = []
            current_tokens = 0
        current_parts.append(block)
        current_tokens += bt
    if current_parts:
        chunks.append("".join(current_parts))

    if log:
        log.info(
            f"  Text too large, split into {len(chunks)} chunks "
            f"(parallel across {len(servers)} server(s))"
        )

    sems = {s.url_str: asyncio.Semaphore(s.concurrency) for s in servers}
    results: list[str | None] = [None] * len(chunks)

    async def process_chunk(i: int, chunk: str) -> None:
        if job_id:
            fresh = get_job(job_id)
            if fresh and fresh.cancelled:
                return
        server = servers[i % len(servers)]
        url = server.url_str
        if log:
            log.info(f"  Chunk {i + 1}/{len(chunks)} → [{url}]")
        async with sems[url]:
            if job_id:
                fresh = get_job(job_id)
                if fresh and fresh.cancelled:
                    return
            results[i] = await call_async(chunk, prompt, url, model=model, temperature=temperature)
        if log:
            log.info(f"  Chunk {i + 1}/{len(chunks)} ✓")

    tasks = [asyncio.create_task(process_chunk(i, c)) for i, c in enumerate(chunks)]

    async def _cancel_watcher_chunks() -> None:
        notified = False
        while not all(t.done() for t in tasks):
            await asyncio.sleep(1)
            if not job_id:
                return
            fresh = get_job(job_id)
            if fresh and fresh.cancelled:
                if not notified:
                    notified = True
                    patch_job(job_id, phase="cancelling")
                    if log:
                        log.info(
                            "Cancellation requested — waiting for in-flight HTTP responses "
                            "to avoid server overhead…"
                        )

    await asyncio.gather(_cancel_watcher_chunks(), *tasks, return_exceptions=True)

    return "\n\n".join(r for r in results if r is not None)


def _patch_job(job_id: str, **fields: object) -> Job:
    updated = patch_job(job_id, **fields)
    if updated is None:
        raise RuntimeError(f"Job not found: {job_id}")
    return updated


def _mark_done(job_id: str) -> None:
    _patch_job(
        job_id,
        phase="done",
        status=JobStatus.DONE,
        finished_at=time.time(),
        current_checkpoint_name="Готово",
    )
