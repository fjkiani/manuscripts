"""
ARQ Worker — processes manuscript formatting jobs from the Redis queue.
Run with: arq app.worker.WorkerSettings
"""

import json
import os
import asyncio
from pathlib import Path
from typing import Optional

import structlog
from arq.connections import RedisSettings
import urllib.parse

from app.jobs import update_job_status, JOB_STATUS, REDIS_URL
from app.converter import convert_input
from app.renderer import render_outputs
from app.utils.storage import UPLOAD_DIR

log = structlog.get_logger()


def _parse_redis_settings(url: str) -> RedisSettings:
    """Parse a Redis URL into ARQ RedisSettings."""
    parsed = urllib.parse.urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password or None,
        database=int(parsed.path.lstrip("/") or 0),
    )


async def process_manuscript_job(ctx: dict, job_payload: str) -> dict:
    """
    Main job processing function called by ARQ.
    Reads file bytes from Redis, writes to worker's /tmp, converts, formats, renders.
    """
    import base64
    payload = json.loads(job_payload) if isinstance(job_payload, str) else job_payload
    job_id = payload["job_id"]
    style = payload["style"]
    outputs = payload["outputs"]

    log.info("job_started", job_id=job_id, style=style, outputs=outputs)

    # Resolve paths for this worker's /tmp
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Mark as processing
        await update_job_status(job_id, JOB_STATUS["PROCESSING"], progress=10)

        # Step 2: Decode file bytes from Redis job data
        from app.jobs import get_redis
        redis = await get_redis()
        raw = await redis.get(f"job:{job_id}")
        await redis.aclose()
        if not raw:
            raise ValueError(f"Job {job_id} not found in Redis")
        job_data = json.loads(raw)

        # Write manuscript to worker's /tmp
        file_suffix = job_data.get("file_suffix", ".md")
        file_bytes = base64.b64decode(job_data["file_b64"])
        input_path = job_dir / f"input{file_suffix}"
        input_path.write_bytes(file_bytes)

        # Write bibliography if present
        bib_path = None
        if job_data.get("bib_b64"):
            bib_bytes = base64.b64decode(job_data["bib_b64"])
            bib_suffix = job_data.get("bib_suffix", ".ris")
            bib_path = job_dir / f"bibliography{bib_suffix}"
            bib_path.write_bytes(bib_bytes)

        # Step 3: Convert input to internal representation
        log.info("converting_input", job_id=job_id, input_path=str(input_path))
        doc_data = await asyncio.get_event_loop().run_in_executor(
            None, convert_input, str(input_path), str(bib_path) if bib_path else None
        )
        await update_job_status(job_id, JOB_STATUS["PROCESSING"], progress=35)

        # Step 4: Apply journal formatting
        log.info("applying_style", job_id=job_id, style=style)
        from app.formats import get_formatter
        formatter = get_formatter(style)
        job_dir = UPLOAD_DIR / job_id
        formatted_docx_path = job_dir / "formatted.docx"

        await asyncio.get_event_loop().run_in_executor(
            None,
            formatter.build,
            doc_data["items"],
            str(formatted_docx_path),
            doc_data.get("ris_data"),
            False,  # zotero_enabled
        )
        await update_job_status(job_id, JOB_STATUS["RENDERING"], progress=60)

        # Step 4: Render all requested output formats
        log.info("rendering_outputs", job_id=job_id, outputs=outputs)
        output_dir = job_dir / "outputs"
        output_dir.mkdir(exist_ok=True)

        output_files = await asyncio.get_event_loop().run_in_executor(
            None,
            render_outputs,
            str(formatted_docx_path),
            str(output_dir),
            outputs,
            style,
        )
        await update_job_status(
            job_id,
            JOB_STATUS["DONE"],
            progress=100,
            output_files=output_files,
        )

        log.info("job_completed", job_id=job_id, output_files=list(output_files.keys()))
        return {"status": "done", "job_id": job_id, "outputs": output_files}

    except Exception as e:
        log.error("job_failed", job_id=job_id, error=str(e), exc_info=True)
        await update_job_status(
            job_id,
            JOB_STATUS["ERROR"],
            progress=0,
            error=str(e),
        )
        return {"status": "error", "job_id": job_id, "error": str(e)}


class WorkerSettings:
    """ARQ worker configuration."""
    functions = [process_manuscript_job]
    redis_settings = _parse_redis_settings(REDIS_URL)
    queue_name = "manuscripts_queue"
    max_jobs = 4
    job_timeout = 120  # 2 minutes max per job
    keep_result = 3600  # keep results for 1 hour
