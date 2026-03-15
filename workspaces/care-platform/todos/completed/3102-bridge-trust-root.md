# Todo 3102: Bridge Trust Root

**Milestone**: M31 — Bridge Trust Foundation
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3101

## What

Implement bilateral trust establishment for bridge activation. When a bridge transitions from NEGOTIATING to ACTIVE (both sides have approved), create a Bridge Trust Record: a pair of linked `DelegationRecord` objects, one signed by each team's authority.

The source team's authority creates a `DelegationRecord` delegating specific capabilities to the target team. The target team's authority acknowledges receipt with a counter-signed record that includes the source record's hash as a reference.

The function to implement is `establish_bridge_trust(bridge, source_authority_id, target_authority_id, eatp_bridge) -> tuple[BridgeDelegation, BridgeDelegation]`. It creates both delegation records, stores both via `TrustStore.store_bridge_delegation()`, and returns the pair.

Integrate into the existing `Bridge` model in `src/care_platform/workspace/bridge.py`. Specifically, extend the `_activate()` private method (called when both approvals are recorded) to call `establish_bridge_trust()`. The bridge model needs to accept an optional `trust_callback` parameter (or use a protocol) so that the bridge activation can trigger trust record creation without a circular import between `workspace.bridge` and `trust.bridge_trust`.

Use the `EATPBridge` (from `src/care_platform/trust/eatp_bridge.py`) to perform the actual DELEGATE operations, passing the bridge's constraint envelope as the scope for both records.

## Where

- `src/care_platform/trust/bridge_trust.py` (add `establish_bridge_trust()` function)
- `src/care_platform/workspace/bridge.py` (extend `_activate()` method with trust callback)

## Evidence

- [ ] `establish_bridge_trust()` function implemented in `bridge_trust.py`
- [ ] Returns a tuple of two `BridgeDelegation` objects (source-side and target-side)
- [ ] Source delegation record created first (commit point)
- [ ] Target delegation record references source record hash
- [ ] Both delegations stored in trust store via `store_bridge_delegation()`
- [ ] `Bridge._activate()` in `bridge.py` calls the trust establishment callback when invoked
- [ ] Integration between bridge.py and bridge_trust.py works without circular imports
- [ ] Both teams' signatures present in their respective delegation records
- [ ] All unit tests pass
