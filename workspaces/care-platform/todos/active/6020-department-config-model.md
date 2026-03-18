# Task 6020: Create DepartmentConfig Model

**Milestone**: M39
**Priority**: Critical
**Effort**: Medium
**Status**: Active

## Description

Add a `DepartmentConfig` model that sits between the organization level and the team level. A department groups teams under a common constraint envelope, enabling 3-level monotonic tightening: organization → department → team → agent.

The model lives in `src/care_platform/build/org/department.py` (post-M38 structure).

Fields:

- `id: str` — unique identifier (slug format, e.g., "engineering")
- `name: str` — human-readable display name
- `teams: list[str]` — list of team IDs belonging to this department
- `head: str | None` — optional agent ID of the department head/coordinator
- `envelope: ConstraintEnvelope` — the department-level constraint envelope (must be tighter than or equal to the org envelope, and at least as permissive as the tightest team envelope)

## Acceptance Criteria

- [ ] `DepartmentConfig` dataclass/Pydantic model created in `build/org/department.py`
- [ ] All five constraint dimensions (Financial, Operational, Temporal, Data Access, Communication) represented in the envelope field
- [ ] `DepartmentConfig` is exported from `care_platform.build.org`
- [ ] Model includes `model_validate` / `from_dict` convenience constructor
- [ ] Unit tests for model instantiation, field validation, and serialization to/from dict
- [ ] Type annotations are complete and mypy-clean

## Dependencies

- Task 6010 (directory structure)
- Tasks 6011-6015 (M38 restructure complete, so this task uses the new path structure)
