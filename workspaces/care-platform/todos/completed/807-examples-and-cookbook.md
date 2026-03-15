# 807: Examples and Cookbook

**Milestone**: 8 — Documentation and Developer Experience
**Priority**: Low (improves adoption but not blocking)
**Estimated effort**: Medium

## Description

Create a collection of working examples and cookbook recipes for common CARE Platform use cases. Each example is a complete, runnable Python script or YAML configuration. These help developers understand the platform by doing rather than reading.

## Tasks

- [ ] Create `examples/` directory structure:
  ```
  examples/
    quickstart/           — Minimal working example (from 112)
    dm-team/              — Full DM team configuration
    foundation-org/       — Full Foundation organization
    custom-constraints/   — How to define custom constraint rules
    shadow-enforcer/      — How to run a ShadowEnforcer calibration
    audit-export/         — How to export and verify audit chains
    bridge-setup/         — How to establish cross-team bridges
  ```
- [ ] Write `examples/custom-constraints/README.md` + example:
  - How to add a custom constraint dimension
  - How to write a custom GradientEngine rule
  - How to test custom constraints
- [ ] Write `examples/shadow-enforcer/README.md` + example:
  - How to run ShadowEnforcer for a team
  - How to read the output report
  - How to use metrics to make posture upgrade decisions
- [ ] Write `examples/audit-export/README.md` + example:
  - How to export audit chain for a date range
  - How to verify chain integrity
  - How to format for regulatory review
- [ ] Write `examples/bridge-setup/README.md` + example:
  - How to request a Scoped bridge between two teams
  - How to approve from both sides
  - How to send knowledge across an active bridge
- [ ] Validate all examples run without errors on a fresh install
- [ ] Link examples from docs and README

## Acceptance Criteria

- All examples runnable from fresh install
- Each example has a README explaining what it demonstrates
- Custom constraints example shows extensibility
- Audit export example produces regulatory-review-ready output

## Dependencies

- 703: Org builder tests (validates Foundation org config)
- 506: Bridge tests (validates bridge setup)
- 304: Audit queries (validates audit export)
- 208: ShadowEnforcer (validates shadow enforcer example)

## References

- EATP SDK examples as inspiration: `packages/eatp/examples/`
