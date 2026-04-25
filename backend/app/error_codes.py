from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException


@dataclass(frozen=True)
class ApiError:
    code: str
    message: str
    http_status: int


ERR_CONFIG_NOT_SET = ApiError("ERR_CONFIG_NOT_SET", "Configuration is not set.", 400)
ERR_INVALID_JSON = ApiError("ERR_INVALID_JSON", "Request body must be valid JSON.", 400)
ERR_INPUT_DOCX_REQUIRED = ApiError("ERR_INPUT_DOCX_REQUIRED", "input_docx_path is required.", 400)
ERR_OUTPUT_DIR_REQUIRED = ApiError("ERR_OUTPUT_DIR_REQUIRED", "output_dir is required.", 400)
ERR_CONFIG_VALIDATION_FAILED = ApiError("ERR_CONFIG_VALIDATION_FAILED", "Configuration validation failed.", 400)
ERR_JOB_NOT_FOUND = ApiError("ERR_JOB_NOT_FOUND", "Job was not found.", 404)
ERR_LOG_NOT_FOUND = ApiError("ERR_LOG_NOT_FOUND", "Log was not found.", 404)
ERR_RESULT_NOT_READY = ApiError("ERR_RESULT_NOT_READY", "Result is not ready.", 400)
ERR_FILE_NOT_FOUND = ApiError("ERR_FILE_NOT_FOUND", "File was not found.", 404)
ERR_ACCESS_DENIED = ApiError("ERR_ACCESS_DENIED", "Access denied.", 403)
ERR_PATH_DENIED = ApiError("ERR_PATH_DENIED", "Path is outside the allowed directory.", 400)
ERR_PROMPT_MISSING = ApiError("ERR_PROMPT_MISSING", "Prompt file was not found.", 500)
ERR_RATE_LIMITED = ApiError("ERR_RATE_LIMITED", "Too many requests.", 429)
ERR_INVALID_FILE_TYPE = ApiError("ERR_INVALID_FILE_TYPE", "Only .docx files are supported.", 400)


def error_detail(err: ApiError, *, message: str | None = None) -> dict[str, str]:
    return {"code": err.code, "message": message or err.message}


def error_detail_from_http_exception(
    exc: HTTPException,
    *,
    fallback: ApiError,
    fallback_message: str | None = None,
) -> dict[str, str]:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    code = detail.get("code")
    message = detail.get("message")
    return {
        "code": code if isinstance(code, str) else fallback.code,
        "message": message if isinstance(message, str) else (fallback_message or fallback.message),
    }


def api_error(err: ApiError, *, message: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=err.http_status,
        detail=error_detail(err, message=message),
    )
