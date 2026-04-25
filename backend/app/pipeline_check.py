from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.config_store import PipelineConfig
from app.doc_models import DocData
from app.job_repo import get_job, patch_job, record_check_progress
from app.jobs import Job
from app.worker_ai_client import call_worker_chat as call_async
from app.worker_servers import WorkerServer
from app.pipeline_infra import ArtifactLogger, _ensure_not_cancelled, _patch_job

logger = logging.getLogger(__name__)


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
        result = results[i]
        record_check_progress(
            job.id,
            completed_delta=1,
            failed_delta=1 if result is not None and result[1].startswith("[ОШИБКА") else 0,
        )

    async def _cancel_watcher(tasks: list[asyncio.Task]) -> None:
        notified = False
        while not all(t.done() for t in tasks):
            await asyncio.sleep(1)
            fresh = get_job(job.id)
            if fresh and fresh.cancelled:
                if not notified:
                    notified = True
                    patch_job(job.id, phase="cancelling")
                    log.info(
                        "Cancellation requested — waiting for in-flight HTTP responses "
                        "to avoid server overhead…"
                    )

    patch_job(
        job.id,
        checkpoint_sub_total=len(sections),
        checkpoint_sub_current=0,
        failed_sections_count=0,
    )
    section_tasks = [asyncio.create_task(check_one(i, s)) for i, s in enumerate(sections)]
    await asyncio.gather(_cancel_watcher(section_tasks), *section_tasks, return_exceptions=True)
    completed = [r for r in results if r is not None]
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


async def _run_check_stage(
    job: Job,
    config: PipelineConfig,
    servers: list[WorkerServer],
    artifact_dir: Path,
    doc_data: DocData,
    log: ArtifactLogger,
) -> str:
    sections = doc_data.sections
    _patch_job(
        job.id,
        phase="check",
        current_checkpoint_name="Проверка",
        checkpoint_sub_total=len(sections),
        checkpoint_sub_current=0,
        failed_sections_count=0,
    )
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
    _patch_job(job.id, result_path=check_result_path)
    log.info("Check done")
    _ensure_not_cancelled(job.id, log)
    return check_result_path
