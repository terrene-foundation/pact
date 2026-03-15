# Todo 3602: Bridge Audit Endpoint

**Milestone**: M36 — Bridge API + Dashboard
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3601, 3104

## What

Add a bridge-specific audit trail endpoint:

`GET /api/v1/bridges/{bridge_id}/audit`

This endpoint returns a paginated list of all cross-team actions that were routed through the specified bridge. Each record in the response must include:

- `timestamp`
- `source_agent` — the agent that submitted the cross-team task
- `target_agent` — the agent that executed the task
- `action` — the action string from the task
- `verification_level` — the result from the verification gradient (`AUTO_APPROVED`, `FLAGGED`, `HELD`, or `BLOCKED`)
- `sharing_mode_applied` — the information sharing mode that governed the response (`auto_share`, `request_share`, `never_share`, or `null` if not applicable)

Supported query parameters:

- `start_date` (ISO 8601) — filter to records at or after this timestamp
- `end_date` (ISO 8601) — filter to records at or before this timestamp
- `agent_id` — filter to records where `source_agent` or `target_agent` matches
- `limit` (integer, default 50, max 200) — page size
- `offset` (integer, default 0) — pagination offset

The response body must include `total_count`, `limit`, `offset`, and `records`.

Each record should include a reference to the dual cross-team audit anchor (from todo 3104) so auditors can trace individual actions back to the cryptographic trust chain.

Wire into `PlatformAPI.bridge_audit()` in `src/care_platform/api/endpoints.py` and register the route in `src/care_platform/api/server.py`.

## Where

- `src/care_platform/api/endpoints.py` (add `bridge_audit()` method)
- `src/care_platform/api/server.py` (register route)

## Evidence

- [ ] `GET /api/v1/bridges/{bridge_id}/audit` returns a paginated audit record list
- [ ] Each record contains `timestamp`, `source_agent`, `target_agent`, `action`, `verification_level`, `sharing_mode_applied`
- [ ] Each record includes a reference to the cross-team audit anchor
- [ ] `start_date` and `end_date` filters correctly bound the result set
- [ ] `agent_id` filter returns only records where source or target matches
- [ ] `limit` and `offset` pagination works correctly
- [ ] `total_count` in the response reflects the unfiltered count for the bridge
- [ ] Endpoint returns 401 without a valid token
- [ ] Non-existent `bridge_id` returns 404
- [ ] All unit and integration tests pass
