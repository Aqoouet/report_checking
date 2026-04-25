"""HTTP client for the official docling-serve microservice.

Converts a .docx file to Markdown via ``POST /v1/convert/file``.
OCR is always disabled — DOCX files contain embedded text.

Environment variables
---------------------
DOCLING_URL
    Base URL of docling-serve (default: ``http://docling:5001``).
DOCLING_TIMEOUT
    Total request timeout in seconds (default: ``300``).
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

_DOCLING_URL = os.getenv("DOCLING_URL", "http://docling:5001").rstrip("/")
_TIMEOUT = float(os.getenv("DOCLING_TIMEOUT", "300"))
_MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "100")) * 1024 * 1024

_CONVERT_PARAMS = {
    "to_formats": "md",
    "do_ocr": "false",
    "image_export_mode": "placeholder",
    "table_mode": "accurate",
    "do_table_structure": "true",
    "include_images": "false",
    "do_picture_classification": "false",
    "do_picture_description": "false",
    "abort_on_error": "false",
    "md_page_break_placeholder": "",
}


def convert_file_to_md(file_path: str) -> str:
    """Upload *file_path* to docling-serve and return the Markdown string.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist locally.
    httpx.HTTPStatusError
        If the service returns a 4xx/5xx response.
    httpx.TimeoutException
        If the service does not respond within *DOCLING_TIMEOUT* seconds.
    RuntimeError
        If docling-serve reports a conversion failure or returns no MD content.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = path.stat().st_size
    if file_size > _MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {file_size / 1024 / 1024:.1f} MB "
            f"(max {_MAX_FILE_SIZE // 1024 // 1024} MB, set MAX_FILE_SIZE_MB to override)"
        )

    with path.open("rb") as fh:
        with httpx.Client() as client:
            response = client.post(
                f"{_DOCLING_URL}/v1/convert/file",
                data=_CONVERT_PARAMS,
                files={"files": (path.name, fh, _content_type(path.suffix))},
                timeout=_TIMEOUT,
            )
    response.raise_for_status()

    body = response.json()
    status = body.get("status", "")

    if status == "failure":
        errors = body.get("errors", [])
        raise RuntimeError(f"docling-serve conversion failed: {errors}")

    doc = body.get("document") or {}
    md = doc.get("md_content")
    if not md:
        raise RuntimeError(
            f"docling-serve returned no md_content (status={status!r}). "
            "Ensure the server version supports to_formats=md."
        )

    return md


def _content_type(suffix: str) -> str:
    return {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(suffix.lower(), "application/octet-stream")
