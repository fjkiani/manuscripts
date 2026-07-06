# Manuscripts

**Scientific manuscript formatter** — convert raw manuscripts to publication-ready output in IEEE, Elsevier, Springer, APA, AMA, and Generic styles.

## Features

- **Web editor** with dual mode: rich text (WYSIWYG) and Markdown with live preview
- **6 journal styles**: IEEE, Elsevier, Springer LNCS, APA 7th, AMA 11th, Generic
- **4 output formats**: PDF (via XeLaTeX), DOCX, LaTeX source, HTML
- **4 input formats**: DOCX, Markdown, LaTeX, plain text
- **Citation reformatting**: auto-converts between numbered [N] and author-date styles via CrossRef API
- **Bibliography support**: BibTeX (.bib) and RIS (.ris) file import
- **Async job queue**: Redis + ARQ for concurrent users
- **One-click Render deploy**

## Quick Start (Local)

### Prerequisites
- Docker and Docker Compose

### Run

```bash
git clone https://github.com/your-org/manuscripts.git
cd manuscripts
docker-compose up
```

Open http://localhost:5173 for the editor, http://localhost:8000/api/docs for the API.

## Deploy to Render

1. Fork this repository
2. Connect to Render: https://render.com/deploy
3. Select `render.yaml` as the Blueprint
4. Click **Deploy**

The Blueprint provisions:
- Web service (API + frontend) on Standard plan (~$25/month)
- Worker service (ARQ job processor) on Standard plan
- Redis on Starter plan (~$3/month)

## Development

### Backend only

```bash
cd backend
pip install -r requirements.txt
# Start Redis first
docker run -d -p 6379:6379 redis:7-alpine
# Run API
uvicorn app.main:app --reload
# Run worker (separate terminal)
python -m arq app.worker.WorkerSettings
```

### Frontend only

```bash
cd frontend
npm install
npm run dev
```

### Run tests

```bash
cd backend
pytest tests/ -v
```

## API Reference

Interactive docs at `/api/docs` (Swagger UI) or `/api/redoc`.

### Submit a job

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "file=@manuscript.docx" \
  -F "style=ieee" \
  -F "outputs=pdf,docx,latex,html"
```

### Poll status

```bash
curl http://localhost:8000/api/jobs/{job_id}
```

### Download output

```bash
curl -O http://localhost:8000/api/files/{job_id}/pdf
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size |
| `JOB_TTL_SECONDS` | `3600` | Job/file retention time (1 hour) |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins |
| `UPLOAD_DIR` | `/tmp/manuscripts` | Upload/output directory |
| `ENVIRONMENT` | `production` | `development` enables hot reload |

## Architecture

```
Browser → FastAPI (main.py) → Redis queue → ARQ Worker
                                                ↓
                                    converter.py (DOCX/MD/TEX/TXT → items)
                                                ↓
                                    formats/{style}.py (apply journal style)
                                                ↓
                                    renderer.py (PDF/DOCX/LaTeX/HTML)
                                                ↓
                                    /tmp/manuscripts/{job_id}/outputs/
```

## License

MIT
