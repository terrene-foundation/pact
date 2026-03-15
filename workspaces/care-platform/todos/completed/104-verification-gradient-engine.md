# 104: Create Verification Gradient Engine

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (core EATP concept)
**Estimated effort**: Medium

## Description

Implement the verification gradient — the four-level classification system that determines how each agent action is handled: auto-approved, flagged, held, or blocked.

## Tasks

- [ ] Define `care_platform/constraint/gradient.py`:
  - `VerificationLevel` enum: AUTO_APPROVED, FLAGGED, HELD, BLOCKED
  - `VerificationResult` model: level, reason, constraint_dimension, action, agent_id, timestamp
  - `GradientEngine.classify(action, envelope)` → VerificationResult
- [ ] Implement classification logic:
  - **Auto-approved**: Action fully within all envelope dimensions, no near-boundary conditions
  - **Flagged**: Action within envelope but near a boundary (configurable threshold)
  - **Held**: Action requires human approval (external communication, strategy changes, sensitive topics)
  - **Blocked**: Action explicitly prohibited or outside envelope scope
- [ ] Implement three verification thoroughness levels (EATP spec):
  - **QUICK** (~1ms): Hash and expiration check only
  - **STANDARD** (~5ms): Capability and constraint validation
  - **FULL** (~50ms): Full cryptographic signature verification of entire chain
- [ ] Implement configurable near-boundary thresholds (e.g., "flag when rate limit is 90% consumed")
- [ ] Write unit tests for:
  - Each gradient level with concrete examples
  - Near-boundary flagging
  - Verification thoroughness levels
  - Multiple dimension evaluation (action touches multiple dimensions)

## Acceptance Criteria

- All four gradient levels correctly classified
- Three verification thoroughness levels implemented
- Near-boundary detection configurable
- Actions evaluated against all relevant constraint dimensions
- Unit tests cover all classification paths

## References

- EATP Operations spec: Verification levels (QUICK, STANDARD, FULL)
- DM team verification gradient examples: `01-analysis/01-research/03-eatp-trust-model-dm-team.md`
- EATP SDK Phase 1: Existing verification gradient model
