---
paths:
  - "src/pact_platform/build/org/**"
  - "src/pact_platform/build/config/schema.py"
  - "**/governance/**"
---

# Governance Layer Rules

## Scope

These rules apply when editing files in:

- `pact.governance` (kailash-pact, upstream)
- `src/pact_platform/build/org/**`
- `src/pact_platform/build/config/schema.py`
- Tests for governance modules

These rules supplement `.claude/rules/security.md` and `.claude/rules/trust-plane-security.md`. All three apply to governance files.
Violations during code review by intermediate-reviewer are BLOCK-level findings.

## MUST Rules

### 1. GovernanceEngine Is the Single Entry Point for Verticals

Verticals (astra, arbor) MUST use `GovernanceEngine` as their primary interface. Direct imports from governance submodules are acceptable for type annotations but all state access and mutations go through engine methods.

```python
# DO:
from pact.governance.engine import GovernanceEngine
engine = GovernanceEngine(compiled_org)
envelope = engine.get_effective_envelope(role_address)

# DO NOT:
from pact.governance.envelopes import compute_effective_envelope
from pact.governance.stores import ClearanceStore
envelope = compute_effective_envelope(role_env, task_env)  # Bypasses engine audit trail
```

**Why**: The engine is the audit boundary. Every state access and mutation through the engine is auditable. Bypassing it means silent, unaudited governance operations.

### 2. All Mutations Emit Audit Anchors

Every state-mutating operation (`grant_clearance`, `create_bridge`, `create_ksp`, `set_role_envelope`, `set_task_envelope`) MUST create an EATP Audit Anchor via the governance audit module. Silent mutations are FORBIDDEN.

```python
# DO:
def grant_clearance(self, role_address: str, level: ClearanceLevel) -> None:
    self._clearance_store.set(role_address, level)
    self._audit.anchor_mutation("grant_clearance", {
        "role_address": role_address,
        "level": level.value,
    })

# DO NOT:
def grant_clearance(self, role_address: str, level: ClearanceLevel) -> None:
    self._clearance_store.set(role_address, level)
    # No audit anchor — mutation is invisible to trust lineage
```

**Why**: EATP requires every trust-relevant state change to be anchored in the audit chain. Unanchored mutations break audit continuity and make compliance verification impossible.

### 3. Frozen Dataclasses for All Governance State

All governance record types MUST be `@dataclass(frozen=True)`:

- `Address`, `AddressSegment`, `OrgNode`, `CompiledOrg`
- `RoleDefinition`, `RoleClearance`, `VettingStatus`
- `KnowledgeItem`, `KnowledgeSharePolicy`, `PactBridge`
- `RoleEnvelope`, `TaskEnvelope`, `AccessDecision`
- `GovernanceContext` (when created for agents)

```python
# DO:
@dataclass(frozen=True)
class RoleEnvelope:
    role_address: str
    constraints: ConstraintEnvelopeConfig
    ...

# DO NOT:
@dataclass  # Mutable — fields can be changed after construction
class RoleEnvelope:
    role_address: str
    constraints: ConstraintEnvelopeConfig
    ...
```

**Why**: Without `frozen=True`, an attacker or buggy code with object reference can bypass validation by directly setting fields after construction. Mutable governance state is a CRITICAL security vulnerability. Use `object.__setattr__` in `__post_init__` if field normalization is needed.

### 4. `math.isfinite()` on All Numeric Constraint Fields

Every numeric field in `ConstraintEnvelopeConfig`, `FinancialConstraintConfig`, `OperationalConstraintConfig`, `TemporalConstraintConfig` MUST be validated with `math.isfinite()` at construction time.

```python
# DO (in __post_init__ or from_dict):
import math
if self.max_budget is not None and not math.isfinite(self.max_budget):
    raise ValueError("max_budget must be finite")

# DO NOT:
if self.max_budget is not None and self.max_budget < 0:
    raise ValueError("negative")  # NaN passes, Inf passes
```

