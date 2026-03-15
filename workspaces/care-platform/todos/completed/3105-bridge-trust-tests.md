# Todo 3105: Bridge Trust Tests

**Milestone**: M31 — Bridge Trust Foundation
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3101, 3102, 3103, 3104

## What

TDD test file covering all M31 deliverables. Write tests that verify both the happy paths and the critical error/edge cases for `BridgeDelegation`, bilateral trust establishment, posture resolution, and dual audit anchoring.

### Test groups to cover

**BridgeDelegation (3101)**

- `BridgeDelegation` instantiation with all required fields
- `create_bridge_delegation()` succeeds when bridge is ACTIVE
- `create_bridge_delegation()` raises `ValueError` when bridge is not ACTIVE (test PENDING, NEGOTIATING, EXPIRED, CLOSED, REVOKED)
- `store_bridge_delegation()` and `get_bridge_delegations()` round-trip

**Bridge Trust Root — bilateral signing (3102)**

- `establish_bridge_trust()` returns a tuple of two `BridgeDelegation` objects
- Source delegation is created first (lower `created_at` or sequential ordering)
- Target delegation's `delegation_record` references the source delegation's ID or hash
- Both delegations are retrievable from the trust store via `get_bridge_delegations(bridge_id)`
- `Bridge._activate()` triggers trust establishment when both approvals are present
- Mismatched team authorities raise an appropriate error

**Cross-team posture resolution (3103)**

- `effective_posture(a, b)` returns minimum for all 25 combinations of the 5 posture levels — use parameterized tests
- Symmetry: `effective_posture(a, b) == effective_posture(b, a)` for all pairs
- Idempotency: `effective_posture(a, a) == a` for all levels
- `bridge_verification_level(PSEUDO_AGENT, any)` returns BLOCKED
- `bridge_verification_level(SUPERVISED, AUTO_APPROVED)` returns HELD
- `bridge_verification_level(SUPERVISED, FLAGGED)` returns HELD
- `bridge_verification_level(SUPERVISED, HELD)` returns HELD
- `bridge_verification_level(SHARED_PLANNING, AUTO_APPROVED)` returns FLAGGED
- `bridge_verification_level(SHARED_PLANNING, FLAGGED)` returns HELD
- `bridge_verification_level(CONTINUOUS_INSIGHT, any)` returns base_level unchanged
- `bridge_verification_level(DELEGATED, any)` returns base_level unchanged

**Dual audit anchoring (3104)**

- `create_bridge_audit_pair()` returns two `BridgeAuditAnchor` objects
- Source anchor has `side == "source"`, target anchor has `side == "target"`
- Target anchor's `counterpart_anchor_hash` equals source anchor's `content_hash`
- Source anchor's `counterpart_anchor_hash` equals target anchor's `content_hash` (after update)
- When target-side creation fails, source anchor's `counterpart_anchor_hash` remains None
- Both anchors record `bridge_id`, `source_team_id`, `target_team_id` correctly
- Both anchors' `metadata` contains `effective_posture` and `effective_verification_level`

## Where

- `tests/unit/trust/test_bridge_trust.py` (new file)

## Evidence

- [ ] `tests/unit/trust/test_bridge_trust.py` exists
- [ ] All BridgeDelegation creation and validation tests pass
- [ ] All bilateral trust root tests pass
- [ ] All 25 posture combination tests pass (parameterized)
- [ ] All symmetry and idempotency tests pass
- [ ] All `bridge_verification_level` escalation tests pass
- [ ] All dual audit anchor tests pass (happy path and failed target-side)
- [ ] All error case tests pass (inactive bridge delegation, mismatched authorities)
- [ ] `pytest tests/unit/trust/test_bridge_trust.py` exits with code 0
