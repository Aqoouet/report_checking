from __future__ import annotations

import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from app.range_parser import parse_range_script


@dataclass
class PipelineConfig:
    input_docx_path: str
    output_dir: str
    check_prompt: str
    validation_prompt: str = ""
    summary_prompt: str = ""
    subchapters_range: str = ""
    chunk_size_tokens: int = 10000
    temperature: float | None = None
    model: str = ""


@dataclass
class _Entry:
    config: PipelineConfig
    expires_at: float


_store: dict[str, _Entry] = {}
_lock = threading.RLock()


def _config_ttl() -> int:
    try:
        return int(os.getenv("CONFIG_TTL_SECONDS", "3600"))
    except ValueError:
        return 3600


def _max_entries() -> int:
    try:
        return int(os.getenv("CONFIG_MAX_ENTRIES", "100"))
    except ValueError:
        return 100


def _evict() -> None:
    now = time.monotonic()
    for k in [k for k, v in _store.items() if now > v.expires_at]:
        del _store[k]
    max_e = _max_entries()
    while len(_store) >= max_e:
        del _store[min(_store, key=lambda k: _store[k].expires_at)]


def parse_config_payload(payload: dict[str, Any]) -> PipelineConfig:
    try:
        return PipelineConfig(
            input_docx_path=str(payload["input_docx_path"]).strip(),
            output_dir=str(payload["output_dir"]).strip(),
            check_prompt=str(payload["check_prompt"]).strip(),
            validation_prompt=str(payload.get("validation_prompt", "")).strip(),
            summary_prompt=str(payload.get("summary_prompt", "")).strip(),
            subchapters_range=str(payload.get("subchapters_range", "")).strip(),
            chunk_size_tokens=int(payload.get("chunk_size_tokens", 10000)),
            temperature=(
                float(payload["temperature"])
                if payload.get("temperature") not in (None, "", "null")
                else None
            ),
            model=str(payload.get("model", "")).strip(),
        )
    except KeyError as exc:
        raise ValueError(f"Missing required field: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid config value: {exc}") from exc


def _validate_fields(
    config: PipelineConfig,
    *,
    validate_range_with_ai: Callable | None,
) -> list[str]:
    errors: list[str] = []

    if not config.check_prompt:
        errors.append("check_prompt: field is required")

    max_chunk = max_chunk_tokens()
    if config.chunk_size_tokens <= 0 or config.chunk_size_tokens > max_chunk:
        errors.append(f"chunk_size_tokens: must be between 1 and {max_chunk}")

    if config.temperature is not None and not (0.0 <= config.temperature <= 2.0):
        errors.append("temperature: must be between 0.0 and 2.0")

    if config.subchapters_range:
        quick = parse_range_script(config.subchapters_range)
        if not quick.get("valid"):
            if validate_range_with_ai is not None:
                ai = validate_range_with_ai(config.subchapters_range)
                if not ai.get("valid"):
                    errors.append("subchapters_range: invalid range format")
            else:
                errors.append("subchapters_range: invalid range format")

    return errors



def save_config(config: PipelineConfig, session_id: str = "default") -> None:
    with _lock:
        _evict()
        _store[session_id] = _Entry(config, time.monotonic() + _config_ttl())


def get_config(session_id: str = "default") -> PipelineConfig | None:
    with _lock:
        entry = _store.get(session_id)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del _store[session_id]
            return None
        return entry.config


def config_to_dict(config: PipelineConfig) -> dict[str, Any]:
    return asdict(config)


def to_dict(session_id: str = "default") -> dict[str, Any] | None:
    cfg = get_config(session_id)
    if cfg is None:
        return None
    return config_to_dict(cfg)


def max_chunk_tokens() -> int:
    try:
        return int(os.getenv("MAX_CHUNK_TOKENS", "3000"))
    except ValueError:
        return 3000


def validate_and_set(
    data: dict[str, Any],
    resolved_docx: str,
    resolved_output: str,
    *,
    validate_range_with_ai: Callable | None = None,
    session_id: str = "default",
) -> list[str]:
    patched = dict(data)
    patched["input_docx_path"] = resolved_docx
    patched["output_dir"] = resolved_output
    if not patched.get("model"):
        patched["model"] = os.getenv("OPENAI_MODEL", "").strip()
    try:
        config = parse_config_payload(patched)
    except ValueError as exc:
        return [str(exc)]

    errors = _validate_fields(config, validate_range_with_ai=validate_range_with_ai)
    if not errors:
        save_config(config, session_id)
    return errors
