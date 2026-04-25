from __future__ import annotations

from app import job_repo

JOB_TTL_SECONDS = 86400  # 24 hours


def cleanup_old_jobs() -> None:
    job_repo.delete_expired_jobs(JOB_TTL_SECONDS)
