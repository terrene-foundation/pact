# Todo 3601: Bridge CRUD Endpoints

**Milestone**: M36 — Bridge API + Dashboard
**Priority**: High
**Effort**: Large
**Source**: Phase 4 plan
**Dependencies**: 3401

## What

Add bridge management API endpoints to the CARE Platform FastAPI application. All endpoints require authentication.

Endpoints to implement:

- `POST /api/v1/bridges` — Create a new bridge. Body: `{ bridge_type, source_team_id, target_team_id, purpose, permissions: [{path, access_type, message_types}], valid_days?, sharing_policy? }`. Returns the created bridge record with status `PENDING`.
- `GET /api/v1/bridges/{bridge_id}` — Retrieve bridge detail including permissions, lifecycle status, access log summary, and sharing policy.
- `POST /api/v1/bridges/{bridge_id}/approve` — Record approval from one side. Body: `{ side: "source" | "target", approver_id }`. When both sides have approved, the bridge status transitions to `ACTIVE` and the trust flow from todo 3401 is triggered to create the underlying `BridgeDelegation`.
- `POST /api/v1/bridges/{bridge_id}/suspend` — Suspend an active bridge. Body: `{ reason }`.
- `POST /api/v1/bridges/{bridge_id}/close` — Close a bridge permanently. Body: `{ reason }`.
- `GET /api/v1/teams/{team_id}/bridges` — Return all bridges (in any lifecycle state) where `team_id` is either the source or target team.

Wire all endpoints into the existing `PlatformAPI` class in `src/care_platform/api/endpoints.py` by adding corresponding methods, and register the routes in `src/care_platform/api/server.py`.

Each lifecycle-changing endpoint (`approve`, `suspend`, `close`) must return the updated bridge record in the response body so callers do not need a follow-up GET.

## Where

- `src/care_platform/api/endpoints.py` (add `PlatformAPI` methods)
- `src/care_platform/api/server.py` (register routes)

## Evidence

- [ ] `POST /api/v1/bridges` creates a bridge with status `PENDING` and returns it
- [ ] `GET /api/v1/bridges/{bridge_id}` returns bridge detail with permissions and sharing policy
- [ ] `POST /api/v1/bridges/{bridge_id}/approve` records approval and returns updated bridge
- [ ] When both sides have approved, bridge status becomes `ACTIVE` and `BridgeDelegation` is created via trust flow
- [ ] `POST /api/v1/bridges/{bridge_id}/suspend` sets status to `SUSPENDED` and returns updated bridge
- [ ] `POST /api/v1/bridges/{bridge_id}/close` sets status to `CLOSED` and returns updated bridge
- [ ] `GET /api/v1/teams/{team_id}/bridges` returns bridges for both source and target roles
- [ ] All endpoints return 401 when called without a valid token
- [ ] Non-existent `bridge_id` returns 404
- [ ] Invalid lifecycle transitions (e.g. approving a CLOSED bridge) return 422 with a descriptive error
- [ ] All unit and integration tests pass
