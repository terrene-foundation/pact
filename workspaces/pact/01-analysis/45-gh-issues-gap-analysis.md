# Gap Analysis: GitHub Issues #21--#25

**Date**: 2026-04-06
**Scope**: L1 (kailash-pact 0.7.x, installed at kailash.trust.pact) and L3 (pact-platform 0.4.0)
**Method**: Source-level inspection of installed L1 site-packages and L3 src/ tree

---

## Executive Summary

Three of the five issues (#21, #23, #24) are largely addressed by existing L1 capabilities that the L3 platform does not yet fully surface. Two issues (#22, #25) require new logic at both layers. The highest-value work is wiring existing L1 primitives into L3 APIs, not rebuilding governance algorithms. The largest risk is issue #22 (vetting FSM), which requires an L1 enum extension (`SUSPENDED` state) that constitutes a breaking change to a frozen dataclass.

Complexity score: 19 (Moderate, approaching Complex threshold).

---

## Issue #21 -- Compartment-based access for SECRET/TOP_SECRET

### What Already Exists

**L1 -- fully implemented.** The 5-step access algorithm in `kailash.trust.pact.access.can_access()` already enforces compartments:

- **Step 3** (lines 379--407 of `access.py`): For items at SECRET or TOP_SECRET, checks `item.compartments - role_clearance.compartments` and denies if any are missing. Returns structured `AccessDecision` with `step_failed=3` and `audit_details` listing missing/role/item compartments.
- `RoleClearance` dataclass (line 98--126 of `clearance.py`): Has `compartments: frozenset[str]` field, frozen, default `frozenset()`.
- `KnowledgeItem` dataclass (line 24--43 of `knowledge.py`): Has `compartments: frozenset[str]` field, frozen, default `frozenset()`.
- `KnowledgeSharePolicy` dataclass (line 52--77 of `access.py`): Has `compartments: frozenset[str]` field for restricting sharing to specific compartments.
- `explain_access()` in `explain.py` (line 235+): Produces a step-by-step human-readable trace including compartment check results.

**L3 -- partially wired:**

- `clearance.py` router `grant_clearance` endpoint (line 87): Already passes `compartments=frozenset(compartments)` when constructing `RoleClearance`.
- `access.py` router `check_access` endpoint (line 115): Already passes `compartments=frozenset(compartments)` when constructing `KnowledgeItem`.
- `get_clearance` endpoint (line 193): Already returns `compartments: list(clearance.compartments)` in the response.

### What's Missing

| Gap                             | Layer | Severity | Detail                                                                                                                                                                            |
| ------------------------------- | ----- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No compartment CRUD API         | L3    | Medium   | Cannot add/remove individual compartments from an existing clearance without re-granting the entire clearance. No `PATCH /api/v1/clearance/{role_address}/compartments` endpoint. |
| No compartment listing endpoint | L3    | Low      | No endpoint to list all compartments in use across the org (useful for dashboard autocomplete).                                                                                   |
| No explain endpoint             | L3    | Medium   | `explain_access()` exists in L1 but is not exposed via any L3 API endpoint. Issue requests explain functions.                                                                     |
| No KnowledgeItem persistence    | L3    | Medium   | Knowledge items are ephemeral (constructed inline per access check). No DataFlow model for registering and persisting knowledge items with their compartments.                    |
| Compartment validation          | L3    | Low      | No validation that compartment names follow a consistent format (e.g., alphanumeric, max length). The L1 accepts arbitrary strings in frozenset.                                  |

### L1 vs L3 Boundary

- **L1 changes needed**: None. The 5-step algorithm, compartment field on `RoleClearance` and `KnowledgeItem`, and `explain_access()` are all present and tested.
- **L3 changes needed**: New API endpoints (explain, compartment CRUD), optional KnowledgeItem DataFlow model, dashboard wiring.

### Risk Assessment

| Risk                                                        | Likelihood | Impact               | Mitigation                                       |
| ----------------------------------------------------------- | ---------- | -------------------- | ------------------------------------------------ |
| Misunderstanding: team thinks compartments need to be built | Medium     | High (wasted effort) | This analysis documents that L1 is complete      |
| KnowledgeItem persistence model could grow unbounded        | Low        | Medium               | Apply MAX_STORE_SIZE (10,000) or paginated query |
| Compartment names with special characters                   | Low        | Low                  | Validate with regex at L3 API boundary           |

---

## Issue #22 -- Vetting workflow FSM for clearance approval

### What Already Exists

**L1 -- partial:**

- `VettingStatus` enum (line 32--38 of `clearance.py`): Has four states: `PENDING`, `ACTIVE`, `EXPIRED`, `REVOKED`. No `SUSPENDED` state.
- `can_access()` Step 1 (line 325 of `access.py`): Checks `vetting_status != VettingStatus.ACTIVE` and denies. This means PENDING, EXPIRED, and REVOKED all correctly block access.
- `GovernanceEngine.grant_clearance()` (line 1056 of `engine.py`): Stores the clearance with whatever `VettingStatus` the caller provides. No FSM enforcement -- the caller can set any status.
- `GovernanceEngine.revoke_clearance()` (line 1104 of `engine.py`): Deletes the clearance entirely (not a state transition -- the record is removed from the store).
- Audit anchors are emitted for both grant and revoke operations.

**L3 -- partial:**

- `clearance.py` router: `grant_clearance` constructs `RoleClearance` with `vetting_status` defaulting to `VettingStatus.ACTIVE` (L1 default). No endpoint for status transitions.
- `AgenticDecision` model: Single `decided_by` field. No multi-approver fields.

### What's Missing

| Gap                                        | Layer | Severity | Detail                                                                                                                                                                                                             |
| ------------------------------------------ | ----- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| No `SUSPENDED` enum value                  | L1    | High     | Issue requests `active->suspended` and `suspended->active` transitions. `VettingStatus` has no `SUSPENDED` member. Adding it to the `str` Enum is backward-compatible for deserialization but is a new L1 release. |
| No FSM enforcement                         | L1    | High     | `grant_clearance()` accepts any `VettingStatus` without validating the transition from the current state. A caller can set `ACTIVE` directly, bypassing the `PENDING->ACTIVE` flow.                                |
| No `update_vetting_status()` engine method | L1    | High     | The engine has `grant_clearance()` and `revoke_clearance()` but no method to transition vetting status. `revoke_clearance()` deletes rather than marking as REVOKED.                                               |
| No transition audit anchors                | L1    | Medium   | Each FSM transition should emit a distinct EATP audit anchor (e.g., `CLEARANCE_SUSPENDED`, `CLEARANCE_REINSTATED`). Currently only `CLEARANCE_GRANTED` and `CLEARANCE_REVOKED` exist in `PactAuditAction`.         |
| No multi-approver per clearance level      | Both  | High     | Issue requests configurable approver count per clearance level (e.g., SECRET requires 2 approvers, TOP_SECRET requires 3). Neither L1 nor L3 has this. See #25 for overlap.                                        |
| No L3 transition endpoints                 | L3    | High     | No `POST /api/v1/clearance/{role_address}/suspend`, `/reinstate`, `/transition` endpoints.                                                                                                                         |
| `revoke_clearance` is destructive          | L1    | Medium   | Current implementation removes the clearance from the store. The issue implies REVOKED should be a terminal state on the record, not deletion.                                                                     |

### L1 vs L3 Boundary

- **L1 changes needed** (kailash-pact release required):
  1. Add `SUSPENDED = "suspended"` to `VettingStatus` enum.
  2. Add `update_vetting_status(role_address, new_status)` to `GovernanceEngine` with FSM transition validation.
  3. Change `revoke_clearance()` to set status to REVOKED rather than deleting.
  4. Add `PactAuditAction` enum values for each transition.
  5. Add FSM transition table as a module constant for validation.
- **L3 changes needed**:
  1. New transition API endpoints.
  2. Multi-approver logic (shared with #25).
  3. Dashboard UI for vetting workflow.

### Dependencies

- Depends on **#25** (multi-approver) for the clearance level approval requirement.
- The `SUSPENDED` enum addition requires a kailash-pact release (minimum 0.8.0).

### Risk Assessment

| Risk                                                            | Likelihood | Impact   | Mitigation                                                                                                                      |
| --------------------------------------------------------------- | ---------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| L1 enum addition breaks deserialization of existing records     | Low        | High     | `str`-backed Enum handles unknown values gracefully; test with `VettingStatus("suspended")` before release                      |
| `revoke_clearance()` behavior change breaks callers             | Medium     | High     | Deprecate delete-based revocation; add `revoke_clearance()` as status transition; provide `delete_clearance()` for true removal |
| FSM bypass if L3 calls `grant_clearance()` with ACTIVE directly | High       | Critical | FSM must be enforced at L1, not L3 -- the engine method must reject invalid transitions                                         |
| Multi-approver scope creep                                      | Medium     | Medium   | Implement vetting FSM without multi-approver first; #25 adds multi-approver as an independent concern                           |

---

## Issue #23 -- Bootstrap mode for new orgs

### What Already Exists

**L1 -- not implemented.** The `GovernanceEngine.__init__()` has no `bootstrap_mode` parameter. `compute_effective_envelope()` (line 700 of `envelopes.py`) returns `None` when no envelopes are configured, which is interpreted as "maximally permissive" by `verify_action()` (line 533-534 of `engine.py`: `level = "auto_approved"`, `reason = "No envelope constraints -- action permitted"`).

This means that a newly created org with no envelopes configured is already effectively in a permissive mode -- but without time limits, audit marking, or dashboard warnings.

**L3 -- partially relevant:**

- `PlatformBootstrap` class (line 145 of `bootstrap.py`): Handles trust hierarchy initialization but has no concept of a time-limited bootstrap mode.
- `governance_gate()` (line 70 of `governance.py`): Has a `_dev_mode` flag that allows operations without a governance engine. This is similar to bootstrap mode but is a binary toggle without time limits or audit marking.
- Emergency bypass router: Implements time-limited permission elevation with auto-expiry and audit. This is architecturally similar to what bootstrap mode needs.

### What's Missing

| Gap                                                             | Layer | Severity | Detail                                                                                                                  |
| --------------------------------------------------------------- | ----- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| No `bootstrap_mode` parameter on `compute_effective_envelope()` | L1    | Medium   | Issue requests a parameter that returns permissive defaults when no envelopes are configured, with explicit time limit. |
| No bootstrap mode state in engine                               | L1    | Medium   | Engine needs to track whether it is in bootstrap mode, when bootstrap started, and when it expires.                     |
| No auto-expiry for bootstrap mode                               | Both  | High     | The most dangerous scenario: bootstrap mode is enabled and never turned off. Must auto-expire.                          |
| No dashboard warning for bootstrap mode                         | L3    | Medium   | Users should see a prominent warning that governance is permissive.                                                     |
| No audit marking for bootstrap-mode decisions                   | L1    | Medium   | Verdicts during bootstrap should be marked in audit trail as `bootstrap_mode=true`.                                     |
| Bootstrap mode API flag                                         | L3    | Low      | Need an endpoint to check if bootstrap mode is active and when it expires.                                              |

### L1 vs L3 Boundary

**Key architectural decision**: Bootstrap mode could be implemented entirely at L3 as a time-limited wrapper around the existing dev_mode/governance_gate, or it could be an L1 engine feature with first-class support.

- **Option A -- L3 only** (lower effort, lower quality):
  - Extend `governance_gate()` with a bootstrap mode that auto-approves with audit marking.
  - Time-limited via a startup timestamp + TTL.
  - No L1 release needed.
  - Risk: bypasses the engine's audit trail; verdicts are not recorded in EATP chain.

- **Option B -- L1 engine feature** (higher effort, proper governance):
  - Add `bootstrap_mode: bool` and `bootstrap_expires_at: datetime | None` to `GovernanceEngine.__init__()`.
  - When bootstrap_mode is active and no envelopes exist, `verify_action()` returns `auto_approved` with `audit_details["bootstrap_mode"] = True`.
  - Engine auto-expires bootstrap mode: after expiry, missing envelopes → BLOCKED (fail-closed).
  - Requires kailash-pact release.

**Recommendation**: Option B. Bootstrap mode is a governance concern and belongs in L1 where audit trail integrity is guaranteed.

### Dependencies

- No hard dependencies on other issues.
- Could benefit from #24 (task envelopes) for time-scoped permission grants, but the use case is different (org-level vs task-level).

### Risk Assessment

| Risk                                                    | Likelihood | Impact   | Mitigation                                                                   |
| ------------------------------------------------------- | ---------- | -------- | ---------------------------------------------------------------------------- |
| Bootstrap mode never expires                            | High       | Critical | Auto-expiry is mandatory; engine must enforce it                             |
| Bootstrap mode used in production as a permanent bypass | Medium     | Critical | Maximum TTL (e.g., 72 hours); requires re-enable with audit anchor           |
| No envelopes configured after bootstrap expires         | Medium     | High     | Engine should BLOCK all actions post-expiry; dashboard shows setup checklist |

---

## Issue #24 -- Task envelopes (ephemeral Layer 2 narrowing)

### What Already Exists

**L1 -- fully implemented:**

- `TaskEnvelope` dataclass (line 674 of `envelopes.py`): Fields: `id`, `task_id`, `parent_envelope_id`, `envelope` (ConstraintEnvelopeConfig), `expires_at`, `created_at`. Has `is_expired` property.
- `compute_effective_envelope()` (line 700 of `envelopes.py`): Accepts optional `task_envelope` parameter and intersects it with the role envelope chain if present and not expired.
- `GovernanceEngine.set_task_envelope()` (line 1755 of `engine.py`): Thread-safe, validates monotonic tightening against parent role envelope, persists via `EnvelopeStore`, emits EATP audit anchor.
- `GovernanceEngine.compute_envelope()` (line 869 of `engine.py`): Accepts `task_id` parameter; looks up active task envelope and passes it to `compute_effective_envelope()`.
- `verify_action()` (line 513 of `engine.py`): Reads `task_id` from context and passes it through to envelope computation. Task envelopes are already factored into governance decisions.
- Monotonic tightening validation on set (line 1772): Parent role envelope is resolved, `RoleEnvelope.validate_tightening()` called.

**L3 -- fully wired:**

- `envelopes.py` router `set_task_envelope` endpoint (line 214): Accepts `task_id`, `parent_envelope_id`, and `envelope` dict. Constructs `TaskEnvelope` and calls `_engine.set_task_envelope()`.
- `get_envelope` endpoint (line 52): Returns the effective envelope which already includes task envelope narrowing.
- Both endpoints validate D/T/R grammar, NaN/Inf, and pass through governance gate.

### What's Missing

| Gap                                                    | Layer | Severity | Detail                                                                                                                                                                                                   |
| ------------------------------------------------------ | ----- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No TaskEnvelope DataFlow model                         | L3    | Low      | Issue requests a DataFlow model for persistence. Currently task envelopes are stored in L1's `EnvelopeStore` (memory or SQLite). A DataFlow model would add dashboard queryability but duplicates state. |
| No auto-expiry scheduler                               | L3    | Medium   | Task envelopes expire via `is_expired` check at access time (lazy expiry). No background job actively cleans up expired envelopes or emits expiry audit events.                                          |
| No agent acknowledgment                                | L3    | Medium   | Issue requests agents acknowledge receipt of task envelopes. No acknowledgment mechanism exists at either layer.                                                                                         |
| No list/query endpoint for task envelopes              | L3    | Low      | Cannot list all active task envelopes for a role or org. No `GET /api/v1/governance/envelopes/tasks` endpoint.                                                                                           |
| `TaskEnvelope` missing `expires_at` in L3 construction | L3    | Low      | The `set_task_envelope` endpoint (line 287) constructs `TaskEnvelope` without setting `expires_at` -- it relies on L1 defaults. Should require the caller to specify an expiry.                          |

### L1 vs L3 Boundary

- **L1 changes needed**: None for core functionality. Optional: add `list_active_task_envelopes()` method to engine for querying, add `expire_task_envelope()` for explicit expiry with audit.
- **L3 changes needed**: Query endpoint, optional DataFlow model (if dashboard needs it), auto-expiry scheduler (asyncio task), `expires_at` required in API body, agent acknowledgment flow.

### Dependencies

- No hard dependencies on other issues.
- The agent acknowledgment mechanism could be a generic pattern reused by #25 (multi-approver).

### Risk Assessment

| Risk                                                            | Likelihood | Impact | Mitigation                                                             |
| --------------------------------------------------------------- | ---------- | ------ | ---------------------------------------------------------------------- |
| Missing `expires_at` in L3 API creates unbounded task envelopes | High       | High   | Make `expires_at` required in endpoint body; validate max TTL          |
| Lazy expiry means stale envelopes accumulate in store           | Medium     | Low    | Background cleanup job; bounded store already enforces MAX_STORE_SIZE  |
| Agent acknowledgment adds complexity for marginal value in v1   | Medium     | Low    | Defer acknowledgment to post-v1; document as future enhancement        |
| DataFlow model duplicates L1 state                              | Medium     | Medium | Use L1 as source of truth; DataFlow model is a read-through cache only |

---

## Issue #25 -- Multi-approver workflows

### What Already Exists

**L1 -- not applicable.** Multi-approver is a platform (L3) concern. The L1 `GovernanceEngine` makes governance decisions (BLOCKED, HELD, AUTO_APPROVED) but does not manage approval workflows. The HELD verdict creates the need for approval; the approval workflow is L3.

**L3 -- single-approver implemented:**

- `AgenticDecision` model (line 307 of `models/__init__.py`): Has `decided_by: Optional[str]`, `decided_at: Optional[str]`, `decision_reason: str`, `envelope_version: int` (optimistic locking). Single-approver only.
- `decisions.py` router (line 155): `approve_decision` and `reject_decision` endpoints accept `decided_by` and `reason`. Use optimistic locking via `envelope_version`.
- `governance_gate()` (line 135 of `governance.py`): Creates `AgenticDecision` record when verdict is HELD. Single decision record per held action.
- Emergency bypass: Already implements a review workflow pattern (reviews_due, reviews_overdue endpoints) that could inform multi-approver design.

### What's Missing

| Gap                                                | Layer | Severity | Detail                                                                                                                                                            |
| -------------------------------------------------- | ----- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No `required_approvers` field on `AgenticDecision` | L3    | High     | Model has single `decided_by`. Needs `required_approvers: int` and `approvals: dict` (list of individual approval records).                                       |
| No per-operation-type configuration                | L3    | High     | Need a config table/model mapping operation types to required approver counts (e.g., `grant_clearance` at SECRET level requires 2 approvers).                     |
| No individual approval records                     | L3    | High     | Each approval should be a separate record with approver identity, timestamp, and audit anchor. Currently a single `decided_by` field.                             |
| No partial approval visibility                     | L3    | Medium   | Dashboard needs to show "2 of 3 approvals received" state.                                                                                                        |
| No auto-reject timeout                             | L3    | Medium   | Pending multi-approver decisions should auto-reject after a configurable timeout.                                                                                 |
| No audit anchor per individual approval            | L3    | Medium   | Issue requests each approval creates an EATP audit anchor. The current single-approval flow creates no anchor at all (only the governance_gate HELD creates one). |
| `governance_gate()` needs multi-approver awareness | L3    | High     | When a HELD action requires 2 approvers, the first approval should not release the hold. gate must check approval count before proceeding.                        |

### L1 vs L3 Boundary

- **L1 changes needed**: None. Multi-approver is entirely an L3 concern. The L1 engine returns HELD; L3 manages how that HELD is resolved.
- **L3 changes needed**:
  1. New `AgenticApproval` DataFlow model (individual approval records).
  2. Add `required_approvers` field to `AgenticDecision`.
  3. New `ApprovalPolicy` model or config mapping operation types to approver counts.
  4. Modify `approve_decision` endpoint to create an `AgenticApproval` record and check if threshold is met.
  5. Auto-reject background scheduler.
  6. Dashboard updates for partial approval state.

### Dependencies

- **#22 depends on this**: Multi-approver per clearance level (e.g., SECRET requires 2 approvers) is a specific instance of the generic multi-approver pattern built here.
- Emergency bypass review pattern provides design precedent.

### Risk Assessment

| Risk                                                         | Likelihood | Impact   | Mitigation                                                                                    |
| ------------------------------------------------------------ | ---------- | -------- | --------------------------------------------------------------------------------------------- |
| Race condition: two approvals arrive simultaneously          | High       | High     | Optimistic locking on approval count; atomic increment via DataFlow Express                   |
| Approval policy misconfiguration (0 approvers required)      | Medium     | Critical | Validate `required_approvers >= 1` at config time                                             |
| Auto-reject timeout fires during legitimate multi-day review | Medium     | Medium   | Configurable per operation type; default 72 hours; extendable                                 |
| Breaking change to `AgenticDecision` model                   | Medium     | Medium   | Add fields with defaults (backward-compatible); existing single-approver records remain valid |

---

## Cross-Cutting Concerns

### 1. Audit Anchors (affects #21, #22, #23, #24, #25)

All five issues mention audit requirements. The pattern is consistent:

- **L1** emits EATP audit anchors via `_emit_audit()` / `_emit_audit_unlocked()` on the `GovernanceEngine`. New operations (vetting transitions, bootstrap mode decisions) need new `PactAuditAction` enum values.
- **L3** should emit additional platform-level audit events (individual approvals, compartment changes) via the audit pipeline (`pact_platform.trust.audit.pipeline`).

**Gap**: No unified audit event schema that spans L1 and L3. L1 uses `PactAuditAction` enum; L3 creates `AgenticDecision` records. These are separate audit trails. Consider a bridging mechanism.

### 2. FSM Enforcement Pattern (affects #22, #25)

Both vetting workflow (#22) and multi-approver (#25) need finite state machine enforcement:

- #22: `PENDING -> ACTIVE -> SUSPENDED -> ACTIVE` (plus terminal states)
- #25: `pending -> partial_approval -> approved` (plus auto-reject)

**Recommendation**: Build a reusable FSM enforcement utility at L3 that validates transitions, emits audit events, and integrates with optimistic locking. Both features can use this shared component.

### 3. Background Schedulers (affects #23, #24, #25)

Three issues require background tasks:

- #23: Bootstrap mode auto-expiry
- #24: Task envelope cleanup
- #25: Auto-reject timeout for pending multi-approver decisions

**Recommendation**: Implement a single `SchedulerService` at L3 using asyncio that manages periodic checks. Avoid separate scheduler per feature.

### 4. L1 Release Requirement (affects #22, #23)

Two issues require changes to kailash-pact (L1):

- #22: `VettingStatus.SUSPENDED` + `update_vetting_status()` + FSM validation + new audit actions
- #23: `bootstrap_mode` parameter on engine + auto-expiry + audit marking

**Recommendation**: Bundle into a single kailash-pact 0.8.0 release. File upstream issues on `terrene-foundation/kailash-py`.

### 5. AgenticDecision Model Evolution (affects #25, indirectly #22)

The `AgenticDecision` model needs expansion:

- Current: `decided_by: Optional[str]`, `decided_at: Optional[str]` (single approver)
- Needed: `required_approvers: int = 1`, `approval_count: int = 0`, plus a new `AgenticApproval` model for individual approvals

This is a DataFlow model migration. Test with existing single-approver records to verify backward compatibility.

---

## Dependency Graph

```
#25 (Multi-approver)          -- standalone L3, no L1 dependency
  |
  v
#22 (Vetting FSM)             -- L1 + L3, depends on #25 for multi-approver clearance
  |
#21 (Compartments)            -- L3 only, L1 complete
#23 (Bootstrap mode)          -- L1 + L3, independent
#24 (Task envelopes)          -- mostly L3, L1 nearly complete
```

**Recommended build order**:

1. **#25** (multi-approver) -- foundational L3 pattern, no L1 dependency
2. **#21** (compartments) -- pure L3 wiring, quick win
3. **#24** (task envelopes) -- mostly L3, small gaps
4. **#22** (vetting FSM) -- requires L1 release + depends on #25
5. **#23** (bootstrap mode) -- requires L1 release, lowest urgency (orgs can use dev_mode interim)

---

## Implementation Effort Estimate

| Issue     | L1 Sessions | L3 Sessions | Total | Notes                                      |
| --------- | ----------- | ----------- | ----- | ------------------------------------------ |
| #21       | 0           | 1           | 1     | API endpoints + optional DataFlow model    |
| #22       | 1           | 1           | 2     | L1 release required; FSM + transition API  |
| #23       | 0.5         | 0.5         | 1     | Small L1 change; L3 scheduler + dashboard  |
| #24       | 0           | 0.5         | 0.5   | Mostly wiring; background scheduler shared |
| #25       | 0           | 1.5         | 1.5   | New model + policy config + approval flow  |
| **Total** | **1.5**     | **4.5**     | **6** | 3 parallel L3 sessions + 1 L1 session      |

Estimates in autonomous execution sessions (not human-days). The L1 changes (#22, #23) can be batched into a single kailash-pact release session. The L3 work for #25, #21, and #24 can run in parallel since they touch different models and routers.

---

## Success Criteria

- [ ] #21: `POST /api/v1/access/explain` returns step-by-step trace including compartment check
- [ ] #21: `PATCH /api/v1/clearance/{role_address}/compartments` adds/removes compartments
- [ ] #22: `VettingStatus.SUSPENDED` exists in kailash-pact; FSM transitions validated at L1
- [ ] #22: `POST /api/v1/clearance/{role_address}/transition` with FSM enforcement
- [ ] #23: `GovernanceEngine(org, bootstrap_mode=True, bootstrap_ttl=timedelta(hours=24))` works
- [ ] #23: Audit trail shows `bootstrap_mode=true` on all verdicts during bootstrap
- [ ] #23: Bootstrap mode auto-expires; post-expiry missing envelopes -> BLOCKED
- [ ] #24: `expires_at` required in `PUT /{role_address}/task` endpoint
- [ ] #24: Background scheduler cleans up expired task envelopes
- [ ] #25: `AgenticDecision` has `required_approvers` field
- [ ] #25: Individual approvals stored as `AgenticApproval` records with audit anchors
- [ ] #25: Decision status transitions from `pending` to `approved` only when `approval_count >= required_approvers`
- [ ] #25: Auto-reject fires after configurable timeout
- [ ] Cross-cutting: Reusable FSM enforcement utility used by both #22 and #25
- [ ] Cross-cutting: Single background scheduler service handles #23, #24, #25 periodic tasks
