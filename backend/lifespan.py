from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

import retention_service
from pipeline_worker import pipeline_worker
from rate_limit import cleanup_rate_store
from settings import RESULT_DIR, RESULT_TTL_SECONDS

logger = logging.getLogger(__name__)


def _cleanup_old_results() -> None:
    now = time.time()
    for f in RESULT_DIR.glob("*_result.txt"):
        try:
            if now - f.stat().st_mtime > RESULT_TTL_SECONDS:
                f.unlink()
                logger.info("Cleaned up old result file: %s", f.name)
        except OSError as exc:
            logger.warning("Failed to clean up result file %s: %s", f.name, exc)


async def _periodic_cleanup() -> None:
    while True:
        try:
            await asyncio.sleep(3600)
            _cleanup_old_results()
            retention_service.cleanup_old_jobs()
            cleanup_rate_store()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("_periodic_cleanup error: %s", exc)


@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ARG001
    _cleanup_old_results()
    retention_service.cleanup_old_jobs()
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    worker_task = asyncio.create_task(pipeline_worker())
    yield
    worker_task.cancel()
    cleanup_task.cancel()
    for t in (worker_task, cleanup_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
