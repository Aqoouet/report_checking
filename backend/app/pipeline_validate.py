from __future__ import annotations

import logging
from pathlib import Path

from app.config_store import PipelineConfig
from app.jobs import Job
from app.worker_servers import WorkerServer
from app.pipeline_infra import ArtifactLogger, _call_in_chunks, _ensure_not_cancelled, _patch_job

logger = logging.getLogger(__name__)


async def _run_validate_stage(
    job: Job,
    config: PipelineConfig,
    servers: list[WorkerServer],
    artifact_dir: Path,
    check_result_path: str,
    log: ArtifactLogger,
) -> str:
    if not config.validation_prompt.strip():
        return check_result_path

    _patch_job(
        job.id,
        phase="validate",
        current_checkpoint_name="Валидация",
        checkpoint_sub_current=0,
        checkpoint_sub_total=0,
    )
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
    _patch_job(job.id, result_path=validated_path)
    log.info("Validate done")
    _ensure_not_cancelled(job.id, log)
    return validated_path
