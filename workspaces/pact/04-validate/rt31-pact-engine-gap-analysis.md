---
type: GAP
date: 2026-04-03
created_at: 2026-04-03T22:45:00+08:00
author: co-authored
session_turn: 1
project: pact
topic: Architectural red team — PactEngine (L1) vs SupervisorOrchestrator (L3) gap analysis
phase: redteam
tags:
  [
    pact-engine,
    L1-L3-gap,
    architecture,
    red-team,
    governance,
    upstream,
    kailash-pact-0.6.0,
  ]
---

# RT31: PactEngine (L1) vs SupervisorOrchestrator (L3) — Architectural Gap Analysis

## Purpose

This is a red-team gap analysis comparing PactEngine (kailash-pact 0.6.0, installed as L1 library) against SupervisorOrchestrator (pact-platform L3, this repository). The question is not "does PactEngine work" but rather: **what did L3 have to build around L1 that L1 should have provided?**

Every gap identified here represents either (a) a security invariant that L1 violates, (b) a production capability that every vertical would need to rebuild independently, or (c) a platform-specific concern correctly left to L3.

## Source Material

| Component               | Location                                                   | Version             |
| ----------------------- | ---------------------------------------------------------- | ------------------- |
| PactEngine              | `.venv/.../pact/engine.py` (495 lines)                     | kailash-pact 0.6.0  |
| SupervisorOrchestrator  | `src/pact_platform/engine/orchestrator.py` (654 lines)     | pact-platform 0.3.0 |
| GovernedDelegate        | `src/pact_platform/engine/delegate.py` (229 lines)         | pact-platform 0.3.0 |
| PlatformEnvelopeAdapter | `src/pact_platform/engine/envelope_adapter.py` (237 lines) | pact-platform 0.3.0 |
| ApprovalBridge          | `src/pact_platform/engine/approval_bridge.py` (229 lines)  | pact-platform 0.3.0 |
| PlatformSettings        | `src/pact_platform/engine/settings.py` (118 lines)         | pact-platform 0.3.0 |
| PostureAssessor         | `src/pact_platform/trust/posture_assessor.py` (182 lines)  | pact-platform 0.3.0 |

## Execution Model Comparison

### PactEngine (L1) Flow

```
PactEngine.submit(objective, role, context)
  1. verify_action(role, "submit", context)      [SINGLE gate, action="submit"]
  2. supervisor.run(objective, context)            [NO per-node governance]
  3. costs.record(cost)                            [post-hoc recording only]
  4. events.emit(...)                              [in-memory bounded deque]
  -> WorkResult(success, results, cost_usd, events)
```

### SupervisorOrchestrator (L3) Flow

```
SupervisorOrchestrator.execute_request(request_id, role_address, objective, context)
  1. NaN-guard all context cost values             [defense-in-depth]
  2. adapter.adapt(role_address) -> supervisor_params  [5-dimension mapping]
  3. Create FRESH GovernedSupervisor per request    [correct budget per call]
  4. Create GovernedDelegate(engine, bridge, role)  [PER-NODE enforcement]
  5. supervisor.run(objective, context, execute_node=delegate)
     -> For EACH node: delegate verifies action    [governance on every action]
     -> BLOCKED: GovernanceBlockedError raised      [supervisor handles recovery]
     -> HELD: AgenticDecision created via bridge    [human approval queue]
     -> AUTO_APPROVED/FLAGGED: proceed              [with audit trail]
  6. NaN-guard supervisor result numerics           [defense-in-depth]
  7. db.express_sync.create("Run", {...})           [persistent record]
  8. event_bridge.on_completion_event(...)          [SSE/WebSocket streaming]
  -> dict with budget_consumed, budget_allocated, audit_trail, run_id
```

---

## Gap Inventory

### Gap 1: Single-Gate vs Per-Node Governance

**Severity: CRITICAL**

**What L1 does**: PactEngine calls `verify_action(role, "submit", context)` once at submission time. The action string is always `"submit"`. After that single gate, the supervisor executes any number of actions (read, write, delete, deploy, transfer_funds) with zero governance checks.

