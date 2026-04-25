from __future__ import annotations

import logging
from typing import Any

from app.ai_config import get_chunk_max_tokens, get_default_temperature, get_model
from app.openai_sync_client import get_client

logger = logging.getLogger(__name__)


def check_text_chunk(text: str, system_prompt: str, temperature: float | None = None) -> str:
    """Send a text chunk to the AI and return the model response."""
    effective_temp = temperature if temperature is not None else get_default_temperature()
    model = get_model()
    logger.info(
        "check_text_chunk | model=%s | chars=%d | temperature=%s",
        model,
        len(text),
        effective_temp,
    )

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
    }
    chunk_max_tokens = get_chunk_max_tokens()
    if chunk_max_tokens is not None:
        kwargs["max_tokens"] = chunk_max_tokens
    if effective_temp is not None:
        kwargs["temperature"] = effective_temp

    response = get_client().chat.completions.create(**kwargs)
    result = response.choices[0].message.content or ""
    logger.info("check_text_chunk done (%d chars)", len(result))
    return result
