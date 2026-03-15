# 503: Implement Ad-Hoc Bridge (One-Time Cross-Team Request)

**Milestone**: 5 — Cross-Functional Bridges
**Priority**: Medium
**Estimated effort**: Small
**Depends on**: 501, 502
**Completed**: 2026-03-12
**Verified by**: AdHocBridge with request_payload + respond_to_adhoc + auto-close on response in `care_platform/workspace/bridge.py`; tests for ad-hoc create, respond, and auto-close in `tests/unit/workspace/test_bridge.py`

## Description

Implement Ad-Hoc Bridges — one-time requests between teams that don't require a standing or scoped relationship. Example: Governance team reviews DM team's public statement about the constitution.

## Tasks

- [ ] Implement `AdHocBridge` model:
  - Single request/response interaction
  - Auto-closes after response delivered
  - Full audit trail (request, review, response)
- [ ] Implement the governance review pattern:
  - DM content about constitution → HELD → Governance Team Lead receives request → reviews → returns APPROVED with attestation → DM Team Lead escalates to human
- [ ] Implement request routing:
  - Ad-hoc requests routed to appropriate team lead
  - Team lead can accept or reject review request
  - Response carries attestation (signed approval/rejection)
- [ ] Write integration tests

## Acceptance Criteria

- One-time requests work between any two teams
- Governance review pattern functional
- Auto-close after response
- Integration tests passing
