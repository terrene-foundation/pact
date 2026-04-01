# L1 Feature Wiring + Express Migration Cleanup

Wires the 3 remaining L1 features (bridge LCA, vacancy, dimension-scoped delegation)
into the L3 platform now that kailash 2.3.1 has them. Also records the Express
migration Phase 2 assessment.

**Last updated**: 2026-03-31
**Depends on**: kailash>=2.3.1 (installed)

---

## T1: Wire bridge LCA approval into CLI and API

**Closes**: TODO-10 from 001-rt25-spec-gaps.md
**Scope**: L3 (pact-platform)
**L1 API**: `GovernanceEngine.approve_bridge(source_address, target_address, approver_address) -> BridgeApproval`

### What

1. **CLI**: Add `pact bridge approve` command in `cli.py`
   - Args: `--source <addr> --target <addr> --approver <addr>`
   - Calls `engine.approve_bridge()`
   - Prints approval confirmation with 24h TTL

2. **API**: Add `POST /api/v1/bridges/approve` endpoint
   - Body: `{"source_address": "...", "target_address": "...", "approver_address": "..."}`
   - Calls `engine.approve_bridge()` on the org router's engine reference
   - Returns approval details

3. **API wiring**: In `endpoints.py:1059`, wire `engine.approve_bridge()` into the existing `approve_bridge` method that currently only updates bridge manager state

4. **Tests**: Unit tests for CLI command, API endpoint, and approval-before-create flow

### Files

- `src/pact_platform/cli.py` — add `bridge approve` command
- `src/pact_platform/use/api/routers/org.py` — add approve endpoint
- `src/pact_platform/use/api/endpoints.py` — wire engine.approve_bridge()
- `tests/unit/cli/test_cli.py` — CLI test
- `tests/unit/api/test_org_router.py` — API test

---

## T2: Wire vacancy handling into CLI, API, and runtime

**Closes**: TODO-11 from 001-rt25-spec-gaps.md
**Scope**: L3 (pact-platform)
**L1 API**: `GovernanceEngine.designate_acting_occupant(vacant_role, acting_role, designated_by) -> VacancyDesignation`
**L1 API**: `GovernanceEngine.get_vacancy_designation(role_address) -> VacancyDesignation | None`

### What

1. **CLI**: Add `pact role designate-acting` command in `cli.py`
   - Args: `--vacant <addr> --acting <addr> --designated-by <addr>`
   - Calls `engine.designate_acting_occupant()`
   - Prints designation confirmation with 24h TTL

2. **CLI**: Add `pact role vacancy-status` command
   - Args: `--role <addr>`
   - Calls `engine.get_vacancy_designation()`
   - Prints current designation or "no designation"

3. **API**: Add `POST /api/v1/org/roles/{role_address}/designate-acting` endpoint
   - Body: `{"acting_role_address": "...", "designated_by": "..."}`
   - Returns designation details

4. **API**: Add `GET /api/v1/org/roles/{role_address}/vacancy` endpoint
   - Returns current vacancy designation or 404

5. **Tests**: Unit tests for CLI commands, API endpoints

### Files

- `src/pact_platform/cli.py` — add 2 commands
- `src/pact_platform/use/api/routers/org.py` — add 2 endpoints
- `tests/unit/cli/test_cli.py` — CLI tests
- `tests/unit/api/test_org_router.py` — API tests

---

## T3: Wire dimension-scoped delegation into runtime envelope computation

**Closes**: TODO-15 from 001-rt25-spec-gaps.md
**Scope**: L3 (pact-platform)
**L1 API**: `DelegationRecord.dimension_scope: frozenset[str]`
**L1 API**: `intersect_envelopes(a, b, *, dimension_scope=None)`

### What

1. **Runtime**: In `runtime.py`, when computing delegated envelopes, extract `dimension_scope` from the `DelegationRecord` and pass it to `intersect_envelopes()`
   - Find where envelope intersection happens in runtime task processing
   - Pass `dimension_scope` so only scoped dimensions are tightened

2. **CLI**: Extend `pact envelope` commands to show dimension scope when present

3. **Config schema**: Add `dimension_scope: list[str] | None` to delegation config in `schema.py` if needed for YAML org definitions

4. **Tests**: Unit tests for scoped intersection behavior via runtime

### Files

- `src/pact_platform/use/execution/runtime.py` — wire dimension_scope
- `src/pact_platform/cli.py` — show scope in envelope display
- `src/pact_platform/build/config/schema.py` — schema extension if needed
- `tests/unit/execution/test_runtime_governance.py` — tests

---

## T4: Update 001-rt25-spec-gaps.md to mark TODOs 10, 11, 15 as DONE

**Scope**: Documentation
**Depends on**: T1, T2, T3

### What

After implementation, update the todo file to mark all three as DONE with implementation details and file references. Update the summary table to show 25/25 complete.

---

## ~~T5: Express migration Phase 2 — Services~~ — CANCELLED

**Reason**: Service audit (2026-03-31) confirmed all 4 DataFlow-using services
use multi-step workflows with read-before-write, cascading updates, and cross-model
atomicity. These are NOT Express-eligible. Workflow primitives are the correct
abstraction for services.

| Service                  | Primitive Calls | Pattern                           | Verdict       |
| ------------------------ | --------------- | --------------------------------- | ------------- |
| request_router.py        | 6               | Governance gate + pool assignment | Keep workflow |
| approval_queue.py        | 10              | State machine + expiry loop       | Keep workflow |
| completion_workflow.py   | 14              | Artifact lifecycle cascade        | Keep workflow |
| cost_tracking.py         | 8               | Nested aggregation + financial    | Keep workflow |
| notification_dispatch.py | 0               | Event fan-out (no DataFlow)       | N/A           |

---

## Summary

| Todo                              | Scope                 | Status    |
| --------------------------------- | --------------------- | --------- |
| T1 Bridge LCA wiring              | CLI + API + endpoints | **DONE**  |
| T2 Vacancy handling wiring        | CLI + API             | **DONE**  |
| T3 Dimension-scoped delegation    | Runtime + CLI         | **DONE**  |
| T4 Update spec gaps doc           | Documentation         | **DONE**  |
| ~~T5 Services Express migration~~ | ~~Services~~          | CANCELLED |