**Why**: `NaN` and `Inf` bypass numeric comparisons (`NaN < 0` is `False`, `Inf < 0` is `False`). Constraints set to `NaN` make all governance checks pass silently. See `rules/trust-plane-security.md` Rule 3 for the same pattern in the trust layer.

### 5. Thread-Safe Stores

All governance store implementations MUST use `threading.Lock` for every public method that reads or writes internal state.

```python
# DO:
import threading

class ClearanceStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: OrderedDict[str, ClearanceLevel] = OrderedDict()

    def get(self, role_address: str) -> Optional[ClearanceLevel]:
        with self._lock:
            return self._data.get(role_address)

    def set(self, role_address: str, level: ClearanceLevel) -> None:
        with self._lock:
            self._data[role_address] = level

# DO NOT:
class ClearanceStore:
    def __init__(self) -> None:
        self._data: dict[str, ClearanceLevel] = {}

    def set(self, role_address: str, level: ClearanceLevel) -> None:
        self._data[role_address] = level  # Race condition under concurrent access
```

**Why**: In-memory stores use `OrderedDict` which is NOT thread-safe for concurrent mutation. A missing lock allows corrupted reads, lost writes, and non-deterministic governance decisions under concurrent agent execution.

### 6. Fail-Closed on All Error Paths

Every governance decision point MUST deny on error. Permissive fallbacks are FORBIDDEN.

- `can_access()` returns DENY when ANY input is missing, malformed, or ambiguous
- `compute_effective_envelope()` returns `None` (maximally restrictive) on error, NOT a permissive envelope
- `GovernanceEngine.verify_action()` returns BLOCKED on error
- Envelope adapter returns BLOCKED if governance engine fails (NO fallback to legacy)

```python
# DO:
def can_access(self, role_address: str, resource: str) -> AccessDecision:
    try:
        clearance = self._clearance_store.get(role_address)
        if clearance is None:
            return AccessDecision(granted=False, reason="no clearance on record")
        ...
    except Exception:
        logger.exception("can_access failed for %s", role_address)
        return AccessDecision(granted=False, reason="internal error — fail closed")

# DO NOT:
def can_access(self, role_address: str, resource: str) -> AccessDecision:
    try:
        ...
    except Exception:
        return AccessDecision(granted=True, reason="error — allowing by default")
```

**Why**: A governance system that permits on error is worse than no governance at all. Fail-closed ensures that bugs and unexpected states result in denied access, not silent privilege escalation.

### 7. Bounded Collections (`maxlen=10,000`)

All governance stores MUST enforce `MAX_STORE_SIZE`. When at capacity, evict oldest entries.

```python
# DO:
MAX_STORE_SIZE = 10_000

class BridgeStore:
    def add(self, bridge: PactBridge) -> None:
        with self._lock:
            while len(self._data) >= MAX_STORE_SIZE:
                self._data.popitem(last=False)  # Evict oldest
            self._data[bridge.bridge_id] = bridge

# DO NOT:
class BridgeStore:
    def add(self, bridge: PactBridge) -> None:
        self._data[bridge.bridge_id] = bridge  # Grows without bound -> OOM
```

**Why**: Unbounded collections in long-running processes lead to memory exhaustion. This prevents denial-of-service via store flooding.

### 8. Compilation Depth and Breadth Limits

`compile_org()` MUST enforce hard limits on organizational structure complexity:

- `MAX_COMPILATION_DEPTH = 50`
- `MAX_CHILDREN_PER_NODE = 500`
- `MAX_TOTAL_NODES = 100_000`

Raise `CompilationError` when exceeded.

```python
# DO:
def compile_org(self, root: OrgNode, depth: int = 0) -> CompiledOrg:
    if depth > MAX_COMPILATION_DEPTH:
        raise CompilationError(f"Exceeded max depth {MAX_COMPILATION_DEPTH}")
    if len(root.children) > MAX_CHILDREN_PER_NODE:
        raise CompilationError(f"Exceeded max children {MAX_CHILDREN_PER_NODE}")
    ...

# DO NOT:
def compile_org(self, root: OrgNode) -> CompiledOrg:
    for child in root.children:  # No depth limit — stack overflow on cyclic input
        self.compile_org(child)
```

