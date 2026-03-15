# 702: Auto-Generate Agent Definitions from Org Structure

**Milestone**: 7 — Organization Builder
**Priority**: Medium
**Estimated effort**: Medium
**Depends on**: 701, 108
**Status**: COMPLETED
**Completed**: 2026-03-12

## Description

Given an organization definition, auto-generate all agent definitions, constraint envelopes, capability attestations, and delegation chains via a fluent builder API and pre-built templates.

## Tasks

- [x] Implement `care_platform/org/builder.py` — OrgBuilder class:
  - Fluent API: add_workspace(), add_envelope(), add_agent(), add_team(), build()
  - build() runs validate_org() and raises ValueError on failure
  - from_config(PlatformConfig) class method for round-trip conversion
- [x] Implement template library — OrgTemplate class:
  - foundation_template() — Terrene Foundation with DM team (5 agents, 5 envelopes, 1 workspace)
  - minimal_template(org_name) — single agent, team, workspace, envelope for quick starts
- [x] Builder validates configuration at build() time (no silently invalid orgs)
- [x] Write integration tests — TestOrgBuilder, TestOrgFromConfigRoundTrip, TestOrgTemplateMinimal, TestOrgTemplateFoundation

## Acceptance Criteria

- [x] Full platform configuration generated from org definition via OrgBuilder.build()
- [x] Templates cover Foundation structure (foundation_template) and minimal case (minimal_template)
- [x] Generated configuration passes validation
- [x] Integration tests verify correctness

## Notes

The spec described `build_from_org(organization)` as a standalone function; implementation uses OrgBuilder class with fluent API which is equivalent and more ergonomic. YAML template files (media-team.yaml, governance-team.yaml, etc.) are deferred — covered by todo 704.

## Implementation

- `care_platform/org/builder.py` — OrgBuilder, OrgTemplate
- `tests/unit/org/test_builder.py` — TestOrgBuilder, TestOrgFromConfigRoundTrip, TestOrgBuildValidation
