import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# How long to wait for the model to respond to a single page (seconds).
# Large local models can take several minutes per page.
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "600"))

_FALLBACK_SYSTEM_PROMPT = (
    "Ты эксперт по проверке отчётов. Проверь следующий фрагмент и дай подробный комментарий."
)

_client: OpenAI | None = None

_CONTEXT_OVERFLOW_COMMENT = (
    "Автоматическая проверка не выполнена: текст этой страницы вместе с системным "
    "промптом не помещается в контекст модели (слишком большой n_ctx / мало места под "
    "вход). Увеличьте Context Length при загрузке модели в LM Studio, сократите "
    "системный промпт или уменьшите объём текста на странице."
)


def _error_text_for_match(exc: APIStatusError) -> str:
    parts: list[str] = [str(exc)]
    msg = getattr(exc, "message", None)
    if msg:
        parts.append(str(msg))
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            parts.append(str(err["message"]))
        else:
            parts.append(str(body))
    elif body is not None:
        parts.append(str(body))
    return " ".join(parts).lower()


def _is_context_window_error(exc: APIStatusError) -> bool:
    if exc.status_code != 400:
        return False
    text = _error_text_for_match(exc)
    markers = (
        "n_ctx",
        "context length",
        "n_keep",
        "tokens to keep",
        "initial prompt",
        "context window",
        "maximum context",
        "exceeds the context",
        "prompt is too long",
    )
    return any(m in text for m in markers)


def _safe_preset(name: str) -> str:
    n = (name or "default").strip().lower()
    if not n:
        return "default"
    if not all(c.isalnum() or c in "_-" for c in n):
        logger.warning("Invalid PROMPT_PRESET %r — using default", name)
        return "default"
    return n


def _read_prompt_file(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.debug("Could not read prompt file %s: %s", path, e)
        return None
    stripped = text.strip()
    return stripped if stripped else None


def _load_system_prompt() -> str:
    """Read system prompt fresh each call so prompt files can be edited without restart."""
    override = os.getenv("SYSTEM_PROMPT_FILE", "").strip()
    if override:
        path = Path(override)
        if not path.is_absolute():
            path = Path.cwd() / path
        loaded = _read_prompt_file(path)
        if loaded:
            return loaded
        logger.warning("SYSTEM_PROMPT_FILE unreadable or empty: %s", path)

    preset = _safe_preset(os.getenv("PROMPT_PRESET", "default"))
    preset_path = Path(__file__).resolve().parent / "prompts" / f"{preset}.txt"
    loaded = _read_prompt_file(preset_path)
    if loaded:
        return loaded
    logger.warning("Preset prompt missing or empty: %s — using env or built-in fallback", preset_path)

    env_prompt = os.getenv("SYSTEM_PROMPT", "").strip()
    if env_prompt:
        return env_prompt
    return _FALLBACK_SYSTEM_PROMPT


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
            base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1"),
            timeout=AI_TIMEOUT,
            max_retries=0,  # don't retry — if it times out, fail fast and report error
        )
    return _client


def check_page(page_text: str, page_label: int) -> str:
    """Send a single page text to the local AI and return the review comment."""
    system_prompt = _load_system_prompt()
    model = os.getenv("OPENAI_MODEL", "qwen3-coder-30b-a3b-instruct")

    preview = page_text[:200].replace("\n", " ")
    pfile = os.getenv("SYSTEM_PROMPT_FILE", "").strip()
    prompt_tag = f"file:{pfile}" if pfile else _safe_preset(os.getenv("PROMPT_PRESET", "default"))
    logger.info(
        "Checking page %d (model=%s, prompt=%s, timeout=%ds) | text preview: %s...",
        page_label,
        model,
        prompt_tag,
        AI_TIMEOUT,
        preview,
    )

    try:
        response = _get_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": page_text},
            ],
        )
    except APIStatusError as e:
        if _is_context_window_error(e):
            logger.warning(
                "Page %d: context window exceeded, annotating with notice instead of failing job: %s",
                page_label,
                e,
            )
            return _CONTEXT_OVERFLOW_COMMENT
        raise

    result = response.choices[0].message.content or ""
    logger.info("Page %d done (%d chars)", page_label, len(result))
    return result
