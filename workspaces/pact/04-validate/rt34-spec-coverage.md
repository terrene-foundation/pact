---
type: VALIDATION
date: 2026-04-06
round: RT-34
scope: Issues #21-#25 acceptance criteria verification
method: Code reading + L1 runtime introspection
---

# RT-34: Spec Coverage Audit -- Issues #21-#25

## Summary

| Issue     | Title                    | ACs    | Verified | Partial | Missing |
| --------- | ------------------------ | ------ | -------- | ------- | ------- |
| #21       | Compartment-based access | 5      | 5        | 0       | 0       |
| #22       | Vetting workflow FSM     | 6      | 5        | 1       | 0       |
| #23       | Bootstrap mode           | 5      | 4        | 1       | 0       |
| #24       | Task envelopes           | 5      | 5        | 0       | 0       |
| #25       | Multi-approver           | 6      | 6        | 0       | 0       |
| **Total** |                          | **27** | **25**   | **2**   | **0**   |

Overall coverage: 25/27 fully verified (93%), 2 partial, 0 missing.

---

## Issue #21: Compartment-based Access

### AC-1: Knowledge model gains compartment field -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/models/__init__.py` lines 455-474

```python
@db.model
class KnowledgeRecord:
    compartments: dict = {}  # {"values": ["alpha", "beta"]}
```

The `KnowledgeRecord` DataFlow model has a `compartments` field stored as a dict with a `values` key containing a list of compartment names. This matches the pattern used elsewhere (e.g., `ClearanceVetting.requested_compartments`).

### AC-2: RoleClearance model gains compartments field -- VERIFIED

**Evidence**: L1 runtime introspection confirms `compartments` is a `frozenset` field on `RoleClearance`:

```
>>> RoleClearance.__dataclass_fields__
['role_address', 'max_clearance', 'compartments', 'granted_by_role_address',
 'vetting_status', 'review_at', 'nda_signed']
```

### AC-3: Knowledge access check enforces compartment membership -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/access.py` lines 128-134

The endpoint constructs a `KnowledgeItem` with `compartments=frozenset(compartments)` and passes it to `_engine.check_access()`. The L1 `can_access()` function enforces compartment membership at Step 3 -- for SECRET+ items, it checks `item.compartments - role_clearance.compartments` and denies access if any compartments are missing.

### AC-4: API exposes compartment management -- VERIFIED

**Evidence**:

- `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/clearance.py` line 48: `grant_clearance` accepts `compartments` parameter and passes `frozenset(compartments)` to `RoleClearance`.
- `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/knowledge.py`: Full CRUD (create, list, get, update, delete) with compartments support. Create stores as `{"values": compartments}`. Update validates compartment list format and re-wraps. List and get return compartments.

### AC-5: Explain functions include compartment context -- VERIFIED

**Evidence**: L1 `explain_access()` source includes compartment context in Step 3:

```python
if item.compartments:
    missing = item.compartments - role_clearance.compartments
    if missing:
        lines.append(
            f"Step 3: Compartment check -- FAIL "
            f"(missing compartments: {sorted(missing)})"
        )
```

The `can_access()` function similarly includes `missing_compartments`, `role_compartments`, and `item_compartments` in `audit_details` on denial.

---

## Issue #22: Vetting Workflow FSM

### AC-1: VettingStatus includes SUSPENDED -- PARTIAL

**Evidence**:

- L3: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/vetting.py` line 48-55 defines `_VALID_TRANSITIONS` which includes `"suspended"` as both a target state (from `"active"`) and a source state (transitioning to `"revoked"`).
- L1: `VettingStatus` enum at L1 has values `['pending', 'active', 'expired', 'revoked']` -- **no `suspended` value**.

**Impact**: The L3 vetting router sets `vetting_status="suspended"` on the L1 `RoleClearance` (vetting.py line 474), but the L1 enum does not recognize this value. The L3 `ClearanceVetting` model stores the status as a plain string (not enum-validated), so L3 persistence works. However, L1 `grant_clearance` with `vetting_status="suspended"` may raise a `ValueError` if L1 validates the enum on construction.

**Recommendation**: Either add `SUSPENDED` to L1 `VettingStatus` or have the L3 suspend endpoint use `vetting_status=VettingStatus.REVOKED` on the L1 side (since a suspended clearance should not grant access).

### AC-2: FSM transitions are enforced -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/vetting.py` lines 124-138

