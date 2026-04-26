from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from typing import Any, cast
from unittest import mock

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config_store
from app import job_repo
from app.error_codes import ERR_ACCESS_DENIED, ERR_CONFIG_NOT_SET, api_error, error_detail_from_http_exception
from app.jobs import JobStatus
from app.routes.config import set_config
from app.routes.defaults import get_config_defaults, get_field_help
from app.routes.results import result, result_log, result_md, status
from app.routes.validation import validate_output_dir_endpoint, validate_path_endpoint


def _detail(exc: HTTPException) -> dict[str, Any]:
    return cast(dict[str, Any], exc.detail)


class _Request:
    def __init__(self, payload: object | None = None, *, raise_json: bool = False) -> None:
        self._payload = payload
        self._raise_json = raise_json
        self.headers: dict[str, str] = {}

    async def json(self) -> object:
        if self._raise_json:
            raise ValueError("invalid json")
        return self._payload


class ErrorContractTests(unittest.TestCase):
    def test_api_error_uses_coded_payload_with_english_message(self) -> None:
        exc = api_error(ERR_CONFIG_NOT_SET)

        self.assertEqual(exc.status_code, 400)
        self.assertEqual(
            exc.detail,
            {"code": "ERR_CONFIG_NOT_SET", "message": "Configuration is not set."},
        )

    def test_error_detail_from_http_exception_preserves_known_api_shape(self) -> None:
        exc = api_error(ERR_ACCESS_DENIED)

        self.assertEqual(
            error_detail_from_http_exception(exc, fallback=ERR_CONFIG_NOT_SET),
            {"code": "ERR_ACCESS_DENIED", "message": "Access denied."},
        )

    def test_error_detail_from_http_exception_uses_fallback_for_plain_detail(self) -> None:
        exc = HTTPException(status_code=403, detail="forbidden")

        self.assertEqual(
            error_detail_from_http_exception(
                exc,
                fallback=ERR_ACCESS_DENIED,
                fallback_message="File is not accessible.",
            ),
            {"code": "ERR_ACCESS_DENIED", "message": "File is not accessible."},
        )


