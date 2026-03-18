# Task 6040: Define Tier 1 Teams — Media/DM, Standards, Governance, Partnerships, Website

**Milestone**: M41
**Priority**: Critical
**Effort**: Large
**Status**: Active

## Description

Define the 5 Tier 1 (highest-priority, externally-facing) teams of the Terrene Foundation as `TeamConfig` objects using the OrgGenerator YAML format. These teams are the Foundation's primary operational teams.

Tier 1 teams:

1. **Media / Digital Media (DM)** — content creation, publication, community voice
2. **Standards** — CARE, EATP, CO specification authorship and maintenance
3. **Governance** — constitutional oversight, EP management, compliance
4. **Partnerships** — contributor framework, external relations
5. **Website** — terrene.foundation and terrene.dev web presence

For each team, define:

- Team ID and name
- Roles (from RoleCatalog) — minimum: coordinator + 2-3 specialist roles
- Team-specific capabilities
- Envelope constraints appropriate to the team's risk profile

## Acceptance Criteria

- [ ] All 5 Tier 1 teams defined in `build/templates/builtin/foundation/tier1_teams.yaml`
- [ ] Each team has a coordinator role defined (or will receive one via auto-injection)
- [ ] Each team's envelope is tighter than the org-level envelope
- [ ] `validate_org_detailed()` passes for each team in isolation
- [ ] Teams are referenced from the department groupings task (6043)
- [ ] YAML files are well-documented with comments explaining role and envelope choices

## Dependencies

- Task 6032 (OrgGenerator, so YAML format is established)
- Tasks 6024 (department validation working, so team definitions can be tested against it)
