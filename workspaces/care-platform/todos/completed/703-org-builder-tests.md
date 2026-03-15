# 703: Organization Builder Integration Tests

**Milestone**: 7 — Organization Builder
**Priority**: Medium (quality gate)
**Estimated effort**: Small
**Depends on**: 701, 702
**Status**: COMPLETED
**Completed**: 2026-03-12

## Description

End-to-end tests for the Organization Builder — from org definition to running platform.

## Tasks

- [x] Test: Terrene Foundation generation — TestOrgTemplateFoundation
  - foundation_template() produces valid org with dm-team, 5 agents, 5 envelopes, 1 workspace
  - Verify name, authority_id, team IDs
- [x] Test: Minimal organization — TestOrgTemplateMinimal
  - minimal_template() produces valid org with 1 agent, 1 team, 1 workspace, 1 envelope
- [x] Test: Round-trip — TestOrgFromConfigRoundTrip
  - PlatformConfig -> from_config() -> OrgDefinition preserves all data (agents, teams, envelopes, workspaces, authority)
- [x] Test: Validation errors caught — TestOrgValidationMissingEnvelope, TestOrgValidationDuplicateIDs
  - Missing envelope reference detected
  - Missing workspace reference detected
  - Duplicate agent/team/envelope/workspace IDs detected
- [x] Test: get_team_agents — TestOrgGetTeamAgents
  - Returns correct subset per team
  - Raises on unknown team
  - Handles empty team
- [x] Test: build() raises on invalid — TestOrgBuildValidation
  - build() raises ValueError with missing envelope
  - build() raises ValueError with missing workspace

## Acceptance Criteria

- [x] All generation scenarios tested
- [x] Round-trip produces identical results
- [x] Terrene Foundation generation validates against DM team config
- [x] Integration tests passing

## Implementation

- `tests/unit/org/test_builder.py` — 25+ test methods across 8 test classes
