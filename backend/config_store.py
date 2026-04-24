from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from range_parser import parse_range_script


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


_configs: dict[str, PipelineConfig] = {}


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


def validate_preflight(
    config: PipelineConfig,
    *,
    validate_file_path: callable,
    validate_range_with_ai: callable,
) -> list[str]:
    errors: list[str] = []

    try:
        validate_file_path(config.input_docx_path)
    except HTTPException as exc:
        errors.append(f"input_docx_path: {exc.detail}")
    except Exception as exc:  # pragma: no cover
        errors.append(f"input_docx_path: {exc}")

    output_path = Path(config.output_dir)
    if not output_path.exists():
        errors.append("output_dir: directory does not exist")
    elif not output_path.is_dir():
        errors.append("output_dir: path is not a directory")
    else:
        try:
            test_file = output_path / ".write_test.tmp"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
        except OSError:
            errors.append("output_dir: directory is not writable")

    if not config.check_prompt:
        errors.append("check_prompt: field is required")

    max_chunk = _max_chunk_tokens()
    if config.chunk_size_tokens <= 0 or config.chunk_size_tokens > max_chunk:
        errors.append(f"chunk_size_tokens: must be between 1 and {max_chunk}")

    if config.temperature is not None and not (0.0 <= config.temperature <= 2.0):
        errors.append("temperature: must be between 0.0 and 2.0")

    if config.subchapters_range:
        quick = parse_range_script(config.subchapters_range)
        if not quick.get("valid"):
            ai = validate_range_with_ai(config.subchapters_range)
            if not ai.get("valid"):
                errors.append("subchapters_range: invalid range format")

    return errors


def save_config(config: PipelineConfig, session_id: str = "default") -> None:
    _configs[session_id] = config


def get_config(session_id: str = "default") -> PipelineConfig | None:
    return _configs.get(session_id)


def config_to_dict(config: PipelineConfig) -> dict[str, Any]:
    return asdict(config)


def to_dict(session_id: str = "default") -> dict[str, Any] | None:
    cfg = get_config(session_id)
    if cfg is None:
        return None
    return config_to_dict(cfg)


def _max_chunk_tokens() -> int:
    try:
        return int(os.getenv("MAX_CHUNK_TOKENS", "3000"))
    except ValueError:
        return 3000


def validate_and_set(
    data: dict[str, Any],
    resolved_docx: str,
    resolved_output: str,
    *,
    validate_range_with_ai: callable | None = None,
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

    max_chunk = _max_chunk_tokens()
    errors: list[str] = []
    if not config.check_prompt:
        errors.append("check_prompt: поле обязательно")
    if config.chunk_size_tokens <= 0 or config.chunk_size_tokens > max_chunk:
        errors.append(f"chunk_size_tokens: должно быть от 1 до {max_chunk}")
    if config.temperature is not None and not (0.0 <= config.temperature <= 2.0):
        errors.append("temperature: должно быть от 0.0 до 2.0")
    if config.subchapters_range:
        quick = parse_range_script(config.subchapters_range)
        if not quick.get("valid"):
            if validate_range_with_ai is not None:
                ai = validate_range_with_ai(config.subchapters_range)
                if not ai.get("valid"):
                    errors.append("subchapters_range: неверный формат диапазона")
            else:
                errors.append("subchapters_range: неверный формат диапазона")

    if not errors:
        save_config(config, session_id)
    return errors
