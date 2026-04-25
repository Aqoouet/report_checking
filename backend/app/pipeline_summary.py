from __future__ import annotations

import logging
from pathlib import Path

from app.aggregator import write_summary
from app.config_store import PipelineConfig
from app.jobs import Job
from app.worker_servers import WorkerServer
from app.pipeline_infra import ArtifactLogger, _call_in_chunks, _patch_job

logger = logging.getLogger(__name__)


async def _run_summary_stage(
    job: Job,
    config: PipelineConfig,
    servers: list[WorkerServer],
    artifact_dir: Path,
    source_path: str,
    log: ArtifactLogger,
) -> None:
    if not config.summary_prompt.strip():
        return

    _patch_job(job.id, phase="summary", current_checkpoint_name="Резюме")
    source_text = Path(source_path).read_text(encoding="utf-8")
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
