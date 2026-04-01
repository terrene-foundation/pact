---
type: DECISION
date: 2026-03-31
created_at: 2026-03-31T22:30:00+08:00
author: co-authored
session_id: rt26-spec-conformance
session_turn: 8
project: pact
topic: Implementation scope and priority for 22 spec-conformance findings
phase: todos
tags: [scope, priority, l1-vs-l3, spec-conformance]
---

# Implementation Scope for RT26 Spec-Conformance Findings

## Decision

Implement all 22 findings from the spec-conformance red team (journal/0007). No
scope-down. Organized into 7 milestones by dependency order, not priority filtering.

## Key Design Decisions

### 1. Emergency Bypass Tier 4: Remove, Don't Fix

Remove Tier 4 entirely rather than trying to make it work. The spec is clear (>72h =
not emergency), and cross-domain research confirms every mature governance system
(military ROE, MAS BCM, NIST, constitutional law) requires re-authorization rather
than perpetual bypass. If an emergency genuinely lasts >72h, operators re-authorize
through Tier 3 every 72 hours.

### 2. EATP Records: Dual Emission, Not Replacement

The L1 engine will emit BOTH its existing PACT audit anchors AND real EATP types.
The PACT audit chain provides tamper-evident runtime governance; the EATP types
provide spec-conformant trust records for external verification. This is additive,
not a rewrite of the audit system.

### 3. Per-Dimension Gradient: Schema Extension, Not New System

Add gradient configuration to the existing `RoleEnvelope` rather than building a
separate gradient engine. The `GradientEngine` that already exists in L1 becomes
the reference implementation; `_evaluate_against_envelope()` reads thresholds from
the envelope's gradient config instead of hardcoded values.

### 4. L1 vs L3 Boundary

16 of 26 todos are L1 (kailash-py). This is correct — the spec-conformance gaps
are primarily in the governance engine primitive, not the platform layer. L3 todos
are either bypass fixes (M0), wiring (M5), or tooling (M6).

## Alternatives Considered

- **Scope to L3 only**: Rejected. The EATP mapping, tightening, gradient, grammar,
  and bridge gaps are all L1. Fixing only L3 would leave the most critical findings
  unaddressed.
- **Update spec to match implementation**: Rejected. User confirmed EATP is the
  authority ("is it deficient or something?") and per-dimension gradient
  "undermines" the spec.

## Consequences

- kailash-pact version bump required (0.5.0 -> 0.6.0 or 0.5.1)
- pact-platform will pin to the new kailash-pact version
- Emergency bypass API changes are breaking (Tier 4 removal, new required params)

## For Discussion

1. The 16 L1 todos require working in kailash-py. Previous sessions did this
   successfully. Should any of these be filed as GitHub issues first, or implement
   directly?

2. The EATP dual-emission pattern means every governance mutation creates two records
   (PACT anchor + EATP type). If this doubles the audit volume and the PACT chain
   alone provides sufficient integrity, would the spec accept a "conversion layer"
   that derives EATP types from PACT anchors on demand rather than at write time?

3. Emergency bypass Tier 4 removal is a breaking change for any consumer using
   `BypassTier.TIER_4`. Should this be a deprecation (warn then remove) or
   immediate removal?
