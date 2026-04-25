from __future__ import annotations

import logging
from pathlib import Path

from error_codes import (
    ERR_ACCESS_DENIED,
    ERR_FILE_NOT_FOUND,
    ERR_INVALID_FILE_TYPE,
    ERR_PATH_DENIED,
    ApiError,
    api_error,
)
from path_mapper import get_allowed_prefixes, map_path
from settings import MAX_PATH_LEN

logger = logging.getLogger(__name__)


def _path_guard(resolved: Path, err: ApiError) -> None:
    """Raise HTTPException if *resolved* is not inside any allowed prefix.

    Fails closed: empty allowlist denies everything, not nothing.
    Uses is_relative_to for exact boundary matching (prevents /foo/bar matching /foo/barz).
    """
    allowed_prefixes = get_allowed_prefixes()
    if not allowed_prefixes:
        logger.error("No path allowlist configured — denying access (fail-close)")
        raise api_error(err)

    if not any(resolved.is_relative_to(Path(pfx).resolve()) for pfx in allowed_prefixes):
        logger.warning("Access denied for path (hash: %s)", str(resolved)[:8])
        raise api_error(err)


def validate_file_path(file_path: str) -> Path:
    if len(file_path) > MAX_PATH_LEN:
        raise api_error(ERR_PATH_DENIED)
    if "\x00" in file_path:
        raise api_error(ERR_PATH_DENIED)

    linux_path = map_path(file_path)
    p = Path(linux_path)

    try:
        resolved = p.resolve()
        if p.is_symlink():
            raise api_error(ERR_ACCESS_DENIED)
    except OSError as e:
        logger.warning("OS error resolving path: %s", e)
        raise api_error(ERR_ACCESS_DENIED)

    _path_guard(resolved, ERR_ACCESS_DENIED)

    try:
        exists = resolved.exists()
        suffix = resolved.suffix.lower()
    except OSError as e:
        logger.warning("OS error checking path: %s", e)
        raise api_error(ERR_ACCESS_DENIED)

    if not exists:
        raise api_error(ERR_FILE_NOT_FOUND)

    if suffix != ".docx":
        raise api_error(ERR_INVALID_FILE_TYPE)

    return resolved


def validate_output_dir(path: str) -> Path:
    resolved = Path(map_path(path)).resolve()
    _path_guard(resolved, ERR_PATH_DENIED)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
