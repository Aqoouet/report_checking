from __future__ import annotations

import os
import sys

import httpx
from fastapi import APIRouter, HTTPException

import config_store
from context_resolver import resolve_context_tokens
from settings import (
    DEFAULT_CHECK_PROMPT_PATH,
    DEFAULT_SUMMARY_PROMPT_PATH,
    DEFAULT_VALIDATION_PROMPT_PATH,
)
from utils import read_prompt_file

router = APIRouter()


@router.get("/runtime_info")
async def runtime_info():
    base = os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1").rstrip("/")
    model_id = os.getenv("OPENAI_MODEL", "").strip()
    context_tokens: int | None = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            context_tokens = await resolve_context_tokens(client, base, model_id)
    except Exception:
        pass
    try:
        chunk = int(os.getenv("DOC_CHUNK_SIZE", "10000"))
    except ValueError:
        chunk = 10000
    return {
        "check_model": model_id or "—",
        "context_tokens": context_tokens,
        "doc_chunk_tokens": chunk,
        "max_chunk_tokens": config_store._max_chunk_tokens(),
        "os": sys.platform,
    }


@router.get("/default_check_prompt")
async def default_check_prompt():
    if not DEFAULT_CHECK_PROMPT_PATH.is_file():
        raise HTTPException(status_code=500, detail="Файл промпта по умолчанию не найден")
    return {"prompt": DEFAULT_CHECK_PROMPT_PATH.read_text(encoding="utf-8")}


@router.get("/default_prompts")
async def default_prompts():
    return {
        "check_prompt": read_prompt_file(DEFAULT_CHECK_PROMPT_PATH),
        "validation_prompt": read_prompt_file(DEFAULT_VALIDATION_PROMPT_PATH),
        "summary_prompt": read_prompt_file(DEFAULT_SUMMARY_PROMPT_PATH),
    }