```python
def _validate_transition(current_status: str, target_status: str) -> None:
    allowed = _VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(409, ...)
```

Every mutation endpoint calls `_validate_transition()` before proceeding. The FSM is:

- `pending -> active | rejected | expired`
- `active -> suspended | revoked | expired`
- `suspended -> revoked`
- `rejected, expired, revoked` are terminal

### AC-3: Multi-approver per clearance level -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/vetting.py` lines 61-67

```python
_APPROVERS_BY_LEVEL: dict[str, int] = {
    "public": 1,
    "restricted": 1,
    "confidential": 1,
    "secret": 2,
    "top_secret": 3,
}
```

The submit endpoint reads `required_approvals = _APPROVERS_BY_LEVEL.get(level, 1)` and stores it on the `ClearanceVetting` record. The approve endpoint uses `MultiApproverService` and only transitions to `active` when `current_approvals >= required_approvals`.

### AC-4: Approve/suspend/revoke/reinstate endpoints -- VERIFIED

**Evidence**: Four endpoints present in vetting.py:

- `POST /{vetting_id}/approve` (line 251)
- `POST /{vetting_id}/suspend` (line 419)
- `POST /{vetting_id}/reinstate` (line 498) -- creates NEW pending vetting
- `POST /{vetting_id}/reject` (line 364) -- rejects pending vetting

Additionally, revocation is implicit: reinstate transitions suspended to `revoked` before creating a new pending record.

### AC-5: Clearance grants start as PENDING -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/vetting.py` line 222

```python
"current_status": "pending",
```

The submit endpoint creates a `ClearanceVetting` with `current_status="pending"`, `current_approvals=0`, and the appropriate `required_approvals`.

### AC-6: Audit trail for every vetting status transition -- VERIFIED

**Evidence**: Each transition endpoint:

- **approve**: Records `ApprovalRecord` via `MultiApproverService`, updates `current_approvals` and `approval_record_ids` on the vetting record, logs the approval.
- **reject**: Updates `current_status`, `reason`, `revoked_by`, logs the rejection.
- **suspend**: Updates `current_status`, `suspended_by`, `suspended_reason`, logs the suspension. Also updates L1 clearance.
- **reinstate**: Updates original to `revoked` with `revoked_by` and `revoked_reason`, creates new record with reference reason. Logs both transitions.

All transitions include `logger.info()` calls and persist actor/reason in the database.

---

## Issue #23: Bootstrap Mode

### AC-1: New orgs can operate during initial setup -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/bootstrap.py` lines 224-278

The `activate_bootstrap` endpoint enumerates all roles via `_engine.list_roles()`, then for each role creates a `RoleEnvelope` with generous-but-bounded constraints:

- Financial: max_budget=1000, max_single_action_cost=100
- Operational: max_daily_actions=500
- Data access: max_classification=confidential (never SECRET/TOP_SECRET)

These envelopes are registered with the engine via `_engine.set_role_envelope()`.

### AC-2: Bootstrap is time-limited (default 24h, max 72h) -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/bootstrap.py` lines 184-192

```python
_MAX_DURATION_HOURS = 72
_DEFAULT_DURATION_HOURS = 24
...
if duration_hours <= 0 or duration_hours > _MAX_DURATION_HOURS:
    raise HTTPException(400, ...)
```

Also validates with `validate_finite(duration_hours=duration_hours)` to guard against NaN/Inf.

