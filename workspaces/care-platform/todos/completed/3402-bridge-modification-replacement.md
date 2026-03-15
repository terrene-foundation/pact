# Todo 3402: Bridge Modification via Replacement

**Milestone**: M34 — Bridge Lifecycle Operations
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3401

## What

Bridge terms are immutable once ACTIVE, per the CARE specification. The platform must not allow in-place modification of an active bridge's permissions or constraints. Instead, modification follows a suspend-replace pattern that preserves the full audit trail.

Add `BridgeManager.modify_bridge(bridge_id, new_permissions, reason)`:

1. Suspend the current bridge (triggers delegation invalidation via 3401)
2. Create a new bridge with the same source team, target team, and bridge type
3. Apply `new_permissions` to the new bridge
4. Set the `replaces_bridge_id` field on the new bridge to the ID of the suspended bridge
5. If the original bridge was a Standing bridge, the new bridge starts in NEGOTIATING state and requires fresh bilateral approval from both sides — it does not inherit approval from the replaced bridge
6. The old bridge remains in SUSPENDED state permanently with a note referencing the replacement bridge

Add a `replaces_bridge_id: str | None` field to the `Bridge` model. This field creates an explicit audit chain linking bridge generations, allowing an auditor to reconstruct the full history of terms changes between two teams.

The old bridge must never be closed or revoked by this operation — it must stay in SUSPENDED state so its trust records and audit trail remain queryable.

## Where

- `src/care_platform/workspace/bridge.py` (extend `Bridge` model and `BridgeManager`)

## Evidence

- [ ] `Bridge.replaces_bridge_id` field added (nullable string)
- [ ] `BridgeManager.modify_bridge(bridge_id, new_permissions, reason)` implemented
- [ ] Old bridge is suspended (not closed or revoked) by the modification
- [ ] New bridge is created with the same source team, target team, and bridge type
- [ ] New bridge has `replaces_bridge_id` set to the old bridge's ID
- [ ] New bridge starts in NEGOTIATING state (requires fresh bilateral approval)
- [ ] Old bridge stays in SUSPENDED state permanently (not closed)
- [ ] A note or metadata on the old bridge references the replacement bridge ID
- [ ] In-place modification of an ACTIVE bridge is rejected (bridge immutability enforced)
- [ ] Old bridge's trust records and audit trail remain queryable after modification
- [ ] All unit tests pass
