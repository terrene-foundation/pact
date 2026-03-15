# 705: Organization Builder CLI Commands

**Milestone**: 7 — Organization Builder
**Priority**: Medium (makes the platform usable without Python knowledge)
**Estimated effort**: Small

## Description

Implement CLI commands that walk users through setting up a CARE-governed organization from scratch. The Organization Builder CLI is the primary user-facing interface for new platform adopters — it should make the platform approachable without requiring direct Python API usage.

## Tasks

- [ ] Implement `care-platform init` command:
  - Interactive wizard: name, domain, genesis authority
  - Generate Ed25519 key pair for genesis signing
  - Store key in `.env` (never in source)
  - Create genesis record
  - Output: platform initialized, ready to add teams
- [ ] Implement `care-platform team add` command:
  - Interactive: team name, function (picks template), team lead name
  - Apply template, prompt for overrides
  - Generate agent definitions
  - Create workspace structure
  - Output: team added, agents defined
- [ ] Implement `care-platform team establish` command:
  - Takes a team that has been defined but not yet cryptographically established
  - Creates EATP delegation chain: genesis → team lead → specialists
  - Signs all delegation records
  - Registers agents in registry
  - Output: team trust chain established, agents active at SUPERVISED posture
- [ ] Implement `care-platform status` command:
  - Show: active teams, agent count per team, pending HELD actions, expiring envelopes
  - Color-coded health summary (green/yellow/red per team)
- [ ] Implement `care-platform validate` command:
  - Validate a YAML org/team/agent configuration without applying it
  - Report all validation errors with clear descriptions
- [ ] Write integration tests for all CLI commands

## Acceptance Criteria

- `care-platform init` creates genesis record end-to-end
- `care-platform team add` + `establish` produces functioning team
- `care-platform status` shows accurate platform state
- `care-platform validate` catches all schema errors
- Integration tests covering each command

## Dependencies

- 702: Auto-generate agents (builder logic)
- 704: Template library (template selection in `team add`)
- 202: Genesis record integration (used by `init`)
- 112: Package CLI entry point (extends existing CLI)

## References

- Existing CLI: `care_platform/cli/__init__.py` (from 112)
- Click documentation for interactive prompts
