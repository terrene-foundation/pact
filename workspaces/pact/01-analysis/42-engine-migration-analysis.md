# Engine Migration Analysis — Primitives → Engines

**Date**: 2026-03-30
**Updated**: 2026-03-30 (engine audit complete — DataFlowEngine and NexusEngine facades discovered)
**Triggered by**: User observation that pact-platform uses low-level SDK primitives instead of engine APIs.

---

## Question 1: Are the engines feature-complete and usable?

### DataFlow — THREE API levels

**Location**: `packages/kailash-dataflow/src/dataflow/core/engine.py` (class `DataFlow`, 8000+ lines)
**Engine facade**: `packages/kailash-dataflow/src/dataflow/engine.py` (class `DataFlowEngine`)

**Three API levels available**:

| Level        | API                                                                | Performance               | Use Case                                              |
| ------------ | ------------------------------------------------------------------ | ------------------------- | ----------------------------------------------------- |
| **Workflow** | `db.create_workflow()` → `db.add_node()` → `db.execute_workflow()` | 2-3ms per op              | Multi-node workflows, transactions, conditional logic |
| **Express**  | `db.express.create("Model", {...})`                                | 0.1ms per op (23x faster) | Simple CRUD, API endpoints, high-throughput           |

**Express API methods** (the ones pact-platform SHOULD use for most operations):

- `db.express.create("Model", {"field": "value"})` → creates record
- `db.express.read("Model", "id")` → reads single record
- `db.express.find_one("Model", {"filter": ...})` → finds first match
- `db.express.update("Model", {"filter": ...}, {"fields": ...})` → updates records
- `db.express.delete("Model", "id")` → deletes record
- `db.express.list("Model", {"filter": ...}, limit=N)` → lists records
- `db.express.count("Model", {"filter": ...})` → counts records
- `db.express.bulk_create("Model", [...])` → bulk create
- `db.express.bulk_update("Model", {...})` → bulk update
- `db.express.bulk_delete("Model", {...})` → bulk delete

**Assessment**: Feature-complete for pact-platform's use case. Verified end-to-end:

```
# Verified 2026-03-30 — DataFlowEngine + Express with string IDs
Created: {'id': 'item-xyz', 'name': 'Widget', 'rows_affected': 1}
List: [{'id': 'item-xyz', 'name': 'Widget', ...}]
Read by string ID: {'id': 'item-xyz', 'name': 'Widget', 'found': True}
```

