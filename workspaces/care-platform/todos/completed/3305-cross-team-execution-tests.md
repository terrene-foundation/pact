# Todo 3305: Cross-Team Execution Tests

**Milestone**: M33 — Cross-Team Execution
**Priority**: High
**Effort**: Large
**Source**: Phase 4 plan
**Dependencies**: 3301, 3302, 3303, 3304

## What

TDD test file covering all M33 deliverables. Tests must be written to the public contracts of the modules under test — no internal state inspection unless testing a clearly defined internal helper.

Test groups required:

**Bridge Verification Pipeline (3301)**

- Cross-team task with an ACTIVE bridge passes verification
- Cross-team task with no bridge at all is BLOCKED
- Cross-team task with a SUSPENDED bridge is BLOCKED
- Effective envelope is intersected from bridge and agent envelopes before gradient evaluation
- Effective posture reflects the more restrictive of the two teams' postures

**Effective Envelope Application (3201 integration)**

- Cross-team task respects the intersected envelope; an action allowed by one team but denied by the other is BLOCKED

**Effective Posture Application (3103 integration)**

- SUPERVISED source team + CONTINUOUS_INSIGHT target team = SUPERVISED behavior applied during execution

**Bridge-Level Revocation (3302)**

- Bridge suspension invalidates delegations (cross-team tasks using those delegations fail)
- Bridge suspension is reversible: resuming the bridge restores delegation validity
- Bridge closure permanently revokes delegations (not restorable)
- Agent revocation cascades to that agent's bridge delegations across all bridges

**Ad-Hoc Bridge Management (3303)**

- `request_adhoc_bridge` auto-closes after response
- Pattern detection: N completions within the window returns a suggestion
- Fewer than N completions returns no suggestion
- FLAGGED event emitted when threshold is reached

**KaizenBridge Cross-Team Routing (3304)**

- Cross-team task routes through bridge, not the standard same-team path
- `BridgeDelegation` record created for the task
- Dual audit anchors created (one per team)
- Result includes bridge metadata (`bridge_id`, `effective_posture`, `effective_envelope_hash`)

**Error Cases**

- No bridge exists between teams: BLOCKED with descriptive reason
- Bridge exists but has expired: BLOCKED
- Agent's team cannot be determined: appropriate error raised

## Where

- `tests/unit/execution/test_bridge_execution.py`

## Evidence

- [ ] Test file exists at the specified path
- [ ] All bridge verification pipeline scenarios covered (active, no bridge, suspended)
- [ ] Effective envelope intersection tested end-to-end
- [ ] Effective posture min() logic tested with SUPERVISED + CONTINUOUS_INSIGHT case
- [ ] Bridge suspension invalidation and restoration tested
- [ ] Bridge closure permanent revocation tested
- [ ] Agent-to-bridge-delegation cascade tested
- [ ] Ad-hoc bridge auto-close tested
- [ ] Pattern detection threshold and FLAGGED event tested
- [ ] KaizenBridge dual audit anchor creation tested
- [ ] KaizenBridge bridge metadata in result tested
- [ ] All error cases covered with assertions on error type and message content
- [ ] All tests pass with no skips or xfails
