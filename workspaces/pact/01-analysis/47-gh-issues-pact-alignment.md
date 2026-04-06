---
type: DISCOVERY
date: 2026-04-06
created_at: 2026-04-06T00:00:00+08:00
author: agent
session_id: gh-issues-alignment
session_turn: 1
project: pact
topic: GitHub Issues #21-#25 PACT Spec Alignment Assessment
phase: analyze
tags:
  [
    pact-spec,
    l1-l3-boundary,
    monotonic-tightening,
    governance,
    compartments,
    vetting,
    bootstrap,
    task-envelopes,
    multi-approver,
  ]
---

# GitHub Issues #21-#25: PACT Spec Alignment Assessment

Assessment of five enhancement issues against the PACT specification, Kailash SDK patterns, the L1/L3 boundary, the boundary test (domain vocabulary), and security invariants.

## Summary Table

| Issue | Title                    | Spec Alignment          | Layer                      | Boundary Test    | Risk                         |
| ----- | ------------------------ | ----------------------- | -------------------------- | ---------------- | ---------------------------- |
| #21   | Compartment-based access | Already in L1           | L3 API exposure only       | PASS (framework) | Low                          |
| #22   | Vetting workflow FSM     | Partially in L1         | L3 service                 | PASS (framework) | Medium -- FSM transitions    |
| #23   | Bootstrap mode           | Extends spec -- careful | L3 operational concern     | PASS (framework) | HIGH -- monotonic tightening |
| #24   | Task envelopes           | Already in L1           | L3 persistence + lifecycle | PASS (framework) | Low                          |
| #25   | Multi-approver           | Not in L1               | L3 workflow                | PASS (framework) | Medium -- concurrency        |

---

## Issue #21: Compartment-Based Access Control for SECRET/TOP_SECRET

**GitHub**: `feat(clearance): compartment-based access control for SECRET/TOP_SECRET`

### Spec Alignment: ALREADY IMPLEMENTED IN L1

This issue is largely misfiled. The PACT spec's 5-step access enforcement algorithm (Step 3: Compartment check) is **already implemented in kailash-pact L1**:

```python
# L1 can_access() -- Step 3 (already exists)
if item_level >= _CLEARANCE_ORDER[ConfidentialityLevel.SECRET]:
    if item.compartments:
        missing = item.compartments - role_clearance.compartments
        if missing:
            return AccessDecision(allowed=False, ...)
```

The L1 types already carry compartments:

- `RoleClearance.compartments: frozenset[str]` -- compartments the role holds
- `KnowledgeItem.compartments: frozenset[str]` -- compartments the item requires
- `GovernanceEngine.grant_clearance()` persists compartments and emits EATP CapabilityAttestations with compartment constraints

**What is genuinely missing at L3**: The platform's clearance API (`/api/v1/clearance/grant`) already accepts `compartments` in the request body and passes them to `RoleClearance`. The `/api/v1/access/check` endpoint already passes `compartments` to `KnowledgeItem`. The L3 platform is wired correctly.

### Boundary Test: PASS

Compartments are a PACT specification concept (Step 3 of the access algorithm). No domain vocabulary. Changing "Project Alpha" to "Project Beta" in compartment names changes configuration data, not framework code.

### L1/L3 Boundary

- **L1 (kailash-pact)**: 5-step algorithm with compartment enforcement -- DONE.
- **L3 (pact-platform)**: API exposure of grant/revoke compartments -- DONE.
- **Remaining work**: The issue's Acceptance Criteria items 1-4 are satisfied. Item 5 (explain functions include compartment context in denial reasons) already works -- `explain_access()` wraps `can_access()` which produces denial reasons including `"Missing compartments: [...]"`.

### Monotonic Tightening Impact: NONE

Compartments do not interact with envelope tightening. They are a separate axis (knowledge access, not operational constraints).

### Security Considerations

- Fail-closed: Already handled. Missing compartments produce DENY at Step 3.
- Thread safety: `GovernanceEngine.check_access()` acquires `self._lock`.
- `frozenset` compartments prevent mutation after construction (frozen dataclass).

### Recommendation

**Close as already implemented**, or re-scope to a much smaller task: verify that the L3 test suite exercises the compartment path end-to-end (clearance grant with compartments, access check against SECRET item with compartment requirement, denial on missing compartment). The core functionality exists at both L1 and L3.

