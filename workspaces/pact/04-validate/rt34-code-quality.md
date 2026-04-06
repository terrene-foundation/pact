---
type: REVIEW
date: 2026-04-06
scope: "Issues #21-#25 governance hardening"
reviewer: quality-reviewer
status: Issues Found
---

# RT34: Code Quality Review -- Governance Hardening (Issues #21-#25)

## Summary

- Overall Status: **Issues Found** (1 critical, 2 high, 4 medium, 3 low)
- Files Reviewed: 11
- New Models: 5 (KnowledgeRecord, ApprovalConfig, ApprovalRecord, ClearanceVetting, BootstrapRecord, TaskEnvelopeRecord)
- New Routers: 5 (knowledge, vetting, bootstrap, task_envelopes, access -- decisions.py updated)
- New Services: 2 (ExpiryScheduler, MultiApproverService)
- Pattern Compliance: All CRUD uses DataFlow Express -- correct
- Boundary Test: PASS -- no domain vocabulary in new framework files
- Stubs/TODOs: PASS -- none found in any new file
- Copyright Headers: PASS -- all new files have correct `SPDX-License-Identifier: Apache-2.0`

## Critical Issues (Must Fix)

### C1. ExpiryScheduler `start()` and `stop()` called without `await`

- **Severity**: CRITICAL
- **Location**: `src/pact_platform/use/api/server.py:1078` and `server.py:1084`
- **Rule**: Python coroutine correctness
- **Impact**: The expiry scheduler **never starts**. All time-limited records (bootstrap expiry, task envelope expiry, decision timeout) silently never expire. Bootstrap mode runs forever. Expired decisions remain pending indefinitely. This defeats Issues #23 and #24 entirely.

**The bug**:

```python
# server.py:1077-1079 -- MISSING await
@app.on_event("startup")
async def _start_expiry_scheduler() -> None:
    _expiry_sched.start(interval_seconds=60.0)   # Returns unawaited coroutine
    logger.info("Expiry scheduler started (60s interval)")

# server.py:1082-1085 -- MISSING await
@app.on_event("shutdown")
async def _stop_expiry_scheduler() -> None:
    _expiry_sched.stop()    # Returns unawaited coroutine
    logger.info("Expiry scheduler stopped")
```

**Fix**: Add `await` to both calls:

```python
@app.on_event("startup")
async def _start_expiry_scheduler() -> None:
    await _expiry_sched.start(interval_seconds=60.0)

@app.on_event("shutdown")
async def _stop_expiry_scheduler() -> None:
    await _expiry_sched.stop()
```

Both `ExpiryScheduler.start()` and `ExpiryScheduler.stop()` are `async def` (expiry_scheduler.py lines 246 and 275). Python will generate a `RuntimeWarning: coroutine was never awaited` at runtime, but the server will start without error -- silently leaving all expiry logic dead.

## High Issues (Should Fix)

### H1. Multi-approver quorum path bypasses optimistic lock

- **Severity**: HIGH
- **Location**: `src/pact_platform/use/api/routers/decisions.py:212-224`
- **Rule**: `rules/pact-governance.md` Rule 8 (Thread Safety), consistency with existing patterns
- **Impact**: The single-approver path uses `_optimistic_lock_update()` with envelope_version checking (TOCTOU defense). The multi-approver path, when quorum is met, does a direct `db.express.update()` without any version check. A concurrent approval arriving between the quorum check (line 212) and the update (line 214) could cause a double-transition -- two approvals both see quorum met and both write `status=approved` with potentially conflicting `decided_by` values.

```python
# decisions.py:212-224 -- no optimistic lock on quorum-met path
if result.get("current_approvals", 0) >= required:
    await db.express.update(        # Direct update, no version check
        "AgenticDecision",
        decision_id,
        {
            "status": "approved",
            "decided_by": decided_by,
            ...
        },
    )
```

**Fix**: Apply the same `envelope_version` increment check used in `_optimistic_lock_update()`, or at minimum re-read the decision status before updating to confirm it's still pending.

### H2. Vetting rejection stores rejector in `revoked_by` field

