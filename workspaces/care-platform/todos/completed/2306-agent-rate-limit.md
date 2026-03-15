# Todo 2306: Per-Agent Rate Limiting in Middleware

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: Medium
**Effort**: Small-Medium
**Source**: I7
**Dependencies**: 2302 (constraint model extended), 2304 (spend lock pattern established)

## What

Add per-agent request throttling to the verification middleware. The rate limit is configured via the operational dimension of the constraint envelope — specifically a new `max_requests_per_minute: Optional[int]` field. When an agent exceeds its configured rate limit within the rolling window, the verification result for that action is BLOCKED with reason `RATE_LIMIT_EXCEEDED`. This prevents a runaway or compromised agent from flooding the verification pipeline. The token-bucket or sliding-window counter must be per-agent and guarded by a lock.

## Where

- `src/care_platform/constraint/middleware.py` — add per-agent rate limit counters with rolling window and lock; evaluate against `max_requests_per_minute` from the operational constraint dimension

## Evidence

- [ ] `max_requests_per_minute` field added to the operational constraint dimension schema in `schema.py`
- [ ] An agent whose request count exceeds its limit within the window receives BLOCKED with reason `RATE_LIMIT_EXCEEDED`
- [ ] An agent within its limit receives normal verification outcomes
- [ ] Rate limit counters are per-agent-ID, not global
- [ ] Rate limit state is guarded by a lock (thread-safe)
- [ ] A constraint envelope with `max_requests_per_minute = None` has no rate limit enforced
- [ ] Unit tests cover: within limit (passes), at limit (passes), over limit (BLOCKED), different agents have independent limits
- [ ] Existing middleware tests continue to pass
