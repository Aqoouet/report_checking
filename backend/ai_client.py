import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# How long to wait for the model to respond to a single page (seconds).
# Large local models can take several minutes per page.
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "600"))

_client: OpenAI | None = None


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
    system_prompt = os.getenv(
        "SYSTEM_PROMPT",
        "Ты эксперт по проверке отчётов. Проверь следующий фрагмент и дай подробный комментарий.",
    )
    model = os.getenv("OPENAI_MODEL", "qwen3-coder-30b-a3b-instruct")

    preview = page_text[:200].replace("\n", " ")
    logger.info(
        "Checking page %d (model=%s, timeout=%ds) | text preview: %s...",
        page_label, model, AI_TIMEOUT, preview,
    )

    response = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": page_text},
        ],
        # thinking disabled by default on qwen3.5-2b
    )
    result = response.choices[0].message.content or ""
    logger.info("Page %d done (%d chars)", page_label, len(result))
    return result
