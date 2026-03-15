# Task 3605 — Bridge Dashboard Tests

**Milestone**: M36 — Bridge API + Dashboard
**Dependencies**: 3601, 3602, 3603, 3604
**Evidence type**: All tests pass

## What

Write comprehensive tests for bridge API endpoints and dashboard components:

### API Client Tests
- POST /bridges — create bridge with all types (Standing, Scoped, Ad-Hoc)
- GET /bridges/{id} — retrieve bridge detail
- PUT /bridges/{id}/approve — bilateral approval flow
- POST /bridges/{id}/suspend — bridge suspension
- POST /bridges/{id}/close — bridge closure
- GET /bridges/{id}/audit — bridge audit trail
- Error cases: invalid bridge ID, unauthorized, invalid state transitions

### Component Tests
- Bridge list with lifecycle badges
- Bridge detail view with constraint intersection visualization
- Bridge creation wizard — all 5 steps
- Approval flow UI

## Where

- `apps/web/__tests__/bridge-api.test.ts` — API client tests
- `apps/web/__tests__/bridge-components.test.ts` — component tests

## Acceptance Criteria

- [ ] API client tests for all bridge CRUD endpoints
- [ ] Error case coverage (invalid IDs, auth failures, bad transitions)
- [ ] Component tests for bridge list, detail, wizard
- [ ] All tests pass
- [ ] Apache 2.0 license headers
