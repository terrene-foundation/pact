# M15-T05: Dual-binding cryptographic signing for reasoning traces

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M15 — EATP v2.2 Alignment
**Dependencies**: 1504 (JCS)

## What

Enhance reasoning trace signing: each trace cryptographically bound both to its parent record (delegation/audit anchor) AND to the trust chain genesis. Prevents reasoning traces from being moved between trust chains.

## Where

- Modify: `src/care_platform/trust/reasoning.py` (add `genesis_binding_hash`, update `compute_hash()`)
- New: `src/care_platform/trust/dual_binding.py` (binding verification logic)

## Evidence

- Tests: reasoning trace bound to genesis A fails verification against genesis B; trace bound to delegation D1 fails against D2
