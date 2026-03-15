# Todo 3404: Bridge Lifecycle Trust Tests

**Milestone**: M34 — Bridge Lifecycle Operations
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3401, 3402, 3403

## What

TDD test file covering all M34 deliverables. Tests must validate the complete bridge lifecycle from both the trust and operational perspectives.

Test groups required:

**Approval Flow (3401)**

- Both sides approve: trust records created in the trust store, `BridgeDelegation` records active, platform event emitted with activation details
- Single-side approval: no trust records created yet
- Trust records are scoped to the bridge's constraint envelope (not wider)

**Suspension Flow (3401)**

- `suspend_bridge()` called: delegations invalidated (not permanently revoked), platform event emitted
- Suspended delegations cannot be used for cross-team task verification
- Resuming a suspended bridge: delegations are restored and become valid again

**Closure Flow (3401)**

- `close()` called: delegations permanently revoked, audit trail archived (marked historical), platform event emitted
- Permanently revoked delegations cannot be restored by any operation
- Archived audit anchors remain queryable but cannot receive new entries

**Revocation Flow (3401)**

- `revoke()` called with a reason: same outcomes as closure plus the revocation reason is recorded
- Revocation reason appears in the platform event payload

**Modification via Replacement (3402)**

- `modify_bridge()`: old bridge enters SUSPENDED state, new bridge created with `replaces_bridge_id` set
- New bridge starts in NEGOTIATING state, not ACTIVE
- Old bridge's `replaces_bridge_id` equivalent field or note references the new bridge
- Old bridge's audit trail remains queryable after modification
- Calling `modify_bridge()` on a bridge that is not ACTIVE raises an appropriate error

**Re-Approval for Modified Standing Bridge (3402)**

- After `modify_bridge()`, the new bridge requires fresh bilateral approval
- The new bridge does not inherit approval status from the replaced bridge

**Review Cadence (3403)**

- Standing bridge: `next_review_date` is 90 days after activation when no reviews exist
- `mark_reviewed()`: resets `next_review_date` to 90 days from the review timestamp
- `get_bridges_due_for_review()`: returns bridges past their date, excludes Ad-Hoc and non-ACTIVE bridges
- Ad-Hoc summary: correct aggregate stats, correct window filtering, most frequent pairs identified

## Where

- `tests/unit/workspace/test_bridge_lifecycle_trust.py`

## Evidence

- [ ] Test file exists at the specified path
- [ ] Approval flow: trust creation, delegation activation, and platform event all tested
- [ ] Single-side approval tested (no premature trust record creation)
- [ ] Suspension: invalidation, blocking of cross-team use, and restoration all tested
- [ ] Closure: permanent revocation and audit archiving tested
- [ ] Revocation: reason recorded and appears in event payload tested
- [ ] Modification: old bridge SUSPENDED, new bridge NEGOTIATING, `replaces_bridge_id` linked
- [ ] Modification on non-ACTIVE bridge: error raised and tested
- [ ] Re-approval required after modification tested
- [ ] Review cadence: 90-day calculation for Standing bridges tested
- [ ] `mark_reviewed()` reset behaviour tested
- [ ] `get_bridges_due_for_review()` correct inclusion/exclusion tested
- [ ] Ad-hoc summary aggregation tested
- [ ] All tests pass with no skips or xfails
