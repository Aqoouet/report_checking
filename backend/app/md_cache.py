"""Кеш Markdown после конвертации DOCX → Docling.

Ключ: SHA-256 содержимого .docx. Значение: файл ``{hex}.md`` в каталоге MD_CACHE_DIR.

При смене параметров Docling (DOCLING_URL, флаги конвертации) очистите каталог кеша
или задайте MD_CACHE_VERSION.
"""

from __future__ import annotations

import hashlib
import logging
import os
import stat
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_CHUNK = 1024 * 1024
_MAX_MD_BYTES = 100 * 1024 * 1024  # 100 MB


def _cache_dir() -> Path:
    raw = (os.getenv("MD_CACHE_DIR") or "").strip()
    if raw:
        return Path(raw)
    return Path(tempfile.gettempdir()) / "report_checker_md_cache"


def _cache_version() -> str:
    return (os.getenv("MD_CACHE_VERSION") or "1").strip() or "1"


def _cache_disabled() -> bool:
    return os.getenv("MD_CACHE_DISABLE", "").strip().lower() in ("1", "true", "yes", "on")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(_CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def get_or_convert_md(file_path: str, convert_fn) -> str:
    """Вернуть Markdown: из кеша по SHA-256 *file_path*, иначе *convert_fn(file_path)* и запись в кеш.

    *convert_fn* — обычно :func:`docling_client.convert_file_to_md`.
    """
    path = Path(file_path)
    if _cache_disabled():
        return convert_fn(file_path)

    digest = sha256_file(path)
    ver = _cache_version()
    cache_root = _cache_dir()
    cache_root.mkdir(parents=True, exist_ok=True)
    # Restrict cache directory to owner only — prevent other local users from reading documents.
    try:
        cache_root.chmod(stat.S_IRWXU)
    except OSError:
        pass
    cache_file = cache_root / ver / f"{digest}.md"

    if cache_file.is_file():
        logger.info("md_cache hit | %s", path.name)
        return cache_file.read_text(encoding="utf-8")

    logger.info("md_cache miss | %s | digest=%s…", path.name, digest[:16])
    md_text = convert_fn(file_path)

    if len(md_text.encode("utf-8")) > _MAX_MD_BYTES:
        raise ValueError(
            f"Converted Markdown exceeds maximum allowed size ({_MAX_MD_BYTES // 1024 // 1024} MB)"
        )

    cache_file.parent.mkdir(parents=True, exist_ok=True)

    import shutil
    md_bytes = len(md_text.encode("utf-8"))
    free = shutil.disk_usage(cache_file.parent).free
    if md_bytes > free:
        raise OSError(
            f"Not enough disk space to cache Markdown "
            f"(need {md_bytes // 1024} KB, free {free // 1024} KB)"
        )

    fd, tmp_path = tempfile.mkstemp(dir=cache_file.parent, suffix=".tmp")
    tmp = Path(tmp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(md_text)
        tmp.replace(cache_file)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise

    logger.info("md_cache stored | %s", cache_file)
    return md_text