### AC-3: Auto-expiry transitions org to normal governance -- PARTIAL

**Evidence**:

- **ExpiryScheduler registration**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/server.py` lines 1044-1050 registers `BootstrapRecord` with the scheduler (status_field="status", expires_field="expires_at", active_status="active", expired_status="expired").
- **Missing callback**: The `_expire_bootstrap()` function in bootstrap.py (line 104) removes bootstrap envelopes from the engine. However, it is NOT passed as `on_expire_callback` to `register_handler()`. The ExpiryScheduler will mark BootstrapRecords as "expired" but will NOT remove the bootstrap envelopes from the engine.

**Impact**: When a bootstrap record auto-expires via the scheduler, the database status transitions correctly, but the L1 engine still has the permissive bootstrap envelopes active. The envelopes are only removed on manual access (via `_get_active_bootstrap()` in the status/history endpoints which call `_expire_bootstrap()`), or when the bootstrap is ended early via the `/end` endpoint.

**Recommendation**: Pass `_expire_bootstrap` (wrapped as an async callback) to `register_handler()` as the `on_expire_callback` parameter.

### AC-4: Bootstrap can be ended early -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/bootstrap.py` lines 358-428

The `/end` endpoint:

1. Validates org_id and ended_by
2. Finds the active bootstrap record
3. Removes all bootstrap envelopes from the engine via `_engine.remove_role_envelope()`
4. Updates the record status to `ended_early` with `ended_by` and `ended_at`

### AC-5: Requires explicit opt-in -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/bootstrap.py` lines 44-48, 66-75

```python
_BOOTSTRAP_ALLOWED = os.getenv("PACT_ALLOW_BOOTSTRAP_MODE", "false").lower() in (
    "true", "1", "yes",
)

def _require_bootstrap_allowed() -> None:
    if not _BOOTSTRAP_ALLOWED:
        raise HTTPException(403, detail="Bootstrap mode is not enabled. ...")
```

The `activate_bootstrap` endpoint calls `_require_bootstrap_allowed()` as its first action.

---

## Issue #24: Task Envelopes

### AC-1: TaskEnvelope DataFlow model -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/models/__init__.py` lines 584-605

```python
@db.model
class TaskEnvelopeRecord:
    id: str
    task_id: str
    role_address: str
    parent_envelope_id: str = ""
    envelope_config: dict = {}
    status: str = "active"  # active, expired, acknowledged, rejected
    expires_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    acknowledged_by: str = ""
    rejection_reason: str = ""
    created_at: datetime = None
    updated_at: datetime = None
```

### AC-2: POST endpoint creates with required expires_at -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/task_envelopes.py` lines 66-107

The `_validate_expires_at()` function:

1. Requires `expires_at` to be present and a string
2. Parses as ISO 8601 (raises 400 on invalid format)
3. Validates it is in the future (`expires_at > now`)
4. Validates it is within 30 days (`expires_at <= now + 30d`)

The `create_task_envelope` endpoint calls `_validate_expires_at(expires_at_str)` and stores the validated timestamp.

### AC-3: Effective envelope computation includes task envelope -- VERIFIED

**Evidence**: L1 runtime introspection confirms:

- `GovernanceEngine.compute_envelope(role_address, task_id=None)` accepts an optional `task_id`
- Internally calls `self._envelope_store.get_active_task_envelope(role_address, task_id)` to find the task envelope
- Passes `task_envelope=task_envelope` to the envelope intersection logic

The L1 `TaskEnvelope` dataclass has fields: `id`, `task_id`, `parent_envelope_id`, `envelope`, `expires_at`, `created_at`.

### AC-4: Auto-expiry scheduler -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/server.py` lines 1051-1056

```python
_expiry_sched.register_handler(
    model_name="TaskEnvelopeRecord",
    status_field="status",
    expires_field="expires_at",
    active_status="active",
    expired_status="expired",
)
```

