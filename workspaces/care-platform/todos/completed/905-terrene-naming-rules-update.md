# 905: Update Terrene Naming Rules — CARE Platform Terminology

**Milestone**: 9 — Cross-Reference Updates
**Priority**: Medium (prevents terminology drift in future work)
**Estimated effort**: Small

## Description

Update `.claude/rules/terrene-naming.md` to include CARE Platform terminology. Currently, the naming rules cover the Trinity (CARE, EATP, CO), COC, and licensing — but do not cover CARE Platform-specific terms: constraint envelopes, verification gradient, trust postures, workspace-as-knowledge-base, cross-functional bridges.

## Tasks

- [ ] Read current state of `.claude/rules/terrene-naming.md`
- [ ] Add CARE Platform terminology section:
  - Platform layer: "CARE Platform" (Apache 2.0) — governed operational model
  - "CARE specification" vs "CARE Platform" — disambiguation rule
  - Constraint envelope dimensions: Financial, Operational, Temporal, Data Access, Communication (these exact names, not synonyms)
  - Verification gradient levels: AUTO_APPROVED, FLAGGED, HELD, BLOCKED (exact names)
  - Trust postures: PSEUDO_AGENT, SUPERVISED, SHARED_PLANNING, CONTINUOUS_INSIGHT, DELEGATED (exact names)
  - Bridge types: Standing, Scoped, Ad-Hoc (these exact names)
  - "workspace-as-knowledge-base" — exact phrase (not "knowledge workspace" or "knowledge base workspace")
  - "Cross-Functional Bridge" — not "cross-team bridge" or "inter-team connector"
- [ ] Add EATP operations terminology:
  - Four operations: ESTABLISH, DELEGATE, VERIFY, AUDIT (uppercase, not "establish operation" or "delegation")
  - Five Trust Lineage Chain elements: Genesis Record, Delegation Record, Constraint Envelope, Capability Attestation, Audit Anchor
  - "ShadowEnforcer" — one word, capitalized (not "shadow enforcer" or "shadow mode")
- [ ] Verify new terminology does not conflict with existing rules
- [ ] Submit to terrene-naming for review (align with Terrene Foundation style)

## Acceptance Criteria

- All CARE Platform terms defined with canonical names
- Disambiguation between "CARE specification" and "CARE Platform" explicit
- No conflicts with existing naming rules
- New rules applied in all M8 documentation (docs validation in 808)

## Dependencies

- 801-807: Documentation using these terms (validate consistency)
- Current `terrene-naming.md` read before editing

## References

- Current naming rules: `.claude/rules/terrene-naming.md`
- CARE specification glossary
- EATP Trust Lineage spec (term definitions)
