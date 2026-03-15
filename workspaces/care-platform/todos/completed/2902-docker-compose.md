# Todo 2902: Docker Compose (API + Frontend + Database)

**Milestone**: M29 — Deployment and Operations
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2901, 2601

## What

Write a `docker-compose.yml` that defines three services: `api` (the FastAPI backend from the Dockerfile in 2901), `web` (the Next.js frontend), and `db` (PostgreSQL). Services must communicate over an internal Docker network; the database must not be exposed on the host by default. All environment variables are loaded from `.env` (use `env_file: .env` in the compose file — never inline secrets). Named volumes must persist the database data across container restarts. Define two Compose profiles: `dev` (mounts source code for live reload) and `prod` (uses built images). The `api` service must declare `depends_on` with a health check condition so it only starts after the database is healthy.

## Where

- `docker-compose.yml`

## Evidence

- [ ] `docker compose up` starts all three services without errors
- [ ] The `api` service waits for the `db` health check to pass before starting
- [ ] The `web` service can reach the `api` service via the service name (internal DNS)
- [ ] The `api` service can reach the `db` service via the service name (internal DNS)
- [ ] Database data persists across `docker compose down` and `docker compose up` (named volume)
- [ ] The `db` service port is not exposed on the host by default
- [ ] No secrets or API keys are hardcoded in `docker-compose.yml`
- [ ] `dev` profile mounts source code and enables live reload
- [ ] `prod` profile uses pre-built images
