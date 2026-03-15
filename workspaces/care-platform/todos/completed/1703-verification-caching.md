# M17-T03: Trust verification caching enhancement

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M17 — Gap Closure: Integrity & Resilience
**Dependencies**: 1601-1605

## What

Existing `VerificationCache` in `constraint/cache.py` is functional but not integrated into the middleware pipeline. Integrate so repeat verifications for same agent+envelope within TTL use cached result. Target: sub-35ms for cached verifications.

## Where

- Modify: `src/care_platform/constraint/middleware.py` (add cache lookup)
- Modify: `src/care_platform/constraint/cache.py` (add cache key generation)

## Evidence

- Performance test: 1000 repeat verifications complete in <35ms total
- Cache hit rate >90% in steady state
