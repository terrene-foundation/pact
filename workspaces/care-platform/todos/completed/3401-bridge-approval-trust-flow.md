# Todo 3401: Bridge Approval Trust Flow

**Milestone**: M34 — Bridge Lifecycle Operations
**Priority**: High
**Effort**: Large
**Source**: Phase 4 plan
**Dependencies**: 3101, 3102, 3302

## What

Wire EATP trust record creation and delegation management into the bridge approval lifecycle. Trust is not established at bridge creation — it is established at bilateral approval, invalidated at suspension, and permanently destroyed at closure or revocation.

**On `Bridge._activate()` (both sides have approved):**

1. Call `establish_bridge_trust(bridge)` from `trust/bridge_trust.py` to create bilateral trust records in the trust store
2. Create `BridgeDelegation` records for each of the bridge's permitted action types
3. Emit a platform event of type `bridge_status` carrying the bridge activation details

**On `BridgeManager.suspend_bridge()`:**

1. Call `invalidate_bridge_delegations(bridge_id)` to temporarily disable bridge delegations (they must be restorable — this is not permanent revocation)
2. Emit a platform event of type `bridge_status` carrying the suspension details

**On `Bridge.close()` or `Bridge.revoke()`:**

1. Call `revoke_bridge_delegations(bridge_id)` from 3302 to permanently revoke all delegations
2. Archive the bridge's audit trail (mark audit anchors as historical, no further appends possible)
3. Emit a platform event of type `bridge_status` carrying the closure or revocation details

The `establish_bridge_trust(bridge)` function in `trust/bridge_trust.py` must create the bilateral trust records using EATP delegation primitives scoped to the bridge's constraint envelope.

## Where

- `src/care_platform/workspace/bridge.py` (extend `_activate`, `suspend_bridge`, `close`, and `revoke` methods)
- `src/care_platform/trust/bridge_trust.py` (extend with `establish_bridge_trust` and `invalidate_bridge_delegations`)

## Evidence

- [ ] `establish_bridge_trust(bridge)` implemented in `bridge_trust.py`
- [ ] Bilateral trust records created in the trust store on `_activate()`
- [ ] `BridgeDelegation` records created for each permitted action type on activation
- [ ] Platform event emitted on activation with bridge details
- [ ] `invalidate_bridge_delegations(bridge_id)` implemented in `bridge_trust.py`
- [ ] Delegation invalidation is reversible (not permanent revocation)
- [ ] Platform event emitted on suspension
- [ ] `revoke_bridge_delegations(bridge_id)` called on `close()` — permanent revocation
- [ ] `revoke_bridge_delegations(bridge_id)` called on `revoke()` — permanent revocation
- [ ] Audit trail archived (marked historical) on close or revoke
- [ ] Platform event emitted on closure with closure details
- [ ] Platform event emitted on revocation with revocation reason
- [ ] Trust records not created until both sides have approved (not at bridge creation)
- [ ] All unit tests pass
