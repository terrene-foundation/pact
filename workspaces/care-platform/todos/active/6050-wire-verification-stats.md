# Task 6050: Wire verification_stats + Fix \_build_platform_api() Fallback

**Milestone**: M42
**Priority**: High
**Effort**: Small
**Status**: Active

## Description

The `seed_demo.py` script computes `verification_stats` (counts of AUTO_APPROVED, FLAGGED, HELD, BLOCKED actions) but `run_seeded_server.py` discards this data instead of passing it to `PlatformAPI`. The dashboard's verification gradient stats panel therefore shows placeholder or zero data.

Two sub-issues:

1. `verification_stats` not passed through to `PlatformAPI` constructor or setter
2. `_build_platform_api()` may have a fallback that returns empty stats rather than raising clearly — fix the fallback to log a warning so the issue is visible in server logs

## Acceptance Criteria

- [ ] `verification_stats` from `seed_demo.py` is passed into `PlatformAPI` and stored
- [ ] `GET /api/v1/verification/stats` returns the actual verification counts (not zeros or placeholders)
- [ ] Dashboard verification gradient panel shows real data from seed
- [ ] `_build_platform_api()` fallback path logs a WARNING (not silent) when stats are unavailable
- [ ] Unit test: `PlatformAPI` with seeded verification_stats returns correct counts from the stats endpoint

## Dependencies

- Tasks 6010-6015 (M38 restructure — this fix uses the new module paths in use/api/)
