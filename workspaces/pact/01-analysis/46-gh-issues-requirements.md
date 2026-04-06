# GitHub Issues #21-#25: Governance Hardening Requirements Breakdown

**Date**: 2026-04-06
**Phase**: 01-analysis
**Scope**: Five governance hardening features spanning L1 (kailash-pact) and L3 (pact-platform)

---

## Executive Summary

Five issues require coordinated work across two package tiers. Two issues (#22, #23) require L1 changes (kailash-pact release). Three issues (#21, #24, #25) can be completed entirely at L3. Two cross-cutting patterns -- multi-approver workflows and auto-expiry scheduling -- are shared infrastructure that must be built once and reused. Optimal execution: build shared infrastructure first, then parallelize the five issues into two tracks (L1-dependent and L3-only).

**Complexity**: Moderate-Complex (score: 18)

- Governance: 7/10 (clearance FSM, multi-approver, bootstrap mode -- all policy-layer)
- Legal: 2/10 (Apache 2.0, no license changes)
- Strategic: 4/10 (L1 release cycle creates a sequencing constraint)
- Technical: 5/10 (FSM, auto-expiry, persistence models -- well-understood patterns)

---

## 1. Per-Issue Requirements Matrix

### Issue #21: Compartment-Based Access for SECRET/TOP_SECRET

**Summary**: Ensure SECRET/TOP_SECRET access checks enforce compartment membership via L1's existing 5-step algorithm, and expose this through L3 API and persistence.

#### Acceptance Criteria

| #    | Criterion                                                                 | Status                  |
| ---- | ------------------------------------------------------------------------- | ----------------------- |
| AC-1 | `can_access()` Step 3 denies access when role lacks required compartments | ALREADY SATISFIED       |
| AC-2 | L1 `KnowledgeItem` has `compartments: frozenset[str]` field               | ALREADY SATISFIED       |
| AC-3 | L3 access router passes compartments to L1's `check_access()`             | ALREADY SATISFIED       |
| AC-4 | L3 clearance router accepts and stores compartments on grant              | ALREADY SATISFIED       |
| AC-5 | L3 has a persistent Knowledge model for classified items                  | NEW -- GAP              |
| AC-6 | Knowledge items can be created, queried, and classified via API           | NEW -- GAP              |
| AC-7 | Compartment-filtered access check works end-to-end through API            | NEW -- integration test |

#### Evidence for "Already Satisfied"

- **AC-1**: `can_access()` at `/Users/esperie/repos/terrene/pact/.venv/lib/python3.13/site-packages/kailash/trust/pact/access.py` lines 379-386 enforce compartment check for SECRET and TOP_SECRET. `missing = item.compartments - role_clearance.compartments` -- exact set subtraction.
- **AC-2**: `KnowledgeItem` at `.venv/.../kailash/trust/pact/knowledge.py` line 42: `compartments: frozenset[str] = field(default_factory=frozenset)`.
- **AC-3**: L3 access router at `src/pact_platform/use/api/routers/access.py` lines 112-116 constructs `KnowledgeItem(compartments=frozenset(compartments))` and passes it to `_engine.check_access()`.
- **AC-4**: L3 clearance router at `src/pact_platform/use/api/routers/clearance.py` lines 84-89 constructs `RoleClearance(compartments=frozenset(compartments))`.

#### New L1 Requirements

None. L1 compartment enforcement is complete.

#### New L3 Requirements

| REQ      | Description                                                                                                                                                                                     | SDK Mapping          |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| 21-L3-01 | `KnowledgeRecord` DataFlow model: `id`, `item_id`, `classification`, `owning_unit_address`, `compartments` (JSON list), `description`, `created_by`, `created_at`, `updated_at`                 | `@db.model`          |
| 21-L3-02 | Knowledge API router (`/api/v1/knowledge`): CRUD endpoints for knowledge items with classification and compartment fields                                                                       | FastAPI router       |
| 21-L3-03 | Knowledge creation passes through `governance_gate()` for mutation control                                                                                                                      | `governance.py`      |
| 21-L3-04 | Access check endpoint (`/api/v1/access/check`) can look up a persisted `KnowledgeRecord` by `item_id` instead of requiring all fields inline                                                    | Router enhancement   |
| 21-L3-05 | Integration test: create knowledge item with compartments via API, grant clearance with matching compartments, verify access allowed; then without compartments, verify access denied at Step 3 | `tests/integration/` |

#### New Models

| Model             | Fields                                                                                                                                            | Purpose                           |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `KnowledgeRecord` | `id`, `item_id`, `classification`, `owning_unit_address`, `compartments: dict`, `description`, `created_by`, `status`, `created_at`, `updated_at` | Persistent knowledge item catalog |

#### New/Modified API Endpoints

| Method | Path                          | Action                                                               |
| ------ | ----------------------------- | -------------------------------------------------------------------- |
| POST   | `/api/v1/knowledge`           | Create knowledge item                                                |
| GET    | `/api/v1/knowledge`           | List knowledge items (filterable by classification, owning_unit)     |
| GET    | `/api/v1/knowledge/{item_id}` | Get knowledge item detail                                            |
| PUT    | `/api/v1/knowledge/{item_id}` | Update classification/compartments                                   |
| DELETE | `/api/v1/knowledge/{item_id}` | Soft-delete knowledge item                                           |
| POST   | `/api/v1/access/check`        | (Modified) Accept `item_id` alone and look up from `KnowledgeRecord` |

---

### Issue #22: Vetting Workflow FSM for Clearance Approval

**Summary**: Enforce a finite state machine on clearance vetting status transitions. Currently L1's `VettingStatus` has 4 states (PENDING, ACTIVE, EXPIRED, REVOKED) but no SUSPENDED state, and `grant_clearance()` stores whatever you give it with no FSM enforcement.

#### Acceptance Criteria

| #    | Criterion                                                        | Status                                 |
| ---- | ---------------------------------------------------------------- | -------------------------------------- |
| AC-1 | `VettingStatus` includes SUSPENDED state                         | NEW -- L1 GAP                          |
| AC-2 | FSM transitions are enforced (not just documented)               | NEW -- L1 or L3                        |
| AC-3 | Multi-approver support for clearance grants at SECRET/TOP_SECRET | NEW -- L3 (uses shared infra from #25) |
| AC-4 | Approve, suspend, revoke, reinstate endpoints at L3              | NEW -- L3                              |
| AC-5 | Clearance grants start as PENDING and require approval workflow  | NEW -- L3                              |
| AC-6 | Audit trail for every vetting status transition                  | NEW -- L3                              |

#### Evidence for Current State

- **VettingStatus enum** at `.venv/.../kailash/trust/pact/clearance.py` lines 32-38: 4 values -- `PENDING`, `ACTIVE`, `EXPIRED`, `REVOKED`. No `SUSPENDED`.
- **RoleClearance** at lines 97-127: `frozen=True` dataclass. `vetting_status` defaults to `ACTIVE` -- meaning `grant_clearance()` can store any status with no transition validation.
- **L1 `grant_clearance()`** at engine.py line 1056: stores the clearance and emits audit. No FSM check.
- **L3 clearance router** at `clearance.py` line 84: constructs `RoleClearance(vetting_status=...)` but does not validate transitions.
- **TODO-2001 spec** specified SUSPENDED state and transition table: `PENDING->ACTIVE, ACTIVE->SUSPENDED/REVOKED, SUSPENDED->REVOKED`. The SUSPENDED state was dropped during implementation (likely because L1 simplified to 4 states).

#### L1 Change Assessment: SUSPENDED State

**Decision: Add SUSPENDED to L1 VettingStatus enum.**

This is a backward-compatible enum addition. Existing code that checks `!= VettingStatus.ACTIVE` already correctly denies SUSPENDED clearances (since SUSPENDED is not ACTIVE). The only change is adding the enum value.

Whether FSM transition enforcement belongs in L1 or L3 is the key architectural question:

| Option               | Where                                     | Pros                                                             | Cons                                                                                             |
| -------------------- | ----------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| A: FSM in L1 engine  | `GovernanceEngine.transition_clearance()` | Enforcement at the lowest layer; cannot be bypassed              | Requires L1 release for any transition table change; L1 currently has no concept of "transition" |
| B: FSM in L3 service | `ClearanceVettingService` at L3           | Faster iteration; L1 only needs the enum; FSM table is L3 config | An L1 consumer could bypass L3 and call `grant_clearance()` with any status                      |

**Recommendation: Option A for the enum + basic validation, Option B for the workflow.**

L1 adds SUSPENDED to the enum and adds a `_VALID_TRANSITIONS` map that `grant_clearance()` checks if the role already has a clearance. L3 builds the approval workflow, multi-approver logic, and API endpoints on top.

#### New L1 Requirements

| REQ      | Description                                                                       | Release Impact                         |
| -------- | --------------------------------------------------------------------------------- | -------------------------------------- |
| 22-L1-01 | Add `SUSPENDED = "suspended"` to `VettingStatus` enum                             | Backward-compatible enum addition      |
| 22-L1-02 | Add `_VALID_TRANSITIONS` map to `clearance.py`                                    | Internal enforcement                   |
| 22-L1-03 | `grant_clearance()` checks transition validity when existing clearance exists     | Fail-closed: reject invalid transition |
| 22-L1-04 | Add `transition_clearance(role_address, new_status)` method to `GovernanceEngine` | New public method                      |

Estimated L1 change size: ~40 lines in `clearance.py`, ~30 lines in `engine.py`. Backward-compatible. Requires kailash-pact patch release (0.7.x -> 0.8.0 or 0.7.1).

#### New L3 Requirements

| REQ      | Description                                                                                                          | SDK Mapping          |
| -------- | -------------------------------------------------------------------------------------------------------------------- | -------------------- |
| 22-L3-01 | `ClearanceVetting` DataFlow model: tracks vetting requests with status, approvals, audit trail                       | `@db.model`          |
| 22-L3-02 | `ClearanceVettingService`: orchestrates the vetting workflow (submit -> pending -> approve/reject -> active/revoked) | Service class        |
| 22-L3-03 | Clearance grant endpoint modified: SECRET/TOP_SECRET grants require multi-approver (delegates to #25 shared infra)   | Router modification  |
| 22-L3-04 | New endpoints: `POST /api/v1/clearance/suspend`, `POST /api/v1/clearance/reinstate`                                  | Router additions     |
| 22-L3-05 | `POST /api/v1/clearance/grant` now creates PENDING vetting record instead of immediately granting ACTIVE             | Behavior change      |
| 22-L3-06 | Audit anchor on every vetting status transition (approve, suspend, revoke, reinstate)                                | `_emit_audit()`      |
| 22-L3-07 | Integration test: full vetting lifecycle PENDING -> ACTIVE -> SUSPENDED -> REVOKED with multi-approver at SECRET     | `tests/integration/` |

#### New Models

| Model              | Fields                                                                                                                                                                                                                                                      | Purpose                           |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `ClearanceVetting` | `id`, `role_address`, `requested_level`, `requested_compartments: dict`, `current_status` (vetting FSM state), `requested_by`, `approved_by: dict` (list of approvers), `required_approvals: int`, `nda_signed: bool`, `reason`, `created_at`, `updated_at` | Tracks clearance vetting requests |

#### New/Modified API Endpoints

| Method | Path                                             | Action                                                        |
| ------ | ------------------------------------------------ | ------------------------------------------------------------- |
| POST   | `/api/v1/clearance/grant`                        | (Modified) Creates PENDING vetting record; returns vetting_id |
| POST   | `/api/v1/clearance/vetting/{vetting_id}/approve` | Approve a pending vetting request (multi-approver aware)      |
| POST   | `/api/v1/clearance/vetting/{vetting_id}/reject`  | Reject a pending vetting request                              |
| POST   | `/api/v1/clearance/suspend`                      | Suspend an ACTIVE clearance (transitions to SUSPENDED)        |
| POST   | `/api/v1/clearance/reinstate`                    | Reinstate a SUSPENDED clearance (creates new PENDING vetting) |
| GET    | `/api/v1/clearance/vetting`                      | List pending vetting requests                                 |
| GET    | `/api/v1/clearance/vetting/{vetting_id}`         | Get vetting request detail                                    |

#### FSM Transition Table

```
PENDING   -> ACTIVE     (on approval -- all required approvers satisfied)
PENDING   -> REVOKED    (on rejection or expiry)
ACTIVE    -> SUSPENDED  (on suspend action)
ACTIVE    -> EXPIRED    (on time-based expiry)
ACTIVE    -> REVOKED    (on revoke action)
SUSPENDED -> ACTIVE     (on reinstate -- creates new PENDING, goes through approval again)
SUSPENDED -> REVOKED    (on revoke action)
EXPIRED   -> (terminal) (must re-apply)
REVOKED   -> (terminal) (must re-apply)
```

Note: SUSPENDED -> ACTIVE is modeled as "reinstate creates a new vetting request" rather than a direct transition. This ensures re-vetting always goes through the approval workflow.

---

### Issue #23: Bootstrap Mode for New Orgs

**Summary**: When a new org is deployed, there are no envelopes configured yet. Currently `compute_envelope()` returns `None` (maximally restrictive). Bootstrap mode should provide time-limited permissive defaults so the org can be configured.

#### Acceptance Criteria

| #    | Criterion                                                           | Status |
| ---- | ------------------------------------------------------------------- | ------ |
| AC-1 | New orgs can operate during initial setup without BLOCKED actions   | NEW    |
| AC-2 | Bootstrap mode is time-limited (configurable, default 24h)          | NEW    |
| AC-3 | Bootstrap envelopes are more permissive than production but bounded | NEW    |
| AC-4 | Auto-expiry transitions org to normal governance after deadline     | NEW    |
| AC-5 | Audit trail records bootstrap mode activation and expiry            | NEW    |
| AC-6 | Bootstrap mode can be ended early by explicit action                | NEW    |

#### L1 Change Assessment: Bootstrap Mode Parameter

**Decision: L3-only implementation using the existing L1 API.**

Rationale: L1's `compute_envelope()` returns `None` when no envelopes are configured. L3 can intercept this `None` and substitute a bootstrap envelope. This keeps bootstrap as a platform concern (L3), not a governance primitive (L1).

The bootstrap envelope is a time-limited `RoleEnvelope` with permissive-but-bounded defaults set on every role via `engine.set_role_envelope()` during org deployment. When bootstrap expires, these envelopes are replaced (or removed) and the org falls back to its configured state.

#### New L1 Requirements

None. L3 handles bootstrap entirely using existing L1 `set_role_envelope()` and `compute_envelope()` APIs.

#### New L3 Requirements

| REQ      | Description                                                                                                                                                      | SDK Mapping          |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| 23-L3-01 | `BootstrapConfig` dataclass: `enabled: bool`, `duration_hours: int` (default 24), `max_budget: float`, `max_daily_actions: int`, `allowed_actions: list[str]`    | Dataclass            |
| 23-L3-02 | `BootstrapManager` service: activates bootstrap mode during org deploy, creates time-limited role envelopes for all roles, schedules expiry                      | Service class        |
| 23-L3-03 | `BootstrapRecord` DataFlow model: tracks bootstrap activation per org with `expires_at`, `status` (active/expired/ended_early), `bootstrap_envelope_ids`         | `@db.model`          |
| 23-L3-04 | Org deploy endpoint (`POST /api/v1/org/deploy`) accepts optional `bootstrap` config                                                                              | Router modification  |
| 23-L3-05 | Auto-expiry: background task checks active bootstrap records and expires them when `datetime.now(UTC) > expires_at` (uses shared auto-expiry scheduler from #24) | Scheduler            |
| 23-L3-06 | `POST /api/v1/org/bootstrap/end` endpoint to end bootstrap early                                                                                                 | Router addition      |
| 23-L3-07 | `GET /api/v1/org/bootstrap/status` endpoint to check bootstrap state                                                                                             | Router addition      |
| 23-L3-08 | Audit anchor on bootstrap activation, expiry, and early termination                                                                                              | `_emit_audit()`      |
| 23-L3-09 | Integration test: deploy org with bootstrap, verify permissive operation, wait for expiry, verify restrictive operation                                          | `tests/integration/` |

#### New Models

| Model             | Fields                                                                                                                                                                                                                         | Purpose                       |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| `BootstrapRecord` | `id`, `org_id`, `status` (active/expired/ended_early), `started_at`, `expires_at`, `bootstrap_config: dict`, `envelope_ids: dict` (list of bootstrap envelope IDs created), `ended_by`, `ended_at`, `created_at`, `updated_at` | Tracks bootstrap mode per org |

#### New/Modified API Endpoints

| Method | Path                           | Action                                                                     |
| ------ | ------------------------------ | -------------------------------------------------------------------------- |
| POST   | `/api/v1/org/deploy`           | (Modified) Accepts optional `bootstrap: {duration_hours, max_budget, ...}` |
| POST   | `/api/v1/org/bootstrap/end`    | End bootstrap early for an org                                             |
| GET    | `/api/v1/org/bootstrap/status` | Get current bootstrap status for an org                                    |

#### Bootstrap Envelope Defaults

```python
BOOTSTRAP_DEFAULTS = ConstraintEnvelopeConfig(
    id="bootstrap-default",
    financial=FinancialConstraintConfig(max_budget=1000.0, max_single_action_cost=100.0),
    operational=OperationalConstraintConfig(
        max_daily_actions=500,
        allowed_actions=["read", "write", "query", "create", "update"],
    ),
    temporal=TemporalConstraintConfig(max_session_hours=8),
    data_access=DataAccessConstraintConfig(
        max_classification="confidential",  # Not SECRET/TOP_SECRET during bootstrap
    ),
    communication=CommunicationConstraintConfig(allowed_channels=["internal"]),
)
```

The bootstrap envelope intentionally caps classification at CONFIDENTIAL -- SECRET and TOP_SECRET access requires explicit clearance grants that should not be auto-provisioned.

---

### Issue #24: Task Envelopes (Ephemeral Layer 2 Narrowing)

**Summary**: L1 has `TaskEnvelope` and `set_task_envelope()`. L3 has a `set_task` endpoint. Gaps are persistence, auto-expiry, and agent acknowledgment.

#### Acceptance Criteria

| #    | Criterion                                                       | Status                  |
| ---- | --------------------------------------------------------------- | ----------------------- |
| AC-1 | Task envelopes are persisted in a DataFlow model                | NEW -- GAP              |
| AC-2 | Task envelopes auto-expire when `expires_at` passes             | NEW -- GAP              |
| AC-3 | Expired task envelopes are cleaned up (not just ignored)        | NEW -- GAP              |
| AC-4 | Agent must acknowledge task envelope before starting work       | NEW -- GAP              |
| AC-5 | Task envelope creation validates monotonic tightening           | ALREADY SATISFIED at L1 |
| AC-6 | `compute_envelope()` uses active task envelope when not expired | ALREADY SATISFIED at L1 |

#### Evidence for "Already Satisfied"

- **AC-5**: `engine.set_task_envelope()` at engine.py lines 1769-1780 validates monotonic tightening via `RoleEnvelope.validate_tightening()`.
- **AC-6**: `compute_effective_envelope()` at envelopes.py line 700 accepts `task_envelope` parameter; the engine passes it at line 903 via `get_active_task_envelope()`.

#### New L1 Requirements

None. L1's `TaskEnvelope` dataclass and `set_task_envelope()` are complete. Persistence and scheduling are L3 concerns.

#### New L3 Requirements

| REQ      | Description                                                                                                                                                                                                                                          | SDK Mapping          |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| 24-L3-01 | `TaskEnvelopeRecord` DataFlow model: `id`, `task_id`, `role_address`, `parent_envelope_id`, `envelope_config: dict`, `status` (active/expired/acknowledged/rejected), `expires_at`, `acknowledged_at`, `acknowledged_by`, `created_at`, `updated_at` | `@db.model`          |
| 24-L3-02 | Task envelope creation endpoint persists to `TaskEnvelopeRecord` AND calls `engine.set_task_envelope()`                                                                                                                                              | Router modification  |
| 24-L3-03 | Auto-expiry scheduler: polls active `TaskEnvelopeRecord` entries, transitions expired ones to `status=expired` (uses shared scheduler from #23)                                                                                                      | Scheduler            |
| 24-L3-04 | Agent acknowledgment endpoint: `POST /api/v1/envelopes/{role_address}/task/{task_id}/acknowledge` -- agent confirms it has read and accepted the task envelope                                                                                       | Router addition      |
| 24-L3-05 | Task envelope rejection endpoint: agent can reject a task envelope it finds too restrictive (triggers re-negotiation)                                                                                                                                | Router addition      |
| 24-L3-06 | `verify_action()` context should include `task_id` when an agent is operating under a task envelope, ensuring the engine uses the task-narrowed envelope                                                                                             | Context injection    |
| 24-L3-07 | Integration test: create task envelope, verify narrowing, acknowledge, expire via time, verify fallback to role envelope                                                                                                                             | `tests/integration/` |

#### New Models

| Model                | Fields                                                                                                                                                                                                                              | Purpose                           |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `TaskEnvelopeRecord` | `id`, `task_id`, `role_address`, `parent_envelope_id`, `envelope_config: dict`, `status` (active/expired/acknowledged/rejected), `expires_at`, `acknowledged_at`, `acknowledged_by`, `rejection_reason`, `created_at`, `updated_at` | Persistent task envelope tracking |

#### New/Modified API Endpoints

| Method | Path                                                                     | Action                                              |
| ------ | ------------------------------------------------------------------------ | --------------------------------------------------- |
| PUT    | `/api/v1/governance/envelopes/{role_address}/task`                       | (Modified) Also persists to `TaskEnvelopeRecord`    |
| GET    | `/api/v1/governance/envelopes/{role_address}/task/active`                | List active (non-expired) task envelopes for a role |
| POST   | `/api/v1/governance/envelopes/{role_address}/task/{task_id}/acknowledge` | Agent acknowledges task envelope                    |
| POST   | `/api/v1/governance/envelopes/{role_address}/task/{task_id}/reject`      | Agent rejects task envelope                         |

---

### Issue #25: Multi-Approver Workflows

**Summary**: The current `AgenticDecision` model supports single-approver only (`decided_by: str`). Need multi-approver support with configurable thresholds, partial approval tracking, and auto-reject timeout.

#### Acceptance Criteria

| #    | Criterion                                                             | Status |
| ---- | --------------------------------------------------------------------- | ------ |
| AC-1 | Decisions can require N approvals (configurable per operation type)   | NEW    |
| AC-2 | Partial approval state is tracked (2/3 approved)                      | NEW    |
| AC-3 | Per-operation-type approval configuration                             | NEW    |
| AC-4 | Auto-reject after configurable timeout                                | NEW    |
| AC-5 | Approval events are audited                                           | NEW    |
| AC-6 | Existing single-approver flow continues to work (backward compatible) | NEW    |

#### New L1 Requirements

None. Multi-approver is entirely an L3 platform workflow concern. L1's `verify_action()` returns HELD; L3 decides how many humans must approve before the hold is released.

#### New L3 Requirements

| REQ      | Description                                                                                                                                                   | SDK Mapping                  |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| 25-L3-01 | `ApprovalConfig` DataFlow model: maps operation types to approval requirements (`required_approvals: int`, `timeout_hours: int`, `eligible_roles: list[str]`) | `@db.model`                  |
| 25-L3-02 | `ApprovalRecord` DataFlow model: individual approval/rejection from one approver on one decision                                                              | `@db.model`                  |
| 25-L3-03 | `MultiApproverService`: orchestrates approval collection, tracks partial state, resolves when threshold met or timeout reached                                | Service class                |
| 25-L3-04 | `AgenticDecision` model enhanced: `required_approvals: int`, `current_approvals: int`, `approval_records: dict` (JSON list of approval IDs)                   | Model modification           |
| 25-L3-05 | Decision approve/reject endpoints updated: record individual approval, check if threshold met, transition decision status only when quorum reached            | Router modification          |
| 25-L3-06 | `POST /api/v1/approval-config` endpoint for configuring per-operation-type approval requirements                                                              | Router addition              |
| 25-L3-07 | Auto-reject scheduler: pending decisions past timeout are auto-rejected (uses shared scheduler)                                                               | Scheduler                    |
| 25-L3-08 | `governance_gate()` enhanced: when creating HELD decision, looks up `ApprovalConfig` for the action type to set `required_approvals`                          | `governance.py` modification |
| 25-L3-09 | Backward compatibility: if no `ApprovalConfig` exists for an action type, `required_approvals` defaults to 1 (current behavior)                               | Default handling             |
| 25-L3-10 | Integration test: create decision requiring 3 approvals, submit 2 (verify still pending), submit 3rd (verify approved), test timeout auto-reject              | `tests/integration/`         |

#### New Models

| Model            | Fields                                                                                                                                            | Purpose                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `ApprovalConfig` | `id`, `operation_type`, `required_approvals: int`, `timeout_hours: int`, `eligible_roles: dict` (JSON list), `org_id`, `created_at`, `updated_at` | Per-operation-type approval requirements |
| `ApprovalRecord` | `id`, `decision_id`, `approver_address`, `approver_identity`, `verdict` (approved/rejected), `reason`, `created_at`                               | Individual approver's vote on a decision |

#### Modified Models

| Model             | Change                                                                                            | Impact                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `AgenticDecision` | Add `required_approvals: int = 1`, `current_approvals: int = 0`, `approval_record_ids: dict = {}` | Backward-compatible (defaults maintain current behavior) |

#### New/Modified API Endpoints

| Method | Path                                        | Action                                                     |
| ------ | ------------------------------------------- | ---------------------------------------------------------- |
| POST   | `/api/v1/decisions/{decision_id}/approve`   | (Modified) Records individual approval, checks quorum      |
| POST   | `/api/v1/decisions/{decision_id}/reject`    | (Modified) Records individual rejection, may auto-reject   |
| GET    | `/api/v1/decisions/{decision_id}/approvals` | List individual approval records for a decision            |
| POST   | `/api/v1/approval-config`                   | Create/update approval configuration for an operation type |
| GET    | `/api/v1/approval-config`                   | List approval configurations                               |
| GET    | `/api/v1/approval-config/{operation_type}`  | Get approval config for a specific operation type          |

---

## 2. Implementation Order

### Dependency Graph

```
#25 Multi-Approver ──────────────┐
                                  │ (shared: multi-approver infra)
#22 Vetting Workflow FSM ────────┤
      │                           │
      │ (L1 enum change)          │
      ▼                           │
  L1 Release (kailash-pact)       │
                                  │
#23 Bootstrap Mode ──────────────┤
      │                           │ (shared: auto-expiry scheduler)
      ▼                           │
#24 Task Envelopes ──────────────┘

#21 Compartment Access ──── (independent)
```

### Phase Ordering

#### Phase 0: Shared Infrastructure (1 session)

Build the three cross-cutting components that multiple issues depend on:

1. **Auto-Expiry Scheduler** -- Background polling service that checks `expires_at` fields across models and transitions expired records. Used by #23 (bootstrap), #24 (task envelopes), #25 (decision timeout).

2. **Multi-Approver Service** -- Generic approval collection engine with configurable thresholds. Used by #22 (clearance vetting) and #25 (general multi-approver).

3. **Audit Anchor Helper** -- Standardized pattern for creating audit anchors on governance mutations. Used by all 5 issues.

#### Phase 1: L1 Changes + Independent L3 Work (1-2 sessions, parallelizable)

**Track A (L1)**: Issue #22 L1 changes only

- Add SUSPENDED to VettingStatus
- Add transition validation to `grant_clearance()`
- Add `transition_clearance()` method
- Run L1 tests, cut kailash-pact release

**Track B (L3, parallel with Track A)**:

- Issue #21: Compartment-based access (fully independent, no L1 change)
- Issue #25: Multi-approver workflows (L3-only, uses Phase 0 shared infra)
- Issue #23: Bootstrap mode (L3-only, uses Phase 0 shared infra)
- Issue #24: Task envelope persistence (L3-only, uses Phase 0 shared infra)

#### Phase 2: L1-Dependent L3 Work (1 session, after L1 release)

- Issue #22 L3 work: Vetting workflow FSM endpoints, ClearanceVetting model, integration with multi-approver service from #25
- Pin `kailash-pact>=0.8.0` (or whatever the release version is)

#### Phase 3: Integration Testing (1 session)

- Cross-issue integration tests (e.g., bootstrap mode + task envelopes, vetting workflow + multi-approver)
- End-to-end test: deploy org with bootstrap, grant clearance with multi-approver, create task envelope, verify compartment access

### Parallel Execution Plan

```
Session 1:  Phase 0 (shared infrastructure)
Session 2:  Track A (L1 #22) || Track B (#21, #25 models + service)
Session 3:  Track B continued (#23, #24) || L1 release
Session 4:  Phase 2 (#22 L3) + Phase 3 (integration tests)
```

Total: 3-4 autonomous sessions.

---

## 3. Shared Infrastructure

### 3.1 Auto-Expiry Scheduler

**Used by**: #23 (bootstrap expiry), #24 (task envelope expiry), #25 (decision timeout)

```python
# src/pact_platform/use/services/expiry_scheduler.py

class ExpiryScheduler:
    """Polls time-limited records and transitions expired ones.

    Registers expiry handlers for each model type. Runs on a configurable
    interval (default: 60 seconds). Thread-safe.
    """

    def register_handler(
        self,
        model_name: str,
        status_field: str,
        expires_field: str,
        active_status: str,
        expired_status: str,
        on_expire: Callable | None = None,  # optional callback
    ) -> None: ...

    async def poll(self) -> int:
        """Check all registered models, expire overdue records. Returns count expired."""
        ...
```

Handlers registered:

- `BootstrapRecord`: `status=active` -> `status=expired` when `expires_at` passed
- `TaskEnvelopeRecord`: `status=active` -> `status=expired` when `expires_at` passed
- `AgenticDecision`: `status=pending` -> `status=expired` when `expires_at` passed (for timeout)

### 3.2 Multi-Approver Service

**Used by**: #22 (clearance vetting at SECRET/TOP_SECRET), #25 (general decision approval)

```python
# src/pact_platform/use/services/multi_approver.py

class MultiApproverService:
    """Generic multi-approver workflow engine.

    Records individual approvals against a target record. Resolves the
    target when the required approval count is met. Supports eligible
    role filtering and duplicate prevention.
    """

    async def record_approval(
        self,
        target_id: str,
        target_model: str,  # "AgenticDecision" or "ClearanceVetting"
        approver_address: str,
        approver_identity: str,
        verdict: str,  # "approved" or "rejected"
        reason: str = "",
    ) -> ApprovalResult: ...

    async def check_quorum(
        self,
        target_id: str,
        target_model: str,
    ) -> QuorumStatus: ...
```

### 3.3 Audit Anchor Pattern

**Used by**: All 5 issues

All governance mutations already follow the pattern in `governance.py` (`_emit_audit()`). The shared pattern is:

1. Call `governance_gate()` before mutation
2. Perform mutation
3. Emit audit anchor with structured details

No new code needed -- the existing pattern is sufficient. Each issue follows it.

---

## 4. L1 Change Assessment

### Summary Table

| Issue | L1 Change Required? | Change Description                          | Release Impact                      |
| ----- | ------------------- | ------------------------------------------- | ----------------------------------- |
| #21   | No                  | Compartment enforcement already exists      | --                                  |
| #22   | Yes                 | SUSPENDED enum + transition validation      | Patch release (backward-compatible) |
| #23   | No                  | Bootstrap is L3 wrapper using existing APIs | --                                  |
| #24   | No                  | TaskEnvelope already complete at L1         | --                                  |
| #25   | No                  | Multi-approver is L3 platform workflow      | --                                  |

### L1 Release Plan

Only Issue #22 requires an L1 change. The change is:

1. **clearance.py**: Add `SUSPENDED = "suspended"` to `VettingStatus` enum (~1 line)
2. **clearance.py**: Add `_VALID_TRANSITIONS` dict (~10 lines)
3. **clearance.py**: Add `validate_transition(current, new)` function (~15 lines)
4. **engine.py**: Add `transition_clearance(role_address, new_status)` public method (~30 lines)
5. **engine.py**: Modify `grant_clearance()` to check transition if existing clearance found (~10 lines)
6. **Tests**: ~50 lines of unit tests for transitions

Total L1 change: ~120 lines. Backward-compatible. Existing code that calls `grant_clearance()` with `VettingStatus.ACTIVE` continues to work (PENDING->ACTIVE is a valid transition, and first-time grants have no existing clearance to check against).

**Version**: kailash-pact 0.7.1 (patch) or 0.8.0 (minor, if the new `transition_clearance()` method is considered a feature).

### What Stays at L3

| Concern                   | Why L3                                          |
| ------------------------- | ----------------------------------------------- |
| Multi-approver workflows  | Platform UX concern, not governance primitive   |
| Bootstrap mode            | Deployment lifecycle, not constraint evaluation |
| Task envelope persistence | Platform data layer, L1 has memory stores       |
| Knowledge item catalog    | Platform data management                        |
| Auto-expiry scheduling    | Infrastructure concern                          |
| Approval configuration    | Per-deployment policy                           |

---

## 5. Risk Register

| Risk                                    | Likelihood | Impact | Mitigation                                                                                   |
| --------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------- |
| L1 release delays Phase 2 (#22 L3 work) | Medium     | Medium | Track B issues (#21, #23, #24, #25) are independent; only #22 L3 is blocked                  |
| Multi-approver complexity creep         | Medium     | High   | Keep the service generic with clear interface; #22 and #25 are the only consumers            |
| Bootstrap envelope too permissive       | Low        | High   | Cap at CONFIDENTIAL classification; bounded financial defaults; mandatory audit trail        |
| Auto-expiry scheduler misses records    | Low        | Medium | Idempotent polling with overlap; records check `is_expired` at read time as defense-in-depth |
| VettingStatus.SUSPENDED backward compat | Low        | Low    | New enum value; existing `!= ACTIVE` checks already handle it correctly                      |
| AgenticDecision model migration         | Medium     | Low    | New fields have defaults (`required_approvals=1`); no schema break                           |

---

## 6. Success Criteria

- [ ] L1 VettingStatus includes SUSPENDED with enforced transitions (kailash-pact release)
- [ ] KnowledgeRecord model persists classified items with compartments
- [ ] Compartment-based access check works end-to-end through API (Step 3 enforcement)
- [ ] Clearance vetting FSM enforces valid transitions (PENDING->ACTIVE, ACTIVE->SUSPENDED, etc.)
- [ ] SECRET/TOP_SECRET clearance grants require multi-approver workflow
- [ ] Bootstrap mode provides time-limited permissive defaults during org setup
- [ ] Bootstrap auto-expires and transitions to normal governance
- [ ] Task envelopes are persisted, auto-expire, and support agent acknowledgment
- [ ] Multi-approver decisions support configurable thresholds per operation type
- [ ] Auto-reject timeout works for pending decisions
- [ ] All mutations emit audit anchors
- [ ] All 5 issues have integration tests covering happy path and failure cases
- [ ] Existing single-approver flow continues to work unchanged (backward compatibility)
