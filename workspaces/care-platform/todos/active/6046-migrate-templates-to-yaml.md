# Task 6046: Migrate Existing Python Templates to YAML in build/templates/builtin/

**Milestone**: M41
**Priority**: Medium
**Effort**: Medium
**Status**: Active

## Description

The existing built-in templates are defined as Python code (dataclasses/functions returning `OrgDefinition` objects). Migrate them to YAML files in `build/templates/builtin/` so they can be used by the `OrgGenerator` and consumed via the `care org generate` CLI without requiring Python knowledge.

Templates to migrate:

- DM team template
- Research team template
- Any other existing built-in templates

Each YAML file should be self-contained and parseable by `OrgGenerator.from_yaml()`. The Python versions can be kept as wrappers that load the YAML, or deprecated.

## Acceptance Criteria

- [ ] Each existing built-in template has a corresponding `.yaml` file in `build/templates/builtin/`
- [ ] Each YAML template is valid input for `OrgGenerator.from_yaml()` and produces a validated `OrgDefinition`
- [ ] Existing Python API (e.g., `get_dm_team_template()`) still works — either loads from YAML or is kept as-is with a deprecation note
- [ ] `care org generate --template dm-team` command works (or equivalent template discovery)
- [ ] `validate_org_detailed()` passes on all migrated YAML templates
- [ ] Tests verify that YAML templates produce the same org structure as the Python equivalents (or document intentional differences)

## Dependencies

- Task 6032 (OrgGenerator must be able to parse the YAML format)
- Task 6034 (CLI must support template loading)
- Tasks 6023 (templates updated with department groupings)
