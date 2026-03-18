# Task 6023: Update Templates to Include Department Grouping

**Milestone**: M39
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

The existing built-in org templates (e.g., `dm_team_template`, `research_team_template`, and any others) define teams but have no department structure. Update templates so they include at least one example department grouping, demonstrating the 3-level hierarchy in practice.

New templates that warrant a department layer (multi-team templates) should define departments from the start. Single-team templates may group the single team into a department or leave departments empty (both are valid).

## Acceptance Criteria

- [ ] All multi-team built-in templates include at least one `DepartmentConfig` grouping all their teams
- [ ] Department envelopes in templates are correctly set (tighter than or equal to org envelope, at least as permissive as team envelopes)
- [ ] Single-team templates document whether departments are optional or recommended
- [ ] `validate_org_detailed()` passes on all updated templates without errors
- [ ] Template docstrings updated to describe the department structure
- [ ] YAML representations of updated templates (if they exist as YAML) are also updated

## Dependencies

- Task 6021 (OrgDefinition must support departments)
- Task 6022 (validation must work before testing templates against it)