**What L3 does**: SupervisorOrchestrator passes a `GovernedDelegate` as the `execute_node` callback. For every node the supervisor plans, the delegate calls `verify_action(role, action, node_context)` where `action` is the specific operation (not the generic "submit"). Each node is independently evaluated against the role's envelope.

**Evidence from source** (PactEngine `engine.py` line 150-154):

```python
verdict = self._governance.verify_action(
    role_address=role,
    action="submit",           # <-- always "submit", never the real action
    context=ctx,
)
```

**Evidence from source** (GovernedDelegate `delegate.py` line 167-171):

```python
verdict = self._verifier.verify_action(
    role_address=role_addr,
    action=action,             # <-- the actual node action (read, write, deploy...)
    context=context if context else None,
)
```

**Impact**: An agent with `allowed_actions: ["read"]` in its envelope can execute write, delete, and deploy actions through PactEngine because the envelope is only checked against the generic "submit" action, not the real operations. This is a governance bypass -- the envelope's operational constraints are effectively ignored during execution.

**Why this breaks the spec**: PACT spec requires that every action by an agent within its operating envelope is verified against that envelope. A single "submit" gate violates the continuous governance principle. The operating envelope is meaningless if it is only checked at the door and never inside the room.

**Classification**: **Upstream to L1** -- This is a fundamental governance invariant. Every vertical (astra, arbor, or any third party importing kailash-pact) would face this same gap and would need to build their own delegate pattern.

---

### Gap 2: No Envelope-to-Execution Dimension Mapping

**Severity: HIGH**

**What L1 does**: PactEngine creates the GovernedSupervisor with three raw parameters:

- `model`: passthrough string
- `budget_usd`: `self._costs.remaining` (or 1.0 fallback)
- `data_clearance`: the clearance string (validated against a hardcoded list)

The five constraint dimensions (Financial, Operational, Temporal, Data Access, Communication) defined in the envelope are never resolved or mapped to supervisor parameters. The tools list, timeout, delegation depth, and rate limits from the envelope are ignored.

**What L3 does**: PlatformEnvelopeAdapter (`envelope_adapter.py`) calls `engine.compute_envelope(role_address)` to resolve the effective envelope, then maps all five dimensions:

| Envelope Dimension                             | Supervisor Parameter    | L1 Maps?                  | L3 Maps?                         |
| ---------------------------------------------- | ----------------------- | ------------------------- | -------------------------------- |
| Financial (max_spend_usd, api_cost_budget_usd) | budget_usd              | Partial (raw budget only) | Yes                              |
| Operational (allowed_actions)                  | tools list              | No                        | Yes                              |
| Confidentiality (clearance level)              | data_clearance          | Partial (hardcoded list)  | Yes (enum mapping)               |
| Temporal (active_hours)                        | timeout_seconds         | No                        | Yes (default, future derivation) |
| Delegation (max_delegation_depth)              | max_depth, max_children | No                        | Yes                              |
| Rate limits (max_actions_per_day/hour)         | logging + enforcement   | No                        | Yes (logged + context injection) |

**Evidence from source** (PactEngine `engine.py` lines 410-431): The `_get_or_create_supervisor()` method never calls `compute_envelope()`. It uses `self._costs.remaining` for budget and `self._clearance` (the constructor string) for clearance. There is no tools list, no timeout, no depth limit, no rate limit.

**Impact**: An envelope that restricts a role to `allowed_actions: ["read_public_data"]` with `max_delegation_depth: 2` has those constraints silently ignored by PactEngine. The supervisor receives no tools restriction and no depth limit.

**Classification**: **Upstream to L1** -- Envelope resolution and dimension mapping is a core engine responsibility. It is domain-agnostic (the five dimensions are PACT-standard). Every vertical would need this identical adapter.

---

### Gap 3: Lazy Supervisor Reuse Causes Stale Budget

**Severity: HIGH**

**What L1 does**: `_get_or_create_supervisor()` (line 391-431) creates a GovernedSupervisor lazily on first call and caches it in `self._supervisor`. The budget is set to `self._costs.remaining` at creation time. On subsequent calls, the same supervisor instance is returned -- but the supervisor was initialized with the remaining budget from the first call, not the current remaining budget.

**What L3 does**: SupervisorOrchestrator creates a **fresh** GovernedSupervisor for every `execute_request()` call (line 245-254). The budget is resolved from the current effective envelope each time.

