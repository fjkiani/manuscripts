"""File storage utilities — manages upload/output directories with TTL cleanup."""

import os
import time
import shutil
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/manuscripts"))
JOB_TTL = int(os.getenv("JOB_TTL_SECONDS", "3600"))


def cleanup_old_jobs() -> int:
    """Remove job directories older than JOB_TTL seconds. Returns count removed."""
    if not UPLOAD_DIR.exists():
        return 0
    removed = 0
    now = time.time()
    for job_dir in UPLOAD_DIR.iterdir():
        if job_dir.is_dir():
            age = now - job_dir.stat().st_mtime
            if age > JOB_TTL:
                shutil.rmtree(job_dir, ignore_errors=True)
                removed += 1
    return removed
