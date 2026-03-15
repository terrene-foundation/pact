<!--
Copyright 2026 Terrene Foundation
Licensed under the Apache License, Version 2.0
-->

# CARE Platform Operator Guide

This guide covers running the CARE Platform in a containerized environment using Docker Compose.

---

## Prerequisites

| Tool           | Minimum version               | Purpose                     |
| -------------- | ----------------------------- | --------------------------- |
| Docker         | 24.0                          | Container runtime           |
| Docker Compose | 2.20 (plugin, not standalone) | Multi-service orchestration |
| Git            | any                           | Cloning the repository      |

Verify your installation:

```bash
docker --version
docker compose version
```

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/terrene-foundation/care.git
cd care
```

### 2. Configure the environment

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

- `POSTGRES_PASSWORD` — a strong password for the database (see Environment Configuration)
- `CARE_API_TOKEN` — a bearer token for API authentication
- One LLM provider key (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`)

For local development you can set `CARE_DEV_MODE=true` to skip the API token requirement, but do not do this in production.

### 3. Start all services

```bash
docker compose up
```

This starts three services in dependency order:

1. `db` — PostgreSQL 16 (waits until healthy)
2. `api` — CARE Platform FastAPI server on port 8000 (waits until db is healthy)
3. `web` — Next.js frontend on port 3000 (waits until api is healthy)

To run in the background:

```bash
docker compose up -d
```

### 4. Verify the deployment

```bash
# API health check
curl http://localhost:8000/health
# Expected: {"status":"healthy","service":"care-platform"}

# Frontend
open http://localhost:3000

# API documentation (interactive)
open http://localhost:8000/docs
```

### 5. Stop services

```bash
docker compose down           # stop containers, keep volumes
docker compose down -v        # stop containers and delete database volume
```

---

## Service Overview

| Service | Port | Description                             |
| ------- | ---- | --------------------------------------- |
| `db`    | 5432 | PostgreSQL 16 — CARE Platform database  |
| `api`   | 8000 | FastAPI server — REST API and WebSocket |
| `web`   | 3000 | Next.js frontend — operator dashboard   |

All three services share the `care_net` bridge network. The `api` and `web` containers communicate with each other over this network using service names as hostnames (`http://api:8000`, `http://db:5432`).

---

## Configuration Reference

All configuration is managed through the `.env` file at the repository root. See `docs/operations/environment-config.md` for the full reference.

The minimum required variables for a working deployment:

```
# Database password (used by both db and api services)
POSTGRES_PASSWORD=your-strong-password

# API authentication token
CARE_API_TOKEN=your-secure-token

# LLM provider (at least one)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

---

## Database Management

### Connecting to the database

While the containers are running:

```bash
docker compose exec db psql -U care -d care_platform
```

From your host machine (requires psql installed locally):

```bash
psql postgresql://care:your-password@localhost:5432/care_platform
```

### Running database migrations

The CARE Platform uses Alembic for database migrations. Run migrations after starting the services:

```bash
docker compose exec api python -m alembic upgrade head
```

To check the current migration state:

```bash
docker compose exec api python -m alembic current
```

### Backup

Create a database backup with pg_dump:

```bash
docker compose exec db pg_dump -U care care_platform > backup_$(date +%Y%m%d_%H%M%S).sql
```

Store the backup file in a secure, off-container location. Do not commit backup files to the repository.

### Restore

To restore from a backup:

```bash
# Stop the api service first to avoid active connections
docker compose stop api web

# Restore
docker compose exec -T db psql -U care care_platform < backup_YYYYMMDD_HHMMSS.sql

# Restart
docker compose start api web
```

### Reset the database

To completely reset the database (all data is deleted):

```bash
docker compose down -v
docker compose up -d
```

---

## Monitoring

### Health endpoints

| Endpoint      | Service | Description                                              |
| ------------- | ------- | -------------------------------------------------------- |
| `GET /health` | api     | Returns `{"status":"healthy","service":"care-platform"}` |
| `GET /`       | web     | Returns the Next.js page (200 = healthy)                 |

These endpoints are used by Docker Compose health checks and can be wired into external monitoring tools.

### Viewing logs

All service logs:

```bash
docker compose logs -f
```

Single service:

```bash
docker compose logs -f api
docker compose logs -f web
docker compose logs -f db
```

Last 100 lines from a service:

```bash
docker compose logs --tail=100 api
```

### Container status and resource usage

```bash
docker compose ps          # service state and health
docker stats               # live CPU, memory, network for all containers
```

---

## Troubleshooting

### api container exits immediately on startup

The most common cause is a missing or invalid `CARE_API_TOKEN` with `CARE_DEV_MODE` not set to `true`.

Check the logs:

```bash
docker compose logs api
```

If you see `EnvConfigError: CARE_API_TOKEN is required in production mode`, either:

- Set `CARE_API_TOKEN=your-token` in `.env`, or
- Set `CARE_DEV_MODE=true` for local development

### web service fails health check

The frontend depends on the api service being healthy. If the api is not running, the web service will not become healthy.

1. Check api service health: `docker compose ps`
2. Check api logs: `docker compose logs api`
3. Resolve api issues first, then restart web: `docker compose restart web`

### Database connection refused

The api service connects to the db container using the hostname `db`. If you see connection errors:

1. Confirm the db container is healthy: `docker compose ps db`
2. Check db logs: `docker compose logs db`
3. Verify `POSTGRES_PASSWORD` matches in both `.env` and the db container environment

### Port already in use

If port 8000 or 3000 is occupied on your host:

```bash
# Find the process using the port
lsof -i :8000

# Or change the host port in docker-compose.yml
# e.g., "8080:8000" maps host 8080 to container 8000
```

### Rebuilding after code changes

Docker Compose caches built images. After changing Python or frontend source:

```bash
docker compose build api        # rebuild API image
docker compose build web        # rebuild frontend image
docker compose build            # rebuild all images
docker compose up --build       # build and start in one step
```

---

## Security Checklist

Before exposing the CARE Platform to external traffic:

- [ ] `CARE_API_TOKEN` is set to a cryptographically random token (at least 32 bytes)
- [ ] `CARE_DEV_MODE` is `false` or absent
- [ ] `POSTGRES_PASSWORD` is not the default `care_dev_password`
- [ ] LLM API keys are present only in `.env`, not in source code or Docker images
- [ ] `.env` is listed in `.gitignore` (it is by default — verify before committing)
- [ ] Database port 5432 is not exposed to the internet (remove the `ports` entry from the `db` service for production)
- [ ] HTTPS/TLS is configured via a reverse proxy (nginx, Caddy, or cloud load balancer) in front of port 8000 and 3000
- [ ] `CARE_CORS_ORIGINS` lists only trusted frontend origins
- [ ] Container images are scanned for vulnerabilities before production deployment

---

## Apache 2.0 License

Copyright 2026 Terrene Foundation

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