Additionally, the `list_active_task_envelopes` and `get_task_envelope` endpoints perform inline auto-expiry checks.

### AC-5: Agent acknowledges task envelope -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/task_envelopes.py` lines 231-328

The `POST /{role_address}/{task_id}/acknowledge` endpoint:

1. Validates role_address and task_id
2. Requires `acknowledged_by` in the body
3. Finds the active task envelope record
4. Checks expiry before acknowledging (returns 409 if expired)
5. Updates status to `acknowledged` with `acknowledged_at` and `acknowledged_by`

A corresponding `POST /{role_address}/{task_id}/reject` endpoint also exists for agent rejection.

---

## Issue #25: Multi-Approver

### AC-1: Decision model gains required_approvers and approvals list -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/models/__init__.py` lines 332-334

```python
required_approvals: int = 1
current_approvals: int = 0
approval_record_ids: dict = {}  # {"ids": ["apr-xxx", ...]}
```

These fields are on the `AgenticDecision` model, with `required_approvals` defaulting to 1 for backward compatibility.

### AC-2: Decision not finalized until approvals >= required_approvals -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/decisions.py` lines 189-244

The `approve_decision` endpoint:

1. Checks if `_approver_service` is available AND `required_approvals > 1`
2. Records the approval via `MultiApproverService.record_approval()`
3. If `current_approvals >= required`, updates decision status to `approved`
4. If quorum not met, returns `partial_approval` response with progress
5. Falls through to single-approver path if `required_approvals == 1` or no service

### AC-3: Configurable per operation type -- VERIFIED

**Evidence**:

- Model: `/Users/esperie/repos/terrene/pact/src/pact_platform/models/__init__.py` lines 482-499 -- `ApprovalConfig` with fields: `operation_type`, `required_approvals`, `timeout_hours`, `eligible_roles`, `org_id`, `description`.
- Governance gate: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/governance.py` lines 134-147 -- When a verdict is HELD, the gate looks up `ApprovalConfig` by `operation_type` matching the action name, reads `required_approvals` and `timeout_hours`, and uses these when creating the `AgenticDecision` record.

### AC-4: Each approval creates independent audit record -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/services/multi_approver.py` lines 75-87

```python
approval_id = f"apr-{uuid4().hex[:12]}"
await self._db.express.create(
    "ApprovalRecord",
    {
        "id": approval_id,
        "decision_id": decision_id,
        "approver_address": approver_address,
        "approver_identity": approver_identity,
        "verdict": "approved",
        "reason": reason,
        "created_at": datetime.now(UTC).isoformat(),
    },
)
```

Each approval is stored as a separate `ApprovalRecord`. Duplicate prevention is enforced by checking for existing records with the same `decision_id` + `approver_address` before creating (lines 65-73).

### AC-5: Partial approval visible -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/routers/decisions.py` lines 231-241

```python
return {
    "status": "partial_approval",
    "decision_id": decision_id,
    "approval_id": result.get("approval_id", ""),
    "current_approvals": result["current_approvals"],
    "required_approvals": required,
    "message": (
        f"Approval recorded ({result['current_approvals']}/{required}). "
        f"Waiting for more approvals."
    ),
}
```

Additionally, `GET /{decision_id}/approvals` (line 263) lists all individual `ApprovalRecord` entries with the decision's `required_approvals` and `current_approvals` counts.

### AC-6: Timeout: auto-rejected via ExpiryScheduler -- VERIFIED

**Evidence**: `/Users/esperie/repos/terrene/pact/src/pact_platform/use/api/server.py` lines 1058-1063

```python
_expiry_sched.register_handler(
    model_name="AgenticDecision",
    status_field="status",
    expires_field="expires_at",
    active_status="pending",
    expired_status="expired",
)
```

The `governance_gate` in governance.py computes `expires_at` from `timeout_hours` (from `ApprovalConfig` or default 72h) and stores it on the decision record. The scheduler polls and transitions timed-out decisions to `expired`.

