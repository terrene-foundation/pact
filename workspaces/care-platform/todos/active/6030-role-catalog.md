# Task 6030: Create RoleCatalog with Standard Role Definitions

**Milestone**: M40
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

Create a `RoleCatalog` that provides standard role definitions for common agent roles in governed organizations. Each role definition specifies: capabilities the role typically has, a default trust posture, and recommended envelope constraints for each of the 5 dimensions.

The catalog is used by `OrgGenerator` (task 6032) to populate teams when generating from high-level YAML input. It is also useful standalone for building custom orgs.

Standard roles to include (minimum):

- `coordinator` — team lead, oversees other agents, SHARED_PLANNING posture
- `analyst` — research and analysis, SUPERVISED posture
- `writer` — content creation, SUPERVISED posture
- `reviewer` — quality review, SUPERVISED posture
- `developer` — code implementation, SUPERVISED posture
- `ops` — operational tasks, SUPERVISED posture
- `compliance` — governance enforcement, SHARED_PLANNING posture

## Acceptance Criteria

- [ ] `RoleCatalog` class created in `src/care_platform/build/org/role_catalog.py`
- [ ] Each role entry has: `id`, `display_name`, `capabilities: list[str]`, `default_posture: TrustPosture`, `default_envelope: ConstraintEnvelope`
- [ ] `RoleCatalog.get(role_id: str) -> RoleDefinition` returns the role or raises `KeyError`
- [ ] `RoleCatalog.list() -> list[str]` returns all available role IDs
- [ ] At least 7 standard roles defined (the list above)
- [ ] `RoleCatalog` is exported from `care_platform.build.org`
- [ ] Unit tests for get(), list(), and that default envelopes are valid (non-negative limits, valid postures)

## Dependencies

- Tasks 6010-6015 (M38 restructure, so this task uses new path structure)
- Task 6020 (ConstraintEnvelope model must be available at new path)
