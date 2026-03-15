# 105: Create Trust Posture Model

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (core EATP concept)
**Estimated effort**: Medium

## Description

Implement the trust posture model — the five-level system describing how much autonomy an agent has earned through demonstrated performance. Postures upgrade gradually based on evidence and downgrade instantly on incidents.

## Tasks

- [ ] Define `care_platform/trust/posture.py`:
  - `TrustPosture` enum with FIVE levels (not four — include Pseudo-Agent):
    1. **PSEUDO_AGENT** — Zero autonomy; agent is interface for human action only
    2. **SUPERVISED** — Internal operations auto-execute; all external actions require human approval
    3. **SHARED_PLANNING** — Human approves at batch level (weekly calendar, not per-post)
    4. **CONTINUOUS_INSIGHT** — Human reviews dashboard; flagged items escalated
    5. **DELEGATED** — Select tasks fully autonomous; periodic audit review
  - `PostureTransitionRules` — Evidence requirements for each upgrade:
    - Minimum track record days
    - Minimum successful operations
    - ShadowEnforcer pass rate threshold
    - No incidents in review period
  - `PostureHistory` — Track posture changes with evidence and timestamps
- [ ] Implement posture upgrade logic (gradual, evidence-based):
  - Check ShadowEnforcer metrics against transition thresholds
  - Require explicit human approval for each upgrade
  - Document evidence in posture history
- [ ] Implement posture downgrade logic (instant on incident):
  - Any trust violation → immediate downgrade (configurable: to Pseudo-Agent or one level down)
  - Log incident details and downgrade reason
- [ ] Implement "never fully delegated" list — actions that stay at Held regardless of posture:
  - Content strategy changes
  - Novel outreach
  - Crisis response
  - Financial decisions
- [ ] Write unit tests for:
  - All five posture levels
  - Upgrade with valid evidence
  - Upgrade blocked by insufficient evidence
  - Instant downgrade on incident
  - "Never delegated" list enforcement

## Acceptance Criteria

- All five postures modeled (including Pseudo-Agent)
- Upgrade requires evidence meeting configurable thresholds
- Downgrade is instant and logged
- "Never delegated" actions enforced regardless of posture
- Unit tests cover full lifecycle

## References

- EATP Core Thesis: Trust postures (5 levels including Pseudo-Agent)
- DM team posture plan: `01-analysis/01-research/03-eatp-trust-model-dm-team.md`
