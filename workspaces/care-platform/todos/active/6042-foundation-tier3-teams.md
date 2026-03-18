# Task 6042: Define Tier 3 Teams — Certification, Training, Legal

**Milestone**: M41
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

Define the 3 Tier 3 (specialized, lower-frequency) teams of the Terrene Foundation.

Tier 3 teams:

1. **Certification** — CARE/EATP/CO conformance certification program
2. **Training** — educational resources, workshops, learning paths
3. **Legal** — IP management, license compliance, contributor agreements

These teams operate with lower operational tempo but higher consequence actions (especially Legal). Legal team should have very conservative autonomous action limits — most actions HELD for human approval.

## Acceptance Criteria

- [ ] All 3 Tier 3 teams defined in `build/templates/builtin/foundation/tier3_teams.yaml`
- [ ] Legal team envelope reflects high-consequence, low-autonomy profile (most dimensions at HELD threshold)
- [ ] Certification team envelope reflects moderate autonomy for assessment tasks
- [ ] Training team envelope reflects broader operational latitude for content creation
- [ ] `validate_org_detailed()` passes for each team in isolation
- [ ] Teams are referenced from department groupings (task 6043)

## Dependencies

- Tasks 6040, 6041 (Tier 1 and 2 should be done first for consistency)
- Task 6032 (OrgGenerator YAML format)
