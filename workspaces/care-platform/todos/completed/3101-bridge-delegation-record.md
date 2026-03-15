# Todo 3101: Bridge Delegation Record

**Milestone**: M31 — Bridge Trust Foundation
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: None

## What

Implement `BridgeDelegation`, a dataclass that wraps an EATP `DelegationRecord` with bridge-specific context. This is the trust primitive for cross-team delegation — every bridge action traces back to a `BridgeDelegation` in the trust store.

The dataclass fields are: `bridge_id`, `source_team_id`, `target_team_id`, `bridge_type` (using the existing `BridgeType` enum from `care_platform/workspace/bridge.py`), `delegation_record` (the underlying `eatp.chain.DelegationRecord`), `created_at`, and `expires_at`.

Factory method `create_bridge_delegation(bridge, delegator_id, delegate_id, constraint_envelope)`:

- Validates that the bridge has `BridgeStatus.ACTIVE` before proceeding; raises `ValueError` if not
- Creates a `DelegationRecord` via `EATPBridge.delegate()`, scoped to the bridge's constraint envelope
- Wraps it in a `BridgeDelegation` and returns it

Extend the `TrustStore` protocol (in `care_platform/trust/eatp_bridge.py` or wherever the protocol lives) with a `store_bridge_delegation(delegation: BridgeDelegation) -> None` method and a `get_bridge_delegations(bridge_id: str) -> list[BridgeDelegation]` method. Implement both on `SQLiteTrustStore`.

## Where

- `src/care_platform/trust/bridge_trust.py` (new file — primary implementation)
- `src/care_platform/trust/eatp_bridge.py` (extend TrustStore protocol if needed)

## Evidence

- [ ] `src/care_platform/trust/bridge_trust.py` exists with `BridgeDelegation` dataclass defined
- [ ] All required fields present: `bridge_id`, `source_team_id`, `target_team_id`, `bridge_type`, `delegation_record`, `created_at`, `expires_at`
- [ ] `create_bridge_delegation()` factory method implemented and validates ACTIVE status
- [ ] Raises `ValueError` when bridge is not ACTIVE
- [ ] `TrustStore` protocol extended with `store_bridge_delegation` and `get_bridge_delegations`
- [ ] `SQLiteTrustStore` implements both new protocol methods
- [ ] All unit tests pass
