# Task 6051: Wire AuditChain from Seed Data into PlatformAPI for Dashboard Trends

**Milestone**: M42
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

The dashboard's trust trend charts (trust score over time, action distribution over time) currently use `Math.random()` on the frontend to generate fake trend data. The real source of this data is the `AuditChain` produced by `seed_demo.py`, which contains timestamped audit anchors that can be aggregated into time-series data.

This task wires the AuditChain into `PlatformAPI` and adds a `/api/v1/audit/trends` endpoint (or extends `/api/v1/audit/history`) to return time-series data the frontend can use instead of Math.random().

## Acceptance Criteria

- [ ] `AuditChain` from seed data is passed into `PlatformAPI` (similar pattern to task 6050)
- [ ] `GET /api/v1/audit/trends` endpoint added returning: list of `{timestamp, trust_score, action_count, verdict_distribution}` data points
- [ ] Endpoint returns at least 7 data points (one per day of seed data) to support a weekly trend chart
- [ ] Frontend dashboard trend charts updated to fetch from `/api/v1/audit/trends` instead of generating random data
- [ ] `Math.random()` removed from dashboard trend chart code
- [ ] Unit test: audit/trends endpoint with seeded AuditChain returns expected data point count and shape

## Dependencies

- Task 6050 (establishes the pattern for wiring seed data into PlatformAPI)
