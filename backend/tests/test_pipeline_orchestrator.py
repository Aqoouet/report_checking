from __future__ import annotations

import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import job_repo
from app import pipeline_check
from app import pipeline_infra
from app import pipeline_orchestrator
from app.config_store import PipelineConfig
from app.doc_models import DocData, Section
from app.jobs import JobStatus
from app.worker_servers import WorkerServer


def _config(output_dir: str, *, validation_prompt: str = "", summary_prompt: str = "") -> PipelineConfig:
    return PipelineConfig(
        input_docx_path="/tmp/input.docx",
        output_dir=output_dir,
        check_prompt="check",
        validation_prompt=validation_prompt,
        summary_prompt=summary_prompt,
        chunk_size_tokens=10000,
        model="model",
    )


def _servers() -> list[WorkerServer]:
    return [WorkerServer.model_validate({"url": "http://example.test", "concurrency": 2})]


class PipelineOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        job_repo._store.clear()

    def test_parallel_check_progress_and_failed_count(self) -> None:
        async def run_check() -> None:
            job = job_repo.create_job()
            sections = [
                Section(number="1", title="One", text="ok", level=1),
                Section(number="2", title="Two", text="bad", level=1),
            ]

            async def fake_call(text: str, *args, **kwargs) -> str:
                if text == "bad":
                    raise RuntimeError("boom")
                return "ok"

            with tempfile.TemporaryDirectory() as tmp, mock.patch(
                "app.pipeline_check.call_async", side_effect=fake_call
            ):
                log = pipeline_infra.ArtifactLogger(str(Path(tmp) / "run.log"), job.id)
                try:
                    results = await pipeline_check._parallel_check(
                        sections,
                        _config(tmp),
                        _servers(),
                        job,
                        log,
                    )
                finally:
                    log.close()

            self.assertEqual(len(results), 2)
            fresh = job_repo.get_job(job.id)
            self.assertIsNotNone(fresh)
            assert fresh is not None
            self.assertEqual(fresh.checkpoint_sub_total, 2)
            self.assertEqual(fresh.checkpoint_sub_current, 2)
            self.assertEqual(fresh.failed_sections_count, 1)

        asyncio.run(run_check())

    def test_call_in_chunks_cancelling_preserves_cancelled_flag(self) -> None:
        async def run_chunks() -> None:
            job = job_repo.create_job()
            job.cancelled = True
            job_repo.update_job(job)
            with tempfile.TemporaryDirectory() as tmp:
                log = pipeline_infra.ArtifactLogger(str(Path(tmp) / "run.log"), job.id)
                try:
                    fake_token_chunker = types.SimpleNamespace(count_tokens=lambda _: 1)
                    with mock.patch.dict(sys.modules, {"app.token_chunker": fake_token_chunker}), mock.patch(
                        "app.pipeline_infra.call_async", return_value="ok"
                    ):
                        await pipeline_infra._call_in_chunks(
                            "small",
                            "prompt",
                            _servers(),
                            model="model",
                            temperature=None,
                            log=log,
                            job_id=job.id,
                            job=job,
                        )
                finally:
                    log.close()
            fresh = job_repo.get_job(job.id)
            self.assertIsNotNone(fresh)
            assert fresh is not None
            self.assertTrue(fresh.cancelled)

        asyncio.run(run_chunks())

    def test_run_success_creates_artifacts_and_marks_done(self) -> None:
        async def run_pipeline() -> None:
            job = job_repo.create_job()
            doc_data = DocData(
                file_path="/tmp/input.docx",
                sections=[Section(number="1", title="One", text="body", level=1)],
            )

            async def fake_call(*args, **kwargs) -> str:
                return "checked"

            async def fake_run_in_executor(_executor, func):
                return func()

            fake_loop = types.SimpleNamespace(run_in_executor=fake_run_in_executor)
            with tempfile.TemporaryDirectory() as tmp, mock.patch(
                "app.pipeline_convert.parse_document", return_value=(doc_data, "# md")
            ), mock.patch(
                "app.pipeline_convert.asyncio.get_event_loop", return_value=fake_loop
            ), mock.patch("app.pipeline_check.call_async", side_effect=fake_call):
                await pipeline_orchestrator.run(job, _config(tmp), _servers())
                fresh = job_repo.get_job(job.id)
                self.assertIsNotNone(fresh)
                assert fresh is not None
                self.assertEqual(fresh.status, JobStatus.DONE)
                self.assertEqual(fresh.phase, "done")
                self.assertIsNotNone(fresh.artifact_dir)
                assert fresh.artifact_dir is not None
                artifact_dir = Path(fresh.artifact_dir)
                self.assertTrue((artifact_dir / "run.log").exists())
                self.assertTrue((artifact_dir / "config.yaml").exists())
                self.assertTrue((artifact_dir / "converted.md").exists())
                self.assertTrue((artifact_dir / "check_result.txt").exists())

        asyncio.run(run_pipeline())

    def test_run_cancelled_marks_cancelled(self) -> None:
        async def run_pipeline() -> None:
            job = job_repo.create_job()
            job.cancelled = True
            job_repo.update_job(job)
            with tempfile.TemporaryDirectory() as tmp:
                await pipeline_orchestrator.run(job, _config(tmp), _servers())
                fresh = job_repo.get_job(job.id)
                self.assertIsNotNone(fresh)
                assert fresh is not None
                self.assertEqual(fresh.status, JobStatus.CANCELLED)
                self.assertEqual(fresh.phase, "cancelled")
                self.assertTrue(fresh.cancelled)

        asyncio.run(run_pipeline())
