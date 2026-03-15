# Todo 2202: Health and Readiness Probes

**Milestone**: M22 — API Hardening
**Priority**: Medium
**Effort**: Small
**Source**: I2
**Dependencies**: 2101, 2102

## What

Add two HTTP probe endpoints to support container orchestration and load-balancer health checking:

- `GET /health` — liveness probe. Returns `200 OK` with `{"status": "ok"}` whenever the process is running. No dependency checks; if the process is alive, this returns 200. Used by orchestrators to decide whether to restart the container.

- `GET /ready` — readiness probe. Returns `503 Service Unavailable` until all of the following are confirmed: bootstrap has completed successfully, the TrustStore backend is reachable/writable, and the event bus is operational. Once all checks pass, returns `200 OK` with `{"status": "ready"}`. Used by load balancers to decide whether to route traffic. The server must track bootstrap completion state internally so `/ready` reflects actual initialization progress.

Both endpoints must be unauthenticated (probes run without credentials in standard Kubernetes/Docker deployments).

## Where

- `src/care_platform/api/server.py` — route registration for `/health` and `/ready`
- `src/care_platform/api/endpoints.py` — handler implementations for both probes

## Evidence

- [ ] `GET /health` returns `200` at all times when the process is up, with no authentication required
- [ ] `GET /ready` returns `503` before bootstrap completes
- [ ] `GET /ready` returns `200` after bootstrap completes and dependency checks pass
- [ ] `GET /ready` returns `503` if TrustStore is unreachable
- [ ] Both endpoints are excluded from API token authentication middleware
- [ ] Unit/integration tests cover: pre-bootstrap state (503), post-bootstrap state (200), TrustStore failure (503)
- [ ] Existing tests continue to pass
