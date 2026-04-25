from __future__ import annotations

import os
import time
from collections import defaultdict
from threading import Lock

try:
    _RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_CHECK_PER_MINUTE", "10"))
except ValueError:
    _RATE_LIMIT_PER_MINUTE = 10

_rate_store: dict[str, list[float]] = defaultdict(list)
_rate_lock = Lock()


def is_rate_limited(client_ip: str) -> bool:
    now = time.time()
    with _rate_lock:
        times = [t for t in _rate_store.get(client_ip, []) if now - t < 60]
        if len(times) >= _RATE_LIMIT_PER_MINUTE:
            _rate_store[client_ip] = times
            return True
        times.append(now)
        _rate_store[client_ip] = times
        return False


def cleanup_rate_store() -> None:
    now = time.time()
    with _rate_lock:
        stale = [ip for ip, ts in _rate_store.items() if not ts or now - ts[-1] > 60]
        for ip in stale:
            del _rate_store[ip]
