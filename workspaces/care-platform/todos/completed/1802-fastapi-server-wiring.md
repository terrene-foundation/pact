# M18-T02: FastAPI/Nexus server wiring

**Status**: ACTIVE
**Priority**: High
**Milestone**: M18 — Frontend Scaffold & API Layer
**Dependencies**: 1801

## What

Create FastAPI application mounting PlatformAPI handlers as HTTP endpoints. Wire BOTH existing Phase 1 endpoints (teams, agents, approve, reject, held-actions, cost) AND new M18 dashboard endpoints. Add CORS middleware for frontend. Add health check at `/health`.

## Where

- New: `src/care_platform/api/server.py`

## Evidence

- `python -m care_platform.api.server` starts server
- `curl http://localhost:8000/api/v1/teams` returns JSON
- `curl http://localhost:8000/health` returns OK
