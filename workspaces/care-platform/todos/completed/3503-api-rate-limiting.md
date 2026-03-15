# Todo 3503: API Rate Limiting

**Milestone**: M35 — Security Hardening
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: None

## What

Add rate limiting middleware to the FastAPI application using `slowapi` to prevent abuse and denial-of-service against the CARE Platform API.

Add `slowapi` to `pyproject.toml` dependencies.

Create `src/care_platform/api/rate_limit.py` with:

- A `Limiter` instance configured to key on the authenticated token for protected endpoints, or on client IP for unauthenticated endpoints (`/health`, `/ready`)
- Two default rate limit tiers:
  - Read tier: 60 requests per minute per token (GET endpoints)
  - Mutating tier: 10 requests per minute per token (POST, PUT, DELETE endpoints)
- Configurable via environment variables `CARE_RATE_LIMIT_GET` (default `60`) and `CARE_RATE_LIMIT_POST` (default `10`)
- A `RateLimitExceededHandler` that returns a standard HTTP 429 response with a `Retry-After` header indicating when the limit resets

Integrate into `src/care_platform/api/server.py`:

- Attach the `Limiter` to the FastAPI app state
- Register the `RateLimitExceededHandler` as the 429 exception handler
- Apply the read-tier decorator to all GET route handlers
- Apply the mutating-tier decorator to all POST, PUT, DELETE route handlers

Add `CARE_RATE_LIMIT_GET` and `CARE_RATE_LIMIT_POST` to `EnvConfig` in `src/care_platform/config/env.py` with documented defaults.

## Where

- `src/care_platform/api/rate_limit.py` (new)
- `src/care_platform/api/server.py` (integrate limiter and exception handler)
- `src/care_platform/config/env.py` (add `CARE_RATE_LIMIT_GET`, `CARE_RATE_LIMIT_POST`)
- `pyproject.toml` (add `slowapi` dependency)

## Evidence

- [ ] `slowapi` present in `pyproject.toml` dependencies
- [ ] `src/care_platform/api/rate_limit.py` exists with `Limiter` and `RateLimitExceededHandler`
- [ ] `CARE_RATE_LIMIT_GET` and `CARE_RATE_LIMIT_POST` present in `EnvConfig`
- [ ] GET endpoints return 429 after exceeding the configured read-tier limit
- [ ] POST/PUT/DELETE endpoints return 429 after exceeding the configured mutating-tier limit
- [ ] 429 response includes a `Retry-After` header
- [ ] Rate limit is keyed on authenticated token for protected routes
- [ ] `/health` and `/ready` use IP-based keying, not token-based
- [ ] Limits are configurable by setting env vars (verified by tests with non-default values)
- [ ] All existing API tests still pass
