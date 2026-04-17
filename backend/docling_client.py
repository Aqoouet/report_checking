"""HTTP client for the docling-service microservice.

Sends a local file to ``POST /convert`` and returns the raw
DoclingDocument dict that the service produces.

Environment variables
---------------------
DOCLING_URL
    Base URL of the docling-service (default: ``http://docling:8000``).
DOCLING_TIMEOUT
    Total request timeout in seconds (default: ``180``).  Large DOCX files
    with many figures/tables may take a while on first cold conversion.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

_DOCLING_URL = os.getenv("DOCLING_URL", "http://docling:8000").rstrip("/")
_TIMEOUT = float(os.getenv("DOCLING_TIMEOUT", "180"))


def convert_file(file_path: str) -> dict:
    """Upload *file_path* to the docling service and return the JSON response.

    Raises
    ------
    httpx.HTTPStatusError
        If the service returns a 4xx/5xx response.
    httpx.TimeoutException
        If the service does not respond within *DOCLING_TIMEOUT* seconds.
    FileNotFoundError
        If *file_path* does not exist locally.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with path.open("rb") as fh:
        response = httpx.post(
            f"{_DOCLING_URL}/convert",
            files={"file": (path.name, fh, _content_type(path.suffix))},
            timeout=_TIMEOUT,
        )
    response.raise_for_status()
    return response.json()


def _content_type(suffix: str) -> str:
    return {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
    }.get(suffix.lower(), "application/octet-stream")
