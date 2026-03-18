# Task 6021: Add departments Field to OrgDefinition and Update OrgBuilder

**Milestone**: M39
**Priority**: Critical
**Effort**: Medium
**Status**: Active

## Description

Extend `OrgDefinition` with an optional `departments: list[DepartmentConfig]` field, and add `add_department()` to `OrgBuilder` so callers can register departments fluently alongside teams.

Teams that belong to a department are still defined as `TeamConfig` objects — the department references them by team ID. A team without a department assignment is valid (standalone team at org level).

## Acceptance Criteria

- [ ] `OrgDefinition.departments: list[DepartmentConfig]` field added (default empty list)
- [ ] `OrgBuilder.add_department(department: DepartmentConfig) -> OrgBuilder` added (fluent builder pattern)
- [ ] `OrgBuilder` validates that all team IDs referenced in departments exist in the org's team list at build time
- [ ] `OrgDefinition` serializes/deserializes departments correctly (including via YAML round-trip)
- [ ] Existing org definitions without departments continue to work unchanged (backward compatible)
- [ ] `OrgBuilder` fluent API example added to docstring showing department usage
- [ ] Unit tests: add department to builder, build org, verify department appears in output

## Dependencies

- Task 6020 (DepartmentConfig model must exist)
