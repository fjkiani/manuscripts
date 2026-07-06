"""
Manuscripts — Scientific Manuscript Formatter
FastAPI backend: file upload, job queue, file download, static frontend serving.
"""

import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional

import aiofiles
import structlog
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.jobs import submit_job, get_job_status, JOB_STATUS
from app.utils.storage import cleanup_old_jobs, UPLOAD_DIR
from app.utils.logging import configure_logging

configure_logging()
log = structlog.get_logger()

app = FastAPI(
    title="Manuscripts API",
    description="Scientific manuscript formatter — converts raw manuscripts to publication-ready output.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS — allow frontend dev server and production
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_MANUSCRIPT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown",
    "text/plain",
    "application/x-tex",
    "application/octet-stream",  # fallback for .tex/.md
}
ALLOWED_BIB_TYPES = {
    "application/x-bibtex",
    "text/plain",
    "application/octet-stream",
}
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
ALLOWED_EXTENSIONS = {".docx", ".md", ".tex", ".txt"}
ALLOWED_BIB_EXTENSIONS = {".bib", ".ris"}


@app.on_event("startup")
async def startup_event():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    log.info("manuscripts_api_started", upload_dir=str(UPLOAD_DIR))

    # Start inline ARQ worker when WORKER_MODE=inline (single-container deploy)
    if os.getenv("WORKER_MODE", "inline") == "inline":
        import asyncio
        asyncio.create_task(_run_inline_worker())
        log.info("inline_worker_started")


async def _run_inline_worker():
    """Run ARQ worker as an asyncio background task (single-container mode)."""
    import asyncio
    from arq import create_pool
    from arq.connections import RedisSettings
    import urllib.parse

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    parsed = urllib.parse.urlparse(redis_url)
    settings = RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password or None,
        database=int(parsed.path.lstrip("/") or 0),
    )

    # Import WorkerSettings and run
    from app.worker import WorkerSettings
    from arq.worker import create_worker

    log.info("arq_worker_starting", redis=f"{parsed.hostname}:{parsed.port}")
    try:
        worker = create_worker(WorkerSettings, redis_settings=settings)
        await worker.async_run()
    except Exception as e:
        log.error("arq_worker_error", error=str(e))


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for Render."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/jobs", tags=["Jobs"], summary="Submit a formatting job")
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Manuscript file (.docx, .md, .tex, .txt)"),
    style: str = Form(..., description="Journal style: ieee | elsevier | springer | apa | ama | generic"),
    outputs: str = Form("pdf,docx,latex,html", description="Comma-separated output formats"),
    bib_file: Optional[UploadFile] = File(None, description="Optional bibliography (.bib or .ris)"),
):
    """
    Submit a manuscript formatting job.
    Returns a job_id immediately; poll GET /api/jobs/{job_id} for status.
    """
    # Validate style
    valid_styles = {"ieee", "elsevier", "springer", "apa", "ama", "generic"}
    if style not in valid_styles:
        raise HTTPException(400, f"Invalid style '{style}'. Choose from: {', '.join(sorted(valid_styles))}")

    # Validate output formats
    valid_outputs = {"pdf", "docx", "latex", "html"}
    requested_outputs = [o.strip().lower() for o in outputs.split(",")]
    invalid = set(requested_outputs) - valid_outputs
    if invalid:
        raise HTTPException(400, f"Invalid output format(s): {invalid}. Choose from: {valid_outputs}")

    # Validate file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Allowed: {ALLOWED_EXTENSIONS}")

    # Read and size-check manuscript
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Generate job ID (no local disk write needed — bytes go via Redis)
    job_id = str(uuid.uuid4())

    # Read bibliography bytes if provided
    bib_content: Optional[bytes] = None
    bib_suffix: Optional[str] = None
    if bib_file and bib_file.filename:
        bib_ext = Path(bib_file.filename).suffix.lower()
        if bib_ext in ALLOWED_BIB_EXTENSIONS:
            bib_content = await bib_file.read()
            bib_suffix = bib_ext

    # Alias for clarity
    bib_path = None  # kept for log message below

    # Submit to job queue (passes file bytes — worker has its own /tmp)
    await submit_job(
        job_id=job_id,
        file_bytes=content,
        file_suffix=suffix,
        style=style,
        outputs=requested_outputs,
        bib_bytes=bib_content,
        bib_suffix=bib_suffix,
    )

    log.info("job_submitted", job_id=job_id, style=style, outputs=requested_outputs)

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "queued",
            "message": f"Job queued. Poll GET /api/jobs/{job_id} for status.",
        },
    )


@app.get("/api/jobs/{job_id}", tags=["Jobs"], summary="Get job status")
async def get_job(job_id: str):
    """
    Poll job status. Status values: queued | processing | rendering | done | error
    When done, outputs contains download URLs for each format.
    """
    try:
        status = await get_job_status(job_id)
    except Exception as e:
        log.error("redis_error", error=str(e))
        raise HTTPException(503, "Job store unavailable. Redis may not be running.")
    if status is None:
        raise HTTPException(404, f"Job '{job_id}' not found.")
    return status


@app.get("/api/files/{job_id}/{format}", tags=["Files"], summary="Download formatted output")
async def download_file(job_id: str, format: str):
    """Download a formatted output file. Format: pdf | docx | latex | html"""
    valid_formats = {"pdf": ".pdf", "docx": ".docx", "latex": ".tex", "html": ".html"}
    if format not in valid_formats:
        raise HTTPException(400, f"Invalid format '{format}'")

    ext = valid_formats[format]
    output_path = UPLOAD_DIR / job_id / "outputs" / f"manuscript{ext}"

    if not output_path.exists():
        raise HTTPException(404, f"Output file not found. Job may still be processing.")

    media_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".tex": "application/x-tex",
        ".html": "text/html",
    }

    return FileResponse(
        path=str(output_path),
        media_type=media_types[ext],
        filename=f"manuscript_formatted{ext}",
    )


@app.post("/api/preview", tags=["Preview"], summary="Get live HTML preview")
async def get_preview(
    content: str = Form(..., description="Manuscript content (Markdown or plain text)"),
    style: str = Form("generic", description="Journal style for preview"),
):
    """
    Returns a quick HTML preview of the manuscript in the selected journal style.
    Uses a lightweight CSS-based render (not full Pandoc) for speed.
    """
    valid_styles = {"ieee", "elsevier", "springer", "apa", "ama", "generic"}
    if style not in valid_styles:
        raise HTTPException(400, f"Invalid style '{style}'. Choose from: {', '.join(sorted(valid_styles))}")
    from app.renderer import render_preview_html
    html = render_preview_html(content, style)
    return JSONResponse({"html": html})


# Serve React frontend (production build)
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
