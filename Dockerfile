# ============================================================
# Stage 1: Build React frontend
# ============================================================
FROM node:20-slim AS node-builder

WORKDIR /app/frontend

# Install dependencies
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install

# Copy source and build
COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: Python + Pandoc + TeX Live base
# ============================================================
FROM python:3.11-slim AS python-base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-latex-extra \
    texlive-science \
    texlive-publishers \
    fonts-liberation \
    fonts-dejavu \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Stage 3: Final production image
# ============================================================
FROM python-base AS final

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 manuscripts && \
    mkdir -p /tmp/manuscripts && \
    chown manuscripts:manuscripts /tmp/manuscripts

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend
COPY --from=node-builder /app/frontend/dist ./frontend/dist

# Set Python path
ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Switch to non-root user
USER manuscripts

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: run the web server
# Override with: arq app.worker.WorkerSettings (for the worker service)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
