# Todo 2403: Align Posture with eatp.postures

**Milestone**: M24 — EATP SDK Alignment
**Priority**: High
**Effort**: Small
**Source**: EATP SDK alignment — posture gap
**Dependencies**: 2101 (M21 complete), 105 (trust posture model — completed), 305 (posture history — completed)

## What

Use `eatp.postures.PostureStateMachine` as the base for CARE's posture management. CARE's `PostureEvidence` and upgrade requirement logic become `TransitionGuards` registered with the EATP state machine — they remain fully functional but are expressed in EATP terms.

The `NEVER_DELEGATED_ACTIONS` set (actions that can never be delegated regardless of posture) is a CARE-specific governance rule that the EATP SDK does not cover; it must be preserved as a CARE layer on top of the state machine.

Four EATP SDK gaps (P1-P4) require adapters. Each must be marked `# EATP-GAP: <gap-id>`.

## Where

- `src/care_platform/trust/posture.py` — use `eatp.postures.PostureStateMachine` as the base; register `PostureEvidence` checks as `TransitionGuards`; preserve `NEVER_DELEGATED_ACTIONS`; add 4 gap adapters with `# EATP-GAP` markers

## Evidence

- [ ] `PostureStateMachine` from `eatp.postures` is used as the base, not a hand-rolled state machine
- [ ] All 5 posture levels (PSEUDO_AGENT, SUPERVISED, SHARED_PLANNING, CONTINUOUS_INSIGHT, DELEGATED) are reachable via state transitions
- [ ] `PostureEvidence` logic is implemented as `TransitionGuards` registered with the EATP state machine
- [ ] `NEVER_DELEGATED_ACTIONS` set is preserved and enforced independently of posture level
- [ ] Posture upgrade and downgrade workflows continue to function correctly
- [ ] Exactly 4 gap adapter blocks present, each marked `# EATP-GAP: P1` through `# EATP-GAP: P4`
- [ ] All existing posture model and posture history tests pass
