# 212: Implement Verification Gradient as Action Middleware

**Milestone**: 2 — EATP Trust Integration
**Priority**: High (connects trust model to runtime)
**Estimated effort**: Medium
**Status**: COMPLETED — 2026-03-12

## Completion Summary

`VerificationMiddleware` implemented in `care_platform/constraint/middleware.py` with all four gradient routing outcomes.

- `care_platform/constraint/middleware.py` — `VerificationMiddleware`, `ActionOutcome`, `MiddlewareResult`
- Routing: AUTO_APPROVED → execute + log; FLAGGED → execute + mark for review; HELD → queue for human; BLOCKED → reject + log
- Human approval queue integrated (`ApprovalQueue` from `execution.approval`)
- Configurable verification level (QUICK/STANDARD/FULL) per action type
- `tests/unit/constraint/test_middleware.py` — all four routing outcomes, approval flow, blocked action not executed

## Description

Implement the verification gradient as middleware that intercepts every agent action, evaluates it against the agent's signed constraint envelope, and applies the correct response.

## Tasks

- [x] `care_platform/constraint/middleware.py` — `VerificationMiddleware`
- [x] Flow: action → verify token → check envelope → classify → route
- [x] Human approval queue for held actions
- [x] Flagging notifications for near-boundary conditions
- [x] Verification level selection (QUICK/STANDARD/FULL)
- [x] Integration tests (each gradient level, approval flow, blocked action)

## Acceptance Criteria

- [x] Every agent action passes through verification middleware
- [x] Correct routing for all four gradient levels
- [x] Human approval queue functional
- [x] Verification level selection configurable
- [x] Integration tests passing

## References

- `care_platform/constraint/middleware.py`
- `tests/unit/constraint/test_middleware.py`