---

## Issue #22: Vetting Workflow FSM for Clearance Approval

**GitHub**: `feat(clearance): vetting workflow FSM for clearance approval`

### Spec Alignment: PARTIALLY IN L1, FSM WORKFLOW IS L3

L1 already defines `VettingStatus` with four states:

```
VettingStatus: pending | active | expired | revoked
```

L1's `can_access()` Step 1 enforces that only `ACTIVE` vetting grants access:

```python
if role_clearance.vetting_status != VettingStatus.ACTIVE:
    return AccessDecision(allowed=False, reason="vetting_not_active")
```

**What L1 provides**: The state enum and the enforcement rule (only ACTIVE clears Step 1).

**What L1 does NOT provide**: Transition validation (which states can transition to which), multi-approver logic, or workflow orchestration. The issue's FSM diagram adds a `suspended` state that does not exist in L1's current enum (`pending`, `active`, `expired`, `revoked`).

### Boundary Test: PASS

Vetting workflows are domain-agnostic governance concepts. Whether the organization is a bank or a university, clearance grants should follow a vetting process. No domain vocabulary.

### L1/L3 Boundary

- **L1 (kailash-pact)**: Owns the `VettingStatus` enum and the enforcement rule (Step 1). If `suspended` is added, it must be added here because Step 1 must know which statuses grant access. The decision "only ACTIVE grants access" is already correct -- `suspended` would correctly be denied by the existing Step 1 check.
- **L3 (pact-platform)**: Owns the FSM transition logic, the approval workflow (how many approvers per level), and the persistence. This is operational workflow, not governance policy.

### Implementation Strategy

1. **L1 change (small)**: Add `SUSPENDED = "suspended"` to `VettingStatus` enum. No other L1 changes needed -- Step 1 already denies anything that is not `ACTIVE`.
2. **L3 service (new)**: `VettingWorkflowService` implementing:
   - FSM transition validation (state machine with allowed transitions)
   - Configurable approver counts per clearance level
   - AgenticDecision creation for pending vetting approvals
   - Audit anchor emission on each transition

### Monotonic Tightening Impact: NONE

Vetting status is orthogonal to envelope constraints. Revoking or suspending a clearance does not widen any envelope -- it restricts access further (fail-closed at Step 1).

### Security Considerations

- **FSM enforcement must be fail-closed**: Invalid transitions must be rejected, not silently ignored. The transition `revoked -> active` must be BLOCKED (terminal state).
- **Race condition on concurrent approvals**: If two approvers try to approve the same vetting simultaneously, the second must detect that the state has already transitioned. Use the same optimistic locking pattern as `AgenticDecision` (`envelope_version` field).
- **Audit trail**: Each FSM transition must emit an audit anchor. The issue correctly calls this out.

### Recommendation

Implement as an **L3 VettingWorkflowService** with a one-line L1 enum extension (`suspended`). The multi-approver aspect overlaps with Issue #25 -- design them together to avoid duplicate approval machinery.

---

## Issue #23: Bootstrap Mode -- Temporary Permissive Envelopes for New Orgs

**GitHub**: `feat(envelopes): bootstrap mode -- temporary permissive envelopes for new orgs`

### Spec Alignment: EXTENDS SPEC -- HIGH CAUTION REQUIRED

Bootstrap mode directly tensions with PACT's monotonic tightening invariant. The PACT spec states:

> Child envelopes can only be equal to or more restrictive than parent envelopes. `intersect_envelopes()` takes the min/intersection of every field.

A "temporary permissive default" is, by definition, a wide envelope that exists where no explicit envelope has been defined. This does not violate monotonic tightening _per se_ (the bootstrap envelope is not widening a parent -- it is _substituting_ for a missing parent), but it creates a governance gap: actions taken under bootstrap envelopes operate outside the intended governance hierarchy.

### Boundary Test: PASS

Bootstrap mode is domain-agnostic. Every organization goes through an initial configuration phase. No domain vocabulary.

### L1/L3 Boundary

