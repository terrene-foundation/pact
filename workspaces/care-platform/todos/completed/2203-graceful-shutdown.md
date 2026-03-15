# Todo 2203: Graceful Shutdown with Signal Handling

**Milestone**: M22 — API Hardening
**Priority**: Medium
**Effort**: Medium
**Source**: I8
**Dependencies**: 2101, 2202

## What

Register `SIGTERM` and `SIGINT` handlers in the server process so that a shutdown signal triggers an ordered drain sequence rather than immediate termination. The drain sequence must:

1. Stop accepting new HTTP and WebSocket connections
2. Allow in-flight HTTP requests to complete (up to a configurable timeout, defaulting to 30 seconds)
3. Close open WebSocket connections with a close frame (not a hard disconnect)
4. Drain the action queue: wait for all queued but not yet processed actions to reach a terminal state (approved, rejected, or timed out) or exhaust the drain timeout
5. Flush any pending TrustStore writes and confirm durability before the process exits

A graceful shutdown must not corrupt TrustStore state. If the drain timeout expires before all pending work completes, the server logs a WARNING listing any items that could not be cleanly closed, then exits.

## Where

- `src/care_platform/api/server.py` — signal handler registration and shutdown orchestration

## Evidence

- [ ] `SIGTERM` triggers graceful shutdown sequence (not immediate process death)
- [ ] `SIGINT` (Ctrl-C) triggers the same graceful shutdown sequence
- [ ] In-flight requests complete before the server stops accepting connections
- [ ] WebSocket connections receive a close frame before the process exits
- [ ] No TrustStore writes are lost on clean SIGTERM (confirmed by inspecting store state post-shutdown)
- [ ] Drain timeout is configurable via environment variable
- [ ] WARNING is logged for any items not cleanly resolved within the drain timeout
- [ ] Test coverage: SIGTERM triggers shutdown; shutdown completes without data corruption; drain timeout enforced
- [ ] Existing tests continue to pass
