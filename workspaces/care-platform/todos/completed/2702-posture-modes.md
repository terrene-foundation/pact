# Todo 2702: All Trust Posture Execution Modes

**Milestone**: M27 — Agent Execution Runtime
**Priority**: High
**Effort**: Large
**Source**: Phase 3 requirement
**Dependencies**: 2701

## What

Implement all five trust posture execution modes in the execution runtime. Each mode must produce the exact behaviour specified by the CARE standard:

- **PSEUDO_AGENT**: All actions blocked before reaching the LLM. No execution permitted.
- **SUPERVISED**: Every action placed in the HELD queue before execution. Nothing auto-approves.
- **SHARED_PLANNING**: Planning actions (reasoning, drafting) auto-approve; consequential actions (writes, sends, calls) require HELD approval.
- **CONTINUOUS_INSIGHT**: All actions execute autonomously within the constraint envelope; only boundary-crossing actions are HELD.
- **DELEGATED**: All actions within the constraint envelope auto-approve. Actions outside the envelope are BLOCKED.

The runtime must read the current posture from the agent's trust record at the time of each action (not cached at startup).

## Where

- `src/care_platform/execution/runtime.py`

## Evidence

- [ ] PSEUDO_AGENT: every submitted action returns BLOCKED before any LLM call is made
- [ ] SUPERVISED: every submitted action is placed in the HELD queue regardless of constraint state
- [ ] SHARED_PLANNING: planning-class actions auto-approve; consequential-class actions are HELD
- [ ] CONTINUOUS_INSIGHT: within-envelope actions auto-approve; boundary-crossing actions are HELD
- [ ] DELEGATED: within-envelope actions auto-approve; out-of-envelope actions are BLOCKED
- [ ] Posture is read from the trust record at action time (not cached)
- [ ] Unit tests cover all five posture modes with at least two action scenarios each
