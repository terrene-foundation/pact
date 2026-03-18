# Task 6033: Universal Agent Injection — Auto-Inject CoordinatorAgent into Every Team

**Milestone**: M40
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

Every generated team must include a `CoordinatorAgent` — the EATP-aware agent that manages task routing, trust verification, and human escalation for the team. Rather than requiring callers to manually add a coordinator to every team definition, the `OrgGenerator` automatically injects one when building from YAML.

The `CoordinatorAgent` definition comes from the `coordinator` role in `RoleCatalog`. If the input YAML already defines a coordinator-role agent for a team, the generator does not add a second one (idempotent).

## Acceptance Criteria

- [ ] `OrgGenerator` injects one `CoordinatorAgent` per team that does not already have one
- [ ] The injected coordinator uses the `coordinator` role definition from `RoleCatalog` (SHARED_PLANNING posture, coordinator capabilities)
- [ ] Injection is idempotent: if coordinator already present, no duplicate is added
- [ ] The coordinator agent ID follows a predictable naming scheme: `{team_id}_coordinator`
- [ ] `validate_org_detailed()` passes on teams with auto-injected coordinators
- [ ] Unit test: generate a team with only non-coordinator roles, verify coordinator appears in output
- [ ] Unit test: generate a team that already has a coordinator, verify no duplicate

## Dependencies

- Task 6030 (RoleCatalog with coordinator role definition)
- Task 6032 (OrgGenerator where injection logic lives)