- **L1 (kailash-pact)**: `compute_effective_envelope()` currently returns `None` when ancestor envelopes are missing. This is the correct fail-closed behavior at L1. L1 MUST NOT implement bootstrap mode -- it would violate the fail-closed invariant at the governance specification layer.
- **L3 (pact-platform)**: Bootstrap mode is an **operational concern**. The platform decides what to do when L1 returns `None` (no effective envelope). Currently, a `None` envelope means "maximally restrictive" (the envelope API says: "No envelope configured -- role operates under default (maximally restrictive) constraints"). Bootstrap mode would override this L3 interpretation.

### Implementation Strategy

Bootstrap mode should be implemented as an L3 `EnforcementMode` extension, NOT as an L1 change:

1. **L3 PlatformSettings**: Add a `bootstrap_mode: bool` flag (or a new `EnforcementMode.BOOTSTRAP` value).
2. **L3 SupervisorOrchestrator**: When bootstrap mode is active and `compute_envelope()` returns `None`, inject a time-limited default envelope with explicit constraints.
3. **Time-limited**: Bootstrap envelopes carry an `expires_at` timestamp. After expiry, the system reverts to strict mode (maximally restrictive).
4. **Audit marking**: Every action under a bootstrap envelope is tagged in the audit trail: `"bootstrap": true`.
5. **Dashboard warning**: L3 surfaces "X roles operating under bootstrap envelopes".

### Monotonic Tightening Impact: HIGH RISK

The critical danger: once bootstrap mode creates a permissive envelope, and an operator later configures a real (tighter) role envelope, monotonic tightening is preserved (the real envelope is tighter than the bootstrap default). However:

- **Risk 1 -- Bootstrap as permanent escape hatch**: If bootstrap mode can be re-enabled after real envelopes are configured, it effectively widens envelopes by reverting to the permissive default. Mitigation: bootstrap mode can only be enabled once per org, or requires explicit emergency bypass authorization to re-enable.
- **Risk 2 -- Actions under bootstrap are ungoverned**: Any action taken during bootstrap operates outside the intended governance hierarchy. If the org later configures tight envelopes, those retroactive constraints do not apply to actions already completed under bootstrap. Mitigation: audit marking + post-bootstrap review requirement.
- **Risk 3 -- Bootstrap expiry race**: If a bootstrap envelope expires while an agent is mid-execution, the agent's next governance check fails (suddenly maximally restrictive). Mitigation: check expiry before execution starts, not mid-stream.

### Security Considerations

- **Must not be enabled in production by default**: Bootstrap mode should require explicit opt-in (similar to `PACT_ALLOW_DISABLED_MODE=true` for disabled enforcement).
- **Bootstrap envelope must have finite constraints**: The "permissive default" must still have bounded financial, operational, and temporal constraints -- not unlimited. Otherwise, an agent operating under bootstrap can consume unlimited resources.
- **Single-use or rate-limited**: Prevent repeated bootstrap enabling as an envelope-widening attack.

### Recommendation

Implement as **L3 only** (never L1). Model it as a `PlatformSettings` extension with time-limited, bounded default envelopes. Require explicit environment variable to enable (`PACT_ALLOW_BOOTSTRAP_MODE=true`). Add a post-bootstrap compliance review workflow that forces the operator to configure real envelopes before the deadline.

---

## Issue #24: Task Envelopes -- Ephemeral Layer 2 Narrowing

**GitHub**: `feat(envelopes): task envelopes -- ephemeral Layer 2 narrowing`

### Spec Alignment: ALREADY IN L1

The PACT spec's three-layer envelope model is **already implemented in kailash-pact L1**:

```python
# L1 types already exist:
TaskEnvelope(id, task_id, parent_envelope_id, envelope, expires_at, created_at)
RoleEnvelope(id, defining_role_address, target_role_address, envelope, gradient_thresholds, version, ...)

# L1 functions already exist:
compute_effective_envelope(role_address, role_envelopes, task_envelope=None, org_envelope=None)
intersect_envelopes(a, b)

# L1 engine methods already exist:
GovernanceEngine.set_task_envelope(task_env)
```

The L1 `compute_effective_envelope()` accepts an optional `task_envelope` parameter and intersects it with the role envelope chain. The intersection is monotonically tightening by construction (`intersect_envelopes` takes the min of each field).

The L3 envelope API already has a `PUT /{role_address}/task` endpoint that constructs a `TaskEnvelope` and calls `_engine.set_task_envelope()`.

