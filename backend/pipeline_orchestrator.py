from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from job_repo import get_job, update_job
from jobs import Job, JobStatus
from config_store import PipelineConfig
from doc_parser import parse_document
from range_parser import parse_range_script
from ai_client import call_async
from aggregator import write_summary
from worker_servers import WorkerServer

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


class ArtifactLogger:
    def __init__(self, path: str) -> None:
        self._f = open(path, "w", encoding="utf-8", buffering=1)

    def info(self, msg: str) -> None:
        ts = datetime.now(MSK_TZ).strftime("%Y-%m-%d %H:%M:%S")
        self._f.write(f"[{ts}] INFO  {msg}\n")

    def error(self, msg: str) -> None:
        ts = datetime.now(MSK_TZ).strftime("%Y-%m-%d %H:%M:%S")
        self._f.write(f"[{ts}] ERROR {msg}\n")

    def close(self) -> None:
        self._f.close()


def _write_config_yaml(config: PipelineConfig, path: Path) -> None:
    payload = asdict(config)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


async def _parallel_check(
    sections: list,
    config: PipelineConfig,
    servers: list[WorkerServer],
    job: Job,
    log: ArtifactLogger,
) -> list[tuple[str, str]]:
    sems = {s.url_str: asyncio.Semaphore(s.concurrency) for s in servers}
    results: list[tuple[str, str] | None] = [None] * len(sections)

    async def check_one(i: int, section) -> None:
        server = servers[i % len(servers)]
        url = server.url_str
        sem = sems[url]
        label = (
            f"{getattr(section, 'number', '')} {getattr(section, 'title', '')}".strip()
            or f"Раздел {i + 1}"
        )
        try:
            async with sem:
                fresh = get_job(job.id)
                if fresh and fresh.cancelled:
                    return
                log.info(f"→ [{url}] {label}")
                response = await call_async(
                    section.text,
                    config.check_prompt,
                    url,
                    model=config.model,
                    temperature=config.temperature,
                )
            log.info(f"✓ [{url}] {label}")
            results[i] = (label, response)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            log.error(f"✗ [{url}] {label}: {exc}")
            results[i] = (label, f"[ОШИБКА при проверке: {exc}]")
        job.checkpoint_sub_current = sum(1 for r in results if r is not None)
        update_job(job)

    async def _cancel_watcher(tasks: list[asyncio.Task]) -> None:
        notified = False
        while not all(t.done() for t in tasks):
            await asyncio.sleep(1)
            fresh = get_job(job.id)
            if fresh and fresh.cancelled:
                if not notified:
                    notified = True
                    job.phase = "cancelling"
                    update_job(job)
                    log.info(
                        "Cancellation requested — waiting for in-flight HTTP responses "
                        "to avoid server overhead…"
                    )

    job.checkpoint_sub_total = len(sections)
    update_job(job)
    section_tasks = [asyncio.create_task(check_one(i, s)) for i, s in enumerate(sections)]
    await asyncio.gather(_cancel_watcher(section_tasks), *section_tasks, return_exceptions=True)
    completed = [r for r in results if r is not None]
    job.failed_sections_count = sum(1 for _, resp in completed if resp.startswith("[ОШИБКА"))
    update_job(job)
    return completed


def _write_check_result(section_results: list[tuple[str, str]], path: str) -> None:
    lines: list[str] = []
    for label, response in section_results:
        lines.append("=" * 40)
        lines.append(f"РАЗДЕЛ: {label}")
        lines.append("=" * 40)
        lines.append(response.strip())
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


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
    model: str | None,
    temperature: float | None,
    max_chunk_tokens: int = 8000,
    log: "ArtifactLogger | None" = None,
    job_id: str | None = None,
    job: "Job | None" = None,
) -> str:
    from token_chunker import count_tokens

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
        log.info(f"  Text too large, split into {len(chunks)} chunks (parallel across {len(servers)} server(s))")

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
                    target = job if job is not None else fresh
                    target.phase = "cancelling"
                    update_job(target)
                    if log:
                        log.info(
                            "Cancellation requested — waiting for in-flight HTTP responses "
                            "to avoid server overhead…"
                        )

    await asyncio.gather(_cancel_watcher_chunks(), *tasks, return_exceptions=True)

    return "\n\n".join(r for r in results if r is not None)