**Evidence from source** (PactEngine `engine.py` lines 391-431):

```python
def _get_or_create_supervisor(self) -> Any | None:
    if self._supervisor is not None:
        return self._supervisor          # <-- returns cached supervisor
    # ... creates supervisor with self._costs.remaining ...
    self._supervisor = supervisor
    return supervisor
```

**Impact**: If PactEngine has a $50 budget and the first `submit()` consumes $10, the second call reuses the supervisor initialized with $50 (or whatever `remaining` was at first-creation time). The CostTracker records the spend correctly, but the supervisor itself does not know about the updated budget -- it may over-allocate. Additionally, under concurrent access, two threads could both see `self._supervisor is None` and both create supervisors (race condition on lazy initialization without locking).

**Classification**: **Upstream to L1** -- Per-request supervisor creation with current budget is the only correct behavior. The lazy-singleton pattern is fundamentally incompatible with budget tracking.

---

### Gap 4: No HELD Verdict Handling

**Severity: HIGH**

**What L1 does**: After `verify_action()`, PactEngine checks `if not verdict.allowed` and returns `WorkResult(success=False)`. There is no distinction between BLOCKED and HELD. Both are treated as terminal failures.

**What L3 does**: GovernedDelegate distinguishes three verdict paths:

- **BLOCKED**: Raises `GovernanceBlockedError` -- the supervisor marks the node as failed and may trigger recovery or escalation.
- **HELD**: Creates an `AgenticDecision` record via ApprovalBridge, raises `GovernanceHeldError` -- the supervisor parks the node. A human can later approve or reject through the approval queue API.
- **AUTO_APPROVED/FLAGGED**: Proceeds normally.

**Evidence from source** (PactEngine `engine.py` lines 174-189): The code only checks `if not verdict.allowed` -- a binary gate. The `verdict.level` is included in the error message but not used for routing.

**Impact**: HELD verdicts represent "near a soft limit, human judgment needed." Without HELD support, PactEngine turns every soft limit into a hard block. There is no path for human oversight to approve actions that governance flags for review. This forces verticals to choose between permissive envelopes (no holds) or brittle ones (everything near a limit fails).

**Classification**: **Upstream to L1** -- HELD is a core governance verdict level defined in the PACT spec. The approval queue persistence is L3 (requires DataFlow), but the verdict routing protocol (BLOCKED vs HELD vs AUTO_APPROVED) and a callback mechanism belong in L1.

---

### Gap 5: No Enforcement Modes (Enforce/Shadow/Disabled)

**Severity: HIGH**

**What L1 does**: PactEngine is always in enforce mode. There is no shadow mode for progressive rollout, no disabled mode for emergencies.

**What L3 does**: EnforcementMode enum (enforce/shadow/disabled) with:

- `_ShadowDelegate`: Evaluates governance but never blocks. Logs verdicts and persists shadow audit records with `shadow=True` marker. Queryable for shadow-to-enforce transition analysis.
- `_PassthroughDelegate`: Approves everything (disabled mode). Requires `PACT_ALLOW_DISABLED_MODE=true` environment variable to prevent accidental production use.
- Production default: `ENFORCE`. Configurable via `PACT_ENFORCEMENT_MODE` env var.

**Impact**: Without shadow mode, organizations cannot progressively roll out governance. They face an all-or-nothing choice: fully enforced or no governance at all. Shadow mode is essential for:

1. Testing envelope configurations before they block production traffic
2. Analyzing what governance would do before turning it on
3. Post-incident analysis ("what would governance have blocked?")

**Classification**: **Upstream to L1** -- Enforcement modes are a PACT operational concept, not platform-specific. Every vertical needs the same three modes. The delegate pattern itself is L1 (see Gap 1); the modes are policy on that pattern.

---

### Gap 6: No NaN-Guard on Supervisor Result Values

**Severity: CRITICAL**

**What L1 does**: PactEngine records `supervisor_result.budget_consumed` directly into the CostTracker (line 221-222) without checking for NaN or Inf. If the supervisor returns NaN for `budget_consumed`, it poisons the CostTracker's accumulator -- all future budget checks pass because `NaN + X` is `NaN`, and `NaN < budget` is always False.