class ConfigRouteErrorTests(unittest.TestCase):
    def setUp(self) -> None:
        config_store._store.clear()

    def test_invalid_json_returns_error_code(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(set_config(_Request(raise_json=True)))  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(_detail(ctx.exception)["code"], "ERR_INVALID_JSON")

    def test_non_object_json_returns_error_code(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(set_config(_Request([])))  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(_detail(ctx.exception)["code"], "ERR_INVALID_JSON")

    def test_missing_input_path_returns_error_code(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(set_config(_Request({"output_dir": "/tmp/out"})))  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(_detail(ctx.exception)["code"], "ERR_INPUT_DOCX_REQUIRED")

    def test_missing_output_dir_returns_error_code(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(set_config(_Request({"input_docx_path": "/tmp/in.docx"})))  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(_detail(ctx.exception)["code"], "ERR_OUTPUT_DIR_REQUIRED")

    def test_validation_failure_returns_error_code(self) -> None:
        payload = {
            "input_docx_path": "/tmp/in.docx",
            "output_dir": "/tmp/out",
            "check_prompt": "",
        }

        with mock.patch("app.routes.config.validate_file_path", return_value=Path("/tmp/in.docx")), mock.patch(
            "app.routes.config.validate_output_dir", return_value=Path("/tmp/out")
        ):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(set_config(_Request(payload)))  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.status_code, 400)
        detail = _detail(ctx.exception)
        self.assertEqual(detail["code"], "ERR_CONFIG_VALIDATION_FAILED")
        self.assertIn("check_prompt: field is required", detail["message"])


class ValidationRouteContractTests(unittest.TestCase):
    def test_validate_path_returns_coded_error_payload_for_blank_input(self) -> None:
        result = asyncio.run(validate_path_endpoint(None))

        self.assertEqual(
            result,
            {
                "valid": False,
                "code": "ERR_INPUT_DOCX_REQUIRED",
                "message": "File path is required.",
                "mapped_path": "",
            },
        )

    def test_validate_path_reuses_api_error_detail_payload(self) -> None:
        exc = api_error(ERR_ACCESS_DENIED)

        with mock.patch("app.routes.validation.validate_file_path", side_effect=exc):
            result = asyncio.run(validate_path_endpoint("/tmp/in.docx"))

        self.assertEqual(
            result,
            {
                "valid": False,
                "code": "ERR_ACCESS_DENIED",
                "message": "Access denied.",
                "mapped_path": "",
            },
        )

    def test_validate_path_falls_back_to_access_denied_for_non_dict_detail(self) -> None:
        with mock.patch(
            "app.routes.validation.validate_file_path",
            side_effect=HTTPException(status_code=403, detail="denied"),
        ):
            result = asyncio.run(validate_path_endpoint("/tmp/in.docx"))

        self.assertEqual(
            result,
            {
                "valid": False,
                "code": "ERR_ACCESS_DENIED",
                "message": "File is not accessible.",
                "mapped_path": "",
            },
        )

    def test_validate_output_dir_returns_error_payload_for_blank_input(self) -> None:
        result = asyncio.run(validate_output_dir_endpoint(None))

        self.assertEqual(
            result,
            {
                "valid": False,
                "code": "ERR_OUTPUT_DIR_REQUIRED",
                "message": "Output directory is required.",
                "resolved_path": "",
            },
        )

    def test_validate_output_dir_returns_resolved_path(self) -> None:
        with mock.patch("app.routes.validation.validate_output_dir", return_value=Path("/tmp/out")):
            result = asyncio.run(validate_output_dir_endpoint("/tmp/out"))

        self.assertEqual(
            result,
            {
                "valid": True,
                "message": "Output directory is accessible.",
                "resolved_path": "/tmp/out",
            },
        )


class DefaultsRouteContractTests(unittest.TestCase):
    def test_config_defaults_returns_scalar_values(self) -> None:
        result = asyncio.run(get_config_defaults())

        self.assertIn("input_docx_path", result)
        self.assertIn("output_dir", result)
        self.assertIn("subchapters_range", result)
        self.assertIn("chunk_size_tokens", result)
        self.assertIn("temperature", result)

    def test_field_help_returns_plain_text(self) -> None:
        result = asyncio.run(get_field_help("temperature"))

        self.assertIn("Температура", result)


class ResultsRouteContractTests(unittest.TestCase):
    def setUp(self) -> None:
        job_repo._store.clear()

    def test_status_missing_job_uses_standard_error_shape(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(status("missing"))

        self.assertEqual(_detail(ctx.exception), {"code": "ERR_JOB_NOT_FOUND", "message": "Job was not found."})

    def test_result_log_missing_file_uses_standard_error_shape(self) -> None:
        job = job_repo.create_job()

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(result_log(job.id))

        self.assertEqual(_detail(ctx.exception), {"code": "ERR_LOG_NOT_FOUND", "message": "Log was not found."})

    def test_result_not_ready_uses_standard_error_shape(self) -> None:
        job = job_repo.create_job()

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(result(job.id))

        self.assertEqual(_detail(ctx.exception), {"code": "ERR_RESULT_NOT_READY", "message": "Result is not ready."})

    def test_result_file_missing_maps_os_error_to_standard_error_shape(self) -> None:
        job = job_repo.create_job()
        job.status = JobStatus.DONE
        job.result_path = "/tmp/result.txt"
        job_repo.update_job(job)

        with mock.patch("app.routes.results.FileResponse", side_effect=OSError("missing")):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(result(job.id))

        self.assertEqual(_detail(ctx.exception), {"code": "ERR_FILE_NOT_FOUND", "message": "File was not found."})

    def test_result_md_file_missing_maps_os_error_to_standard_error_shape(self) -> None:
        job = job_repo.create_job()
        job.status = JobStatus.DONE
        job.md_result_path = "/tmp/result.md"
        job_repo.update_job(job)

        with mock.patch("app.routes.results.FileResponse", side_effect=OSError("missing")):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(result_md(job.id))

        self.assertEqual(_detail(ctx.exception), {"code": "ERR_FILE_NOT_FOUND", "message": "File was not found."})
