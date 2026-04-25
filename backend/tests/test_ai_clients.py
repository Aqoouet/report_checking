from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx
from openai import APIStatusError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import range_ai_validator
import worker_ai_client

_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _mock_async_client(transport: httpx.MockTransport):
    return lambda **kwargs: _REAL_ASYNC_CLIENT(transport=transport, **kwargs)


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(str(outcome))


class _Chat:
    def __init__(self, completions: _Completions) -> None:
        self.completions = completions


class _Client:
    def __init__(self, outcomes: list[object]) -> None:
        self.completions = _Completions(outcomes)
        self.chat = _Chat(self.completions)


def _api_status_error(status: int, body: dict) -> APIStatusError:
    request = httpx.Request("POST", "http://example.test/v1/chat/completions")
    response = httpx.Response(status, request=request, json=body)
    return APIStatusError("status error", response=response, body=body)


class RangeAiValidatorTests(unittest.TestCase):
    def test_validate_range_uses_strict_response_format(self) -> None:
        payload = {
            "valid": True,
            "type": "sections",
            "items": [{"start": "3.1", "end": "3.4"}],
            "display": "Разделы: 3.1-3.4",
            "suggestion": "",
        }
        client = _Client([json.dumps(payload)])

        with mock.patch("range_ai_validator.get_client", return_value=client):
            result = range_ai_validator.validate_range("3.1-3.4")

        self.assertTrue(result["valid"])
        self.assertEqual(result["items"], [{"start": "3.1", "end": "3.4"}])
        self.assertEqual(
            client.completions.calls[0]["response_format"]["type"],
            "json_schema",
        )

    def test_validate_range_rejects_non_json_without_salvage(self) -> None:
        client = _Client(['```json\n{"valid": true, "items": []}\n```'])

        with mock.patch("range_ai_validator.get_client", return_value=client):
            result = range_ai_validator.validate_range("3")

        self.assertFalse(result["valid"])
        self.assertFalse(result["server_error"])

    def test_validate_range_rejects_invalid_schema(self) -> None:
        client = _Client([json.dumps({"valid": True, "items": [{"start": 1, "end": "2"}]})])

        with mock.patch("range_ai_validator.get_client", return_value=client):
            result = range_ai_validator.validate_range("1-2")

        self.assertFalse(result["valid"])
        self.assertFalse(result["server_error"])

    def test_validate_range_falls_back_when_response_format_unsupported(self) -> None:
        unsupported = _api_status_error(
            400,
            {"error": {"message": "response_format json_schema is not supported"}},
        )
        payload = {
            "valid": True,
            "items": [{"start": "1", "end": "1"}],
            "display": "Разделы: 1",
            "suggestion": "",
        }
        client = _Client([unsupported, json.dumps(payload)])

        with mock.patch("range_ai_validator.get_client", return_value=client):
            result = range_ai_validator.validate_range("1")

        self.assertTrue(result["valid"])
        self.assertEqual(len(client.completions.calls), 2)
        self.assertEqual(
            client.completions.calls[1]["response_format"],
            {"type": "json_object"},
        )

    def test_validate_range_falls_back_to_plain_json_when_json_mode_unsupported(self) -> None:
        strict_unsupported = _api_status_error(
            400,
            {"error": {"message": "response_format json_schema is not supported"}},
        )
        json_object_unsupported = _api_status_error(
            400,
            {"error": {"message": "response_format json_object is not supported"}},
        )
        payload = {
            "valid": True,
            "items": [{"start": "2", "end": "2"}],
            "display": "Разделы: 2",
            "suggestion": "",
        }
        client = _Client([strict_unsupported, json_object_unsupported, json.dumps(payload)])

        with mock.patch("range_ai_validator.get_client", return_value=client):
            result = range_ai_validator.validate_range("2")

        self.assertTrue(result["valid"])
        self.assertEqual(len(client.completions.calls), 3)
        self.assertNotIn("response_format", client.completions.calls[2])

    def test_validate_range_does_not_fallback_on_arbitrary_400(self) -> None:
        error = _api_status_error(
            400,
            {"error": {"message": "bad request"}},
        )
        client = _Client([error])

        with mock.patch("range_ai_validator.get_client", return_value=client):
            result = range_ai_validator.validate_range("1")

        self.assertFalse(result["valid"])
        self.assertFalse(result["server_error"])
        self.assertEqual(len(client.completions.calls), 1)

    def test_validate_range_model_not_found_message_is_preserved(self) -> None:
        error = _api_status_error(
            400,
            {"error": {"code": "model_not_found", "message": "missing model"}},
        )
        client = _Client([error])

        with mock.patch("range_ai_validator.get_client", return_value=client):
            result = range_ai_validator.validate_range("1")

        self.assertFalse(result["valid"])
        self.assertTrue(result["server_error"])
        self.assertIn("OPENAI_VALIDATE_MODEL", result["range_message"])


class WorkerAiClientTests(unittest.TestCase):
    def test_call_worker_chat_success(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode())
            self.assertEqual(body["model"], "model")
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
                request=request,
            )

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            with mock.patch(
                "worker_ai_client.httpx.AsyncClient",
                _mock_async_client(transport),
            ):
                result = await worker_ai_client.call_worker_chat(
                    "text",
                    "prompt",
                    "http://worker.test",
                    model="model",
                )
            self.assertEqual(result, "ok")

        asyncio.run(run())

    def test_call_worker_chat_wraps_http_error_body(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="broken", request=request)

        async def run() -> None:
            transport = httpx.MockTransport(handler)
            with mock.patch(
                "worker_ai_client.httpx.AsyncClient",
                _mock_async_client(transport),
            ):
                with self.assertRaises(httpx.HTTPStatusError) as ctx:
                    await worker_ai_client.call_worker_chat(
                        "text",
                        "prompt",
                        "http://worker.test",
                        model="model",
                    )
            self.assertIn("HTTP 500 from http://worker.test: broken", str(ctx.exception))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