**What L3 does**: SupervisorOrchestrator validates both `budget_consumed` and `budget_allocated` with `math.isfinite()` (lines 357-369) before recording. Non-finite values are logged as errors and replaced with 0.0.

**Evidence from source** (PactEngine `engine.py` lines 220-222):

```python
cost_usd = supervisor_result.budget_consumed
if cost_usd > 0:                                    # NaN > 0 is False -- skips recording
    self._costs.record(cost_usd, f"submit: {objective[:80]}")
```

Note: the `cost_usd > 0` check would actually skip NaN (since NaN > 0 is False), so the CostTracker accumulator is not poisoned by this specific path. However, this is accidental correctness -- if the comparison were `cost_usd >= 0` or `cost_usd != 0`, NaN would flow through. There is no intentional NaN guard.

**What L1 DOES guard**: The constructor validates `budget_usd` with `math.isfinite()` (line 76). But it does not validate values flowing back from the supervisor or values in the submit context dict.

**Impact**: While the current code path accidentally avoids NaN poisoning, the lack of explicit validation means any refactoring that changes the comparison operator would silently introduce a budget bypass. Per pact-governance.md Rule 6 and trust-plane-security.md Rule 3, all numeric values crossing trust boundaries must be explicitly validated with `math.isfinite()`.

**Classification**: **Upstream to L1** -- NaN validation on trust boundary crossings is a security invariant, not a platform feature.

---

### Gap 7: No Persistent Run Records

**Severity: MEDIUM**

**What L1 does**: `submit()` returns a `WorkResult` -- a frozen dataclass with success, results, cost_usd, events. There is no persistence. Once the caller discards the WorkResult, the execution is lost.

**What L3 does**: Every execution is persisted as a `Run` record via DataFlow Express with: run_id, request_id, agent_address, status, started_at, ended_at, duration_ms, cost_usd, verification_level, error_message, and metadata. This enables:

- Audit trail queries
- Cost reporting across runs
- Performance analysis
- Compliance evidence

**Impact**: Without persistence, PactEngine cannot support audit compliance or cost analysis across executions. The caller must build their own persistence layer.

**Classification**: **Correct at L3** -- Persistence requires a database (DataFlow). L1 should not mandate a database dependency. However, L1 should provide a **persistence hook** (callback protocol) that L3 can wire into, rather than requiring L3 to wrap the entire submit flow.

---

### Gap 8: No Degenerate Envelope Detection

**Severity: MEDIUM**

**What L1 does**: No envelope inspection at init or submit time. An envelope with `max_spend_usd: 0.0` and `allowed_actions: []` is silently accepted, creating a role that can never do anything useful.

**What L3 does**: `_check_degenerate_envelopes()` runs at init time, iterating all role addresses in the compiled org. It calls L1's `check_degenerate_envelope()` (if available) and caches degenerate addresses. Per-request, it logs a warning when operating under a degenerate envelope.

**Evidence from source** (SupervisorOrchestrator `orchestrator.py` lines 421-482): Full implementation with bounded warning output (max 50 warnings) to prevent log flooding.

**Impact**: Without detection, operators deploy governance configurations that silently prevent all work. They see "governance blocked" errors with no explanation that the envelope itself is the problem.

**Classification**: **Upstream to L1** -- Degenerate detection is domain-agnostic (checking for zero budget, empty tool lists, impossible temporal windows). L1 already has `check_degenerate_envelope()` as a utility function but does not call it automatically. The engine should at minimum log warnings during org compilation.

---

### Gap 9: In-Memory EventBus vs Streaming EventBridge

**Severity: LOW**

**What L1 does**: EventBus with bounded deque (maxlen=10000). Subscribe/emit/history pattern. Events are in-memory and lost on process exit.

**What L3 does**: EventBridge that forwards events to SSE and WebSocket connections for real-time dashboard streaming.

**Classification**: **Correct at L3** -- Real-time streaming is a platform concern. L1's EventBus is the correct abstraction for library-level event notification. L3 bridges it to transport.

---

### Gap 10: No Posture Assessment Integration

**Severity: LOW**

