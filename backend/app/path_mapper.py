"""Convert Windows file paths to Linux paths using a mapping dictionary.

The mapping is stored in ``path_mapping.json`` next to this file and is loaded
once at import time.  Each key is a Windows path prefix (e.g.
``C:\\Users\\name\\``) and the corresponding value is the Linux prefix to
replace it with.

If the supplied path already starts with ``/`` it is returned as-is
(after optional normalization of GNOME/Nautilus paste prefixes and
``file://`` URLs).
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urlparse

_MAPPING_FILE = Path(__file__).parent / "path_mapping.json"

# Loaded once at import time; sorted longest-first so more-specific entries win.
_MAPPING: dict[str, str] = {}
if _MAPPING_FILE.exists():
    with _MAPPING_FILE.open(encoding="utf-8") as _f:
        _MAPPING = json.load(_f)

_SORTED_KEYS: list[str] = sorted(_MAPPING, key=len, reverse=True)

_NAUTILUS_CLIPBOARD = "x-special/nautilus-clipboard copy "


def _normalize_pasted_path(raw_path: str) -> str:
    """Убрать префикс вставки Nautilus и ``file://`` URL (GNOME копирует путь с обёрткой)."""
    s = raw_path.strip().strip('"').strip("'")
    if s.lower().startswith(_NAUTILUS_CLIPBOARD.lower()):
        s = s[len(_NAUTILUS_CLIPBOARD) :].strip()
    if s.lower().startswith("file://"):
        u = urlparse(s)
        path = unquote(u.path or "")
        return path if path else s
    return s


def _normalize_for_mapping_lookup(raw_path: str) -> str:
    """Build ``X:\\rest`` so JSON keys like ``U:\\`` match ``U:/…``, ``U:\\…``, pasted quotes, etc."""
    s = raw_path.strip().strip('"').strip("'")
    if len(s) >= 2 and s[1] == ":" and s[0].isalpha():
        body = s[2:]
        if not body:
            return s[:2] + "\\"
        if body[0] in "/\\":
            body = body[1:]
        return s[:2] + "\\" + body.replace("/", "\\")
    return s


def map_path(raw_path: str) -> str:
    """Return the Linux path corresponding to *raw_path*.

    - Strips ``x-special/nautilus-clipboard copy `` and resolves ``file://`` URLs.
    - If *raw_path* starts with ``/`` it is returned unchanged.
    - Otherwise the longest matching Windows prefix from the mapping is
      substituted with the corresponding Linux prefix.
    - If no prefix matches the path is returned as-is (caller should
      validate the resulting path exists).
    """
    raw_path = _normalize_pasted_path(raw_path).strip()

    if raw_path.startswith("/"):
        return raw_path

    lookup = _normalize_for_mapping_lookup(raw_path)

    for win_prefix in _SORTED_KEYS:
        if lookup.lower().startswith(win_prefix.lower()):
            linux_prefix: str = _MAPPING[win_prefix]
            remainder = lookup[len(win_prefix):]
            remainder = remainder.replace("\\", "/")
            return linux_prefix.rstrip("/") + "/" + remainder.lstrip("/")

    return lookup.replace("\\", "/")


def get_allowed_prefixes() -> list[str]:
    """Return all allowed Linux directory prefixes from the mapping."""
    return list(_MAPPING.values())


def map_linux_to_windows(raw_path: str) -> str:
    """Return Windows path for a Linux path, or the original if no mapping found."""
    path = (raw_path or "").strip()
    if not path:
        return path
    for win_prefix in _SORTED_KEYS:
        linux_prefix: str = _MAPPING[win_prefix]
        if path.lower().startswith(linux_prefix.lower().rstrip("/")):
            remainder = path[len(linux_prefix.rstrip("/")) :].lstrip("/")
            return win_prefix.rstrip("\\") + ("\\" + remainder.replace("/", "\\") if remainder else "")
    return path


def to_file_url(path: str) -> str:
    """Convert a Windows or Linux absolute path to a file:/// URL."""
    p = (path or "").strip()
    if len(p) >= 2 and p[1] == ":":
        return "file:///" + p.replace("\\", "/")
    if p.startswith("/"):
        return "file://" + p
    return ""
