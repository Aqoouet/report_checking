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
from app.error_codes import ERR_CONFIG_NOT_SET, api_error
from app.routes.config import set_config


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
