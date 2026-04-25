from __future__ import annotations

import os

import httpx


def _read_float(name: str, default: str) -> float | None:
    raw = os.getenv(name, default).strip().lower()
    if raw in ("0", "", "none", "inf", "infinite", "unlimited"):
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def get_connect_timeout() -> float:
    try:
        return float(os.getenv("AI_CONNECT_TIMEOUT", "15"))
    except ValueError:
        return 15.0


def get_read_timeout() -> float | None:
    """None means no limit while waiting for the model response."""
    return _read_float("AI_TIMEOUT", "0")


def get_http_timeout() -> httpx.Timeout | None:
    read_timeout = get_read_timeout()
    if read_timeout is None:
        return None
    connect_timeout = get_connect_timeout()
    return httpx.Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=min(read_timeout, 120.0),
        pool=connect_timeout,
    )


def get_chunk_max_tokens() -> int | None:
    raw = os.getenv("AI_CHUNK_MAX_TOKENS", "0").strip().lower()
    if raw in ("0", "", "none", "unlimited"):
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def get_default_temperature() -> float | None:
    raw = os.getenv("AI_TEMPERATURE", "").strip().lower()
    if not raw or raw in ("none", "auto"):
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if 0.0 <= value <= 2.0 else None


def get_model() -> str:
    return os.getenv("OPENAI_MODEL", "qwen3-coder-30b-a3b-instruct")


def get_validate_model() -> str:
    raw = os.getenv("OPENAI_VALIDATE_MODEL", "").strip()
    return raw if raw else get_model()
