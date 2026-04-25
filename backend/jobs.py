from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    current_checkpoint: int = 0
    total_checkpoints: int = 0
    current_checkpoint_name: str = ""
    current_checkpoint_short_name: str = ""
    checkpoint_sub_current: int = 0
    checkpoint_sub_total: int = 0
    checkpoint_sub_location: str = ""
    checkpoint_sub_name: str = ""
    previous_result: str = ""
    cancelled: bool = False
    error: Optional[str] = None
    result_path: Optional[str] = None
    md_result_path: Optional[str] = None
    source_doc_stem: str = ""
    created_at: float = field(default_factory=time.time)
    docx_name: str = ""
    token_count: int = 0
    queue_position: int = 0
    phase: str = ""
    artifact_dir: Optional[str] = None
    log_path: Optional[str] = None
    submitted_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    failed_sections_count: int = 0
    # Config frozen at job creation so worker uses original settings even if
    # the user changes config while the job is queued (bug #4).
    config_snapshot: Optional[object] = field(default=None, repr=False)
