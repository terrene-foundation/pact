# Task 6035: Comprehensive Tests for Auto-Generation

**Milestone**: M40
**Priority**: High
**Effort**: Large
**Status**: Active

## Description

A comprehensive test suite for the entire auto-generation engine: RoleCatalog, EnvelopeDeriver, OrgGenerator, and coordinator injection. The core invariant: every organization produced by OrgGenerator must pass `validate_org_detailed()`.

## Acceptance Criteria

- [ ] `tests/unit/test_role_catalog.py`: all standard roles retrievable, invalid role raises KeyError, default envelopes have positive limits
- [ ] `tests/unit/test_envelope_deriver.py`: derive() with factors 0.5, 0.8, 1.0, derived <= parent for all dimensions, no negative outputs
- [ ] `tests/unit/test_org_generator.py`: single-team org, multi-team with department, org with custom envelope constraints — all pass validate_org_detailed()
- [ ] `tests/unit/test_coordinator_injection.py`: team without coordinator gets one injected, team with coordinator does not get a duplicate
- [ ] `tests/integration/test_org_generation_pipeline.py`: YAML input → OrgGenerator → OrgDefinition → validate_org_detailed() → serialize → deserialize → validate again (full round-trip)
- [ ] `tests/integration/test_org_generate_cli.py`: CLI command integration test using subprocess
- [ ] Property-based test (hypothesis or manual parameterization): 20+ randomly constructed org inputs, all must pass validation
- [ ] Zero failures on `pytest tests/unit/ tests/integration/ -x`

## Dependencies

- Tasks 6030-6034 (all auto-generation components must be implemented)
