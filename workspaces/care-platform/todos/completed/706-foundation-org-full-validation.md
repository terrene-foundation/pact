# 706: Terrene Foundation Full Organization Validation

**Milestone**: 7 — Organization Builder
**Priority**: Medium (proves the builder generates the correct Foundation setup)
**Estimated effort**: Medium

## Description

Use the Organization Builder to generate the complete Terrene Foundation operational structure: all Tier 1 teams (Media, Standards, Governance, Partnerships), universal agents for each team, and cross-team bridge policies. The generated configuration must match the manually specified DM team exactly, proving the builder is correct.

## Tasks

- [ ] Create `examples/foundation-org.yaml`:
  - Organization: Terrene Foundation, `terrene.foundation`
  - Tier 1 teams: Media, Standards, Governance, Partnerships
  - Universal agents per team: Knowledge Curator + Cross-Team Coordinator
  - Bridge policies: which teams have standing bridges vs scoped-only
  - Review cadence: monthly posture reviews, 90-day envelope renewals
- [ ] Run builder to generate full configuration:
  - `care-platform validate examples/foundation-org.yaml`
  - `care-platform team add --from-file examples/foundation-org.yaml`
  - Verify 4 teams × ~8 agents = ~32 agent definitions generated
  - Verify all constraint envelopes match expected (Media team matches DM spec)
- [ ] Cross-validate generated config against manual DM team spec:
  - DM Team Lead envelope (generated) = DM Team Lead envelope (601) — must match exactly
  - Content Creator envelope (generated) = Content Creator envelope (601) — must match
  - Any divergence is a builder bug
- [ ] Generate workspace structure for all 4 teams:
  - `workspaces/media/` — already exists; verify builder doesn't overwrite
  - `workspaces/standards/` — create
  - `workspaces/constitution/` — already exists; verify builder doesn't overwrite
  - `workspaces/partnerships/` — create
- [ ] Write integration test: builder generates Foundation config, cross-validate against DM spec

## Acceptance Criteria

- Foundation org definition generates 4 complete teams
- Generated DM team config matches manual DM spec exactly
- Workspace creation doesn't overwrite existing workspaces
- Integration test catches any builder regressions
- Foundation is ready to run on its own platform

## Dependencies

- 701-705: All Organization Builder todos
- 601: DM team spec (cross-validation reference)
- 304: Audit query (verify teams generate audit infrastructure)

## References

- Full team inventory: `01-analysis/01-research/06-architecture-gap-analysis.md`
