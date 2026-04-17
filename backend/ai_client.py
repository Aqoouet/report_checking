from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AI_CONNECT_TIMEOUT = float(os.getenv("AI_CONNECT_TIMEOUT", "15"))


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


def _compute_chunk_max_tokens() -> int | None:
    """None = omit max_tokens (LM Studio / server default)."""
    raw = os.getenv("AI_CHUNK_MAX_TOKENS", "0").strip().lower()
    if raw in ("0", "", "none", "unlimited"):
        return None
    try:
        v = int(raw)
    except ValueError:
        return None
    return v if v > 0 else None


_CHUNK_MAX_TOKENS: int | None = _compute_chunk_max_tokens()


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


def _validate_model() -> str:
    """Model id for range validation. If OPENAI_VALIDATE_MODEL is empty, uses OPENAI_MODEL."""
    raw = os.getenv("OPENAI_VALIDATE_MODEL", "").strip()
    if raw:
        return raw
    return _model()


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


_COMMON_PREAMBLE = (
    "ОБЩЕЕ ПРАВИЛО (применяется ко всем проверкам):\n"
    "Конструкции «Рисунок Рисунок X.Y‑N» и «Таблица Таблица X.Y‑N» — это НЕ ошибка и НЕ тавтология. "
    "Это артефакт скрытых полей Word: часть текста скрыта в реальном документе, "
    "поэтому слово «Рисунок»/«Таблица» может казаться продублированным. "
    "Никогда не отмечай это как ошибку.\n\n"
)


def check_text_chunk(text: str, system_prompt: str) -> str:
    """Send a text chunk to the AI with the given system prompt.

    Returns the model's response as a plain string.
    """
    preview = text[:200].replace("\n", " ")
    logger.info("check_text_chunk | model=%s | preview: %s...", _model(), preview)

    full_prompt = _COMMON_PREAMBLE + system_prompt

    create_kwargs: dict[str, Any] = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": text},
        ],
    }
    if _CHUNK_MAX_TOKENS is not None:
        create_kwargs["max_tokens"] = _CHUNK_MAX_TOKENS

    response = _get_client().chat.completions.create(**create_kwargs)
    result = response.choices[0].message.content or ""
    logger.info("check_text_chunk done (%d chars)", len(result))
    return result


_VALIDATE_RANGE_PROMPT = """Ты помощник по разбору пользовательского ввода диапазона проверки документа.

КОНТЕКСТ: пользователь вводит диапазон разделов (.docx) или страниц (.pdf) в произвольной форме.
Тебе передаётся тип файла и строка ввода.

ЗАДАЧА: ВСЕГДА пытайся распознать намерение, даже при опечатках и нестандартных форматах.
Делай valid=false ТОЛЬКО если понять намерение абсолютно невозможно.

ПРАВИЛА ИНТЕРПРЕТАЦИИ:
- Если тип файла .docx и нет явных слов «страниц»/«стр» — считай, что имеются в виду разделы.
- Если тип файла .pdf и нет явных слов «раздел»/«разд» — считай, что имеются в виду страницы.
- Числа без ключевых слов интерпретируй по типу файла (docx → разделы, pdf → страницы).
- «5.1» в .docx → раздел 5.1. «5» в .pdf → страница 5.
- Диапазон «3-5», «3–5», «от 3 до 5», «3 по 5» → start="3", end="5".
- Список «1, 3, 5» → три отдельных диапазона: [{start:"1",end:"1"},{start:"3",end:"3"},{start:"5",end:"5"}].
- Смешанные записи: «3.1 3.3-3.5» → [{start:"3.1",end:"3.1"},{start:"3.3",end:"3.5"}].
- Игнорируй лишние пробелы, опечатки в ключевых словах («раздлел», «стрнаица» и т.п.).

НОМЕРА РАЗДЕЛОВ — только цифры и ТОЧКИ: «5», «5.1», «5.2.3».

ДЕСЯТИЧНАЯ ЗАПЯТАЯ (русская традиция): если запятая стоит между двумя числами И результат
выглядит как номер подраздела (например «5,1», «3,2», «10,4»), трактуй как точку:
  «5,1» → раздел 5.1: [{start:"5.1",end:"5.1"}]
  «3,2» → раздел 3.2: [{start:"3.2",end:"3.2"}]

ЗАПЯТАЯ КАК РАЗДЕЛИТЕЛЬ СПИСКА — только когда хотя бы один операнд сам содержит точку
или явно введено несколько независимых разделов с пробелами:
  «5.1,5.3» = раздел 5.1 И раздел 5.3: [{start:"5.1",end:"5.1"},{start:"5.3",end:"5.3"}]
  «раздел 1, раздел 5» = раздел 1 И раздел 5

ДИАПАЗОН — только через дефис или тире:
  «5.1-5.3» или «5.1–5.3» = диапазон от 5.1 до 5.3 → [{start:"5.1",end:"5.3"}]

ПОЛЕ suggestion:
- Когда valid=true: suggestion="" (пусто).
- Когда valid=false: suggestion должен содержать КОНКРЕТНУЮ исправленную строку в стандартном формате,
  максимально близкую к тому, что ввёл пользователь.
  Примеры: ввод "5.1" для .docx при ошибке → suggestion="раздел 5.1"
           ввод "стр 5" при ошибке → suggestion="страница 5"
           ввод "3 по 5" → suggestion="разделы 3–5"
           ввод "abc xyz" → suggestion="Не удалось распознать. Пример: раздел 3.1 или страница 5"

Стремись уложиться в 20 токенов.
Верни СТРОГО JSON без пояснений вокруг:
{
  "valid": true|false,
  "type": "sections"|"pages",
  "items": [{"start": "3.1", "end": "3.4"}, {"start": "5", "end": "5"}],
  "display": "Разделы: 3.1–3.4, 5",
  "suggestion": ""
}
"""


