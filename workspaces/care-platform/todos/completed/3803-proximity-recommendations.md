# 3803: Verification Gradient — Proximity + Recommendations ✓

**Milestone**: 8 — EATP SDK Integration (Tier 1)
**Item**: 1.3
**Status**: COMPLETED
**Completed**: 2026-03-15

## What Was Built

Integrated EATP's `ProximityScanner` into CARE's `GradientEngine` and added actionable recommendation generation for all 4 verification levels.

### ProximityScanner Integration

- GradientEngine now accepts optional `proximity_scanner` parameter
- When envelope evaluation has dimension utilizations, they're converted to EATP `ConstraintCheckResult` objects and fed to the scanner
- Proximity alerts are attached to `VerificationResult.proximity_alerts` as serialized dicts
- `escalate_verdict()` monotonically upgrades the classification level (never downgrades)
- Fail-safe: scanner errors are caught and logged — never block classification

### Recommendation Generation

- `_build_recommendations()` generates actionable text for all levels:
  - AUTO_APPROVED → empty list (no action needed)
  - AUTO_APPROVED + proximity alerts → dimension usage warnings with percentages
  - FLAGGED → "Action near operational boundary. Review before proceeding."
  - HELD → "Action exceeds soft limit on [dimensions]. Requires human approval."
  - BLOCKED → "Action violates hard constraint on [dimensions]. Cannot proceed."
- Includes specific dimension names and utilization percentages from proximity alerts
- Recommendations are always a list (never None) — set on every classify() call

### Backward Compatibility

- `proximity_alerts` and `recommendations` are Optional fields with None/None defaults
- Existing callers constructing VerificationResult without these fields are unaffected
- All 444 pre-existing constraint tests pass without modification

## Where

- **Modified**: `src/care_platform/constraint/gradient.py` (ProximityScanner integration + recommendations)
- **New**: `tests/unit/constraint/test_gradient_proximity.py` (11 tests)
- **New**: `tests/unit/constraint/test_gradient_recommendations.py` (8 tests)

## Evidence

- [x] ProximityScanner integrated into classify() via `_apply_proximity()`
- [x] ProximityAlerts attached as Optional field (backward compatible)
- [x] Per-dimension support via DimensionEvaluation → ConstraintCheckResult mapping
- [x] `_build_recommendations()` generates actionable text for all 4 levels
- [x] Recommendations include dimension names and utilization percentages
- [x] Existing callers unaffected: 444/444 pre-existing constraint tests pass
- [x] Proximity tests: escalation at boundary values (79%, 80%, 82%, 95%, 96%)
- [x] Recommendation tests: content correctness for all levels + dimension naming
- [x] Monotonic escalation preserved (BLOCKED stays BLOCKED regardless of proximity)
- [x] 982/982 total tests pass (constraint + trust suites)
