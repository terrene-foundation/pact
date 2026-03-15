# 107: Create Trust Scoring Model

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: Medium (enables policy-driven auto-approval)
**Estimated effort**: Small

## Description

Implement trust scoring — the five-factor weighted scoring system that provides quantitative input for policy decisions (e.g., "auto-approve only for agents with grade B or above").

## Tasks

- [ ] Define `care_platform/trust/scoring.py`:
  - `TrustScore` model with five weighted factors:
    1. **Chain completeness** (30%) — Is the full delegation chain intact?
    2. **Delegation depth** (15%) — How many hops from genesis? (fewer = higher trust)
    3. **Constraint coverage** (25%) — Are all five dimensions defined?
    4. **Posture level** (20%) — Current trust posture
    5. **Chain recency** (10%) — How fresh is the chain? (recent re-verification = higher)
  - Score maps to letter grades: A (90-100), B (80-89), C (70-79), D (60-69), F (<60)
  - `calculate_trust_score(agent_id)` → TrustScore
- [ ] Implement grade-based policy evaluation:
  - `meets_threshold(score, required_grade)` → bool
  - Configurable per-action grade requirements
- [ ] Write unit tests for:
  - Score calculation with various factor combinations
  - Grade assignment
  - Threshold checking

## Acceptance Criteria

- Five-factor weighted scoring implemented
- Letter grades correctly assigned
- Policy threshold checking works
- Unit tests cover scoring edge cases

## References

- EATP Operations spec: Trust scoring (5-factor weighted, lines 209-219)
