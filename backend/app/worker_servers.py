from __future__ import annotations

import json
import logging
import os

from pydantic import BaseModel, HttpUrl, field_validator

logger = logging.getLogger(__name__)

_DEFAULT_SERVERS = [
    {"url": "http://10.99.66.97:1234", "concurrency": 3},
    {"url": "http://10.99.66.212:1234", "concurrency": 6},
]


class WorkerServer(BaseModel):
    url: HttpUrl
    concurrency: int = 3

    @field_validator("concurrency")
    @classmethod
    def concurrency_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("concurrency must be >= 1")
        return v

    @property
    def url_str(self) -> str:
        return str(self.url)


def get_worker_servers() -> list[WorkerServer]:
    raw = os.getenv("WORKER_SERVERS", "").strip()
    if not raw:
        return _parse_servers(_DEFAULT_SERVERS)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            return _parse_servers(parsed)
    except Exception:
        logger.warning("WORKER_SERVERS env var is not valid JSON, using defaults")
    return _parse_servers(_DEFAULT_SERVERS)


def _parse_servers(data: list[dict]) -> list[WorkerServer]:
    servers: list[WorkerServer] = []
    for entry in data:
        try:
            servers.append(WorkerServer.model_validate(entry))
        except Exception as exc:
            logger.warning("Skipping invalid worker server entry %s: %s", entry, exc)
    if not servers:
        raise ValueError("No valid worker servers available")
    return servers
