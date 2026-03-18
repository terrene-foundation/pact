# Task 6043: Create Department Groupings for All 11 Teams

**Milestone**: M41
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

Group all 11 Foundation teams into departments using the `DepartmentConfig` model. Departments represent logical organizational units with shared budget authority and governance scope.

Proposed department structure (subject to review):

- **External Affairs** — Media/DM, Partnerships, Website (Tier 1 external teams)
- **Standards and Governance** — Standards, Governance, Legal, Certification (Tier 1-3 standards teams)
- **Ecosystem Growth** — Developer Relations, Community, Training (community and adoption teams)
- **Operations** — Finance (standalone operational team)

Each department gets a `DepartmentConfig` with an envelope derived from the org envelope but appropriate to the department's risk profile and budget authority.

## Acceptance Criteria

- [ ] All 11 teams assigned to exactly one department (no team in two departments, no team orphaned)
- [ ] `DepartmentConfig` objects defined for all 4 departments (or revised structure)
- [ ] Department envelopes are correctly positioned between org envelope and team envelopes (monotonic tightening)
- [ ] Full Foundation org with all departments passes `validate_org_detailed()`
- [ ] Department YAML defined in `build/templates/builtin/foundation/departments.yaml`
- [ ] Comments explain the department structure rationale

## Dependencies

- Tasks 6040, 6041, 6042 (all 11 teams defined)
- Task 6022 (department validation working)
