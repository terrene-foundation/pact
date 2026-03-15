# 303: Implement Queryable Audit History

**Milestone**: 3 — Persistence Layer
**Priority**: Medium (needed for operational visibility)
**Estimated effort**: Medium
**Depends on**: 301
**Completed**: 2026-03-12
**Verified by**: AuditQuery + AuditReport in `care_platform/persistence/audit_query.py`; 23 unit tests pass in `tests/unit/persistence/test_audit_query.py`

## Description

Make the audit trail queryable — filter by agent, team, time range, verification level, action type. Essential for operational review and regulatory compliance.

## Tasks

- [ ] Implement query API for audit anchors:
  - By agent (all actions by Content Creator)
  - By team (all DM team actions)
  - By verification level (all HELD actions this week)
  - By time range (everything today)
  - By action type (all external publications)
  - Combined filters
- [ ] Implement aggregation queries:
  - Actions per agent per day
  - Hold rate by agent over time (trend)
  - Block rate by team over time
  - Most common flagged conditions
- [ ] Implement audit dashboard data endpoints:
  - Summary stats for operational review
  - Trend data for posture upgrade decisions
  - Exportable for external auditors
- [ ] Write integration tests for queries

## Acceptance Criteria

- All query types functional with correct results
- Aggregation queries produce useful operational insights
- Performance acceptable for Foundation-scale data (thousands of anchors)
- Integration tests cover all query types
