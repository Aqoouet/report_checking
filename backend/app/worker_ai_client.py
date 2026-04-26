from __future__ import annotations

from typing import Any

import httpx

from app.ai_config import get_model


async def call_worker_chat(
    text: str,
    prompt: str,
    server_url: str,
    model: str = "",
    temperature: float | None = None,
    timeout: float = 1800.0,
) -> str:
    base_url = server_url.rstrip("/")
    effective_model = model or get_model()
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
        response = await client.post(f"{base_url}/v1/chat/completions", json=body)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body_text = response.text[:500].strip()
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code} from {base_url}: {body_text}",
                request=exc.request,
                response=exc.response,
            ) from exc
        return response.json()["choices"][0]["message"]["content"]
