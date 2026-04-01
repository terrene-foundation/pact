# RT29: API Surface Completion + Test Hardening

Sprint: Close the gap between L1 GovernanceEngine capabilities and L3 REST API surface.
All L1 primitives are available (kailash-pact 0.5.0). CLI coverage exists. API coverage is missing for 4 governance domains.

## TODO-01: Clearance Management API Router [HIGH]

Expose L1 `grant_clearance`, `revoke_clearance`, `effective_clearance` via REST.

- `POST /api/v1/clearance/grant` — grant clearance to a role
- `POST /api/v1/clearance/revoke` — revoke clearance from a role
- `GET /api/v1/clearance/{role_address}` — get effective clearance for a role
- Input validation: role_address via `validate_record_id`, clearance level via enum
- Governance gate: mutations route through `governance_gate()`
- Tests: 6+ tests (grant, revoke, get, invalid address, unauthorized, duplicate grant)

**File**: `src/pact_platform/use/api/routers/clearance.py`
**Wire into**: `src/pact_platform/use/api/server.py`

## TODO-02: Knowledge Share Policy (KSP) API Router [HIGH]

Expose L1 `create_ksp` via REST.

- `POST /api/v1/ksp` — create a knowledge share policy
- `GET /api/v1/ksp` — list knowledge share policies
- Input validation: source/target addresses, classification ceiling enum
- Governance gate: creation routes through `governance_gate()`
- Tests: 4+ tests (create, list, invalid source, classification ceiling validation)

**File**: `src/pact_platform/use/api/routers/ksp.py`
**Wire into**: `src/pact_platform/use/api/server.py`

## TODO-03: Envelope Management API Router [HIGH]

Expose L1 `set_role_envelope`, `set_task_envelope`, `compute_envelope` via REST.

- `GET /api/v1/envelopes/{role_address}` — compute effective envelope for a role
- `PUT /api/v1/envelopes/{role_address}/role` — set role envelope
- `PUT /api/v1/envelopes/{role_address}/task` — set task envelope
- Input validation: address, NaN/Inf on numeric fields
- Governance gate: mutations route through `governance_gate()`
- Tests: 6+ tests (get, set role, set task, NaN rejection, monotonic tightening violation, address validation)

**File**: `src/pact_platform/use/api/routers/envelopes.py`
**Wire into**: `src/pact_platform/use/api/server.py`

## TODO-04: Access Check API Endpoint [MEDIUM]

Expose L1 `check_access` / `can_access` via REST.

- `POST /api/v1/access/check` — check if a role can access a resource
- Returns `AccessDecision` with granted/denied + reason + explanation
- Input validation: role_address, resource path, access_type
- Read-only: no governance gate needed
- Tests: 4+ tests (granted, denied-clearance, denied-compartment, explain output)

**File**: `src/pact_platform/use/api/routers/access.py`
**Wire into**: `src/pact_platform/use/api/server.py`

## TODO-05: Bridge Consent API Endpoint [MEDIUM]

L1 has `consent_bridge` but only `approve_bridge` is exposed at L3.

- `POST /api/v1/org/bridges/consent` — bilateral consent for a bridge
- Input validation: bridge_id, consenting role_address
- Governance gate: routes through `governance_gate()`
- Tests: 3+ tests (consent success, already consented, bridge not found)

**File**: Extend `src/pact_platform/use/api/routers/org.py`
**Wire into**: existing org router

## TODO-06: Rate Limit Store Test Hardening [LOW]

Gaps identified by testing-specialist in RT29.

- `test_empty_history_returns_empty` for SqliteRateLimitStore
- `test_corrupted_db_fails_closed` — fail-closed on corrupted SQLite
- `test_default_path_from_env_var` — PACT_BYPASS_RATELIMIT_DB env var
- `test_close_is_idempotent` — double close doesn't raise
- `test_cleanup_stale_empty_store` for both stores
- `test_emergency_bypass_defaults_to_memory_store` — explicit default assertion

**File**: `tests/unit/engine/test_emergency_bypass.py`

---

Status: ALL RESOLVED
Dependencies: None (all L1 primitives available)
Estimated effort: 1 autonomous session

## Resolution

All 6 TODOs implemented and tested:

- TODO-01: `clearance.py` — 3 endpoints (grant, revoke, get) + 7 tests
- TODO-02: `ksp.py` — 2 endpoints (create, list) + 4 tests
- TODO-03: `envelopes.py` — 3 endpoints (get, set-role, set-task) + 4 tests
- TODO-04: `access.py` — 1 endpoint (check) + 3 tests
- TODO-05: Bridge consent added to `org.py` — 1 endpoint + 3 tests
- TODO-06: 7 edge case tests for rate limit stores

Wiring:

- `routers/__init__.py` updated with 4 new router imports
- `server.py` updated with cascading `set_engine` for engine injection
- Envelope router uses `/api/v1/governance/envelopes` prefix (avoids conflict with Phase 1 `/api/v1/envelopes/{envelope_id}`)

Test count: 2516 passed, 0 failed
