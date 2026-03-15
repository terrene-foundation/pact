# 304: Audit History Query Interface

**Milestone**: 3 — Persistence Layer
**Priority**: Medium
**Estimated effort**: Medium
**Depends on**: 301, 302, 205
**Completed**: 2026-03-12
**Verified by**: AuditQuery.by_agent, by_time_range, by_verification_level, filter, held_actions + AuditReport.team_summary, compliance_check in `care_platform/persistence/audit_query.py`; 23 unit tests pass in `tests/unit/persistence/test_audit_query.py`

## Description

Implement the query interface for the audit history stored in DataFlow. Audit anchors are written by every agent action (from todo 205), but they are only useful if humans and the platform can query them efficiently. This todo builds the query layer: search by agent, time range, action type, and verification gradient level.

## Tasks

- [ ] Implement `care_platform/persistence/audit_query.py`:
  - `AuditQuery.by_agent(agent_id, limit=100) -> list[AuditAnchor]`
  - `AuditQuery.by_team(team_id, limit=100) -> list[AuditAnchor]`
  - `AuditQuery.by_time_range(start, end) -> list[AuditAnchor]`
  - `AuditQuery.by_action_type(action_type) -> list[AuditAnchor]`
  - `AuditQuery.by_gradient_level(level) -> list[AuditAnchor]`
  - `AuditQuery.chain_walk(anchor_id) -> list[AuditAnchor]` — follow chain links forward/backward
  - `AuditQuery.export(query_result) -> dict` — export for reporting or compliance
- [ ] Implement compound query support:
  - `AuditQuery.filter(agent_id=None, team_id=None, start=None, end=None, action_type=None, gradient=None)`
  - Combine multiple filters with AND semantics
  - Paginate results (default limit 100, max 1000)
- [ ] Implement audit report generation:
  - `AuditReport.by_team(team_id, days=7)` — summary of team actions over period
  - `AuditReport.compliance_check(team_id)` — verify chain integrity and completeness
  - `AuditReport.held_actions(team_id)` — list all held actions and their outcomes
- [ ] Implement chain integrity verification:
  - Walk the audit chain from genesis to latest anchor
  - Verify each anchor's hash links correctly to predecessor
  - Report any broken links (tampering indicator)
- [ ] Implement CLI command: `care-platform audit report --team dm --days 7`
- [ ] Write integration tests:
  - Query by agent returns correct anchors
  - Query by time range returns correct subset
  - Chain walk follows links correctly
  - Chain integrity check detects a deliberately broken link

## Acceptance Criteria

- All query operations return correct results from DataFlow
- Compound filter queries work correctly
- Chain integrity check reliably detects tampering
- Audit report CLI command produces human-readable output
- Integration tests passing

## Dependencies

- 301: DataFlow schema (audit anchor table)
- 302: Trust object persistence (anchors written to DataFlow)
- 205: Audit anchor pipeline (anchors created on every action)

## References

- Audit anchor model: `care_platform/models/audit.py` (from 110)
- EATP AUDIT operation: EATP SDK `src/eatp/operations/audit.py`
