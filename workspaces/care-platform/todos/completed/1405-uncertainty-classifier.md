# M14-T05: Uncertainty classifier (5 levels)

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M14 — CARE Formal Specifications
**Dependencies**: 1301-1304

## What

Implement `UncertaintyLevel` enum (NONE, INFORMATIONAL, INTERPRETIVE, JUDGMENTAL, FUNDAMENTAL) and `UncertaintyClassifier`. Each level maps to a minimum verification gradient level.

Mapping: NONE→AUTO_APPROVED, INFORMATIONAL→AUTO_APPROVED, INTERPRETIVE→FLAGGED, JUDGMENTAL→HELD, FUNDAMENTAL→BLOCKED.

Classifier takes action metadata (data completeness, precedent availability, reversibility, impact scope).

## Where

- New: `src/care_platform/trust/uncertainty.py`

## Evidence

- Unit tests for classification of sample decisions, mapping to verification levels
