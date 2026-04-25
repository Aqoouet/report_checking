from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException

from range_ai_validator import validate_range as validate_range_with_ai
from range_parser import parse_range_script
from settings import MAX_RANGE_SPEC_LEN
from validators import validate_file_path

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/validate_path")
async def validate_path_endpoint(file_path: str = Form(...)):
    raw = (file_path or "").strip()
    if not raw:
        return {"valid": False, "message": "Укажите путь к файлу", "mapped_path": ""}
    try:
        resolved = validate_file_path(raw)
        return {"valid": True, "message": "Файл доступен", "mapped_path": str(resolved)}
    except HTTPException as exc:
        return {"valid": False, "message": exc.detail, "mapped_path": ""}


@router.post("/validate_range_quick")
async def validate_range_quick(range_text: str = Form(...)):
    return parse_range_script(range_text.strip())


@router.post("/validate_range")
async def validate_range(range_text: str = Form(...)):
    if not range_text.strip():
        return {"valid": True, "type": "sections", "items": [], "display": "", "suggestion": ""}
    if len(range_text) > MAX_RANGE_SPEC_LEN:
        return {"valid": False, "range_message": "Текст диапазона слишком длинный", "server_error": False}
    result = validate_range_with_ai(range_text.strip())
    if not result.get("valid") and result.get("server_error"):
        logger.warning("AI range validation failed: %s", result.get("range_message", "unknown error"))
    return result
