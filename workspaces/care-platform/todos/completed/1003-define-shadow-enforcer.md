# 1003: Define ShadowEnforcer in CARE Platform Context (H-3)

**Milestone**: 10 — Red Team Findings
**Priority**: Medium (referenced but never defined)
**Estimated effort**: Small
**Depends on**: 208

## Description

Red team finding H-3: ShadowEnforcer is referenced throughout the analysis but never fully defined in the CARE Platform context. Todo 208 implements it — this todo ensures the concept is properly documented.

## Tasks

- [ ] Create `docs/concepts/shadow-enforcer.md`:
  - What: Parallel trust evaluation that runs without enforcement
  - Why: Provides empirical evidence for trust posture upgrades
  - How: Evaluates every action against current and potential future constraint envelopes
  - Metrics: Block rate, hold rate, pass rate, per-agent breakdowns
  - Usage: Deploy for 2-4 weeks before any posture upgrade
  - Three-phase rollout: ShadowEnforcer → tune thresholds → StrictEnforcer
- [ ] Ensure all documents referencing ShadowEnforcer link to this definition
- [ ] Verify ShadowEnforcer is included in architecture documentation (todo 802)

## Acceptance Criteria

- ShadowEnforcer concept fully documented
- All references link to definition
- Included in architecture docs
