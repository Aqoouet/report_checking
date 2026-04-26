from __future__ import annotations

import os
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

MSK_TZ = ZoneInfo("Europe/Moscow")

RESULT_DIR = Path(tempfile.gettempdir()) / "report_checker"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CHECK_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "clarity.txt"
DEFAULT_VALIDATION_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "validation.txt"
DEFAULT_SUMMARY_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "summary.txt"
CONFIG_DEFAULTS_PATH = Path(__file__).resolve().parent / "config_defaults.yaml"
HELP_DIR = Path(__file__).resolve().parent / "help"
CHECK_PROMPT_MAX_BYTES = 256 * 1024

try:
    RESULT_TTL_SECONDS = int(os.getenv("RESULT_TTL_HOURS", "24")) * 3600
except ValueError:
    RESULT_TTL_SECONDS = 24 * 3600

MAX_PATH_LEN = 1024
MAX_RANGE_SPEC_LEN = 4096
ERROR_ID_LENGTH = 8

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:80").split(",")
    if o.strip()
]
