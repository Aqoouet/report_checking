from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app import config_store
from app.error_codes import (
    ERR_CONFIG_VALIDATION_FAILED,
    ERR_INPUT_DOCX_REQUIRED,
    ERR_INVALID_JSON,
    ERR_OUTPUT_DIR_REQUIRED,
    api_error,
)
from app.range_ai_validator import validate_range
from app.utils import get_session_id
from app.validators import validate_file_path, validate_output_dir

router = APIRouter()


@router.post("/config")
async def set_config(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise api_error(ERR_INVALID_JSON)
    if not isinstance(data, dict):
        raise api_error(ERR_INVALID_JSON)
    payload: dict[str, Any] = data

    raw_docx = (payload.get("input_docx_path") or "").strip()
    raw_output = (payload.get("output_dir") or "").strip()

    if not raw_docx:
        raise api_error(ERR_INPUT_DOCX_REQUIRED)
    if not raw_output:
        raise api_error(ERR_OUTPUT_DIR_REQUIRED)

    resolved_docx = str(validate_file_path(raw_docx))
    resolved_output = str(validate_output_dir(raw_output))

    session_id = get_session_id(request)
    errors = config_store.validate_and_set(
        payload,
        resolved_docx,
        resolved_output,
        original_yaml=str(payload.get("_original_yaml", "") or ""),
        validate_range_with_ai=validate_range,
        session_id=session_id,
    )
    if errors:
        raise api_error(ERR_CONFIG_VALIDATION_FAILED, message="; ".join(errors))

    return {"ok": True}


@router.get("/config")
async def get_config(request: Request):
    session_id = get_session_id(request)
    cfg = config_store.to_dict(session_id)
    if cfg is None:
        return {}
    return cfg
