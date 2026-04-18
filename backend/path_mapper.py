"""Convert Windows file paths to Linux paths using a mapping dictionary.

The mapping is stored in ``path_mapping.json`` next to this file and is loaded
once at import time.  Each key is a Windows path prefix (e.g.
``C:\\Users\\name\\``) and the corresponding value is the Linux prefix to
replace it with.

If the supplied path already starts with ``/`` it is returned as-is.
"""

from __future__ import annotations

import json
from pathlib import Path

_MAPPING_FILE = Path(__file__).parent / "path_mapping.json"

# Loaded once at import time; sorted longest-first so more-specific entries win.
_MAPPING: dict[str, str] = {}
if _MAPPING_FILE.exists():
    with _MAPPING_FILE.open(encoding="utf-8") as _f:
        _MAPPING = json.load(_f)

_SORTED_KEYS: list[str] = sorted(_MAPPING, key=len, reverse=True)


def _normalize_for_mapping_lookup(raw_path: str) -> str:
    """Build ``X:\\rest`` so JSON keys like ``U:\\`` match ``U:/…``, ``U:\\…``, pasted quotes, etc."""
    s = raw_path.strip().strip('"').strip("'")
    if len(s) >= 2 and s[1] == ":":
        body = s[2:]
        if not body:
            return s[:2] + "\\"
        if body[0] in "/\\":
            body = body[1:]
        return s[:2] + "\\" + body.replace("/", "\\")
    return s


def map_path(raw_path: str) -> str:
    """Return the Linux path corresponding to *raw_path*.

    - If *raw_path* starts with ``/`` it is returned unchanged.
    - Otherwise the longest matching Windows prefix from the mapping is
      substituted with the corresponding Linux prefix.
    - If no prefix matches the path is returned as-is (caller should
      validate the resulting path exists).
    """
    raw_path = raw_path.strip()

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
