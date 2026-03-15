# 603: DM Team — Verification Gradient Rules Configuration

**Milestone**: 6 — DM Team Vertical
**Priority**: High (defines exactly what each DM agent can/cannot do at runtime)
**Estimated effort**: Medium
**Status**: COMPLETED
**Completed**: 2026-03-12

## Description

Configure the verification gradient rules for the DM team based on the detailed action tables from the analysis. The rules define AUTO_APPROVED, FLAGGED, HELD, and BLOCKED actions for DM agents.

## Tasks

- [x] Define gradient rules for DM team:
  - AUTO*APPROVED: read*_, draft\__, analyze\_\* — safe internal operations
  - FLAGGED: default level for unmatched actions
  - HELD: approve*\*, publish*_, external\__ — require human review
  - BLOCKED: delete\_\*, modify_constraints — rejected outright
- [x] Configure DM-specific gradient defaults:
  - Default level: FLAGGED (conservative default)
  - External publication: always HELD
  - Destructive operations: always BLOCKED
- [x] Implement gradient configuration in code (DM_VERIFICATION_GRADIENT)
- [x] Write tests: verify all pattern levels match expected gradient classification

## Acceptance Criteria

- [x] All action categories correctly classified (AUTO_APPROVED, FLAGGED, HELD, BLOCKED)
- [x] Default level is FLAGGED (conservative)
- [x] Gradient applied to DM team via DM_TEAM.verification_gradient
- [x] Tests cover all four gradient levels — TestDMVerificationGradient

## Notes

Rules implemented as Python `VerificationGradientConfig` (not YAML). The YAML configuration loading described in the original todo (603) is a future enhancement. Core gradient classification is functional and tested.

## Implementation

- `care_platform/verticals/dm_team.py` — DM_VERIFICATION_GRADIENT with 8 gradient rules
- `tests/unit/verticals/test_dm_team.py` — TestDMVerificationGradient (9 test methods)

## Dependencies

- 104: Verification gradient engine (configurable) — COMPLETED
- 601: DM team agent definitions — COMPLETED
