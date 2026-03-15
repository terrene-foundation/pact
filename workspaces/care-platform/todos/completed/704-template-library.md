# 704: Constraint Envelope Template Library

**Milestone**: 7 — Organization Builder
**Priority**: Medium (makes the platform accessible to new organizations)
**Estimated effort**: Medium

## Description

Build a template library of pre-configured constraint envelopes for common team types and agent roles. Instead of every organization defining envelopes from scratch, they start from a template and override what they need. The DM team envelopes from Milestone 6 become the first templates.

## Tasks

- [ ] Create `care_platform/templates/` directory:
  - `care_platform/templates/teams/` — team-level constraint templates
  - `care_platform/templates/agents/` — agent role-level constraint templates
  - `care_platform/templates/orgs/` — complete org structure templates
- [ ] Implement Media/Marketing team templates:
  - `templates/teams/media.yaml` — Media team with standard 5-agent structure
  - `templates/agents/content-creator.yaml` — Content Creator role template
  - `templates/agents/analytics.yaml` — Analytics role template
  - `templates/agents/scheduler.yaml` — Scheduling role template
  - Directly derived from DM team specification (601-605)
- [ ] Implement Governance/Management team templates:
  - `templates/teams/governance.yaml` — Governance team
  - `templates/agents/compliance-monitor.yaml` — Compliance role
  - `templates/agents/meeting-coordinator.yaml` — Meeting coordination role
- [ ] Implement Standards/Research team templates:
  - `templates/teams/standards.yaml` — Standards team
  - `templates/agents/spec-drafter.yaml` — Specification drafting role
  - `templates/agents/cross-reference-validator.yaml` — Validation role
- [ ] Implement Partnerships/Outreach team templates:
  - `templates/teams/partnerships.yaml` — Partnerships team
  - `templates/agents/researcher.yaml` — Research role
  - `templates/agents/grant-writer.yaml` — Grant writing role (stricter financial controls)
- [ ] Implement template inheritance:
  - Templates can extend other templates (`extends: content-creator`)
  - Override only what differs
  - Validate that overrides cannot expand constraints (monotonic tightening preserved)
- [ ] Implement template registry:
  - `TemplateRegistry.list()` — available templates
  - `TemplateRegistry.get(name)` — load a template
  - `TemplateRegistry.apply(template, overrides)` — template + org-specific overrides
- [ ] Write unit tests for template loading, inheritance, and override validation

## Acceptance Criteria

- Templates for all four Foundation team types defined
- Template inheritance works correctly
- Override validation prevents constraint expansion
- Template registry queryable
- Unit tests passing

## Dependencies

- 701: Org definition schema (templates feed into org definitions)
- 601-605: DM team as source of media team template

## References

- Full team inventory: `01-analysis/01-research/06-architecture-gap-analysis.md`
- Analysis synthesis: `01-analysis/02-synthesis.md` (team inventory table)
