# Todo 2103: CARE_DEV_MODE Guard for Empty API Token

**Milestone**: M21 — Hardening and Operational Readiness
**Priority**: High
**Effort**: Small
**Source**: RT10-A6
**Dependencies**: 2101, 2102

## What

In production mode (default), refuse to start if `CARE_API_TOKEN` is absent or empty. Allow the server to start without a token only when `CARE_DEV_MODE=true` is explicitly set. When dev mode is active, emit a `WARNING` log at startup so the condition is visible in logs and is never silent. The guard must be evaluated during `get_app()` initialization, before any request handler is registered, so a misconfigured server never silently accepts unauthenticated traffic.

The guard logic:

- `CARE_DEV_MODE` not set or not `"true"` and `CARE_API_TOKEN` absent/empty → raise `RuntimeError` with a descriptive message and exit
- `CARE_DEV_MODE=true` and `CARE_API_TOKEN` absent/empty → log `WARNING: Running in dev mode with no API token. Do not use in production.` and continue

## Where

- `src/care_platform/api/server.py` — `get_app()` initialization block

## Evidence

- [ ] Server process exits with a non-zero code and a clear error message when `CARE_DEV_MODE` is not `"true"` and `CARE_API_TOKEN` is empty
- [ ] Server starts successfully when `CARE_DEV_MODE=true` and token is absent
- [ ] WARNING log line is emitted when dev mode allows an empty token
- [ ] Unit tests cover: production mode with token (passes), production mode without token (fails), dev mode without token (passes with warning), dev mode with token (passes, no warning)
- [ ] Existing tests continue to pass
