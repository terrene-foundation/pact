# Todo 3302: Bridge-Level Revocation

**Milestone**: M33 — Cross-Team Execution
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3101

## What

Extend `RevocationManager` with delegation-level revocation that is scoped to bridges. Bridge delegations have their own revocation lifecycle distinct from agent-level revocation.

Add `revoke_bridge_delegations(bridge_id, reason)` — this revokes all `BridgeDelegation` records for a specific bridge without revoking the agents themselves. Agent identity and team membership are unaffected; only their cross-team delegation authority is removed.

Lifecycle rules:

- When a bridge is **suspended**: invalidate (but do not permanently revoke) all bridge delegations for that bridge. The delegations must be restorable when the bridge is resumed.
- When a bridge is **closed or revoked**: permanently revoke all bridge delegations for that bridge.
- When an **agent is revoked**: the existing cascade already calls `revoke_team_bridges`; extend that cascade to also permanently revoke all bridge delegations for that individual agent across all bridges they participate in.

Bridge delegations must use short-lived credentials with a 5-minute validity window, per the EATP specification recommendation for cross-team trust. The `create_bridge_delegation` factory (3101) must enforce this TTL; `RevocationManager` must treat expired bridge delegations as already-revoked during verification.

## Where

- `src/care_platform/trust/revocation.py` (extend)

## Evidence

- [ ] `revoke_bridge_delegations(bridge_id, reason)` implemented
- [ ] Bridge suspension invalidates delegations (restorable on resume, not permanently revoked)
- [ ] Bridge closure permanently revokes all delegations for that bridge
- [ ] Bridge revocation permanently revokes all delegations for that bridge
- [ ] Agent revocation cascades to permanently revoke that agent's bridge delegations across all bridges
- [ ] Short-lived credentials enforced: bridge delegations have a 5-minute validity TTL
- [ ] Expired bridge delegations treated as revoked during verification checks
- [ ] Suspended delegations cannot be used for new cross-team task approvals
- [ ] All unit tests pass
