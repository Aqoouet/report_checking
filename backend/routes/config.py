from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

import ai_client
import config_store
from utils import get_session_id
from validators import validate_file_path, validate_output_dir

router = APIRouter()


@router.post("/config")
async def set_config(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный JSON")

    raw_docx = (data.get("input_docx_path") or "").strip()
    raw_output = (data.get("output_dir") or "").strip()

    if not raw_docx:
        raise HTTPException(status_code=400, detail="input_docx_path обязателен")
    if not raw_output:
        raise HTTPException(status_code=400, detail="output_dir обязателен")

    resolved_docx = str(validate_file_path(raw_docx))
    resolved_output = str(validate_output_dir(raw_output))

    session_id = get_session_id(request)
    errors = config_store.validate_and_set(
        data,
        resolved_docx,
        resolved_output,
        validate_range_with_ai=ai_client.validate_range,
        session_id=session_id,
    )
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    return {"ok": True}


@router.get("/config")
async def get_config(request: Request):
    session_id = get_session_id(request)
    cfg = config_store.to_dict(session_id)
    if cfg is None:
        return {}
    return cfg
