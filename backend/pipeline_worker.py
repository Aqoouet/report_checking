from __future__ import annotations

import asyncio
import logging

import config_store
import jobs as job_store
import pipeline_orchestrator
from jobs import JobStatus
from worker_servers import get_worker_servers

logger = logging.getLogger(__name__)


async def pipeline_worker() -> None:
    while True:
        try:
            job_id = await job_store.get_next_job_id()
            job = job_store.get_job(job_id)
            if job is None:
                job_store.complete_active_job()
                job_store.task_done()
                continue
            if job.status == JobStatus.CANCELLED:
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
            servers = get_worker_servers()
            try:
                await pipeline_orchestrator.run(job, cfg, servers)
            except Exception as exc:
                logger.error(
                    "pipeline_worker unhandled error for job %s: %s", job_id, exc, exc_info=True
                )
                failed_job = job_store.get_job(job_id)
                if failed_job is not None and failed_job.status not in (
                    JobStatus.DONE,
                    JobStatus.CANCELLED,
                ):
                    failed_job.status = JobStatus.ERROR
                    failed_job.error = str(exc)
                    job_store.update_job(failed_job)
            finally:
                job_store.complete_active_job()
                job_store.task_done()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("pipeline_worker loop error: %s", exc, exc_info=True)
