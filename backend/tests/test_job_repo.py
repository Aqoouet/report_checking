from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import job_repo
from app.jobs import JobStatus


class JobRepoAtomicTests(unittest.TestCase):
    def setUp(self) -> None:
        job_repo._store.clear()

    def test_patch_job_preserves_cancelled_flag(self) -> None:
        job = job_repo.create_job()
        job.cancelled = True
        job_repo.update_job(job)

        patched = job_repo.patch_job(job.id, phase="check", result_path="result.txt")

        self.assertIsNotNone(patched)
        fresh = job_repo.get_job(job.id)
        self.assertIsNotNone(fresh)
        assert fresh is not None
        self.assertTrue(fresh.cancelled)
        self.assertEqual(fresh.phase, "check")
        self.assertEqual(fresh.result_path, "result.txt")

    def test_record_check_progress_updates_counts(self) -> None:
        job = job_repo.create_job()
        job_repo.patch_job(job.id, checkpoint_sub_total=2, status=JobStatus.PROCESSING)

        job_repo.record_check_progress(job.id, completed_delta=1)
        updated = job_repo.record_check_progress(job.id, completed_delta=1, failed_delta=1)

        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.checkpoint_sub_current, 2)
        self.assertEqual(updated.failed_sections_count, 1)
