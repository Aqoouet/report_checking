from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_CONTEXT_FIELD_KEYS = (
    "max_context_length",
    "context_length",
    "context_window",
    "max_model_len",
    "n_ctx",
)


def _openai_base_to_lm_root(openai_base: str) -> str:
    base = openai_base.rstrip("/")
    if base.lower().endswith("/v1"):
        return base[:-3] or base
    return base


def _context_from_model_entry(entry: dict) -> int | None:
    for key in _CONTEXT_FIELD_KEYS:
        v = entry.get(key)
        if isinstance(v, int) and v > 0:
            return v
    return None


def _model_id_matches_listing(eid: str, configured: str) -> bool:
    if not configured:
        return False
    return eid == configured or configured in eid or eid in configured


async def resolve_context_tokens(
    client: httpx.AsyncClient,
    openai_base: str,
    model_id: str,
) -> int | None:
    if not model_id.strip():
        return None
    openai_base = openai_base.rstrip("/")
    root = _openai_base_to_lm_root(openai_base)

    def _from_entries(entries: list) -> int | None:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            eid = str(entry.get("id") or entry.get("model") or "")
            if not _model_id_matches_listing(eid, model_id):
                continue
            ctx = _context_from_model_entry(entry)
            if ctx is not None:
                return ctx
        return None

    try:
        r = await client.get(f"{root}/api/v0/models")
        if r.status_code == 200:
            payload = r.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list):
                found = _from_entries(data)
                if found is not None:
                    return found
    except Exception as exc:
        logger.debug("resolve_context_tokens /api/v0/models list failed: %s", exc)

    try:
        r = await client.get(f"{root}/api/v0/models/{quote(model_id, safe='')}")
        if r.status_code == 200:
            payload = r.json()
            if isinstance(payload, dict):
                ctx = _context_from_model_entry(payload)
                if ctx is not None:
                    return ctx
    except Exception as exc:
        logger.debug("resolve_context_tokens /api/v0/models/<id> failed: %s", exc)

    try:
        r = await client.get(f"{openai_base}/models")
        if r.status_code == 200:
            payload = r.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list):
                return _from_entries(data)
    except Exception as exc:
        logger.debug("resolve_context_tokens /v1/models failed: %s", exc)

    return None
