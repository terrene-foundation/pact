# Task 6045: Foundation Org Full Validation Test Suite — Generate, Validate, Deploy, Query Round-Trip

**Milestone**: M41
**Priority**: Critical
**Effort**: Large
**Status**: Active

## Description

The dog-food test: run the complete Terrene Foundation org definition through the full platform stack — generate, validate, deploy to a live instance, and query back via the API. This is the integration test that proves the platform works end-to-end with a realistic, complex organization.

Stages:

1. **Generate**: `OrgGenerator.from_yaml(foundation.yaml)` produces an `OrgDefinition`
2. **Validate**: `validate_org_detailed()` passes with zero errors
3. **Deploy**: org is loaded into the running platform (via bootstrap or API)
4. **Query**: API endpoints return correct data for all 11 teams, all departments, all bridges
5. **Verify trust**: trust chain is valid, audit anchors created for the org deployment
6. **Revoke and re-deploy**: simulate a constraint envelope update and verify the audit chain records it

## Acceptance Criteria

- [ ] `tests/integration/test_foundation_org_round_trip.py` created
- [ ] Test generates Foundation org from YAML and passes validation (stage 1-2)
- [ ] Test deploys to a running platform instance using test fixtures (stage 3)
- [ ] Test queries `/api/v1/teams` and receives all 11 teams (stage 4)
- [ ] Test queries `/api/v1/departments` and receives all 4 departments (stage 4)
- [ ] Test queries `/api/v1/bridges` and receives all defined bridges (stage 4)
- [ ] Test verifies trust chain validity for the deployed org (stage 5)
- [ ] Test simulates envelope update and verifies audit anchor is recorded (stage 6)
- [ ] All stages pass without errors
- [ ] Test is marked as requiring real infrastructure (pytest.mark.integration) and runs in CI integration job

## Dependencies

- Tasks 6040-6044 (all 11 teams, departments, bridges defined)
- Task 6035 (auto-generation tests passing)
- Task 6022 (3-level validation working)
