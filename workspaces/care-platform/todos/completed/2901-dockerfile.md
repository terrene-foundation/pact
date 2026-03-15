# Todo 2901: Dockerfile (FastAPI + Python Dependencies)

**Milestone**: M29 — Deployment and Operations
**Priority**: High
**Effort**: Small
**Source**: Phase 3 requirement
**Dependencies**: 2101, 2103

## What

Write a multi-stage Dockerfile for the FastAPI backend. The build stage installs all Python dependencies from `pyproject.toml` using `pip` or `uv` into a virtual environment. The runtime stage copies only the virtual environment and application source (no build tools). Run the application with `uvicorn` as the ENTRYPOINT. Configure a Docker `HEALTHCHECK` that calls the `/health` endpoint every 30 seconds and fails after 3 consecutive failures. Run the process as a non-root user (create a dedicated `care` user in the Dockerfile). Do not embed any secrets or default API keys in the image.

## Where

- `Dockerfile`

## Evidence

- [ ] `docker build` completes without errors
- [ ] `docker run` starts the container and the FastAPI app responds on the configured port
- [ ] `HEALTHCHECK` is defined and the `docker inspect` output shows the health configuration
- [ ] Process inside the container runs as a non-root user (verify with `docker exec whoami`)
- [ ] No API keys, secrets, or `.env` files are embedded in the image layers
- [ ] Image size is reasonable (under 1 GB)
- [ ] Build is deterministic: same source produces the same image hash
