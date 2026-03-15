# 601: Define DM Team Lead Agent with Constraint Envelope

**Milestone**: 6 — DM Team Vertical
**Priority**: High (team lead is root of DM delegation chain)
**Estimated effort**: Medium
**Depends on**: 103, 108
**Status**: COMPLETED
**Completed**: 2026-03-12

## Description

Define the Digital Marketing Team Lead agent — the coordinator for all DM specialist agents. Includes full constraint envelope across all five CARE dimensions, agent definition, and capability attestation.

## Tasks

- [x] Create agent definition for DM Team Lead:
  - Role: Coordinate DM team, review drafts, maintain editorial calendar, generate reports
  - Allowed tools: workspace read/write (drafts), team coordination, scheduling review
  - LLM preference: Claude (for complex coordination tasks)
- [x] Create constraint envelope (from analysis):
  - Financial: $0 direct spending. May request budget but cannot approve.
  - Operational: Coordinate team, review drafts, maintain calendar. BLOCKED: publish externally, modify brand guidelines, engage legal/regulatory.
  - Temporal: 06:00-22:00 active (implementation uses broader window).
  - Data Access: Read: public Foundation content, published standards, social analytics. Write: internal drafts, editorial calendar. NO: member PII, financial records, legal, board minutes.
  - Communication: Internal channels only. Cannot send external email, post to social, respond to external comments.
- [x] Create capability attestation for Team Lead (via AgentConfig capabilities list)
- [x] Define verification gradient rules specific to Team Lead actions (DM_VERIFICATION_GRADIENT)
- [x] Write validation tests (envelope consistency, attestation-envelope alignment)

## Acceptance Criteria

- [x] Agent definition complete and valid — `DM_TEAM_LEAD` in `care_platform/verticals/dm_team.py`
- [x] Constraint envelope covers all five dimensions with specific rules — `DM_LEAD_ENVELOPE`
- [x] Capability attestation consistent with envelope — capabilities list on AgentConfig
- [x] Validation tests passing — `tests/unit/verticals/test_dm_team.py`

## Implementation

- `care_platform/verticals/dm_team.py` — DM_TEAM_LEAD, DM_LEAD_ENVELOPE, validate_dm_team()
- `tests/unit/verticals/test_dm_team.py` — TestDMTeamAgents, TestDMTeamEnvelopeReferences

## References

- `01-analysis/01-research/03-eatp-trust-model-dm-team.md` — Complete DM trust model
