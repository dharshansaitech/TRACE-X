# backend/Dockerfile
# Multi-stage Python 3.12 build

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pip tools
RUN pip install --no-cache-dir hatchling pip --upgrade

# Copy and install deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.32.0 \
    pydantic>=2.9.0 \
    pydantic-settings>=2.6.0 \
    google-cloud-firestore>=2.19.0 \
    google-cloud-bigquery>=3.27.0 \
    google-cloud-pubsub>=2.27.0 \
    google-cloud-aiplatform>=1.74.0 \
    vertexai>=1.74.0 \
    mcp>=1.1.0 \
    python-jose[cryptography]>=3.3.0 \
    python-multipart>=0.0.12 \
    httpx>=0.28.0 \
    websockets>=13.1 \
    asyncio-throttle>=1.0.2 \
    structlog>=24.4.0 \
    tenacity>=9.0.0 \
    numpy>=2.1.0

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Security: create non-root user
RUN groupadd --gid 1000 tracex && \
    useradd --uid 1000 --gid tracex --shell /bin/bash --create-home tracex

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=tracex:tracex . .

# Switch to non-root user
USER tracex

# Cloud Run port
ENV PORT=8080
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Start command
CMD exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --workers 2 \
    --loop uvloop \
    --no-access-log
