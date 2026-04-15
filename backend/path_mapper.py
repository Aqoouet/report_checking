"""Convert Windows file paths to Linux paths using a mapping dictionary.

The mapping is stored in ``path_mapping.json`` next to this file.
Each key is a Windows path prefix (e.g. ``C:\\Users\\name\\``) and the
corresponding value is the Linux prefix to replace it with.

If the supplied path already starts with ``/`` it is returned as-is.
"""

from __future__ import annotations

import json
from pathlib import Path

_MAPPING_FILE = Path(__file__).parent / "path_mapping.json"


def _load_mapping() -> dict[str, str]:
    if not _MAPPING_FILE.exists():
        return {}
    with _MAPPING_FILE.open(encoding="utf-8") as f:
        return json.load(f)


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

    mapping = _load_mapping()

    # Try longest prefix first so more-specific entries win.
    for win_prefix in sorted(mapping, key=len, reverse=True):
        # Case-insensitive comparison for Windows paths.
        if raw_path.lower().startswith(win_prefix.lower()):
            linux_prefix: str = mapping[win_prefix]
            remainder = raw_path[len(win_prefix):]
            # Replace Windows backslashes with forward slashes.
            remainder = remainder.replace("\\", "/")
            return linux_prefix.rstrip("/") + "/" + remainder.lstrip("/")

    # No mapping found — still normalise backslashes just in case.
    return raw_path.replace("\\", "/")