async def run(job: Job, config: PipelineConfig, servers: list[WorkerServer]) -> None:
    ts = datetime.now(MSK_TZ).strftime("%Y%m%d_%H%M%S")
    stem = Path(config.input_docx_path).stem
    artifact_dir = Path(config.output_dir) / f"{stem}_{ts}"

    log: ArtifactLogger | None = None
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)

        log_path = str(artifact_dir / "run.log")
        log = ArtifactLogger(log_path)
        config_path = artifact_dir / "config.yaml"
        _write_config_yaml(config, config_path)

        job.artifact_dir = str(artifact_dir)
        job.log_path = log_path
        job.phase = "convert"
        job.status = JobStatus.PROCESSING
        job.current_checkpoint_name = "Конвертация"
        update_job(job)

        log.info(f"Start: {config.input_docx_path}")
        log.info(f"Model: {config.model or '(from env)'}")
        log.info(f"Config saved: {config_path}")
        _ensure_not_cancelled(job.id, log)

        # CONVERT
        range_spec = None
        if config.subchapters_range.strip():
            parsed = parse_range_script(config.subchapters_range)
            if parsed.get("valid") and parsed.get("items"):
                range_spec = parsed

        import functools
        loop = asyncio.get_event_loop()
        doc_data, md_text = await loop.run_in_executor(
            None,
            functools.partial(
                parse_document,
                config.input_docx_path,
                range_spec,
                config.chunk_size_tokens,
            ),
        )

        converted_path = str(artifact_dir / "converted.md")
        Path(converted_path).write_text(md_text, encoding="utf-8")
        job.md_result_path = converted_path
        job.source_doc_stem = stem
        log.info("Convert done")
        _ensure_not_cancelled(job.id, log)

        # CHECK
        job.phase = "check"
        job.current_checkpoint_name = "Проверка"
        sections = doc_data.sections
        job.checkpoint_sub_total = len(sections)
        job.checkpoint_sub_current = 0
        update_job(job)
        log.info(f"Split: {len(sections)} sections")
        for idx, sec in enumerate(sections):
            sec_label = (
                f"{getattr(sec, 'number', '')} {getattr(sec, 'title', '')}".strip()
                or f"Раздел {idx + 1}"
            )
            log.info(f"  [{idx + 1}/{len(sections)}] {sec_label}")

        section_results = await _parallel_check(sections, config, servers, job, log)

        check_result_path = str(artifact_dir / "check_result.txt")
        _write_check_result(section_results, check_result_path)
        job.result_path = check_result_path
        update_job(job)
        log.info("Check done")
        _ensure_not_cancelled(job.id, log)

        # VALIDATE (optional)
        if config.validation_prompt.strip():
            job.phase = "validate"
            job.current_checkpoint_name = "Валидация"
            job.checkpoint_sub_current = 0
            job.checkpoint_sub_total = 0
            update_job(job)

            check_text = Path(check_result_path).read_text(encoding="utf-8")
            validated_text = await _call_in_chunks(
                check_text,
                config.validation_prompt,
                servers,
                model=config.model,
                temperature=config.temperature,
                max_chunk_tokens=config.chunk_size_tokens,
                log=log,
                job_id=job.id,
                job=job,
            )
            validated_path = str(artifact_dir / "validated_result.txt")
            Path(validated_path).write_text(validated_text, encoding="utf-8")
            job.result_path = validated_path
            update_job(job)
            log.info("Validate done")
        _ensure_not_cancelled(job.id, log)

        # SUMMARY (optional)
        if config.summary_prompt.strip():
            job.phase = "summary"
            job.current_checkpoint_name = "Резюме"
            update_job(job)

            source_text = Path(job.result_path).read_text(encoding="utf-8")
            summary_text = await _call_in_chunks(
                source_text,
                config.summary_prompt,
                servers,
                model=config.model,
                temperature=config.temperature,
                max_chunk_tokens=config.chunk_size_tokens,
                log=log,
                job_id=job.id,
                job=job,
            )
            summary_path = str(artifact_dir / "summary.txt")
            write_summary(summary_text, summary_path)
            log.info("Summary done")

        # DONE
        job.phase = "done"
        job.status = JobStatus.DONE
        job.finished_at = time.time()
        job.current_checkpoint_name = "Готово"
        update_job(job)
        log.info("Pipeline complete")

    except PipelineCancelledError:
        job.phase = "cancelled"
        job.status = JobStatus.CANCELLED
        job.finished_at = time.time()
        job.current_checkpoint_name = "Отменено"
        update_job(job)
        if log:
            log.info("Job cancelled — pipeline stopped")
    except Exception as exc:
        logger.error("Pipeline error for job %s: %s", job.id, exc, exc_info=True)
        if log:
            log.error(f"Pipeline error: {exc}")
        job.status = JobStatus.ERROR
        job.finished_at = time.time()
        job.error = str(exc)
        update_job(job)
    finally:
        if log:
            log.close()
