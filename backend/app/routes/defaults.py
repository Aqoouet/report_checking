from __future__ import annotations

import platform

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from app.settings import CONFIG_DEFAULTS_PATH, HELP_DIR

router = APIRouter()

ALLOWED_HELP_FIELDS = {
    "input_docx_path",
    "output_dir",
    "subchapters_range",
    "chunk_size_tokens",
    "temperature",
    "check_prompt",
    "validation_prompt",
    "summary_prompt",
}


@router.get("/config_defaults")
async def get_config_defaults() -> dict:
    with CONFIG_DEFAULTS_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    is_windows = platform.system() == "Windows"
    return {
        "input_docx_path": raw["input_docx_path_windows"] if is_windows else raw["input_docx_path_linux"],
        "output_dir": raw["output_dir_windows"] if is_windows else raw["output_dir_linux"],
        "subchapters_range": raw.get("subchapters_range", ""),
        "chunk_size_tokens": raw.get("chunk_size_tokens", 3000),
        "temperature": raw.get("temperature"),
    }


@router.get("/field_help/{field_name}", response_class=PlainTextResponse)
async def get_field_help(field_name: str) -> str:
    if field_name not in ALLOWED_HELP_FIELDS:
        raise HTTPException(status_code=404, detail="Field help not found")
    help_file = HELP_DIR / f"{field_name}.txt"
    if not help_file.exists():
        raise HTTPException(status_code=404, detail="Help file not found")
    return help_file.read_text(encoding="utf-8")
