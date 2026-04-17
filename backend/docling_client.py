"""HTTP client for the official docling-serve microservice.

Uses the v1 API of ``ghcr.io/docling-project/docling-serve-cpu``.

File-upload endpoint:  ``POST /v1/convert/file``
Request:  multipart/form-data  (field ``files`` + conversion options)
Response: ``{"document": {"json_content": <DoclingDocument dict>}, "status": "..."}``

Only ``to_formats=json`` is requested so the returned payload is exactly the
same ``DoclingDocument.export_to_dict()`` dict that ``docling_docx_parser``
knows how to map.

Environment variables
---------------------
DOCLING_URL
    Base URL of docling-serve (default: ``http://docling:5001``).
DOCLING_TIMEOUT
    Total request timeout in seconds (default: ``180``).
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

_DOCLING_URL = os.getenv("DOCLING_URL", "http://docling:5001").rstrip("/")
_TIMEOUT = float(os.getenv("DOCLING_TIMEOUT", "180"))

# Parameters sent with every conversion request.
# OCR is disabled — our DOCX files contain embedded text.
# image_export_mode=placeholder keeps the JSON small (we don't need image bytes).
_CONVERT_PARAMS = {
    "to_formats": "json",
    "do_ocr": "false",
    "image_export_mode": "placeholder",
    "abort_on_error": "false",
}


def convert_file(file_path: str) -> dict:
    """Upload *file_path* to docling-serve and return the DoclingDocument dict.

    Extracts ``response["document"]["json_content"]`` from the v1 API response
    and returns it directly — this is the same structure as
    ``DoclingDocument.export_to_dict()``, ready for ``docling_docx_parser``.

    Raises
    ------
    httpx.HTTPStatusError
        If the service returns a 4xx/5xx response.
    httpx.TimeoutException
        If the service does not respond within *DOCLING_TIMEOUT* seconds.
    FileNotFoundError
        If *file_path* does not exist locally.
    RuntimeError
        If docling-serve reports a conversion failure or returns no JSON content.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with path.open("rb") as fh:
        response = httpx.post(
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
    json_content = doc.get("json_content")
    if not json_content:
        raise RuntimeError(
            f"docling-serve returned no JSON content (status={status!r}). "
            "Check that to_formats=json is supported by this server version."
        )

    return json_content


def _content_type(suffix: str) -> str:
    return {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
    }.get(suffix.lower(), "application/octet-stream")