### What Is Actually Needed at L3

The issue's real value is in L3 **lifecycle management**, not L1 envelope computation:

1. **Persistence**: TaskEnvelopes are currently in-memory (L1 `MemoryEnvelopeStore`). L3 needs a DataFlow model to persist them across restarts.
2. **Auto-expiry**: A scheduler or TTL mechanism that removes expired TaskEnvelopes. L1's `TaskEnvelope.expires_at` field exists but L3 must enforce expiry.
3. **Agent acknowledgment**: Before execution, the agent should acknowledge the task envelope constraints. This is an L3 UX concern (acknowledgment record in DataFlow).
4. **Linking to requests**: The platform should link TaskEnvelopes to `AgenticRequest` records via `envelope_id`.

### Boundary Test: PASS

Task envelopes are a PACT specification concept. No domain vocabulary.

### L1/L3 Boundary

- **L1 (kailash-pact)**: TaskEnvelope type, `set_task_envelope()`, `compute_effective_envelope()` with task intersection -- ALL DONE.
- **L3 (pact-platform)**: Persistence, lifecycle (create/expire/acknowledge), linking to requests, auto-expiry scheduler -- THIS IS THE WORK.

### Monotonic Tightening Impact: NONE (BY CONSTRUCTION)

`compute_effective_envelope()` calls `intersect_envelopes()` which takes the min/intersection. A TaskEnvelope can only narrow, never widen. The L1 invariant is structurally enforced.

The only risk: if L3 persistence allows editing an existing TaskEnvelope to widen it after creation. Mitigation: TaskEnvelopes should be immutable once created. To change constraints, create a new TaskEnvelope (superseding the old one).

### Security Considerations

- **Immutability**: TaskEnvelopes should be `frozen=True` dataclasses (already the case in L1). L3 must not allow UPDATE on TaskEnvelope records -- only CREATE and soft-DELETE (expire).
- **Expiry enforcement**: Expired TaskEnvelopes must be treated as non-existent by L1. If L3 fails to clean up, L1 should check `expires_at` and ignore expired envelopes. This check should be in `compute_effective_envelope()`.
- **Thread safety**: `set_task_envelope()` acquires `self._lock` in GovernanceEngine. L3 must not bypass the engine for direct store access.

### Recommendation

Re-scope the issue to **L3 lifecycle management only**. The L1 functionality is complete. Deliverables: (1) TaskEnvelope DataFlow model, (2) auto-expiry scheduler, (3) acknowledgment record, (4) link to AgenticRequest via `envelope_id`.

---

## Issue #25: Multi-Approver Workflows for High-Clearance Operations

**GitHub**: `feat(governance): multi-approver workflows for high-clearance operations`

### Spec Alignment: NOT IN L1 -- PURE L3 WORKFLOW

The PACT specification defines governance decisions as binary outcomes from `verify_action()`: `AUTO_APPROVED`, `FLAGGED`, `HELD`, or `BLOCKED`. The spec does not prescribe how many humans must approve a HELD action -- that is an operational policy decision.

L1's `GovernanceEngine.verify_action()` returns a `GovernanceVerdict`. The ApprovalBridge (L3) creates an `AgenticDecision` from HELD verdicts. Currently, a single `approve()` call resolves the decision. Multi-approver is a pure L3 workflow extension.

### Boundary Test: PASS

Multi-approver is domain-agnostic. Dual control and split knowledge are governance patterns that apply equally to financial services, healthcare, and government. No domain vocabulary.

### L1/L3 Boundary

- **L1 (kailash-pact)**: No changes needed. L1 produces HELD verdicts. L1 does not care how many approvers are required to resolve them.
- **L3 (pact-platform)**: Owns the entire multi-approver workflow:
  - `AgenticDecision` model extension: `required_approvers: int`, `approvals: list[dict]`
  - Approval resolution logic: decision is finalized only when `len(approvals) >= required_approvers`
  - Configurable per operation type (clearance grants, emergency bypass, budget overrides)
  - Auto-rejection on timeout
  - Partial approval visibility in API

### Implementation Strategy

