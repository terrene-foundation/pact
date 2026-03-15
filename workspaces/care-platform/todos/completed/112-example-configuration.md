# 112: Create Example Configuration (Foundation as First Deployer)

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: Medium (demonstrates the platform, needed for DM team)
**Estimated effort**: Small
**Status**: COMPLETED — 2026-03-12

## Completion Summary

Example configuration implemented in `examples/care-config.yaml` (Foundation as first deployer).
Consolidated format (single file rather than `terrene-foundation/` subdirectory) validated by schema and tests.

- `examples/care-config.yaml` — Full Foundation config with all teams, agents, constraint envelopes
- `examples/minimal-config.yaml` — Minimal valid config for quickstart
- `tests/unit/config/test_example_configs.py` — Schema validation tests for both example files

## Description

Create an example CARE Platform configuration that models the Terrene Foundation itself — teams, agents, constraint envelopes, workspaces. This serves as both documentation and the actual configuration the Foundation will use.

## Tasks

- [x] Create Foundation example configuration:
  - Platform config (name: Terrene Foundation, genesis authority: terrene.foundation)
  - Teams: DM, Governance, Standards, Partnerships, Platform Development
  - Workspace mappings for each team
  - Default trust posture: Supervised (Phase 1)
- [x] DM Team Lead, content creator, analytics agent constraint envelopes included
- [x] Validate example configs against the schema (passes validation)
- [x] Comments explaining each configuration choice

## Acceptance Criteria

- [x] Example configuration passes schema validation
- [x] All five constraint dimensions populated for DM agents
- [x] Comments explain the rationale for each constraint choice
- [x] Configuration matches the analysis (DM team design from research)

## References

- `01-analysis/01-research/03-eatp-trust-model-dm-team.md` — DM constraint envelopes
- `01-analysis/02-synthesis.md` — Full team inventory