**Why**: Without limits, a malicious or malformed org definition can cause stack overflow (unbounded recursion) or memory exhaustion (exponential node expansion). These limits protect the compilation pipeline from adversarial input.

### 9. Address Validation on All Store Inputs

All store methods accepting `role_address`, `unit_address`, or any positional address MUST validate the address format before storage.

```python
# DO:
from pact.governance.dtr import Address
def set_role_envelope(self, role_address: str, envelope: RoleEnvelope) -> None:
    Address.parse(role_address)  # Raises ValueError on invalid D/T/R grammar
    with self._lock:
        self._envelopes[role_address] = envelope

# DO NOT:
def set_role_envelope(self, role_address: str, envelope: RoleEnvelope) -> None:
    self._envelopes[role_address] = envelope  # Accepts any string — no grammar validation
```

**Why**: Invalid addresses bypass the D/T/R grammar invariant (every D or T must be immediately followed by exactly one R). Unvalidated addresses can create phantom governance records that never match real org positions. Use `Address.parse()` for full grammar validation, or `validate_id()` for simple ID fields.

### 10. Boundary Test Compliance

No domain-specific vocabulary in `src/pact/governance/` or `src/pact/build/`. See `rules/boundary-test.md` for the full blacklist. The governance layer is domain-agnostic — it knows about Departments, Teams, Roles, Envelopes, Clearances, and Bridges, but NEVER about specific industries, organizations, or domain roles.

## MUST NOT Rules

### 1. MUST NOT Import from `governance` in Trust Layer

The dependency direction is: `governance` -> `build.config.schema` (downward) and `governance` -> `trust.eatp_bridge` (for audit). The trust layer MUST NOT import from governance.

```python
# CORRECT dependency direction:
# src/pact/governance/engine.py imports from src/pact/trust/eatp_bridge.py

# FORBIDDEN:
# src/pact/trust/constraint/enforcement.py imports from src/pact/governance/envelopes.py
```

**Why**: PactEngine handles envelope adaptation internally via `_adapt_envelope()`. Bidirectional imports between governance and trust create circular dependencies and conflate policy (governance) with enforcement (trust).

### 2. MUST NOT Pass Mutable State to Agents

Agents receive `GovernanceContext` (`frozen=True`), NOT the `GovernanceEngine` itself. An agent cannot call `engine.grant_clearance()` or `engine.set_role_envelope()`. State mutations are orchestrator-only operations.

```python
# DO:
context = engine.create_context(role_address="D1-R1-T1-R1")
agent.run(context)  # Agent gets frozen snapshot

# DO NOT:
agent.run(engine)  # Agent can mutate governance state directly
```

**Why**: Agents operate within governance constraints. They must not be able to modify the constraints they are subject to. This is the fundamental separation between the Trust Plane (sets policy) and the Execution Plane (operates within policy).

### 3. MUST NOT Use Legacy Envelope Path for New Code

New code MUST use `governance.envelopes` (`RoleEnvelope`, `TaskEnvelope`, `compute_effective_envelope`). Direct use of `trust.constraint.envelope.ConstraintEnvelope` for envelope policy is DEPRECATED.

```python
# DO (new code):
from pact.governance.envelopes import RoleEnvelope, TaskEnvelope, compute_effective_envelope
effective = compute_effective_envelope(role_env, task_env)

# DO NOT (new code):
from pact.trust.constraint.envelope import ConstraintEnvelope
envelope = ConstraintEnvelope(...)  # Legacy — for runtime evaluation only
```

**Why**: The trust-layer `ConstraintEnvelope` is for runtime evaluation only. Governance sets the policy through `RoleEnvelope` and `TaskEnvelope`. Mixing the two conflates policy definition with runtime enforcement.

