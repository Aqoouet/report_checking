from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_SERVERS = [
    {"url": "http://10.99.66.97:1234", "concurrency": 3},
    {"url": "http://10.99.66.212:1234", "concurrency": 6},
]


def get_worker_servers() -> list[dict]:
    raw = os.getenv("WORKER_SERVERS", "").strip()
    if not raw:
        return _DEFAULT_SERVERS
    try:
        servers = json.loads(raw)
        if isinstance(servers, list) and servers:
            return servers
    except Exception:
        logger.warning("WORKER_SERVERS env var is not valid JSON, using defaults")
    return _DEFAULT_SERVERS
