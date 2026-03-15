# Todo 2402: Integrate Revocation with eatp.revocation

**Milestone**: M24 — EATP SDK Alignment
**Priority**: High
**Effort**: Medium
**Source**: EATP SDK alignment — revocation gap
**Dependencies**: 2101 (M21 complete), 207 (cascade revocation — completed)

## What

Integrate `RevocationManager` with `eatp.revocation.RevocationBroadcaster` so that CARE revocation events are published to the EATP event bus. External systems that subscribe to the EATP revocation stream will then receive CARE-originated events.

Six EATP SDK gaps (R1-R6) require adapters because the SDK does not yet cover them. These gaps include CARE-specific features: reparenting on cascade revocation (RT9-07 fix), cooling-off periods before re-delegation, and credential integration at revocation time. Each gap must be implemented as a thin adapter with a `# EATP-GAP: <gap-id>` comment.

Do not remove any CARE-specific behaviour. The reparenting logic, cooling-off periods, and credential revocation must be preserved and remain functional.

## Where

- `src/care_platform/trust/revocation.py` — wire `RevocationBroadcaster` at the point where a revocation completes; add 6 gap adapters with `# EATP-GAP` markers

## Evidence

- [ ] `RevocationManager.revoke()` publishes an event via `eatp.revocation.RevocationBroadcaster` after completing the revocation
- [ ] Reparenting logic (RT9-07) is preserved and functional
- [ ] Cooling-off period logic is preserved and functional
- [ ] Credential revocation integration is preserved and functional
- [ ] Exactly 6 gap adapter blocks present, each marked `# EATP-GAP: R1` through `# EATP-GAP: R6`
- [ ] All existing revocation and cascade revocation tests pass
- [ ] Integration test: revoke an agent; assert the event appears on the EATP broadcaster's event stream
