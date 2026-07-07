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


def _redis_settings_from_url(url: str):
    """Parse a Redis URL into ARQ RedisSettings, handling rediss:// (TLS)."""
    import urllib.parse
    from arq.connections import RedisSettings
    parsed = urllib.parse.urlparse(url)
    ssl = parsed.scheme == "rediss"
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password or None,
        database=int(parsed.path.lstrip("/") or 0),
        ssl=ssl,
    )


async def get_redis() -> aioredis.Redis:
    return await aioredis.from_url(REDIS_URL, decode_responses=True)


async def _get_arq_redis():
    """Return an ARQ ArqRedis connection pool for enqueue_job()."""
    from arq.connections import create_pool
    settings = _redis_settings_from_url(REDIS_URL)
    return await create_pool(settings, default_queue_name="manuscripts_queue")


async def submit_job(
    job_id: str,
    file_bytes: bytes,
    file_suffix: str,
    style: str,
    outputs: list[str],
    bib_bytes: Optional[bytes] = None,
    bib_suffix: Optional[str] = None,
    assets_bytes: Optional[bytes] = None,
    assets_filename: Optional[str] = None,
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
        "assets_b64": base64.b64encode(assets_bytes).decode("ascii") if assets_bytes else "",
        "assets_filename": assets_filename or "",
        "style": style,
        "outputs": outputs,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "error": "",
        "output_files": {},
    }

    # Store job state (worker reads full payload from here by job_id)
    await redis.setex(f"job:{job_id}", JOB_TTL, json.dumps(job_data))
    await redis.aclose()

    # Enqueue via ARQ's proper mechanism (sorted set + msgpack serialization)
    # Pass the full payload as a JSON string — process_manuscript_job expects this.
    task_payload = json.dumps({
        "job_id": job_id,
        "style": style,
        "outputs": outputs,
    })
    arq_redis = await _get_arq_redis()
    await arq_redis.enqueue_job(
        "process_manuscript_job",
        task_payload,
        _job_id=job_id,
        _queue_name="manuscripts_queue",
    )
    await arq_redis.aclose()

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