1. **Extend AgenticDecision model**: Add `required_approvers` (int, default 1) and `approval_records` (dict, stores individual approvals).
2. **Configurable approval policies**: A new `ApprovalPolicyConfig` in PlatformSettings mapping operation types to required approver counts.
3. **Partial approval API**: `GET /api/v1/decisions/{id}` returns `approvals_received` / `approvals_required`.
4. **Individual approve endpoint**: `POST /api/v1/decisions/{id}/approve` records one approval. When `approvals_received >= required_approvers`, the decision status transitions to `approved`.
5. **Timeout**: A scheduler checks `expires_at` and auto-rejects decisions that do not reach quorum.

### Monotonic Tightening Impact: NONE

Multi-approver does not affect envelope constraints. It affects the operational workflow for resolving HELD verdicts, which is entirely L3.

### Security Considerations

- **Duplicate approver prevention**: The same person must not be counted twice. Each approval must check that the `decided_by` address is unique within the approval set.
- **Authority validation**: Each approver must have sufficient authority to approve (e.g., a junior role cannot approve a SECRET clearance grant). This validation should use `GovernanceEngine.verify_action()` to check if the approver's role is authorized for the approval action.
- **Race condition on final approval**: When two approvers submit simultaneously and both would be the Nth (final) approval, only one should trigger the state transition. Use the existing optimistic locking pattern (`envelope_version` increment on state change).
- **Audit**: Each individual approval creates its own audit anchor, not just the final resolution. This enables post-hoc analysis of who approved and when.

### Overlap with Issue #22

Issue #22 (vetting workflow FSM) specifies multi-approver for clearance grants as part of the vetting workflow. Issue #25 generalizes multi-approver across all decision types. **Recommendation**: Implement multi-approver as a general-purpose L3 mechanism (Issue #25), then wire it into the vetting workflow (Issue #22). Do not build two separate approval mechanisms.

### Recommendation

Implement as a **general-purpose L3 multi-approver extension** to `AgenticDecision` and `ApprovalBridge`. Design it generically so it can be used by clearance vetting (#22), emergency bypass, and budget overrides. No L1 changes required.

---

## Cross-Issue Dependencies

```
#25 (Multi-Approver)
  |
  |--- used by ---> #22 (Vetting FSM) -- multi-approver for clearance grants
  |--- used by ---> Emergency Bypass (existing) -- could adopt multi-approver
  |
#24 (Task Envelopes)
  |--- independent, L3 lifecycle only
  |
#23 (Bootstrap Mode)
  |--- independent, L3 operational concern
  |--- interacts with #24: bootstrap default envelopes should be expressible as
  |    task envelopes (time-limited, auto-expire)
  |
#21 (Compartments)
  |--- already implemented at L1 and L3
  |--- close or re-scope to test coverage
```

**Recommended implementation order**:

1. **#21**: Close or re-scope (already done).
2. **#25**: Multi-approver (foundational -- #22 depends on it).
3. **#22**: Vetting FSM (uses #25's multi-approver).
4. **#24**: Task envelope lifecycle (independent, moderate scope).
5. **#23**: Bootstrap mode (highest risk, most design required, benefits from #24's expiry mechanism).

---

## For Discussion

1. Issue #23 (bootstrap mode) proposes creating permissive envelopes where none are configured. Given that `compute_effective_envelope()` currently returns `None` (maximally restrictive) as its fail-closed behavior, and that PACT's core invariant is "unknown state = deny," what specific bounded constraints should the bootstrap default contain? If the answer is "domain-dependent," does bootstrap mode itself fail the boundary test?

2. If Issue #22's `suspended` vetting status had existed when L1's `VettingStatus` enum was originally designed, would the current four-state enum (`pending`, `active`, `expired`, `revoked`) have been designed differently? Specifically, does the distinction between `expired` (time-based) and `revoked` (action-based) still hold, or does `suspended` (temporary, reinstatable) create a need to rethink the enum as a proper state machine with explicit transition rules at L1?

3. Issues #22 and #25 both require multi-approver functionality, but #22 scopes it to clearance operations while #25 generalizes it. If the general mechanism (#25) is implemented first, is there a risk that the clearance-specific requirements of #22 (approver count scaling with clearance level) will be awkward to express in the general framework, or does the `ApprovalPolicyConfig` mapping operation types to approver counts handle this naturally?
