# 701: Organization Definition Schema

**Milestone**: 7 — Organization Builder
**Priority**: Medium (Phase 5 — depends on all prior milestones)
**Estimated effort**: Medium
**Depends on**: Milestones 1-5
**Status**: COMPLETED
**Completed**: 2026-03-12

## Description

Define the organizational schema — how an organization describes its structure, teams, roles, and governance model. The Organization Builder auto-generates agent teams, constraint envelopes, and workspaces from this definition.

## Tasks

- [x] Define `care_platform/org/builder.py` — OrgDefinition model:
  - org_id, name, authority_id (genesis authority)
  - teams (list of TeamConfig)
  - agents (list of AgentConfig)
  - envelopes (list of ConstraintEnvelopeConfig)
  - workspaces (list of WorkspaceConfig)
- [x] Define organization configuration format — uses existing PlatformConfig YAML format
- [x] Validate organization configs — validate_org() method:
  - Duplicate ID detection across all entity types
  - Agent envelope reference resolution
  - Team workspace reference resolution
- [x] Write unit tests for schema validation — TestOrgDefinition, TestOrgValidationMissingEnvelope, TestOrgValidationDuplicateIDs

## Acceptance Criteria

- [x] Organization schema captures all structural elements (teams, agents, envelopes, workspaces)
- [x] YAML format human-readable via PlatformConfig schema
- [x] Validation catches inconsistencies (missing envelope, missing workspace, duplicate IDs)
- [x] Unit tests passing

## Implementation

- `care_platform/org/builder.py` — OrgDefinition class with validate_org()
- `tests/unit/org/test_builder.py` — TestOrgDefinition, TestOrgValidationMissingEnvelope, TestOrgValidationDuplicateIDs
