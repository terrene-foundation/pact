# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
#
# CARE Platform — FastAPI API server
# Multi-stage build: builder installs dependencies, runtime runs the app.
#
# IMPORTANT: Uses AsyncLocalRuntime — required for all container deployments.
# LocalRuntime hangs in containerized environments due to event loop conflicts.

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools (needed for packages with C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specification first for layer caching
COPY pyproject.toml ./
COPY src/ ./src/

# Install the package and all runtime dependencies into a prefix directory
# --no-cache-dir keeps the image lean; --prefix isolates from system Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --prefix=/install ".[dev]" --no-deps \
    && pip install --no-cache-dir --prefix=/install .

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install only the runtime system libraries needed (libpq for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN groupadd --gid 1001 care \
    && useradd --uid 1001 --gid care --shell /bin/bash --create-home care

WORKDIR /app

# Copy application source (owned by non-root user)
COPY --chown=care:care src/ ./src/
COPY --chown=care:care pyproject.toml ./

# Switch to non-root user
USER care

# Expose the API port
EXPOSE 8000

# Health check — polls the /health endpoint every 30s
# Allows 60s startup time (start-period) before counting failures
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default environment (overridden by docker-compose or runtime env)
ENV CARE_API_HOST=0.0.0.0 \
    CARE_API_PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Run the FastAPI server via uvicorn.
# care_platform.api.server:get_app is the factory function — uvicorn calls it
# to get the ASGI app, which uses AsyncLocalRuntime internally (required for
# container deployments — LocalRuntime hangs due to event loop conflicts).
CMD ["python", "-m", "uvicorn", \
     "care_platform.api.server:get_app", \
     "--factory", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1"]
