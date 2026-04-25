from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException

from path_mapper import get_allowed_prefixes, map_path
from settings import MAX_PATH_LEN

logger = logging.getLogger(__name__)


def validate_file_path(file_path: str) -> Path:
    if len(file_path) > MAX_PATH_LEN:
        raise HTTPException(status_code=400, detail="Путь к файлу слишком длинный")
    if "\x00" in file_path:
        raise HTTPException(status_code=400, detail="Недопустимый путь к файлу")

    linux_path = map_path(file_path)
    p = Path(linux_path)

    try:
        resolved = p.resolve()
        if p.is_symlink():
            raise HTTPException(status_code=403, detail="Доступ к файлу запрещён")
    except HTTPException:
        raise
    except OSError as e:
        logger.warning("OS error resolving path: %s", e)
        raise HTTPException(status_code=403, detail="Нет доступа к файлу или каталогу")

    allowed_prefixes = get_allowed_prefixes()
    if not allowed_prefixes:
        logger.warning(
            "No path allowlist configured (path_mapping.json missing or empty) — all paths are accessible"
        )
    else:
        resolved_str = str(resolved)
        if not any(resolved_str.startswith(str(Path(pfx).resolve())) for pfx in allowed_prefixes):
            logger.warning("Access denied for path (hash: %s)", resolved_str[:8])
            raise HTTPException(status_code=403, detail="Доступ к файлу запрещён")

    try:
        exists = resolved.exists()
        suffix = resolved.suffix.lower()
    except OSError as e:
        logger.warning("OS error checking path: %s", e)
        raise HTTPException(status_code=403, detail="Нет доступа к файлу или каталогу")

    if not exists:
        raise HTTPException(status_code=400, detail="Файл не найден")

    if suffix != ".docx":
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .docx")

    return resolved


def validate_output_dir(path: str) -> Path:
    p = Path(map_path(path)).resolve()
    allowed_prefixes = get_allowed_prefixes()
    if allowed_prefixes:
        resolved_str = str(p)
        if not any(resolved_str.startswith(str(Path(pfx).resolve())) for pfx in allowed_prefixes):
            raise HTTPException(status_code=400, detail="Путь output_dir вне разрешённой директории")
    p.mkdir(parents=True, exist_ok=True)
    return p
