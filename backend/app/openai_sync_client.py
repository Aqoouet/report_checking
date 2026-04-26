from __future__ import annotations

import json
import os
from threading import Lock
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

from app.ai_config import get_connect_timeout, get_http_timeout, get_range_read_timeout

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


_range_client: OpenAI | None = None
_range_client_lock = Lock()


def get_range_client() -> OpenAI:
    """Dedicated client for range validation: no retries, hard 30 s timeout.

    Uses OPENAI_VALIDATE_BASE_URL when set (e.g. a lightweight model on port 1235),
    falling back to OPENAI_BASE_URL so existing deployments keep working.
    """
    global _range_client
    with _range_client_lock:
        if _range_client is None:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY not set. Set it to 'lm-studio' for local LM Studio "
                    "or your OpenAI API key for remote endpoints."
                )
            connect = get_connect_timeout()
            read = get_range_read_timeout()
            base_url = (
                os.getenv("OPENAI_VALIDATE_BASE_URL", "").strip()
                or os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
            )
            _range_client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=httpx.Timeout(connect=connect, read=read, write=read, pool=connect),
                max_retries=0,
            )
    return _range_client


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
