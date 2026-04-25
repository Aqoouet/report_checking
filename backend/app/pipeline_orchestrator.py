from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

from app.config_store import PipelineConfig
from app.jobs import Job, JobStatus
from app.worker_servers import WorkerServer
from app.pipeline_infra import ArtifactLogger, MSK_TZ, PipelineCancelledError, _mark_done, _patch_job, _write_config_yaml
from app.pipeline_convert import _run_convert_stage
from app.pipeline_check import _run_check_stage
from app.pipeline_validate import _run_validate_stage
from app.pipeline_summary import _run_summary_stage

logger = logging.getLogger(__name__)


async def run(job: Job, config: PipelineConfig, servers: list[WorkerServer]) -> None:
    ts = datetime.now(MSK_TZ).strftime("%Y%m%d_%H%M%S")
    stem = Path(config.input_docx_path).stem
    artifact_dir = Path(config.output_dir) / f"{stem}_{ts}"
    log: ArtifactLogger | None = None
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)

        log_path = str(artifact_dir / "run.log")
        log = ArtifactLogger(log_path, job.id)
        config_path = artifact_dir / "config.yaml"
        _write_config_yaml(config, config_path)
        _patch_job(job.id, artifact_dir=str(artifact_dir), log_path=log_path)

        log.info(f"Start: {config.input_docx_path}")
        log.info(f"Model: {config.model or '(from env)'}")
        log.info(f"Config saved: {config_path}")

        doc_data = await _run_convert_stage(job, config, artifact_dir, stem, log)
        result_path = await _run_check_stage(job, config, servers, artifact_dir, doc_data, log)
        result_path = await _run_validate_stage(job, config, servers, artifact_dir, result_path, log)
        await _run_summary_stage(job, config, servers, artifact_dir, result_path, log)
        _mark_done(job.id)
        log.info("Pipeline complete")

    except PipelineCancelledError:
        _patch_job(
            job.id,
            phase="cancelled",
            status=JobStatus.CANCELLED,
            finished_at=time.time(),
            current_checkpoint_name="Отменено",
        )
        if log:
            log.info("Job cancelled — pipeline stopped")
    except Exception as exc:
        logger.error("Pipeline error for job %s: %s", job.id, exc, exc_info=True)
        if log:
            log.error(f"Pipeline error: {exc}")
        _patch_job(job.id, status=JobStatus.ERROR, finished_at=time.time(), error=str(exc))
    finally:
        if log:
            log.close()
