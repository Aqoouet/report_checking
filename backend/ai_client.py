from __future__ import annotations

import json
import logging
import os
from threading import Lock
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

AI_CONNECT_TIMEOUT = float(os.getenv("AI_CONNECT_TIMEOUT", "15"))


def _read_timeout() -> float | None:
    """None = no limit on waiting for the model response."""
    raw = os.getenv("AI_TIMEOUT", "0").strip().lower()
    if raw in ("0", "", "none", "inf", "infinite", "unlimited"):
        return None
    try:
        sec = float(raw)
    except ValueError:
        return None
    return sec if sec > 0 else None


def _chunk_max_tokens() -> int | None:
    raw = os.getenv("AI_CHUNK_MAX_TOKENS", "0").strip().lower()
    if raw in ("0", "", "none", "unlimited"):
        return None
    try:
        v = int(raw)
    except ValueError:
        return None
    return v if v > 0 else None


_READ_TIMEOUT = _read_timeout()
_CHUNK_MAX_TOKENS = _chunk_max_tokens()


def _default_temperature() -> float | None:
    raw = os.getenv("AI_TEMPERATURE", "").strip().lower()
    if not raw or raw in ("none", "auto"):
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    return v if 0.0 <= v <= 2.0 else None


_DEFAULT_TEMPERATURE = _default_temperature()


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
_client_lock = Lock()


def _get_client() -> OpenAI:
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
                timeout=_http_timeout(),
                max_retries=2,
            )
    return _client


def _model() -> str:
    return os.getenv("OPENAI_MODEL", "qwen3-coder-30b-a3b-instruct")


def _validate_model() -> str:
    raw = os.getenv("OPENAI_VALIDATE_MODEL", "").strip()
    return raw if raw else _model()


def _openai_error_payload(exc: APIStatusError) -> dict[str, Any]:
    try:
        body = getattr(exc, "body", None)
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            return body["error"]
        if isinstance(body, str) and body.strip().startswith("{"):
            data = json.loads(body)
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                return data["error"]
        r = getattr(exc, "response", None)
        if r is not None:
            data = r.json()
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                return data["error"]
    except Exception:
        pass
    return {}


def check_text_chunk(text: str, system_prompt: str, temperature: float | None = None) -> str:
    """Send a text chunk to the AI and return the model response."""
    effective_temp = temperature if temperature is not None else _DEFAULT_TEMPERATURE
    logger.info(
        "check_text_chunk | model=%s | chars=%d | temperature=%s",
        _model(), len(text), effective_temp,
    )

    kwargs: dict[str, Any] = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
    }
    if _CHUNK_MAX_TOKENS is not None:
        kwargs["max_tokens"] = _CHUNK_MAX_TOKENS
    if effective_temp is not None:
        kwargs["temperature"] = effective_temp

    response = _get_client().chat.completions.create(**kwargs)
    result = response.choices[0].message.content or ""
    logger.info("check_text_chunk done (%d chars)", len(result))
    return result


# ---------------------------------------------------------------------------
# Range validation
# ---------------------------------------------------------------------------

_VALIDATE_RANGE_PROMPT = """Ты помощник по разбору диапазона разделов технического документа (.docx).

ЗАДАЧА: распознай намерение пользователя, даже при опечатках. Возвращай valid=false только
если намерение абсолютно непонятно.

ПРАВИЛА:
- Любой ввод без явного слова «страниц/стр» — разделы.
- Номера разделов — только цифры и точки: «5», «5.1», «5.2.3».
- Десятичная запятая → точка: «5,1» → раздел 5.1.
- Диапазон через дефис/тире: «3.1-3.4» → start="3.1", end="3.4".
- Список: «3.1, 3.3» → два элемента [{start:"3.1",end:"3.1"},{start:"3.3",end:"3.3"}].
- Когда valid=true: suggestion="" (пусто).
- Когда valid=false: suggestion — конкретный исправленный вариант.

Уложись в 20 токенов.
Верни СТРОГО JSON:
{
  "valid": true|false,
  "type": "sections",
  "items": [{"start": "3.1", "end": "3.4"}],
  "display": "Разделы: 3.1–3.4",
  "suggestion": ""
}
"""


def _parse_json(raw: str) -> dict | None:
    if not raw or not raw.strip():
        return None
    t = raw.strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1]
            if t.lstrip().startswith("json"):
                t = t.lstrip()[4:]
    t = t.strip()
    candidates = [t]
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        candidates.append(t[i: j + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return None


def _range_error(*, server_error: bool = True, range_message: str = "") -> dict:
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


def validate_range(text: str) -> dict:
    """Parse a free-form section range string via AI. Returns a structured dict."""
    logger.info("validate_range | model=%s | text=%s", _validate_model(), text[:100])

    try:
        response = _get_client().chat.completions.create(
            model=_validate_model(),
            messages=[
                {"role": "system", "content": _VALIDATE_RANGE_PROMPT},
                {"role": "user", "content": f"Ввод: {text}"},
            ],
            max_tokens=150,
        )
    except (APIConnectionError, APITimeoutError) as exc:
        logger.warning("validate_range transport error: %s", exc)
        return _range_error()
    except APIStatusError as exc:
        sc = getattr(exc, "status_code", None)
        logger.warning("validate_range API status error: %s", exc)
        if sc == 400:
            err = _openai_error_payload(exc)
            if err.get("code") == "model_not_found":
                raw_msg = (err.get("message") or "").strip()[:100]
                # Redact anything that looks like a key or token
                _SENSITIVE = ("api_key", "token", "secret", "password", "bearer")
                msg = raw_msg if not any(k in raw_msg.lower() for k in _SENSITIVE) else ""
                return _range_error(
                    range_message=(
                        "Неверный идентификатор модели (OPENAI_VALIDATE_MODEL). "
                        "Укажите точное имя модели из LM Studio или оставьте поле пустым."
                        + (f" Ответ сервера: {msg}" if msg else "")
                    ),
                )
            return _range_error(server_error=False)
        return _range_error()
    except Exception as exc:
        logger.warning("validate_range unexpected error: %s", exc)
        return _range_error()

    raw = (response.choices[0].message.content or "").strip()
    logger.info("validate_range done: %s", raw[:200])

    result = _parse_json(raw)
    if result is not None:
        if (
            isinstance(result.get("valid"), bool)
            and isinstance(result.get("items"), list)
            and all(
                isinstance(item, dict)
                and isinstance(item.get("start"), str)
                and isinstance(item.get("end"), str)
                for item in result["items"]
            )
        ):
            return result
        logger.warning("validate_range: AI response failed schema validation: %s", raw[:200])
        return _range_error(server_error=False)

    logger.warning("validate_range: model output is not JSON")
    return _range_error(server_error=False)


async def call_async(
    text: str,
    prompt: str,
    server_url: str,
    model: str = "",
    temperature: float | None = None,
    timeout: float = 300.0,
) -> str:
    effective_model = model or _model()
    body: dict[str, Any] = {
        "model": effective_model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
    }
    if temperature is not None:
        body["temperature"] = temperature
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{server_url}/v1/chat/completions", json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
