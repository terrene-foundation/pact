# M18-T01: Extend PlatformAPI with dashboard endpoints

**Status**: ACTIVE
**Priority**: High
**Milestone**: M18 — Frontend Scaffold & API Layer
**Dependencies**: 1301-1304

## What

Add API handler methods for dashboard views: trust chain listing, constraint envelope details, workspace status, bridge status, verification gradient statistics.

New endpoints:
- `GET /api/v1/trust-chains` (list all with status)
- `GET /api/v1/trust-chains/{agent_id}` (chain detail)
- `GET /api/v1/envelopes/{envelope_id}` (all 5 dimensions)
- `GET /api/v1/workspaces` (all workspaces with state/phase)
- `GET /api/v1/bridges` (all bridges with status)
- `GET /api/v1/verification/stats` (gradient counts)

## Where

- Modify: `src/care_platform/api/endpoints.py`

## Evidence

- Unit tests for each new endpoint handler