**What L1 does**: No posture assessment wiring. No D/T/R-aware assessor validator.

**What L3 does**: `wire_posture_assessor()` creates a D/T/R-aware validator that blocks direct supervisors from assessing their subordinates (conflict of interest), while allowing compliance roles and distant ancestors.

**Classification**: **Correct at L3** -- Posture assessment is a platform operational feature. The D/T/R hierarchy traversal uses L1's Address parsing, which is the correct boundary. L1 provides the primitives; L3 wires the policy.

---

### Gap 11: No Input Validation on submit()

**Severity: MEDIUM**

**What L1 does**: `submit()` accepts empty strings for `objective` and `role`. An empty role passes through to `verify_action(role_address="", ...)` which may behave unpredictably depending on the GovernanceEngine's handling of empty addresses.

**What L3 does**: `execute_request()` validates both `request_id` and `role_address` as non-empty (lines 167-169), raising `ValueError` before any governance evaluation.

**Classification**: **Upstream to L1** -- Input validation at the public API boundary is a basic correctness requirement.

---

### Gap 12: No Read-Only Verifier Wrapper for Delegation

**Severity: HIGH**

**What L1 does**: PactEngine exposes the full GovernanceEngine via `self.governance` property (line 326-333). The docstring warns against passing it to agents, but there is no code-level enforcement. Any code with a PactEngine reference can call `engine.governance.set_role_envelope()` or `engine.governance.grant_clearance()`.

**What L3 does**: GovernedDelegate uses a `_VerifierWrapper` (lines 64-92) that binds only `verify_action()` -- no other engine methods are accessible. The wrapper uses `__slots__ = ("_verify_fn",)` so there is no `__dict__` to introspect for the original engine reference.

**Evidence from source** (PactEngine `engine.py` lines 326-333):

```python
@property
def governance(self) -> Any:
    """WARNING: This returns the mutable GovernanceEngine. Do NOT pass this
    reference to agent code..."""
    return self._governance
```

**Impact**: Per pact-governance.md MUST NOT Rule 1, agents must never receive the mutable GovernanceEngine. PactEngine has no mechanism to enforce this -- it relies on the caller reading the docstring warning. Any vertical that passes `engine.governance` to agent code (easy mistake) creates a self-modification attack vector.

**Classification**: **Upstream to L1** -- PactEngine should provide a `create_verifier()` method that returns a read-only wrapper, following the same pattern as L3's `_VerifierWrapper`. This is a security invariant, not a platform feature.

---

## Severity Summary

| Severity | Count | Gaps                                                                                                                      |
| -------- | ----- | ------------------------------------------------------------------------------------------------------------------------- |
| CRITICAL | 2     | #1 (single-gate governance), #6 (NaN on results)                                                                          |
| HIGH     | 4     | #2 (no dimension mapping), #3 (stale budget), #4 (no HELD handling), #5 (no enforcement modes), #12 (no verifier wrapper) |
| MEDIUM   | 3     | #7 (no persistence), #8 (no degenerate detection), #11 (no input validation)                                              |
| LOW      | 2     | #9 (event bus vs bridge), #10 (posture assessment)                                                                        |

---

## Recommendations

### Tier 1: Upstream to L1 (kailash-pact)

These gaps represent security invariants or core governance capabilities that every vertical would need to rebuild.