- **Severity**: HIGH
- **Location**: `src/pact_platform/use/api/routers/vetting.py:396-404`
- **Rule**: Data model semantic correctness
- **Impact**: When a vetting request is rejected, the rejector's address is stored in `revoked_by` (a field intended for the revocation lifecycle). The `ClearanceVetting` model has no `rejected_by` field. The response correctly returns `rejected_by` (line 413), but the persisted data uses the wrong field. This means:
  1. A subsequent revocation would overwrite the rejection audit trail
  2. Querying "who rejected this vetting" requires reading `revoked_by`, which is misleading

```python
# vetting.py:396-404
await db.express.update(
    "ClearanceVetting",
    vetting_id,
    {
        "current_status": "rejected",
        "reason": rejection_reason,
        "revoked_by": rejector_address,   # Wrong field -- should be rejected_by
    },
)
```

**Fix**: Either add a `rejected_by` field to the `ClearanceVetting` model, or consistently use `revoked_by` for both rejection and revocation (and document this convention).

## Medium Issues (Should Fix in Current Session)

### M1. D/T/R address validation duplicated across 4 files

- **Severity**: MEDIUM
- **Location**: `knowledge.py:71-83`, `vetting.py:92-103`, `task_envelopes.py:51-63`, `access.py:89-94` (inline)
- **Rule**: DRY principle, maintainability
- **Impact**: Four near-identical implementations of D/T/R address validation. If the validation logic changes (e.g., a new address format), four files need updating. The existing `validate_record_id()` in `models/__init__.py` shows the shared-utility pattern already in use.

**Fix**: Add `validate_dtr_address(address, field_name)` to `models/__init__.py` alongside `validate_record_id()`, then import from there in all routers.

### M2. `_validate_classification()` docstring claims fallback that does not exist

- **Severity**: MEDIUM
- **Location**: `knowledge.py:44-68`, `vetting.py:106-121`
- **Rule**: `rules/no-stubs.md` Rule 4 (Section existence is not coverage)
- **Impact**: The knowledge.py docstring states "Falls back to a string check against the known valid values if the enum import fails" but there is no `except ImportError` handler. If `pact_platform.build.config.schema` is not importable (e.g., during isolated testing), the unhandled `ImportError` will surface as a 500. The vetting.py version does not claim a fallback (correct) but has the same structural risk.

**Fix**: Either add `except ImportError` with a string-check fallback, or correct the docstring to reflect the actual behavior.

### M3. Multi-approver duplicate check has TOCTOU window

- **Severity**: MEDIUM
- **Location**: `src/pact_platform/use/services/multi_approver.py:64-73`
- **Rule**: `rules/infrastructure-sql.md` Rule 5 (use upsert, not check-then-act)
- **Impact**: The duplicate approval check (list + check + create) is not atomic. Two simultaneous approval requests from the same approver could both pass the duplicate check and both insert, creating two `ApprovalRecord` entries and inflating the approval count. This is a classic TOCTOU race. In practice, the risk is low (same human clicking twice near-simultaneously) but it violates the check-then-act prohibition.

**Fix**: Use a unique constraint on `(decision_id, approver_address)` at the database level, or implement an insert-if-not-exists pattern via DataFlow Express if supported.

### M4. ExpiryScheduler ISO 8601 string comparison may fail across timezones

- **Severity**: MEDIUM
- **Location**: `src/pact_platform/use/services/expiry_scheduler.py:179-183`
- **Rule**: Temporal correctness
- **Impact**: The expiry check uses string comparison (`expires_str >= now_iso`) which only works when both timestamps use the same ISO 8601 format and timezone offset. If `expires_at` was stored as `2026-04-06T12:00:00` (naive) and `now_iso` is `2026-04-06T04:00:00+00:00` (with offset), the string comparison produces incorrect results because `"2026-04-06T12:00:00" >= "2026-04-06T04:00:00+00:00"` is `True` lexicographically but temporally ambiguous. The code comment acknowledges this limitation.

**Fix**: Parse both timestamps as `datetime` objects for comparison, matching the pattern already used in `bootstrap.py:94-96` and `task_envelopes.py:155-158`.

## Low Issues (Can Defer)

### L1. Missing `from __future__ import annotations` in `models/__init__.py`

- **Severity**: LOW
- **Location**: `src/pact_platform/models/__init__.py`
- **Rule**: EATP SDK conventions (every module)
- **Impact**: Pre-existing issue. All new files correctly include the import. The models file doesn't need it functionally (it uses `Optional[str]` syntax which works without it), but it breaks the convention stated in `rules/eatp.md`.

