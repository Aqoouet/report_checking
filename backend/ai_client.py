from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AI_CONNECT_TIMEOUT = float(os.getenv("AI_CONNECT_TIMEOUT", "15"))
AI_REF_MAX_TOKENS = int(os.getenv("AI_REF_MAX_TOKENS", "8192"))
AI_AGG_MAX_TOKENS = int(os.getenv("AI_AGG_MAX_TOKENS", "8192"))


def _chunk_max_tokens() -> int | None:
    """None = omit max_tokens (LM Studio / server default)."""
    raw = os.getenv("AI_CHUNK_MAX_TOKENS", "0").strip().lower()
    if raw in ("0", "", "none", "unlimited"):
        return None
    try:
        v = int(raw)
    except ValueError:
        return None
    return v if v > 0 else None


def _read_timeout_seconds() -> float | None:
    """None = no limit on waiting for the model response (read/write)."""
    raw = os.getenv("AI_TIMEOUT", "0").strip().lower()
    if raw in ("0", "", "none", "inf", "infinite", "unlimited"):
        return None
    try:
        sec = float(raw)
    except ValueError:
        return None
    if sec <= 0:
        return None
    return sec


_READ_TIMEOUT = _read_timeout_seconds()


def _http_timeout() -> httpx.Timeout | None:
    if _READ_TIMEOUT is None:
        return None
    return httpx.Timeout(
        connect=AI_CONNECT_TIMEOUT,
        read=_READ_TIMEOUT,
        write=min(_READ_TIMEOUT, 120.0),
        pool=AI_CONNECT_TIMEOUT,
    )

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
            base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1"),
            timeout=_http_timeout(),
            max_retries=0,
        )
    return _client


def _model() -> str:
    return os.getenv("OPENAI_MODEL", "qwen3-coder-30b-a3b-instruct")


def check_text_chunk(text: str, system_prompt: str) -> str:
    """Send a text chunk to the AI with the given system prompt.

    Returns the model's response as a plain string.
    """
    preview = text[:200].replace("\n", " ")
    logger.info("check_text_chunk | model=%s | preview: %s...", _model(), preview)

    create_kwargs: dict[str, Any] = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
    }
    _mt = _chunk_max_tokens()
    if _mt is not None:
        create_kwargs["max_tokens"] = _mt

    response = _get_client().chat.completions.create(**create_kwargs)
    result = response.choices[0].message.content or ""
    logger.info("check_text_chunk done (%d chars)", len(result))
    return result


def check_references(payload: dict[str, Any], system_prompt: str) -> list[dict]:
    """Send the cross-reference payload to the AI and parse the JSON response.

    Returns a list of dicts with keys ``caption`` and ``error``.
    """
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    logger.info("check_references | entries=%d", len(payload))

    response = _get_client().chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload_json},
        ],
        max_tokens=AI_REF_MAX_TOKENS,
    )
    raw = (response.choices[0].message.content or "").strip()
    logger.info("check_references done (%d chars)", len(raw))

    # Strip markdown code fences if the model wrapped the JSON.
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        logger.warning("check_references: could not parse JSON response; raw=%s", raw[:500])

    return []


def aggregate_errors(errors_text: str, system_prompt: str) -> str:
    """Send all collected errors to the AI for final aggregation.

    Returns the structured report as a plain string.
    """
    logger.info("aggregate_errors | input length=%d chars", len(errors_text))

    response = _get_client().chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": errors_text},
        ],
        max_tokens=AI_AGG_MAX_TOKENS,
    )
    result = response.choices[0].message.content or ""
    logger.info("aggregate_errors done (%d chars)", len(result))
    return result
