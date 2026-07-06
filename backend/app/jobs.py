"""
Job queue management using ARQ (async Redis queue).
Handles job submission, status tracking, and result retrieval.
"""

import json
import os
from typing import Optional
from datetime import datetime, timezone

import redis.asyncio as aioredis
import structlog

log = structlog.get_logger()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JOB_TTL = int(os.getenv("JOB_TTL_SECONDS", "3600"))  # 1 hour

# Job status constants
JOB_STATUS = {
    "QUEUED": "queued",
    "PROCESSING": "processing",
    "RENDERING": "rendering",
    "DONE": "done",
    "ERROR": "error",
}


async def get_redis() -> aioredis.Redis:
    return await aioredis.from_url(REDIS_URL, decode_responses=True)


async def submit_job(
    job_id: str,
    file_bytes: bytes,
    file_suffix: str,
    style: str,
    outputs: list[str],
    bib_bytes: Optional[bytes] = None,
    bib_suffix: Optional[str] = None,
) -> None:
    """Store job metadata + file bytes in Redis and enqueue via ARQ.

    File bytes are base64-encoded so they survive the Redis JSON round-trip
    and are accessible to the worker container (which has its own /tmp).
    """
    import base64
    redis = await get_redis()

    file_b64 = base64.b64encode(file_bytes).decode("ascii")
    bib_b64 = base64.b64encode(bib_bytes).decode("ascii") if bib_bytes else ""

    job_data = {
        "job_id": job_id,
        "status": JOB_STATUS["QUEUED"],
        "progress": 0,
        "file_b64": file_b64,
        "file_suffix": file_suffix,
        "bib_b64": bib_b64,
        "bib_suffix": bib_suffix or "",
        "style": style,
        "outputs": outputs,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "error": "",
        "output_files": {},
    }

    # Store job state
    await redis.setex(f"job:{job_id}", JOB_TTL, json.dumps(job_data))

    # Enqueue the job payload (worker reads from Redis by job_id)
    task_payload = json.dumps({
        "job_id": job_id,
        "style": style,
        "outputs": outputs,
    })
    await redis.rpush("arq:queue:manuscripts_queue", task_payload)

    await redis.aclose()
    log.info("job_enqueued", job_id=job_id)


async def get_job_status(job_id: str) -> Optional[dict]:
    """Retrieve job status from Redis."""
    redis = await get_redis()
    raw = await redis.get(f"job:{job_id}")
    await redis.aclose()

    if not raw:
        return None

    data = json.loads(raw)

    # Build response with download URLs if done
    response = {
        "job_id": data["job_id"],
        "status": data["status"],
        "progress": data["progress"],
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "error": data.get("error", ""),
        "outputs": {},
    }

    if data["status"] == JOB_STATUS["DONE"]:
        # output_files is a dict {format: local_path} stored by the worker
        for fmt in data.get("output_files", {}).keys():
            response["outputs"][fmt] = f"/api/files/{job_id}/{fmt}"

    return response


async def update_job_status(
    job_id: str,
    status: str,
    progress: int = 0,
    error: str = "",
    output_files: Optional[dict] = None,
) -> None:
    """Update job status in Redis (called by worker)."""
    redis = await get_redis()
    raw = await redis.get(f"job:{job_id}")

    if raw:
        data = json.loads(raw)
        data["status"] = status
        data["progress"] = progress
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        if error:
            data["error"] = error
        if output_files:
            data["output_files"] = output_files
        await redis.setex(f"job:{job_id}", JOB_TTL, json.dumps(data))

    await redis.aclose()
