# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
#
# CARE Platform — FastAPI API server with seeded demo data
# Single-stage build for Cloud Run deployment.

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python package
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Clean up build deps
RUN apt-get purge -y gcc libpq-dev 2>/dev/null; apt-get autoremove -y 2>/dev/null; rm -rf /var/lib/apt/lists/*

# Copy seed scripts
COPY scripts/ ./scripts/

# Create non-root user
RUN groupadd --gid 1001 care \
    && useradd --uid 1001 --gid care --shell /bin/bash --create-home care

# Change ownership
RUN chown -R care:care /app

USER care

EXPOSE 8080

ENV CARE_API_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Start with seeded data — seeds on every cold start, then serves
CMD sh -c "python scripts/run_seeded_server.py"