| Gap | Title                   | Recommendation                                                                                                                                                                                                                                                   | Priority          |
| --- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| #1  | Single-gate governance  | Add `execute_node` callback protocol to PactEngine. submit() should accept an optional callback that receives `(node_id, action, context)` and returns approval status. Default: no callback (current behavior for scripts). When provided: per-node governance. | P0 -- security    |
| #2  | No dimension mapping    | Add `EnvelopeAdapter` protocol and default implementation. PactEngine should resolve the effective envelope via `compute_envelope()` and map all five dimensions to supervisor parameters.                                                                       | P0 -- functional  |
| #3  | Stale budget            | Create a fresh GovernedSupervisor per `submit()` call. Remove the lazy singleton pattern. Budget must be resolved at call time, not construction time.                                                                                                           | P0 -- correctness |
| #4  | No HELD handling        | Add HELD verdict routing with a callback protocol. PactEngine should accept an optional `on_held: Callable[[verdict, context], Decision]` that verticals wire to their approval mechanism. Default: treat HELD as BLOCKED (current fail-closed behavior).        | P1 -- governance  |
| #5  | No enforcement modes    | Add `EnforcementMode` enum and `enforcement_mode` parameter to PactEngine constructor. Shadow mode evaluates but never blocks. Disabled mode requires explicit opt-in.                                                                                           | P1 -- operational |
| #6  | NaN on results          | Add explicit `math.isfinite()` check on `supervisor_result.budget_consumed` before recording. Do not rely on accidental comparison behavior.                                                                                                                     | P0 -- security    |
| #8  | No degenerate detection | Call `check_degenerate_envelope()` during org compilation and log warnings. Already exists as a utility -- just needs to be wired in.                                                                                                                            | P2 -- usability   |
| #11 | No input validation     | Validate `objective` and `role` as non-empty strings at the top of `submit()`.                                                                                                                                                                                   | P1 -- correctness |
| #12 | No verifier wrapper     | Add `create_verifier()` method that returns a read-only wrapper exposing only `verify_action()`. Deprecate the `governance` property or make it return the wrapper by default.                                                                                   | P1 -- security    |

### Tier 2: Correct at L3 (pact-platform)

These gaps represent platform-specific concerns that depend on infrastructure (databases, transport, UI) not appropriate for a library.

| Gap | Title              | Why L3 is Correct                                                                                                              |
| --- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| #7  | No persistence     | Requires DataFlow/database dependency. L1 should provide a persistence hook (callback protocol), not mandate a specific store. |
| #9  | Event streaming    | Transport-specific (SSE, WebSocket). L1's in-memory EventBus is the correct library-level abstraction.                         |
| #10 | Posture assessment | Platform operational policy. L1 provides D/T/R Address primitives; L3 wires the assessor policy.                               |

### Tier 3: File GitHub Issue

The upstream gaps should be tracked as a single umbrella issue on `terrene-foundation/kailash-py` with sub-items for each gap. This extends the existing issue #232 (referenced in journal entry 0015).

**Recommended issue structure**:

```
Title: feat(pact-engine): close L1/L3 gap -- per-node governance, dimension mapping, enforcement modes

Body:
PactEngine (kailash-pact 0.6.0) has 9 gaps identified in RT31 that every
vertical would need to rebuild. These are not platform-specific -- they are
core governance capabilities.

P0 (security/correctness):
- [ ] Per-node governance callback protocol (#1)
- [ ] Envelope dimension mapping (#2)
- [ ] Per-request supervisor creation (#3)
- [ ] NaN-guard on supervisor results (#6)

P1 (governance/operational):
- [ ] HELD verdict callback protocol (#4)
- [ ] Enforcement modes (#5)
- [ ] Input validation on submit() (#11)
- [ ] Read-only verifier wrapper (#12)

P2 (usability):
- [ ] Degenerate envelope detection at compile time (#8)

See: workspaces/pact/04-validate/rt31-pact-engine-gap-analysis.md
Extends: #232
```

---

## Relationship to Prior Analysis (0015)

Journal entry 0015 identified 13 deficiencies in a summary format. This RT31 report provides the full architectural analysis with:

- Source code evidence for each gap (line numbers, code snippets)
- Precise impact analysis (what happens when the gap is exercised)
- Classification logic (why each gap belongs at L1 or L3)
- The critical single-gate finding (#1) which 0015 listed as item #7 but without the full severity analysis showing it bypasses operational constraints entirely

The two documents are complementary: 0015 is the inventory, RT31 is the forensic analysis.

---

## Methodology

1. Read the complete PactEngine source (495 lines, kailash-pact 0.6.0)
2. Read the complete SupervisorOrchestrator source (654 lines) and all its dependencies (delegate, adapter, bridge, settings, posture_assessor -- combined 995 lines)
3. For each L3 component, traced the exact code path to identify what governance behavior it provides
4. For each identified behavior, checked whether PactEngine has equivalent functionality
5. Classified each gap against PACT governance rules (pact-governance.md), trust-plane security rules (trust-plane-security.md), and the PACT spec
6. Verified severity by constructing the attack or failure scenario each gap enables