def _parse_validate_range_json(raw: str) -> dict | None:
    """Parse model output into a single JSON object, or None if not possible."""
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
    candidates: list[str] = [t]
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        candidates.append(t[i : j + 1])
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _range_error(*, server_error: bool = True, range_message: str = "") -> dict:
    """Return a standard error response for validate_range."""
    result: dict[str, Any] = {
        "valid": False,
        "type": "",
        "items": [],
        "display": "",
        "suggestion": "",
        "server_error": server_error,
    }
    if range_message:
        result["range_message"] = range_message
    return result


def validate_range(text: str, file_type: str) -> dict:
    """Ask the AI to parse and normalise a free-form range string.

    Returns a dict with keys: valid, type, items, display, suggestion.
    - On API/transport failure: valid=False, suggestion="", server_error=True.
    - When the model replied but output is not a JSON object: valid=False,
      suggestion="", server_error=False (UI: check format).
    """
    user_content = f"Тип файла: {file_type}\nВвод пользователя: {text}"
    logger.info("validate_range | model=%s | file_type=%s | text=%s", _validate_model(), file_type, text[:100])

    try:
        response = _get_client().chat.completions.create(
            model=_validate_model(),
            messages=[
                {"role": "system", "content": _VALIDATE_RANGE_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=150,
        )
    except (APIConnectionError, APITimeoutError) as exc:
        logger.warning("validate_range API transport error: %s", exc)
        return _range_error()
    except APIStatusError as exc:
        sc = getattr(exc, "status_code", None)
        logger.warning("validate_range API status error: %s", exc)
        # 400: distinguish wrong model id (OPENAI_VALIDATE_MODEL) from bad range / params.
        if sc == 400:
            err = _openai_error_payload(exc)
            if err.get("code") == "model_not_found":
                msg = (err.get("message") or "").strip()
                if len(msg) > 500:
                    msg = msg[:500] + "…"
                logger.warning("validate_range: HTTP 400 model_not_found — check OPENAI_VALIDATE_MODEL / OPENAI_MODEL")
                return _range_error(
                    range_message=(
                        "Неверный идентификатор модели для валидации диапазона (OPENAI_VALIDATE_MODEL). "
                        "Укажите в .env точное имя модели из LM Studio или оставьте OPENAI_VALIDATE_MODEL пустым — "
                        "будет использована OPENAI_MODEL. "
                        f"Ответ сервера: {msg}"
                    ),
                )
            logger.warning("validate_range: HTTP 400 from API — using format fallback (not server_error)")
            return _range_error(server_error=False)
        return _range_error()
    except Exception as exc:
        logger.warning("validate_range unexpected API error: %s", exc)
        return _range_error()

    raw = (response.choices[0].message.content or "").strip()
    logger.info("validate_range done: %s", raw[:300])

    result = _parse_validate_range_json(raw)

    if result is not None:
        return result

    logger.warning("validate_range: model output not a JSON object (format fallback)")
    return _range_error(server_error=False)


