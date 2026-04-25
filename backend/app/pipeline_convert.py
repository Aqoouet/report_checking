from __future__ import annotations

import asyncio
import functools
import logging
from pathlib import Path

from app.artifact_writer import write_artifact
from app.config_store import PipelineConfig
from app.doc_models import DocData
from app.doc_parser import parse_document
from app.jobs import Job, JobStatus
from app.range_parser import parse_range_script
from app.pipeline_infra import ArtifactLogger, _ensure_not_cancelled, _patch_job

logger = logging.getLogger(__name__)


async def _run_convert_stage(
    job: Job,
    config: PipelineConfig,
    artifact_dir: Path,
    stem: str,
    log: ArtifactLogger,
) -> DocData:
    _patch_job(
        job.id,
        artifact_dir=str(artifact_dir),
        phase="convert",
        status=JobStatus.PROCESSING,
        current_checkpoint_name="Конвертация",
    )
    _ensure_not_cancelled(job.id, log)

    range_spec = None
    if config.subchapters_range.strip():
        parsed = parse_range_script(config.subchapters_range)
        if parsed.get("valid") and parsed.get("items"):
            range_spec = parsed

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
    write_artifact(converted_path, md_text)
    _patch_job(job.id, md_result_path=converted_path, source_doc_stem=stem)
    log.info("Convert done")
    _ensure_not_cancelled(job.id, log)
    return doc_data
