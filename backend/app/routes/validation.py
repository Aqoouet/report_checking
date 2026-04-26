from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException

from app.error_codes import (
    ERR_ACCESS_DENIED,
    ERR_INPUT_DOCX_REQUIRED,
    ERR_OUTPUT_DIR_REQUIRED,
    error_detail,
    error_detail_from_http_exception,
)
from app.range_ai_validator import validate_range as validate_range_with_ai
from app.range_parser import parse_range_script
from app.settings import MAX_RANGE_SPEC_LEN
from app.validators import validate_file_path, validate_output_dir

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/validate_path")
async def validate_path_endpoint(file_path: str | None = Form(None)):
    raw = (file_path or "").strip()
    if not raw:
        detail = error_detail(ERR_INPUT_DOCX_REQUIRED, message="File path is required.")
        return {
            "valid": False,
            **detail,
            "mapped_path": "",
        }
    try:
        resolved = validate_file_path(raw)
        return {"valid": True, "message": "File is accessible.", "mapped_path": str(resolved)}
    except HTTPException as exc:
        detail = error_detail_from_http_exception(
            exc,
            fallback=ERR_ACCESS_DENIED,
            fallback_message="File is not accessible.",
        )
        return {
            "valid": False,
            **detail,
            "mapped_path": "",
        }


@router.post("/validate_output_dir")
async def validate_output_dir_endpoint(output_dir: str | None = Form(None)):
    raw = (output_dir or "").strip()
    if not raw:
        detail = error_detail(ERR_OUTPUT_DIR_REQUIRED, message="Output directory is required.")
        return {
            "valid": False,
            **detail,
            "resolved_path": "",
        }
    try:
        resolved = validate_output_dir(raw)
        return {"valid": True, "message": "Output directory is accessible.", "resolved_path": str(resolved)}
    except HTTPException as exc:
        detail = error_detail_from_http_exception(
            exc,
            fallback=ERR_ACCESS_DENIED,
            fallback_message="Output directory is not accessible.",
        )
        return {
            "valid": False,
            **detail,
            "resolved_path": "",
        }


@router.post("/validate_range_quick")
async def validate_range_quick(range_text: str | None = Form(None)):
    return parse_range_script((range_text or "").strip())


@router.post("/validate_range")
async def validate_range(range_text: str | None = Form(None)):
    raw = (range_text or "").strip()
    if not raw:
        return {"valid": True, "type": "sections", "items": [], "display": "", "suggestion": ""}
    if len(raw) > MAX_RANGE_SPEC_LEN:
        return {"valid": False, "range_message": "Range text is too long.", "server_error": False}
    result = validate_range_with_ai(raw)
    if not result.get("valid") and result.get("server_error"):
        logger.warning("AI range validation failed: %s", result.get("range_message", "unknown error"))
    return result
