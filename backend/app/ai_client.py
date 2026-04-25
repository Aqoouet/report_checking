from __future__ import annotations

# Compatibility facade only. Active code should import focused AI modules.

from app.range_ai_validator import validate_range
from app.text_ai_client import check_text_chunk
from app.worker_ai_client import call_worker_chat as call_async

__all__ = ["call_async", "check_text_chunk", "validate_range"]