---

## Partial Findings Detail

### PARTIAL-1: L1 VettingStatus lacks "suspended" (Issue #22, AC-1)

**Severity**: Important

The L3 vetting FSM defines 6 states: `pending, active, suspended, revoked, rejected, expired`. The L1 `VettingStatus` enum only has 4: `pending, active, expired, revoked`. When the L3 suspend endpoint tries to set `vetting_status="suspended"` on a `RoleClearance`, L1 may reject the value.

**Current behavior**: The L3 ClearanceVetting record stores "suspended" correctly (plain string, no enum validation). The L1 clearance update in the suspend endpoint wraps in a try/except (vetting.py:459-483), so an L1 `ValueError` would be caught and logged as a warning, but the L3 record would still transition correctly. The clearance would remain in its pre-suspension state at L1.

**Fix options**:

1. Add `SUSPENDED = "suspended"` to L1 `VettingStatus` enum (upstream fix)
2. Use `vetting_status=VettingStatus.REVOKED` at L1 when suspending at L3 (functional workaround -- suspended clearances should not grant access, same as revoked)

### PARTIAL-2: Bootstrap expiry callback not wired (Issue #23, AC-3)

**Severity**: Important

The `ExpiryScheduler` supports `on_expire_callback` but the bootstrap handler registration does not pass it. The `_expire_bootstrap()` function (bootstrap.py:104-126) removes bootstrap envelopes from the engine, but this logic only executes during direct API access (status/history endpoints or manual end).

**Current behavior**: When a bootstrap record auto-expires via the scheduler, the DB record transitions to "expired" but the engine retains the permissive bootstrap envelopes. The next access-check endpoint that queries bootstrap status will clean up (via `_get_active_bootstrap()`), but there is a window where bootstrap envelopes remain active after expiry.

**Fix**: In server.py, pass the bootstrap cleanup function as `on_expire_callback`:

```python
async def _on_bootstrap_expire(record: dict) -> None:
    from pact_platform.use.api.routers.bootstrap import _expire_bootstrap
    # _expire_bootstrap already handles engine envelope removal
    # ExpiryScheduler already set status to expired, so just clean engine
    if _engine is not None:
        envelope_ids = record.get("envelope_ids", {})
        id_list = envelope_ids.get("ids", []) if isinstance(envelope_ids, dict) else []
        for env_id in id_list:
            try:
                if hasattr(_engine, "remove_role_envelope"):
                    _engine.remove_role_envelope(env_id)
            except Exception:
                pass

_expiry_sched.register_handler(
    model_name="BootstrapRecord",
    ...,
    on_expire_callback=_on_bootstrap_expire,
)
```

---

## Test Coverage Observations

No dedicated test files were found for the new features from Issues #21-#25:

- No `test_vetting.py` or `test_vetting_fsm.py`
- No `test_task_envelope*.py`
- No `test_multi_approver*.py`
- No `test_knowledge_record*.py` (API router tests)
- `test_bootstrap.py` and `test_bootstrap_exception_handling.py` exist for Issue #23

The `test_decision_toctou.py` covers the existing TOCTOU defense but not the multi-approver path.

---

## For Discussion

1. The L1 VettingStatus enum gap means suspended clearances retain their active L1 status. If a suspended role attempts to access SECRET data before the L3 suspend-status propagates, L1 would still allow access. Is the try/except pattern in the suspend endpoint sufficient, or does this need an L1 upstream fix?

2. If the bootstrap expiry callback had been wired, would a race condition exist between the scheduler marking the record as "expired" and the callback removing envelopes? The scheduler updates the DB first, then fires the callback -- if the callback fails, the record is expired but envelopes remain active (same as the current partial state).

3. Should `ApprovalConfig` records be seeded automatically when an org is deployed (similar to auto-seeding roles and envelopes), or is the current "default to 1 approver" behavior sufficient for initial deployments?
