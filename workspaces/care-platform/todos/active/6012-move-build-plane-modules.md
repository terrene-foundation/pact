# Task 6012: Move Build-Plane Modules into build/

**Milestone**: M38
**Priority**: Critical
**Effort**: Large
**Status**: Active

## Description

Move all Build Plane source modules into the new `src/care_platform/build/` package. Build Plane modules are those used to define organizations — schemas, templates, the org builder, CLI, bootstrap, and workspace config.

Modules to move:

- `org/` — OrgDefinition, OrgBuilder, TeamConfig, AgentDefinition
- `templates/` — built-in org templates
- `verticals/` — vertical-specific org definitions (e.g., DM team)
- `workspace/` — workspace model and config
- `config/` — platform configuration schemas
- `bootstrap.py` — platform bootstrap entry point
- `cli/` — CLI commands (care org, care workspace, etc.)

This task covers only the file moves and within-module relative imports. Cross-module imports are updated in task 6014.

## Acceptance Criteria

- [ ] All build-plane source files are under `src/care_platform/build/`
- [ ] Each moved module has its own `__init__.py` with `__all__`
- [ ] Relative imports within the `build/` subtree are correct
- [ ] `src/care_platform/build/__init__.py` re-exports the primary public API (OrgBuilder, OrgDefinition, etc.)
- [ ] CLI entry point in `pyproject.toml` updated to point to new path
- [ ] Git history preserved (use `git mv`)

## Dependencies

- Task 6010 (directory structure must exist)
- Can be done in parallel with 6011 and 6013

## Risk

CLI entry point path change must be coordinated with pyproject.toml `[project.scripts]` update. Verify CLI still works after move.
