# Red Team Findings: PACT Platform Build Analysis

**Date**: 2026-03-24
**Method**: Adversarial review of 5 agent analysis outputs (#35 requirements, #36 COC analysis, #38 value audit, #33 final synthesis) against actual source code in kailash-py, kaizen-agents, pact web frontend, and Docker configuration
**Scope**: 10 attack vectors assigned by brief, plus emergent findings from source verification
**Severity**: CRITICAL > HIGH > MEDIUM > LOW

---

## Executive Summary

The analysis team produced thorough, internally consistent work. The requirements (#35) are precise, the COC analysis (#36) correctly identifies the three fault lines, and the value audit (#38) frames the platform story honestly. However, source code verification reveals several concrete gaps that would cause implementation failures if not addressed before `/todos`. The most dangerous finding is that the envelope type mismatch is worse than any agent described -- there are three fundamentally different envelope types with incompatible field structures, not two. The second most dangerous finding is that the `auto-seeding` requirement the value auditor calls essential is not in the requirements (#35) at all. The third is that the `GovernedSupervisor` does not integrate with kailash-pact's `GovernanceEngine` in any way -- they are parallel governance systems with no bridge.

**Complexity Score**: Complex (28 points -- Governance 10, Legal 4, Strategic 14)

---

## FINDING RT-R01: Three-Way Envelope Type Mismatch (Not Two-Way)

**Severity**: CRITICAL
**Agents affected**: All five -- none fully described the problem

### The Problem

The analysis describes a two-way mismatch: `ConstraintEnvelopeConfig` (kailash-pact, Pydantic) vs `ConstraintEnvelope` (kaizen-agents, dataclass with dict fields). Source verification reveals there are actually three distinct types:

**Type 1: `pact.governance.config.ConstraintEnvelopeConfig`** (kailash-pact)

- Pydantic `BaseModel` with `frozen=True`
- Five typed sub-models: `FinancialConstraintConfig`, `OperationalConstraintConfig`, `TemporalConstraintConfig`, `DataAccessConstraintConfig`, `CommunicationConstraintConfig`
- `financial` is `Optional[FinancialConstraintConfig]` (None means "no financial capability")
- Has additional fields: `id`, `description`, `confidentiality_clearance`, `max_delegation_depth`, `expires_at`
- NaN/Inf validation via Pydantic validators
- Verified at: `/Users/esperie/repos/kailash/kailash-py/packages/kailash-pact/src/pact/governance/config.py` line 239

**Type 2: `kaizen_agents.types.ConstraintEnvelope`** (kaizen-agents)

- Dataclass with `frozen=True`
- Five `dict[str, Any]` fields: `financial`, `operational`, `temporal`, `data_access`, `communication`
- `financial` default is `{"limit": 1.0}` (dict with "limit" key, NOT a typed sub-model)
- No `id`, `description`, `confidentiality_clearance`, `max_delegation_depth`, or `expires_at`
- NaN validation only on `financial.limit` and `temporal.limit_seconds` in `__post_init__`
- Verified at: `/Users/esperie/repos/kailash/kailash-py/packages/kaizen-agents/src/kaizen_agents/types.py` line 104

**Type 3: The platform's existing `pact.trust.constraint.envelope.ConstraintEnvelope`** (local code being kept)

- Requirements (#35 TODO-0006) keeps `trust/constraint/envelope.py` as "ConstraintEnvelope runtime evaluation"
- This is a THIRD envelope type -- the existing platform code uses it for runtime evaluation
- The governance.md MUST NOT Rule 3 says "do not use legacy envelope path for new code" but M0 keeps the file

### What the Adapter Must Actually Do

The `PlatformEnvelopeAdapter` must convert between Types 1 and 2 (the framework advisor correctly identified this). But the analysis misses:

1. **Type 1 has `financial: Optional` semantics** -- `None` means "dimension not applicable." Type 2 has `financial: dict` with a default `{"limit": 1.0}`. Converting `None` to `{"limit": 1.0}` silently assigns a $1 budget to agents that should have no financial constraints. Converting `None` to `{}` means the kaizen-agents `BudgetTracker` gets no limit, which is the opposite problem.

2. **Type 1 has `confidentiality_clearance` as a top-level field**. Type 2 encodes clearance inside `data_access.ceiling` as a string ("public", "confidential", etc.). The mapping is non-trivial -- kailash-pact uses `ConfidentialityLevel` enum, kaizen-agents uses a string from `_CLEARANCE_MAP`.

3. **Type 1 has `max_delegation_depth` and `expires_at`**. Type 2 has neither. These constraints are silently dropped during conversion. If an operator configures `max_delegation_depth=3` in the org definition, the GovernedSupervisor will not enforce it.

4. **NaN validation gap**: Type 1 validates via Pydantic field validators. Type 2 validates only `financial.limit` and `temporal.limit_seconds`. Other numeric values in dict fields (e.g., `operational.max_concurrent`) are NOT validated for NaN/Inf. The adapter MUST validate ALL numeric dict values during conversion -- the COC analysis (#36) identified this but the requirements (#35) do not include it as a specific acceptance criterion for any TODO.

### Recommendation

Add a dedicated TODO in M4 specifically for envelope adapter testing with these edge cases:

- `financial=None` round-trip
- `confidentiality_clearance` to `data_access.ceiling` mapping
- `max_delegation_depth` and `expires_at` preservation (or documented loss)
- NaN/Inf injection in every dict field path
- Property tests: `adapt(config).financial["limit"] == config.financial.max_spend_usd` for non-None

---

## FINDING RT-R02: GovernedSupervisor and GovernanceEngine Are Parallel Systems

**Severity**: CRITICAL
**Agents affected**: #35 (requirements), #38 (value audit)

### The Problem

The requirements (#35) and value audit (#38) describe a future where `GovernedSupervisor` routes actions through `GovernanceEngine.verify_action()` via an `execute_node` callback. The value audit Journey 3 describes: "For each action the agent takes, the governance wrapper calls `engine.verify_action()`."

Source verification of `GovernedSupervisor` (at `/Users/esperie/repos/kailash/kailash-py/packages/kaizen-agents/src/kaizen_agents/supervisor.py`) reveals:

1. **GovernedSupervisor has its own complete governance stack**: `AccountabilityTracker`, `BudgetTracker`, `CascadeManager`, `ClearanceEnforcer`, `BypassManager`, `VacancyManager`, `DerelictionDetector`, `AuditTrail`. None of these reference `GovernanceEngine`.

2. **GovernedSupervisor's `run()` method does budget checking internally** (lines 320-331) via `self._budget.get_snapshot()`. It does NOT call `engine.verify_action()`. The budget check uses the kaizen-agents `BudgetTracker`, not the kailash-pact governance engine.

3. **GovernedSupervisor's `execute_node` callback is a plain async function** with signature `Callable[[AgentSpec, dict[str, Any]], Awaitable[dict[str, Any]]]` (line 148). There is no governance gating in the callback protocol. The callback receives `AgentSpec` and returns `{"result": ..., "cost": ...}`. There is no `GovernanceVerdict` in the return type.

4. **GovernedSupervisor emits `PlanEvent` objects** (lines 309-414). The platform must bridge these to the existing WebSocket event system and DataFlow models. But the events contain only basic execution information, not governance verdicts from `GovernanceEngine`.

### The Implication

M4 is not "wiring GovernedSupervisor to GovernanceEngine." M4 is building a bridge between two complete, parallel governance systems:

- **System A (kailash-pact)**: GovernanceEngine with D/T/R addressing, 3-layer envelopes, knowledge clearance, verification gradient, audit anchors, thread-safe facade
- **System B (kaizen-agents)**: GovernedSupervisor with budget tracking, cascade management, clearance enforcement, accountability tracking, dereliction detection

The platform's `execute_node` callback must serve as the bridge point: when GovernedSupervisor calls `execute_node(spec, inputs)`, the callback must:

1. Resolve the agent's D/T/R address from `spec`
2. Call `GovernanceEngine.verify_action()` with the action
3. If BLOCKED, raise an exception (GovernedSupervisor will catch it and mark node as FAILED)
4. If HELD, somehow pause the GovernedSupervisor execution until the HELD action is resolved -- BUT GovernedSupervisor has no built-in HELD mechanism that waits for external resolution

### The HELD Problem

GovernedSupervisor handles HELD by setting `node.state = PlanNodeState.HELD` (line 329) but only for budget exhaustion. There is NO mechanism for:

- An external governance verdict of HELD
- Pausing execution and waiting for human approval
- Resuming a HELD node after approval

If `GovernanceEngine.verify_action()` returns HELD, the `execute_node` callback has no way to pause and wait. It can only raise an exception (which fails the node) or block the async event loop (which deadlocks). The `_find_ready_nodes` method (line 632) skips nodes that are not PENDING, so a HELD node will never be re-evaluated.

### Recommendation

This is the single highest-risk technical challenge in the build. The requirements (#35) need:

1. A TODO specifically for the HELD-verdict bridge mechanism (async wait with timeout, polling DataFlow for approval status)
2. A TODO for reconciling the dual governance systems (which budget tracker is authoritative? which audit trail is canonical?)
3. A red team focus on the interaction patterns between the two systems

---

## FINDING RT-R03: Auto-Seeding Is Missing From Requirements

**Severity**: HIGH
**Agents affected**: #35 (requirements) vs #38 (value audit)

### The Problem

The value audit (#38) states explicitly: "Data credibility: REAL if M4 auto-seeds activity on first boot. EMPTY if the evaluator has to manually create everything." (Section 2, Journey 5, Step 2) and "If the example vertical is auto-seeded (which it should be in M4), there is immediately data to explore."

The requirements (#35) contain 55 numbered TODOs across M0-M6. None of them include auto-seeding. There is no TODO for:

- Auto-loading the university example org on first boot
- Generating seed agent activity for the dashboard
- Creating sample objectives/requests/decisions to demonstrate the work management workflow
- Populating the approval queue with a sample HELD action

The existing `scripts/seed_demo.py` (verified at `/Users/esperie/repos/terrene/pact/scripts/seed_demo.py`) populates seed data but uses old import paths (`from pact.build.config.schema`, `from pact.trust.audit.anchor`, etc.) and will break after M0.

### Recommendation

Add a TODO in M4 or M5 for:

1. Migrate `scripts/seed_demo.py` to use `pact_platform.*` imports (or delete and rewrite)
2. Create an auto-seed module that runs on first boot when no data exists
3. The auto-seed must create at least: one org, one objective, three requests, one HELD decision, five audit anchors, and basic verification gradient stats

---

## FINDING RT-R04: Dockerfile and Docker Compose Reference Old Module Paths

**Severity**: HIGH
**Agents affected**: #35 (requirements) -- partially covered in TODO-0013 but incomplete

### The Problem

The Dockerfile (verified at `/Users/esperie/repos/terrene/pact/Dockerfile`) runs:

```
CMD sh -c "python scripts/run_seeded_server.py"
```

`scripts/run_seeded_server.py` (verified) imports:

```python
from pact.use.api.endpoints import PactAPI
from pact.use.api.server import create_app
```

`scripts/seed_demo.py` (verified) has 16 imports from `pact.*` paths that will all break after M0.

The `docker-compose.yml` (verified at `/Users/esperie/repos/terrene/pact/docker-compose.yml`) references `apps/web/Dockerfile` for the frontend build context. The frontend API client (verified at `/Users/esperie/repos/terrene/pact/apps/web/lib/api.ts`) uses hardcoded API paths like `/api/v1/teams`, `/api/v1/held-actions`, etc. These are HTTP paths, not Python imports, so the rename does not break them. However:

1. The API client class is named `CareApiClient` (line 80) and the WebSocket client is `CareWebSocketClient` (line 652). These should be renamed to `PactApiClient` / `PactWebSocketClient` for consistency with the platform rename. The Docker Compose network is named `care_net` (line 112).

2. The CORS origin is `CARE_CORS_ORIGINS` (line 56). The API host env var is `CARE_API_HOST` (line 58), `CARE_API_PORT` (line 59). All "CARE" environment variables need to be renamed to "PACT" for namespace consistency.

### What is NOT in the Requirements

TODO-0013 lists `scripts/seed_demo.py` for import path updates. But it does NOT list:

- `scripts/run_seeded_server.py` (2 broken imports)
- `scripts/shadow_calibrate.py` (1 broken import: `from pact.build.verticals.dm_runner`)
- `Dockerfile` CMD reference (still valid path but the script it runs will break)
- Docker Compose environment variables (`CARE_*` to `PACT_*`)
- Frontend class names (`CareApiClient` to `PactApiClient`)
- Docker Compose network name (`care_net` to `pact_net`)

### Recommendation

Expand TODO-0013 or create a separate TODO-0014 for Docker and infrastructure renaming. The current list in TODO-0013 is incomplete and will leave Docker builds broken after M0.

---

## FINDING RT-R05: 153 Test Collection Errors -- Root Cause Unknown

**Severity**: HIGH
**Agents affected**: All -- referenced as fact but no root cause analysis

### The Problem

Every analysis document references "153 test collection errors" as a known issue to be fixed in M0. No document provides:

1. What causes these errors
2. Whether they are import errors (which the rename would fix), fixture errors (which it would not), or dependency errors
3. Whether they existed before the current session or were introduced by a recent change
4. A list of which test files are affected

The requirements (#35 TODO-0012) says "Fix any remaining test failures" as a catch-all. But fixing 153 collection errors without understanding their root cause is dangerous:

- If they are caused by `from pact.governance import X` and governance was just deleted, the fix is straightforward (redirect to kailash-pact).
- If they are caused by missing fixtures, the fix requires understanding test infrastructure.
- If they are caused by circular imports between `pact.build.*` and `pact.trust.*`, the rename may create new circular imports between `pact_platform.build.*` and `pact_platform.trust.*`.

### Recommendation

Before M0 starts, run `pytest --collect-only 2>&1 | head -50` to capture the actual error messages. Categorize the 153 errors into buckets (import errors, fixture errors, missing dependencies, other). This takes 5 minutes and saves hours of debugging during M0.

---

## FINDING RT-R06: ConstraintEnvelopeConfig Is Pydantic, Not "Frozen Pydantic"

**Severity**: MEDIUM
**Agents affected**: #33 (synthesis), #38 (value audit)

### The Problem

The synthesis (#33) describes `ConstraintEnvelopeConfig` as "frozen Pydantic." Source verification confirms it uses `ConfigDict(frozen=True)`, which in Pydantic v2 means the model is immutable at the instance level. However, the value audit (#38) and the synthesis compare this favorably to kaizen-agents' "frozen dataclass" as if they were equivalent.

They are not:

- Pydantic `frozen=True` prevents field assignment after construction. But `ConstraintEnvelopeConfig.financial` is an `Optional[FinancialConstraintConfig]` -- if it is a sub-model instance, the sub-model is also frozen. This is genuinely immutable.
- kaizen-agents' `ConstraintEnvelope(frozen=True)` prevents field assignment. But its fields are `dict[str, Any]` -- the dicts themselves are MUTABLE. Line 109 of `types.py` documents this explicitly: "frozen=True prevents wholesale field replacement while allowing dict mutation for the builder pattern."

This means kaizen-agents' `ConstraintEnvelope` is NOT actually immutable in the security-relevant sense. An agent with a reference to its `ConstraintEnvelope` can do:

```python
envelope.financial["limit"] = float("inf")  # Bypasses budget!
```

This is `frozen=True` on the dataclass, but the dict contents are fully mutable.

### Security Implication

The `GovernedSupervisor.envelope` property (line 537) returns `copy.deepcopy(self._envelope)`, which prevents external mutation. But within the supervisor's internal code, mutations to dict contents are possible. The `_ReadOnlyView` proxy (lines 69-82) protects Layer 3 subsystems but NOT the envelope's dict fields.

### Recommendation

The PlatformEnvelopeAdapter must deep-copy all dict fields when constructing kaizen-agents `ConstraintEnvelope` objects, and the platform code must never hold a reference to the original dicts. This should be an explicit acceptance criterion in the M4 adapter TODO.

---

## FINDING RT-R07: WebSocket Event Bridge Contract Undefined

**Severity**: MEDIUM
**Agents affected**: #35 (requirements), #38 (value audit)

### The Problem

The value audit (#38) describes real-time dashboard updates via WebSocket: "The dashboard updates in real-time via WebSocket. The evaluator sees: Request decomposition in the Request Queue, Agent execution with verification gradient classifications..." (Journey 5, Step 4).

The existing WebSocket server emits `PlatformEvent` objects (verified in `apps/web/lib/api.ts` line 766). GovernedSupervisor emits `PlanEvent` objects (verified in `kaizen_agents/types.py` line 480).

These are different types:

- `PlatformEvent`: Used by the web frontend, expected shape is `{type: string, ...}` parsed from JSON
- `PlanEvent`: kaizen-agents dataclass with `event_type: PlanEventType`, `node_id`, `output`, `error`, `dimension`, `usage_pct`, etc.

The requirements (#35) do not include a TODO for:

1. Defining the mapping from `PlanEvent` to `PlatformEvent`
2. Specifying which `PlanEventType` values map to which dashboard updates
3. Handling the serialization (PlanEvent contains `PlanModification` which contains `PlanNode` which contains `AgentSpec` -- deep nested objects)
4. Rate limiting event emission (a 50-node plan emits 100+ events in seconds)

The requirements mention "PlanEvent -> WebSocket bridge for real-time dashboard" in the synthesis (#33 M4 description) but there is no numbered TODO for it.

### Recommendation

Add a TODO in M4 for the event bridge with:

- PlanEvent to PlatformEvent mapping table
- Serialization contract (what the frontend expects vs what GovernedSupervisor emits)
- Rate limiting and batching strategy
- Frontend type updates (`types/pact.ts` may need new event type definitions)

---

## FINDING RT-R08: COC Security Findings Not Reflected in Requirements

**Severity**: MEDIUM
**Agents affected**: #35 (requirements) vs #36 (COC analysis)

### The Problem

The COC analysis (#36 Section 4) identifies 6 new attack vectors for M4:

1. Agent self-modification
2. Envelope adapter type confusion
3. Event bridge injection
4. HELD verdict bypass
5. execute_node callback escape
6. Stale context after envelope update

The requirements (#35) M4 section has 7 TODOs (TODO-4001 through TODO-4007). None of them include:

- Security testing for each attack vector
- Specific acceptance criteria addressing the 6 vectors
- A dedicated security test TODO

The COC analysis recommends creating `delegate-wiring.md` rule before M4 starts (P15 in Section 5.4). The requirements do not include a TODO for creating this rule file.

### Recommendation

Either:

- Add a TODO-4008: "Create delegate-wiring.md rule file" with the 6 attack vectors as constraints
- Add security-specific acceptance criteria to each existing M4 TODO
- Add a TODO-4009: "Red team M4 wiring" with explicit test scenarios for each vector

---

## FINDING RT-R09: seed_demo.py References Dead Vertical Code

**Severity**: MEDIUM
**Agents affected**: #35 (requirements)

### The Problem

`scripts/seed_demo.py` (line 2086, verified) imports:

```python
from pact.build.verticals.dm_runner import DMTeamRunner
```

TODO-0007 deletes `build/verticals/` (5 files including `dm_runner.py`). TODO-0013 lists `seed_demo.py` for import path updates. But `DMTeamRunner` has no replacement -- it is dead code being deleted. The seed script will fail not because of a path change but because the module it depends on no longer exists.

Additionally, `scripts/shadow_calibrate.py` (line 27, verified) imports the same dead module:

```python
from pact.build.verticals.dm_runner import DMTeamRunner
```

Neither script is listed for deletion in the requirements, only for "import path updates."

### Recommendation

TODO-0007 must include: "Delete or rewrite `scripts/seed_demo.py` and `scripts/shadow_calibrate.py` references to `pact.build.verticals.dm_runner`. If DMTeamRunner functionality is needed, reimplement using the university example vertical."

---

## FINDING RT-R10: Frontend Naming Inconsistency ("CARE" vs "PACT")

**Severity**: LOW
**Agents affected**: None identified this

### The Problem

The web frontend API client (verified at `/Users/esperie/repos/terrene/pact/apps/web/lib/api.ts`) uses "Care" naming throughout:

- `CareApiClient` (line 80)
- `CareWebSocketClient` (line 652)

The Docker Compose (verified at `/Users/esperie/repos/terrene/pact/docker-compose.yml`) uses "CARE" naming:

- `CARE_CORS_ORIGINS` (line 56)
- `CARE_API_HOST` (line 58)
- `CARE_API_PORT` (line 59)
- `care_net` network (line 112)

This is not a functional bug -- everything works. But it creates confusion for evaluators who see "PACT Platform" in documentation but "CARE" in code. The value audit (#38) describes the evaluator experience without noting this naming inconsistency.

The `DmStatus` and `DmTask` types are imported in the API client (line 23-24), referencing "DM" (Decision-Making) team -- a domain-specific concept from the old vertical that violates the boundary test.

### Recommendation

Add to M5 (Frontend Updates): rename `CareApiClient` to `PactApiClient`, `CareWebSocketClient` to `PactWebSocketClient`, remove `DmStatus`/`DmTask` types, rename Docker env vars from `CARE_*` to `PACT_*`, rename network from `care_net` to `pact_net`.

---

## FINDING RT-R11: DelegateProtocol Not in kaizen-agents

**Severity**: MEDIUM
**Agents affected**: #33 (synthesis), #38 (value audit)

### The Problem

The synthesis (#33) lists "DelegateProtocol interface (abstract boundary between L2 and L3)" as a key M4 deliverable. The value audit (#38 Risk 3) recommends: "PACT Platform should depend on the protocol interface, not on GovernedSupervisor directly."

Source verification of kaizen-agents (59 source files at `/Users/esperie/repos/kailash/kailash-py/packages/kaizen-agents/src/kaizen_agents/`) reveals no `DelegateProtocol` or equivalent abstract interface. The `GovernedSupervisor` class is concrete with no protocol/ABC base class.

This means `DelegateProtocol` must be created in the pact-platform codebase. The requirements (#35) reference it but do not include a specific TODO for defining its interface.

### What DelegateProtocol Must Define

Based on the GovernedSupervisor API:

```python
class DelegateProtocol(Protocol):
    async def run(self, objective: str, context: dict | None = None,
                  execute_node: ExecuteNodeFn | None = None) -> SupervisorResult: ...
    async def run_plan(self, plan: Plan, execute_node: ExecuteNodeFn | None = None,
                       context: dict | None = None) -> SupervisorResult: ...
```

But this protocol does not capture the governance subsystem access (Layer 3 properties) or the event subscription mechanism the platform needs for WebSocket bridging.

### Recommendation

Add an explicit TODO in M4 for defining `DelegateProtocol` with:

- The execute interface (run, run_plan)
- Event subscription (how the platform gets PlanEvents)
- Governance state queries (budget snapshot, audit trail)
- The explicit decision: does the protocol expose governance internals or only the simple API?

---

## FINDING RT-R12: Dual Database Topology Creates Consistency Risks

**Severity**: MEDIUM
**Agents affected**: #33 (synthesis) mentions "dual database topology" but does not analyze risks

### The Problem

The plan calls for:

- **Database A**: SQLite via kailash-pact for governance stores (envelopes, clearances, bridges, audit anchors)
- **Database B**: DataFlow (SQLite dev / PostgreSQL production) for work management (objectives, requests, sessions, decisions)

A single operation like "agent requests access to CONFIDENTIAL data, is HELD, human approves, agent continues" touches both databases:

1. `GovernanceEngine.verify_action()` checks clearance in Database A, returns HELD
2. `AgenticDecision` record created in Database B
3. Human approves via API, updating Database B
4. Agent execution resumes, emitting audit anchor in Database A

There is no transaction spanning both databases. If step 3 succeeds but step 4 fails:

- Database B says the action is approved
- Database A has no audit anchor for the approval
- The audit trail is broken

If Database A is SQLite and Database B is PostgreSQL (production), they cannot share a transaction coordinator.

### Recommendation

The requirements should include a TODO for a reconciliation strategy:

- Eventual consistency via a two-phase approach (write to DataFlow first, then emit audit anchor, with retry on failure)
- Idempotency keys to prevent duplicate audit anchors on retry
- A health check that verifies the two databases are in sync (count of approved AgenticDecisions should match count of approval audit anchors)

---

## FINDING RT-R13: Existing API Types Reference Domain Vocabulary

**Severity**: LOW
**Agents affected**: None

### The Problem

The frontend types file (imported in `apps/web/lib/api.ts` lines 14-32) includes:

- `DmStatus` -- "DM" = Decision-Making team (domain-specific)
- `DmTask` -- domain-specific task type

The API client has methods:

- `getDmStatus()` -- `/api/v1/dm/status` (line 577)
- `submitDmTask()` -- `/api/v1/dm/tasks` (line 582)
- `getDmTaskStatus()` -- `/api/v1/dm/tasks/{id}` (line 596)

These are boundary-test violations in the platform layer. The "DM team" concept is from the old vertical that is being deleted in TODO-0007.

The backend server (`src/pact/use/api/endpoints.py`) presumably has corresponding endpoints that serve these routes. After governance deletion and vertical deletion, these endpoints will either break or return empty data.

### Recommendation

Add to M0 or M2: remove DM-specific API endpoints and frontend types. Replace with the generic work management API from M2 (objectives, requests, sessions).

---

## FINDING RT-R14: GovernedSupervisor Executes Nodes Sequentially Despite DAG

**Severity**: LOW
**Agents affected**: #38 (value audit Journey 3)

### The Problem

The value audit describes "Request decomposition in the Request Queue, each assigned to an agent pool" suggesting parallel execution. Source verification of `GovernedSupervisor.run()` (lines 304-393) shows:

```python
while ready_nodes and not plan_failed:
    for node_id in ready_nodes:  # Sequential iteration
        ...
        output = await executor(node.agent_spec, inputs)  # Awaited one at a time
```

Ready nodes are found (potentially multiple independent nodes), but they are executed in a `for` loop with `await` -- meaning sequential execution. A plan with 3 independent nodes executes them one after another, not in parallel.

This is a performance concern, not a correctness issue. But the value audit implies parallel execution for the evaluator experience.

### Recommendation

Note this as a kaizen-agents enhancement opportunity. The platform's `execute_node` callback could use `asyncio.gather()` for independent nodes, but this requires changes upstream in GovernedSupervisor. For the initial platform build, sequential execution is acceptable.

---

## Summary: Risk Prioritization

| #      | Finding                                     | Severity | Impact                                  | Recommendation                                            |
| ------ | ------------------------------------------- | -------- | --------------------------------------- | --------------------------------------------------------- |
| RT-R01 | Three-way envelope mismatch                 | CRITICAL | M4 blocks on incorrect adapter          | Add envelope edge-case TODOs with specific test scenarios |
| RT-R02 | Dual governance systems with no HELD bridge | CRITICAL | M4 approval workflow does not work      | Add HELD-bridge TODO, reconciliation strategy             |
| RT-R03 | Auto-seeding not in requirements            | HIGH     | Empty dashboard on first boot           | Add auto-seed TODO in M4                                  |
| RT-R04 | Docker and scripts reference old paths      | HIGH     | Docker builds break after M0            | Expand TODO-0013 or add TODO-0014                         |
| RT-R05 | 153 test errors undiagnosed                 | HIGH     | Unknown M0 risk                         | Run `pytest --collect-only` before M0                     |
| RT-R06 | kaizen-agents envelope dict mutability      | MEDIUM   | Security gap in agent isolation         | Deep-copy dicts in adapter                                |
| RT-R07 | WebSocket event bridge undefined            | MEDIUM   | No real-time dashboard in M4            | Add event bridge TODO                                     |
| RT-R08 | COC security findings not in requirements   | MEDIUM   | 6 attack vectors untested               | Add security TODOs or acceptance criteria                 |
| RT-R09 | seed_demo.py depends on dead code           | MEDIUM   | Scripts break silently                  | Update TODO-0007                                          |
| RT-R10 | CARE naming in frontend/Docker              | LOW      | Evaluator confusion                     | Add to M5                                                 |
| RT-R11 | DelegateProtocol does not exist             | MEDIUM   | No anti-corruption layer for v0.1.0 API | Add protocol definition TODO                              |
| RT-R12 | Dual database consistency                   | MEDIUM   | Broken audit trails                     | Add reconciliation TODO                                   |
| RT-R13 | DM-specific API in platform                 | LOW      | Boundary test violation                 | Clean up in M0 or M2                                      |
| RT-R14 | Sequential node execution                   | LOW      | Slower than expected                    | Note as enhancement                                       |

---

## Decision Points Requiring Stakeholder Input

1. **RT-R01/RT-R02**: Should the PACT Platform use GovernedSupervisor's internal governance (BudgetTracker, ClearanceEnforcer) OR route everything through GovernanceEngine? Using both creates reconciliation problems. Using only GovernanceEngine means ignoring GovernedSupervisor's built-in governance. Using only GovernedSupervisor means the platform's extensive GovernanceEngine infrastructure is unused by agents.

2. **RT-R02**: The HELD-verdict bridge is architecturally novel -- no analysis described how to pause an async callback and resume after external approval. The options are: (a) block the callback with a polling loop (resource-intensive), (b) fail the node and re-submit after approval (loses execution context), (c) modify GovernedSupervisor upstream to support external HELD resolution (requires kailash-py changes). Which approach?

3. **RT-R03**: The value auditor says auto-seeding is essential for evaluator experience. The requirements analyst excluded it. Is auto-seeding in scope for the initial build, or is it deferred to a post-M6 polish pass?

4. **RT-R12**: Is eventual consistency between governance SQLite and DataFlow PostgreSQL acceptable, or must approval/audit operations be atomic? This drives whether the platform needs a two-phase commit or can tolerate brief windows of inconsistency.
