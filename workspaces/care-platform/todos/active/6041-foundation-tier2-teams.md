# Task 6041: Define Tier 2 Teams — Community, Developer Relations, Finance

**Milestone**: M41
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

Define the 3 Tier 2 (important but internally-supporting) teams of the Terrene Foundation.

Tier 2 teams:

1. **Community** — forum, Discord, contributor onboarding, community health
2. **Developer Relations** — SDK adoption, developer experience, technical evangelism
3. **Finance** — budget tracking, grant management, transparency reporting

For each team, define roles, capabilities, and envelope constraints appropriate to the team's function and risk profile. Finance team will have the tightest financial constraints; Community and Dev Relations will have broader operational latitude.

## Acceptance Criteria

- [ ] All 3 Tier 2 teams defined in `build/templates/builtin/foundation/tier2_teams.yaml`
- [ ] Each team has at minimum: coordinator + 2 specialist roles
- [ ] Finance team envelope has conservative financial limits (appropriate for budget oversight without autonomous spend)
- [ ] `validate_org_detailed()` passes for each team in isolation
- [ ] Teams are referenced from department groupings (task 6043)
- [ ] YAML files have comments explaining design choices

## Dependencies

- Task 6040 (Tier 1 teams should be defined first to ensure consistency in format and approach)
- Task 6032 (OrgGenerator YAML format established)
