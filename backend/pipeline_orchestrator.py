from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

from jobs import Job, JobStatus, get_job, update_job
from config_store import PipelineConfig
from doc_parser import parse_document
from range_parser import parse_range_script
from ai_client import call_async
from aggregator import write_summary

logger = logging.getLogger(__name__)


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
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._f.write(f"[{ts}] INFO  {msg}\n")

    def error(self, msg: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._f.write(f"[{ts}] ERROR {msg}\n")

    def close(self) -> None:
        self._f.close()


async def _parallel_check(
    sections: list,
    config: PipelineConfig,
    servers: list[dict],
    job: Job,
    log: ArtifactLogger,
) -> list[tuple[str, str]]:
    sems = {s["url"]: asyncio.Semaphore(s.get("concurrency", 3)) for s in servers}
    results: list[tuple[str, str] | None] = [None] * len(sections)

    async def check_one(i: int, section) -> None:
        server = servers[i % len(servers)]
        url = server["url"]
        sem = sems[url]
        label = (
            f"{getattr(section, 'number', '')} {getattr(section, 'title', '')}".strip()
            or f"Раздел {i + 1}"
        )
        fresh = get_job(job.id)
        if fresh and fresh.cancelled:
            return
        try:
            log.info(f"→ [{url}] {label}")
            async with sem:
                response = await call_async(
                    section.text,
                    config.check_prompt,
                    url,
                    model=config.model,
                    temperature=config.temperature,
                )
            log.info(f"✓ [{url}] {label}")
            results[i] = (label, response)
        except Exception as exc:
            log.error(f"✗ [{url}] {label}: {exc}")
            results[i] = (label, f"[ОШИБКА при проверке: {exc}]")
        job.checkpoint_sub_current = sum(1 for r in results if r is not None)
        update_job(job)

    job.checkpoint_sub_total = len(sections)
    update_job(job)
    await asyncio.gather(*[check_one(i, s) for i, s in enumerate(sections)])
    return [r for r in results if r is not None]


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
    server_url: str,
    model: str | None,
    temperature: float | None,
    max_chunk_tokens: int = 8000,
    log: "ArtifactLogger | None" = None,
) -> str:
    from token_chunker import count_tokens

    if count_tokens(text) <= max_chunk_tokens:
        return await call_async(text, prompt, server_url, model=model, temperature=temperature)

    blocks = _split_check_result_blocks(text)
    if not blocks:
        return await call_async(text, prompt, server_url, model=model, temperature=temperature)

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
        log.info(f"  Text too large, split into {len(chunks)} chunks")

    results: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        if log:
            log.info(f"  Chunk {i}/{len(chunks)}")
        results.append(await call_async(chunk, prompt, server_url, model=model, temperature=temperature))

    return "\n\n".join(results)


async def run(job: Job, config: PipelineConfig, servers: list[dict]) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(config.input_docx_path).stem
    artifact_dir = Path(config.output_dir) / f"{stem}_{ts}"

    log: ArtifactLogger | None = None
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)

        log_path = str(artifact_dir / "run.log")
        log = ArtifactLogger(log_path)

        job.artifact_dir = str(artifact_dir)
        job.log_path = log_path
        job.phase = "convert"
        job.status = JobStatus.PROCESSING
        job.current_checkpoint_name = "Конвертация"
        update_job(job)

        log.info(f"Start: {config.input_docx_path}")
        log.info(f"Model: {config.model or '(from env)'}")
        _ensure_not_cancelled(job.id, log)

        # CONVERT
        range_spec = None
        if config.subchapters_range.strip():
            parsed = parse_range_script(config.subchapters_range)
            if parsed.get("valid") and parsed.get("items"):
                range_spec = parsed

        loop = asyncio.get_event_loop()
        doc_data, md_text = await loop.run_in_executor(
            None, parse_document, config.input_docx_path, range_spec
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
                servers[0]["url"],
                model=config.model,
                temperature=config.temperature,
                log=log,
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
                servers[0]["url"],
                model=config.model,
                temperature=config.temperature,
                log=log,
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
