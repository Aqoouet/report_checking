from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException


@dataclass(frozen=True)
class ApiError:
    code: str
    message: str
    http_status: int


ERR_CONFIG_NOT_SET   = ApiError("ERR_CONFIG_NOT_SET",   "Конфигурация не задана", 400)
ERR_JOB_NOT_FOUND    = ApiError("ERR_JOB_NOT_FOUND",    "Задача не найдена", 404)
ERR_LOG_NOT_FOUND    = ApiError("ERR_LOG_NOT_FOUND",    "Лог не найден", 404)
ERR_RESULT_NOT_READY = ApiError("ERR_RESULT_NOT_READY", "Результат не готов", 400)
ERR_FILE_NOT_FOUND   = ApiError("ERR_FILE_NOT_FOUND",   "Файл не найден", 404)
ERR_ACCESS_DENIED    = ApiError("ERR_ACCESS_DENIED",    "Доступ запрещён", 403)
ERR_PATH_DENIED      = ApiError("ERR_PATH_DENIED",      "Путь вне разрешённой директории", 400)
ERR_PROMPT_MISSING   = ApiError("ERR_PROMPT_MISSING",   "Файл промпта не найден", 500)
ERR_RATE_LIMITED        = ApiError("ERR_RATE_LIMITED",        "Слишком много запросов", 429)
ERR_INVALID_FILE_TYPE   = ApiError("ERR_INVALID_FILE_TYPE",   "Поддерживаются только файлы .docx", 400)


def api_error(err: ApiError) -> HTTPException:
    return HTTPException(
        status_code=err.http_status,
        detail={"code": err.code, "message": err.message},
    )
