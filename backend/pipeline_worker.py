from __future__ import annotations

import asyncio
import logging

import config_store
import job_repo
import pipeline_orchestrator
import queue_service
from jobs import JobStatus
from worker_servers import get_worker_servers

logger = logging.getLogger(__name__)


async def pipeline_worker() -> None:
    while True:
        try:
            job_id = await queue_service.get_next_job_id()
            job = job_repo.get_job(job_id)
            if job is None:
                queue_service.complete_active_job()
                queue_service.task_done()
                continue
            if job.status == JobStatus.CANCELLED:
                queue_service.complete_active_job()
                queue_service.task_done()
                continue
            cfg = job.config_snapshot or config_store.get_config()
            if cfg is None:
                job.status = JobStatus.ERROR
                job.error = "Конфигурация не задана"
                job_repo.update_job(job)
                queue_service.complete_active_job()
                queue_service.task_done()
                continue
            servers = get_worker_servers()
            try:
                await pipeline_orchestrator.run(job, cfg, servers)
            except Exception as exc:
                logger.error(
                    "pipeline_worker unhandled error for job %s: %s", job_id, exc, exc_info=True
                )
                failed_job = job_repo.get_job(job_id)
                if failed_job is not None and failed_job.status not in (
                    JobStatus.DONE,
                    JobStatus.CANCELLED,
                ):
                    failed_job.status = JobStatus.ERROR
                    failed_job.error = str(exc)
                    job_repo.update_job(failed_job)
            finally:
                queue_service.complete_active_job()
                queue_service.task_done()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("pipeline_worker loop error: %s", exc, exc_info=True)