### L2. `server.py` uses non-standard SPDX header

- **Severity**: LOW
- **Location**: `src/pact_platform/use/api/server.py:2`
- **Rule**: `rules/terrene-naming.md` (License Accuracy)
- **Impact**: Pre-existing. Server.py uses `# Licensed under the Apache License, Version 2.0` while all new files correctly use `# SPDX-License-Identifier: Apache-2.0`. Not a licensing error -- just inconsistent formatting.

### L3. `on_event("startup")`/`on_event("shutdown")` is deprecated in FastAPI

- **Severity**: LOW (INFO)
- **Location**: `src/pact_platform/use/api/server.py:1076-1085`
- **Rule**: None (advisory)
- **Impact**: Pre-existing pattern (line 949 also uses `on_event`). FastAPI recommends `lifespan` context manager for new code. Not a bug, but worth noting for future migration.

## Positive Observations

1. **DataFlow Express everywhere**: All CRUD operations in all new routers use `db.express.*` -- fully compliant with `rules/patterns.md`.

2. **Governance gate pattern**: Knowledge router correctly applies `governance_gate()` on create, update, and delete mutations. Vetting router applies it on submit. Bootstrap router uses environment-gated activation instead (appropriate for bootstrap mode). Task envelopes router delegates to L1 engine. All read-only endpoints correctly skip governance gates.

3. **Input validation thorough**: Every endpoint validates required fields, string lengths, record IDs, D/T/R addresses, and classification levels at the API boundary. NaN/Inf guards are present where financial fields are involved (bootstrap.py, task_envelopes.py).

4. **Rate limiting consistent**: All endpoints apply `RATE_GET` or `RATE_POST` via the shared limiter, matching existing router patterns.

5. **Fail-closed error handling**: The governance gate (governance.py:117-122) correctly treats engine errors as BLOCKED. The access check endpoint (access.py:122-123) returns 503 when no engine is configured. Bootstrap mode requires explicit env var opt-in.

6. **FSM transition table well-structured**: Vetting.py uses a clear `_VALID_TRANSITIONS` dict with explicit terminal states and a `_validate_transition()` helper that provides informative error messages.

7. **ExpiryScheduler design**: Clean separation of concerns -- the scheduler is model-agnostic and uses registered handlers. Thread-safe handler registration. Good error isolation (individual record failures don't halt the poll cycle).

8. **Boundary test clean**: No domain vocabulary (company names, industry terms, specific role names) found in any of the new files. All terminology is PACT specification terms.

9. **Copyright and SPDX**: All 10 new files have the correct `# Copyright 2026 Terrene Foundation` + `# SPDX-License-Identifier: Apache-2.0` header.

10. **Optimistic locking on decisions**: The `_optimistic_lock_update()` pattern in decisions.py (lines 110-163) provides TOCTOU defense via double-read with envelope_version checking -- a well-implemented pattern.

## File-by-File Summary

| File                              | Status                 | Issues                                                     |
| --------------------------------- | ---------------------- | ---------------------------------------------------------- |
| `models/__init__.py` (new models) | PASS                   | L1 (pre-existing: missing `__future__`)                    |
| `services/expiry_scheduler.py`    | PASS (code is correct) | M4 (string timestamp comparison)                           |
| `services/multi_approver.py`      | Issues                 | M3 (TOCTOU on duplicate check)                             |
| `routers/knowledge.py`            | Issues                 | M1 (duplicated validation), M2 (docstring mismatch)        |
| `routers/vetting.py`              | Issues                 | H2 (wrong field for rejection), M1 (duplicated validation) |
| `routers/bootstrap.py`            | PASS                   | Clean                                                      |
| `routers/task_envelopes.py`       | PASS                   | M1 (duplicated validation)                                 |
| `routers/decisions.py`            | Issues                 | H1 (quorum path bypasses optimistic lock)                  |
| `routers/access.py`               | PASS                   | M1 (inline validation instead of shared)                   |
| `api/governance.py`               | PASS                   | Clean                                                      |
| `api/server.py` (new wiring)      | **CRITICAL**           | C1 (missing await), L2 (SPDX), L3 (deprecated API)         |
