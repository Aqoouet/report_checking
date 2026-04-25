from __future__ import annotations

import json
import os
from threading import Lock
from typing import Any

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

from ai_config import get_http_timeout

load_dotenv()

_client: OpenAI | None = None
_client_lock = Lock()


def get_client() -> OpenAI:
    global _client
    with _client_lock:
        if _client is None:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY not set. Set it to 'lm-studio' for local LM Studio "
                    "or your OpenAI API key for remote endpoints."
                )
            _client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1"),
                timeout=get_http_timeout(),
                max_retries=2,
            )
    return _client


def openai_error_payload(exc: APIStatusError) -> dict[str, Any]:
    try:
        body = getattr(exc, "body", None)
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            return body["error"]
        if isinstance(body, str) and body.strip().startswith("{"):
            data = json.loads(body)
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                return data["error"]
        response = getattr(exc, "response", None)
        if response is not None:
            data = response.json()
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                return data["error"]
    except Exception:
        return {}
    return {}
