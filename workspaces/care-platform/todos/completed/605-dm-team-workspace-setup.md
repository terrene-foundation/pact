# 605: DM Team Workspace Setup

**Milestone**: 6 — DM Team Vertical
**Priority**: Medium (operational workspace for DM team)
**Estimated effort**: Small

## Description

Initialize the DM team workspace (`workspaces/media/`) as a fully governed CARE workspace with proper directory structure, knowledge base seeding, and registration in the platform's workspace registry. The DM team's workspace is their institutional memory — structured for the Knowledge Curator to maintain.

## Tasks

- [ ] Initialize workspace structure at `workspaces/media/`:
  ```
  workspaces/media/
    briefs/                    — User-provided briefs and objectives
    01-research/               — Content research, trend analysis
    02-plans/                  — Content calendar, strategy plans
    03-content/
      drafts/                  — Content Creator's drafts (writable)
      approved/                — Human-approved content
      published/               — Published content archive
    04-analytics/
      reports/                 — Analytics Agent's reports
      raw/                     — Raw metrics (read-only for most agents)
    05-outreach/
      drafts/                  — Outreach Agent's draft emails
    todos/active/              — DM team's active tasks
    todos/completed/           — Completed DM tasks
    .care/                     — Platform metadata
      agents.yaml              — DM team agent definitions
      posture-plan.yaml        — Posture evolution plan
      gradient-rules.yaml      — DM-specific gradient rules
  ```
- [ ] Seed knowledge base with Foundation brand assets:
  - Brand voice guidelines (brief document)
  - Approved terminology list (key Foundation terms)
  - Publication platforms and accounts (LinkedIn, newsletter, etc.)
  - Content categories and approved topics
- [ ] Register workspace with platform:
  - `WorkspaceRepository.register(media_workspace)` — into DataFlow
  - Set lifecycle phase: ACTIVE
  - Assign team: DM team
- [ ] Register DM team in agent registry:
  - All 8 agents registered (from 602 delegation establishment)
  - Initial posture: SUPERVISED for all
- [ ] Write a DM workspace brief template (`workspaces/media/briefs/00-team-brief.md`):
  - Team mission statement
  - Success metrics
  - Operating constraints summary (human-readable version of constraint envelopes)
  - Contact for approvals (human operator)

## Acceptance Criteria

- Workspace directory structure created correctly
- Knowledge base seeded with Foundation brand assets
- Workspace registered in DataFlow
- All 8 DM agents registered in agent registry
- Brief template created and accurate

## Dependencies

- 303: Workspace persistence (registration)
- 601: DM team agent definitions
- 602: DM team genesis and delegation (agents must be established)

## References

- Workspace model: `care_platform/workspace/model.py` (from 109)
- Existing workspace structure in this repo as reference
