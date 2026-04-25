from __future__ import annotations

from pathlib import Path

from fastapi import Request


def safe_download_stem(raw: str, max_len: int = 80) -> str:
    t = (raw or "").strip()
    s = "".join(c if (c.isalnum() or c in "._-") else "_" for c in t)
    s = "_".join(p for p in s.split("_") if p)
    return (s or "report")[:max_len]


def get_session_id(request: Request) -> str:
    raw = request.headers.get("X-Session-ID", "default")
    return raw[:64] if raw.strip() else "default"


def read_prompt_file(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""
