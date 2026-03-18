# Task 6024: Tests for Department Validation, Tightening, and Builder Integration

**Milestone**: M39
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

Comprehensive test suite covering all aspects of the Department Layer: model instantiation, OrgBuilder fluent API, monotonic tightening validation (valid and invalid cases), serialization round-trips, and template compatibility.

## Acceptance Criteria

- [ ] `tests/unit/test_department_config.py`: model creation, field validation, serialization
- [ ] `tests/unit/test_org_builder_departments.py`: add_department(), build(), verify departments in output, backward compatibility (org without departments still builds)
- [ ] `tests/unit/test_validate_org_departments.py`: 3-level tightening — 5 passing cases (one per dimension), 5 failing cases (one per dimension with specific violation)
- [ ] `tests/integration/test_department_layer.py`: full org with departments → validate → serialize → deserialize → validate again (round-trip)
- [ ] All new tests pass with `pytest -x`
- [ ] No existing tests broken by the department layer additions

## Dependencies

- Tasks 6020, 6021, 6022, 6023 (all department layer components must be implemented first)