### 4. MUST NOT Create Stores Without Thread Safety

Any new store implementation (SQLite, PostgreSQL, DataFlow) MUST include thread synchronization from day 1. Do not add thread safety as an afterthought.

```python
# DO:
class PostgresClearanceStore:
    def __init__(self, conn) -> None:
        self._conn = conn
        self._lock = threading.Lock()  # Thread safety from construction
    ...

# DO NOT:
class PostgresClearanceStore:
    def __init__(self, conn) -> None:
        self._conn = conn
        # "We'll add locking later" — this never happens safely
    ...
```

**Why**: Retrofitting thread safety requires auditing every method, every caller, and every interaction pattern. Missing a single path creates a race condition that may only manifest under production load. Build it in from the start.

### 5. MUST NOT Allow Agents to Access Unregistered Tools

When `PactGovernedAgent` is active, tool access is DEFAULT-DENY. Tools must be explicitly registered with the governance engine. Unregistered tools are blocked.

```python
# DO:
engine.register_tool("web_search", clearance_required=ClearanceLevel.OFFICIAL)
engine.register_tool("database_write", clearance_required=ClearanceLevel.CONFIDENTIAL)
# Only registered tools are accessible — everything else is blocked

# DO NOT:
# No tool registration — agent can access any tool in the runtime
agent.run(context, tools=all_available_tools)
```

**Why**: DEFAULT-DENY for tool access ensures that agents cannot escalate their capabilities by discovering unregistered tools. Every tool must be explicitly approved and mapped to a clearance level. This is the governance equivalent of the principle of least privilege.

### 11. No Local Governance Evaluation — All Decisions via verify_action()

All governance decisions in `pact_platform/` (L3) MUST route through `GovernanceEngine.verify_action()`. Local constraint evaluation outside of `verify_action()` is FORBIDDEN.

```python
# DO:
verdict = engine.verify_action(role_address=role_address, action=action, context=ctx)
if not verdict.allowed:
    return BLOCKED

# DO NOT:
envelope = load_envelope(role_address)
if action_cost > envelope.max_cost:          # Local evaluation — FORBIDDEN
    return BLOCKED
if action not in envelope.allowed_actions:   # Local evaluation — FORBIDDEN
    return BLOCKED
```

**Why**: Parallel evaluation paths produce split-brain governance — the engine's audit log does not reflect locally-evaluated decisions, breaking audit continuity and EATP compliance.

### 12. Cumulative Budget MUST Be Injected into verify_action() Context

When calling `verify_action()`, the current per-agent cumulative spend MUST be included in the context dict. The engine cannot track cumulative spend across calls on its own.

```python
# DO:
verdict = engine.verify_action(
    role_address=role_address,
    action=action_name,
    context={
        "cost": this_action_cost,
        "cumulative_spend": self._agent_spend.get(role_address, 0.0),
        **action_context,
    },
)

# DO NOT:
verdict = engine.verify_action(
    role_address=role_address,
    action=action_name,
    context={"cost": this_action_cost},  # Missing cumulative_spend — budget bypass!
)
```

**Why**: The engine evaluates `cost` against `max_budget`. Without `cumulative_spend`, each action is evaluated in isolation — an agent can make unlimited low-cost calls that collectively exceed the budget.

### 13. Rate Limits MUST Be Enforced, Not Just Logged

When a rate limit is exceeded (rolling 24h window exceeded), the call MUST be blocked via `verify_action()` context injection or by returning BLOCKED directly. Logging alone is insufficient.

```python
# DO:
daily_calls = self._get_call_count(role_address)
verdict = engine.verify_action(
    role_address=role_address,
    action=action_name,
    context={"daily_calls": daily_calls, ...},
)
# engine evaluates daily_calls against operational.max_daily_actions

# DO NOT:
daily_calls = self._get_call_count(role_address)
if daily_calls > MAX_RATE:
    logger.warning("Rate limit exceeded for %s", role_address)
    # Execution continues! — FORBIDDEN
```

