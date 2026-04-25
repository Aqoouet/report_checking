from __future__ import annotations

from pathlib import Path


def write_artifact(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    """Write text artifact to disk.

    Single point of consolidation for all file writes in the pipeline.
    Can be extended later to add encoding validation, write auditing, etc.
    """
    Path(path).write_text(text, encoding=encoding)
