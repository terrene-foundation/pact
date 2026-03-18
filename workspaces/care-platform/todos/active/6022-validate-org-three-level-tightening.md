# Task 6022: Extend validate_org_detailed() for 3-Level Monotonic Tightening

**Milestone**: M39
**Priority**: Critical
**Effort**: Large
**Status**: Active

## Description

Extend the existing `validate_org_detailed()` function (or create a new `validate_departments()` sub-validator called from it) to enforce the 3-level monotonic tightening rule across departments.

The rule: for every constraint dimension (Financial, Operational, Temporal, Data Access, Communication), the limit at each level must be less than or equal to the limit at the level above it.

```
org.envelope.financial_limit
  >= dept.envelope.financial_limit
    >= team.envelope.financial_limit
      >= agent.envelope.financial_limit
```

Violations should produce named `ValidationError` entries with:

- Which department, team, or agent violated the rule
- Which constraint dimension
- What the conflicting values are

## Acceptance Criteria

- [ ] `validate_org_detailed()` checks org → department envelope monotonic tightening for all 5 dimensions
- [ ] `validate_org_detailed()` checks department → team envelope monotonic tightening for all 5 dimensions
- [ ] Existing team → agent monotonic tightening check still works
- [ ] Violations produce clear, named `ValidationError` objects (not bare exceptions)
- [ ] Validation passes for correctly tightened hierarchies
- [ ] Validation fails fast on first violation per dimension (or collects all violations — choose one approach and document it)
- [ ] Unit tests: valid hierarchy passes, 5 invalid cases (one per dimension) each produce expected error
- [ ] Integration test: a full org with 3 departments, multiple teams each, passes validation

## Dependencies

- Task 6021 (OrgDefinition must have departments field before validation can use it)
