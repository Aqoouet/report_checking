from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import job_repo, queue_service
from app.routes.check import cancel_job


class QueueServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        job_repo._store.clear()
        queue_service._pipeline_queue = asyncio.Queue()
        queue_service._active_job_id = None
        queue_service._waiting.clear()

    async def test_enqueue_updates_job_positions_from_queue_state(self) -> None:
        first = job_repo.create_job()
        second = job_repo.create_job()

        self.assertEqual(await queue_service.enqueue_job(first.id), 1)
        self.assertEqual(await queue_service.enqueue_job(second.id), 2)

        fresh_first = job_repo.get_job(first.id)
        fresh_second = job_repo.get_job(second.id)
        assert fresh_first is not None and fresh_second is not None
        self.assertEqual(fresh_first.queue_position, 1)
        self.assertEqual(fresh_second.queue_position, 2)

    async def test_cancel_pending_job_reindexes_waiting_positions(self) -> None:
        first = job_repo.create_job()
        second = job_repo.create_job()

        await queue_service.enqueue_job(first.id)
        await queue_service.enqueue_job(second.id)

        response = await cancel_job(first.id)

        fresh_first = job_repo.get_job(first.id)
        fresh_second = job_repo.get_job(second.id)
        assert fresh_first is not None and fresh_second is not None
        self.assertEqual(response, {"ok": True})
        self.assertEqual(fresh_first.status.value, "cancelled")
        self.assertEqual(fresh_first.queue_position, 0)
        self.assertEqual(fresh_second.queue_position, 1)
        self.assertEqual(queue_service._waiting, [second.id])

    async def test_get_next_job_skips_cancelled_entries_and_promotes_next_job(self) -> None:
        first = job_repo.create_job()
        second = job_repo.create_job()

        await queue_service.enqueue_job(first.id)
        await queue_service.enqueue_job(second.id)
        await cancel_job(first.id)

        next_job_id = await asyncio.wait_for(queue_service.get_next_job_id(), timeout=1)

        fresh_second = job_repo.get_job(second.id)
        assert fresh_second is not None
        self.assertEqual(next_job_id, second.id)
        self.assertEqual(fresh_second.queue_position, 0)
        queue_service.complete_active_job()
        queue_service.task_done()