**Verified**: Express works with explicit `id: str` models (pact's pattern). `DataFlowEngine.builder()` provides validation, classification, and health monitoring on top.

**Gap**: Express is async-only (`await db.express.create(...)`) — pact-platform's API routers are currently sync. Migration requires `async def` on all router handlers (trivial with FastAPI).

**Gotcha**: Default `@db.model` without explicit `id: str` creates auto-increment integer IDs. Pact's models already declare `id: str`, so this is not a blocker.

### Nexus Engine

**Location**: `packages/kailash-nexus/src/nexus/core.py` (class `Nexus`)

**API**: `Nexus()` → `nexus.register("name", workflow)` → `nexus.start()`

Nexus provides:

- Automatic API + CLI + MCP from a single workflow registration
- Built-in CORS, rate limiting, auth, monitoring
- Multi-channel deployment (one workflow, three interfaces)

**Assessment**: Feature-complete for workflow-based APIs. However, pact-platform's API layer is NOT workflow-based — it has 62+ custom endpoints with complex business logic, governance integration, WebSocket auth, and custom middleware. Nexus is designed for exposing workflows, not for custom API servers.

**Verdict**: Nexus is NOT the right choice for pact-platform's API layer. The current FastAPI server is appropriate. Nexus would be the right choice if pact-platform exposed DataFlow CRUD as a simple REST API.

### Kaizen Engine

**Location**: `packages/kailash-kaizen/src/kaizen/` + `packages/kaizen-agents/`

**Assessment**: Already correctly used. `GovernedSupervisor` from kaizen-agents is the right engine-level API, and pact-platform uses it in `orchestrator.py`. No migration needed.

---

## Question 2: Why did Claude dive into primitives? Are the COC artifacts deficient?

### The Root Cause: COC artifacts actively teach primitives

**Finding: CLAUDE.md "Critical Execution Rules" — the single most impactful instruction — teaches ONLY primitives.**

```python
# ALWAYS: runtime.execute(workflow.build())
# NEVER: workflow.execute(runtime)
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
```

This is loaded on EVERY turn of EVERY session. It is the first code pattern any agent sees. It anchors behavior toward:

1. `WorkflowBuilder` construction
2. `add_node()` calls
3. `runtime.execute(workflow.build())`

**There is no mention of `db.express`, `ExpressDataFlow`, or engine-level APIs in CLAUDE.md.**

### Artifact-by-artifact breakdown

| Artifact                                           | What it teaches                                                              | Gap                                                      |
| -------------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------- |
| **CLAUDE.md** "Critical Execution Rules"           | `runtime.execute(workflow.build())`                                          | **No mention of DataFlow express or engine-level APIs**  |
| **rules/patterns.md**                              | `runtime.execute(workflow.build())`, `workflow.add_node()`, `LocalRuntime()` | **100% primitive patterns. Zero engine patterns.**       |
| **skills/02-dataflow/dataflow-quickstart.md**      | `WorkflowBuilder()` → `add_node()` → `runtime.execute()`                     | **Teaches primitives as the "30-second quick start"**    |
| **skills/02-dataflow/dataflow-express.md**         | `db.express.create()` etc.                                                   | **EXISTS but is a deep-dive skill, not the quickstart**  |
| **skills/02-dataflow/dataflow-crud-operations.md** | `workflow.add_node("UserCreateNode", ...)`                                   | **Teaches node-level primitives**                        |
| **rules/agents.md** Rule 3                         | "Consult dataflow-specialist for DataFlow work"                              | Correct guidance but specialist also teaches primitives  |
| **Kailash Platform table** in CLAUDE.md            | Lists DataFlow as "Zero-config database operations"                          | **No mention of Express API as the preferred interface** |

### The COC failure mode

This is a textbook **convention drift** (COC Fault Line 2). The SDK evolved to provide engine-level APIs (`db.express`), but the COC artifacts were never updated to reflect this evolution. They still teach the v1 primitive pattern because that's what they were written against.

The hierarchy of influence on Claude's behavior:

1. **CLAUDE.md** (loaded every turn) → teaches primitives ← **THIS IS THE ANCHOR**
2. **rules/patterns.md** (loaded on .py edits) → teaches primitives
3. **skills/02-dataflow/quickstart** (loaded when DataFlow questions arise) → teaches primitives
4. **skills/02-dataflow/express** (loaded only if specifically asked) → teaches engine

The express skill EXISTS but is buried. It's never referenced by CLAUDE.md, never mentioned in patterns.md, and the quickstart teaches the opposite pattern. A developer (or AI) following the COC artifacts would NEVER discover the Express API unless they specifically searched for "performance" or "express."

### What the COC artifacts SHOULD say

**CLAUDE.md "Critical Execution Rules"** should be:

```python
# DataFlow: Use Express API for simple CRUD (23x faster)
user = await db.express.create("User", {"name": "Alice"})
users = await db.express.list("User", {"active": True}, limit=10)

# Only use workflow pattern for multi-node operations
workflow = WorkflowBuilder()
# ... (multi-node logic) ...
results, run_id = runtime.execute(workflow.build())
```

**rules/patterns.md** should have a "DataFlow Express" section BEFORE the workflow section.

**skills/02-dataflow/quickstart** should lead with Express, not workflows.

---

## Primitive Usage in pact-platform (Audit Results)

| Layer       | Files        | Primitive Calls              | Engine Equivalent                                      |
| ----------- | ------------ | ---------------------------- | ------------------------------------------------------ |
| API routers | 8 files      | 38 create/add/execute        | `db.express.create/read/list/update/delete`            |
| Services    | 4 files      | 34 create/add/execute        | `db.express.*` for simple ops; workflow for multi-step |
| Engine      | 3 files      | 11 create/add/execute        | Mixed — some are acceptable (seeding, orchestration)   |
| **Total**   | **15 files** | **~83 primitive call sites** | Most should be express                                 |

Every single API router operation is a single-node CRUD: create one record, read one record, list records, update one record. These are textbook Express API use cases.

---

## Migration Plan

### Phase 1: Switch API routers to Express (8 files, ~38 call sites)

Each router currently does:

```python
wf = db.create_workflow()
wf.add_node("ObjectiveCreateNode", "create", {fields...})
results, _ = db.execute_workflow(wf)
return results["create"]
```

Should become:

```python
result = await db.express.create("AgenticObjective", {fields...})
return result
```

**Blocker**: Express is async-only. API routers are currently sync. Need to make routers async (FastAPI supports both — just add `async def` to handlers).

### Phase 2: Switch services to Express (4 files, ~34 call sites)

Same pattern as routers. Services that do single-operation CRUD should use Express.

### Phase 3: Leave engine layer as-is (3 files, ~11 call sites)

Orchestrator `_record_run()`, seed, and approval bridge use workflows for legitimate reasons (seeding workflows, multi-step orchestration). These can stay as workflow primitives or be migrated later.

### Phase 4: Update COC artifacts

1. **CLAUDE.md**: Add Express pattern to Critical Execution Rules
2. **rules/patterns.md**: Add DataFlow Express section as the DEFAULT pattern
3. **skills/02-dataflow/quickstart**: Lead with Express, not workflows
4. **File kailash-coc-claude-py codify proposal**: Upstream the pattern change

---

## Effort Estimate

| Phase     | Scope                            | Autonomous Sessions |
| --------- | -------------------------------- | ------------------- |
| Phase 0   | DataFlowEngine.builder() init    | Part of Phase 1     |
| Phase 1   | 8 router files → async + express | 1 session           |
| Phase 2   | 4 service files → express        | 1 session           |
| Phase 3   | Leave engine layer as-is         | 0                   |
| Phase 4   | COC artifacts                    | 0.5 session         |
| **Total** |                                  | **~2.5 sessions**   |

---

## Addendum: Engine Facade Layer (from engine audit)

The engine audit revealed an additional layer ABOVE Express that was introduced in kailash v2.2.0:

### DataFlowEngine (facade)

```python
from dataflow import DataFlowEngine

engine = await DataFlowEngine.builder("postgresql://localhost/mydb")
    .slow_query_threshold(0.5)
    .validation_layer(my_validator)
    .classification_policy(policy)
    .validate_on_write(True)
    .build()
```

Adds: field-level validation, data classification with retention policies, query performance monitoring with slow query detection, health checks with pool utilization. The `.dataflow` property gives access to Express and workflow APIs.

**Recommendation for pact**: Use DataFlowEngine as the initialization layer (Phase 0), then Express for CRUD. The validation and classification features align with PACT's governance requirements.

### NexusEngine (facade)

```python
from nexus import NexusEngine, Preset

engine = NexusEngine.builder().preset(Preset.ENTERPRISE).bind("0.0.0.0:443").build()
engine.register("workflow", workflow.build())
engine.start()
```

Enterprise preset gives: CSRF, audit, metrics, error handling, security headers, structured logging, rate limiting (100 req/min), CORS — all via one builder call.

**Recommendation for pact**: NOT applicable — pact's 62+ custom endpoints with governance, WebSocket, and custom middleware exceed Nexus's workflow-registration model. Keep FastAPI.

### Kaizen Delegate (v0.5.0)

```python
from kaizen_agents.delegate import Delegate

delegate = Delegate(model="claude-sonnet-4-6", budget_usd=10.0, tools=["read_file", "bash"])
async for event in delegate.run("analyze this"):
    match event:
        case TextDelta(text=t): print(t, end="")
        case BudgetExhausted(): warn("Budget!")
```

Streaming events, budget tracking, tool search/hydration. This is the SIMPLER alternative to GovernedSupervisor for single-agent tasks.

**Recommendation for pact**: Consider Delegate for simple agent tasks; keep GovernedSupervisor for multi-agent orchestration with PACT governance.

### GovernedSupervisor (v0.5.0)

Already correctly used in pact's `orchestrator.py`. Now has 9 governance subsystems: audit, accountability, budget, cascade, clearance, classifier, dereliction, bypass, vacancy.

**Recommendation for pact**: Already correct. The vacancy and bypass subsystems are now built into the supervisor — may reduce need for custom pact-platform implementations.

### Full Engine Hierarchy (what the COC artifacts SHOULD teach)

```
DataFlowEngine.builder()     ← Phase 0: initialization + validation + classification
    └─ .dataflow.express.*   ← Phase 1-2: simple CRUD (23x faster)
    └─ .dataflow workflows   ← Phase 3: multi-node operations (rare)

NexusEngine.builder()        ← NOT for pact (workflow-only APIs)

Delegate(model=...)          ← Simple agent tasks
GovernedSupervisor(model=...)← Multi-agent orchestration (already used)
```
