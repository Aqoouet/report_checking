from __future__ import annotations

import json
import logging
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.ai_config import get_validate_model
from app.openai_sync_client import get_range_client, openai_error_payload

logger = logging.getLogger(__name__)

_VALIDATE_RANGE_PROMPT = """/no_think
Ты помощник по разбору диапазона разделов технического документа (.docx).

ЗАДАЧА: распознай намерение пользователя, даже при опечатках. Возвращай valid=false только
если намерение абсолютно непонятно.

ПРАВИЛА:
- Любой ввод без явного слова «страниц/стр» — разделы.
- Опечатки в слове «раздел» (например: «раздул», «разделл», «раздле») интерпретируй как «раздел».
- Если во вводе только латинские буквы, считай это ошибкой раскладки и попробуй переключить раскладку клавиатуры (латиница -> кириллица) перед разбором.
- Номера разделов — только цифры и точки: «5», «5.1», «5.2.3».
- Десятичная запятая → точка: «5,1» → раздел 5.1.
- Диапазон через дефис/тире: «3.1-3.4» → start="3.1", end="3.4".
- Список: «3.1, 3.3» → два элемента [{start:"3.1",end:"3.1"},{start:"3.3",end:"3.3"}].
- Когда valid=true: suggestion="" (пусто).
- Когда valid=false: suggestion — конкретный исправленный вариант.

Верни строго JSON.
"""

_RANGE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "valid": {"type": "boolean"},
        "type": {"type": "string", "enum": ["sections"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                },
                "required": ["start", "end"],
            },
        },
        "display": {"type": "string"},
        "suggestion": {"type": "string"},
    },
    "required": ["valid", "type", "items", "display", "suggestion"],
}

_STRICT_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "range_validation",
        "strict": True,
        "schema": _RANGE_RESPONSE_SCHEMA,
    },
}

_JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}
_SENSITIVE = ("api_key", "token", "secret", "password", "bearer")


def _range_error(*, server_error: bool = True, range_message: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {
        "valid": False,
        "type": "sections",
        "items": [],
        "display": "",
        "suggestion": "",
        "server_error": server_error,
    }
    if range_message:
        result["range_message"] = range_message
    return result


def _is_response_format_unsupported(exc: APIStatusError) -> bool:
    if getattr(exc, "status_code", None) != 400:
        return False
    err = openai_error_payload(exc)
    message = str(err.get("message", "")).lower()
    code = str(err.get("code", "")).lower()
    return (
        "response_format" in message
        or "json_schema" in message
        or "json_object" in message
        or "response_format" in code
    )


def _is_model_not_found(exc: APIStatusError) -> bool:
    if getattr(exc, "status_code", None) != 400:
        return False
    return openai_error_payload(exc).get("code") == "model_not_found"


def _model_not_found_error(exc: APIStatusError) -> dict[str, Any]:
    err = openai_error_payload(exc)
    raw_msg = (err.get("message") or "").strip()[:100]
    msg = raw_msg if not any(key in raw_msg.lower() for key in _SENSITIVE) else ""
    return _range_error(
        range_message=(
            "Invalid model identifier (OPENAI_VALIDATE_MODEL). "
            "Use the exact model name from LM Studio or leave the field empty."
            + (f" Server response: {msg}" if msg else "")
        ),
    )


def validate_range_response(payload: object) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("valid"), bool):
        return None
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    normalized_items: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            return None
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, str) or not isinstance(end, str):
            return None
        normalized_items.append({"start": start, "end": end})

    result: dict[str, Any] = {
        "valid": payload["valid"],
        "type": "sections",
        "items": normalized_items,
        "display": payload.get("display")
        if isinstance(payload.get("display"), str)
        else "",
        "suggestion": payload.get("suggestion")
        if isinstance(payload.get("suggestion"), str)
        else "",
    }
    return result


def _parse_direct_json(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return validate_range_response(parsed)


def _create_completion(text: str, response_format: dict[str, Any] | None) -> Any:
    kwargs: dict[str, Any] = {
        "model": get_validate_model(),
        "messages": [
            {"role": "system", "content": _VALIDATE_RANGE_PROMPT},
            {"role": "user", "content": f"Ввод: {text}"},
        ],
        "temperature": 0,
        "max_tokens": 400,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    return get_range_client().chat.completions.create(**kwargs)


_FORMAT_UNSET = object()
_cached_format: Any = _FORMAT_UNSET


def _completion_with_fallback(text: str) -> Any:
    global _cached_format
    if _cached_format is not _FORMAT_UNSET:
        return _create_completion(text, _cached_format)

    formats: tuple[dict[str, Any] | None, ...] = (
        _STRICT_RESPONSE_FORMAT,
        _JSON_OBJECT_RESPONSE_FORMAT,
        None,
    )
    last_unsupported: APIStatusError | None = None
    for response_format in formats:
        try:
            result = _create_completion(text, response_format)
            _cached_format = response_format
            return result
        except APIStatusError as exc:
            if _is_response_format_unsupported(exc) and response_format is not None:
                last_unsupported = exc
                continue
            raise
    if last_unsupported is not None:
        raise last_unsupported
    raise RuntimeError("range validation completion failed before request")


def validate_range(text: str) -> dict[str, Any]:
    """Parse a free-form section range string via AI. Returns a structured dict."""
    logger.info("validate_range | model=%s | text=%s", get_validate_model(), text[:100])

    try:
        response = _completion_with_fallback(text)
    except (APIConnectionError, APITimeoutError) as exc:
        logger.warning("validate_range transport error: %s", exc)
        return _range_error()
    except APIStatusError as exc:
        logger.warning("validate_range API status error: %s", exc)
        if _is_model_not_found(exc):
            return _model_not_found_error(exc)
        if getattr(exc, "status_code", None) == 400:
            return _range_error(server_error=False)
        return _range_error()
    except Exception as exc:
        logger.warning("validate_range unexpected error: %s", exc, exc_info=True)
        return _range_error()

    raw = (response.choices[0].message.content or "").strip()
    logger.info("validate_range done: %s", raw[:200])

    result = _parse_direct_json(raw)
    if result is not None:
        return result

    logger.warning("validate_range: model output is not valid range JSON")
    return _range_error(server_error=False)
