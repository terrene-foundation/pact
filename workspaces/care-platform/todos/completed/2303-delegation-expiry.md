# Todo 2303: Delegation Expiry Enforcement at Runtime

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: High
**Effort**: Small
**Source**: RT5-24
**Dependencies**: 2201 (M22 security prerequisites complete)

## What

Check delegation `expires_at` timestamps in the verification pipeline at the point where the delegation record is consulted. An expired delegation must be treated as revoked: verification fails and the result is BLOCKED. This mirrors the existing envelope expiry check pattern already present in the middleware. The check should be applied whenever a delegation record is resolved during trust chain traversal, not only at envelope evaluation time.

## Where

- `src/care_platform/constraint/middleware.py` — add expiry check in the delegation resolution step of the verification pipeline
- `src/care_platform/trust/delegation.py` — expose a helper or property that reports whether a delegation record is currently valid (not expired and not revoked)

## Evidence

- [ ] A delegation record with `expires_at` in the past causes BLOCKED when used in verification
- [ ] A delegation record with `expires_at` in the future passes the expiry check normally
- [ ] A delegation record with `expires_at = None` (no expiry) is treated as perpetually valid
- [ ] Expired delegation is distinguished from revoked delegation in the audit anchor reason field
- [ ] Unit tests cover: expired delegation blocks, future expiry passes, no-expiry passes
- [ ] Existing delegation chain tests continue to pass