**Why**: Rate limit logging without enforcement is a governance gap. An agent can exceed rate limits with only a warning — this breaks operational envelope constraints.

### 14. Emergency Halt MUST Be Checked Before Task Processing

`ExecutionRuntime.is_halted()` MUST be the FIRST check in any task processing method. It runs before governance checks, before any work.

```python
# DO:
def process_next(self, task: Task) -> TaskResult:
    if self.is_halted():  # FIRST — before everything
        return TaskResult(blocked=True, reason="runtime halted")
    verdict = self._hook_enforcer.enforce(task.action, task.context)
    if not verdict.allowed:
        return TaskResult(blocked=True, reason=verdict.reason)
    return self._execute(task)

# DO NOT:
def process_next(self, task: Task) -> TaskResult:
    verdict = self._hook_enforcer.enforce(task.action, task.context)  # Governance first? WRONG
    if not verdict.allowed:
        return TaskResult(blocked=True, reason=verdict.reason)
    if self.is_halted():  # Halt after governance? WRONG
        return TaskResult(blocked=True, reason="runtime halted")
    return self._execute(task)
```

**Why**: Emergency halt is a safety override that must preempt governance. A halted runtime must stop ALL work regardless of what governance would permit. Checking halt after governance allows governance to "approve" work that the operator has explicitly stopped.

## MUST NOT Rules (Continued)

### 6. MUST NOT Implement Retired Constraint/ Modules

The following modules are RETIRED from `pact_platform/trust/constraint/` as of v0.3.0. Do NOT re-implement or import them:

- `gradient.py` — verification gradient (now in L1 GovernanceEngine)
- `envelope.py` — constraint envelope evaluation (now in L1 GovernanceEngine)
- `middleware.py` — enforcement middleware (replaced by HookEnforcer/ShadowEnforcer)

The ONLY permitted `constraint/` module at L3 is `bridge_envelopes.py`.

```python
# DO NOT re-implement or import:
from pact_platform.trust.constraint.gradient import VerificationGradient    # RETIRED
from pact_platform.trust.constraint.envelope import ConstraintEnvelopePipeline  # RETIRED
from pact_platform.trust.constraint.middleware import EnforcementMiddleware  # RETIRED

# DO: use HookEnforcer for blocking enforcement
from pact_platform.engine.hook_enforcer import HookEnforcer
```

**Why**: These modules implemented parallel governance logic that diverged from the engine's state. Re-implementing them recreates the split-brain problem that v0.3.0 was designed to eliminate.

### 7. MUST NOT Expose Mock Governance Engines as Public API

Mock governance engines (for examples, seeding, tests) MUST be function-scoped or use underscore-prefixed names. They MUST NOT be exported from module `__all__` or used outside their immediate scope.

```python
# DO: function-scoped or prefixed
def _make_mock_engine() -> GovernanceEngine: ...   # underscore prefix
def test_something():
    engine = _make_permissive_engine()             # function-scoped

# DO NOT:
class MockGovernanceEngine(GovernanceEngine): ...  # Public class — FORBIDDEN
__all__ = ["MockGovernanceEngine"]                  # Export — FORBIDDEN
```

**Why**: Mock engines bypass real governance. If exposed as public API, they risk being imported in production paths — silently disabling all governance enforcement.

## Cross-References

- `rules/boundary-test.md` — Domain vocabulary blacklist
- `rules/trust-plane-security.md` — Trust store security patterns (apply same patterns to governance stores)
- `rules/eatp.md` — EATP SDK conventions (dataclasses, error hierarchy)
- `rules/security.md` — Global security rules (secrets, injection, input validation)
- `skills/29-pact/pact-governance-engine.md` — Single-path architecture, L1/L3 boundary, cumulative budget injection
- `skills/29-pact/pact-governed-agents.md` — HookEnforcer, ShadowEnforcer, emergency halt patterns
