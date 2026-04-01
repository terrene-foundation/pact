# Engine API Verification Report — kailash-py v2.2.1

**Date**: 2026-03-30
**Tested against**: kailash 2.2.1, kailash-dataflow 1.2.1, kailash-nexus 1.6.0, kaizen-agents 0.5.0
**Context**: pact-platform (USE repo) evaluating migration from SDK primitives to engine APIs
**Methodology**: All claims verified by running actual code, not code reading

---

## 1. DataFlowEngine

### What it is

`DataFlowEngine` (`dataflow.engine`) is a builder-pattern wrapper around the core `DataFlow` class. It adds field-level validation, data classification with retention policies, query performance monitoring, and health checks.

### Verified API

```python
from dataflow import DataFlowEngine

engine = await DataFlowEngine.builder("sqlite:///app.db").build()

# Builder methods (verified):
# .slow_query_threshold(float)
# .validation_layer(ValidationLayer)
# .classification_policy(DataClassificationPolicy)
# .validate_on_write(bool)
# .config(**kwargs)
# .build() -> DataFlowEngine

# Engine methods (verified):
# .dataflow -> DataFlow (underlying instance)
# .query_engine -> QueryEngine
# .health_check() -> HealthStatus
# .register_model(registry, model)
# .validate_record(instance) -> ValidationResult
# .validate_fields(model_name, fields) -> List[str]
# .classify_field(model_name, field_name) -> str
# .get_retention_days(classification) -> Optional[int]
# .get_model_classification_report(model) -> Dict
# .close()
```

### Express API (accessed via engine.dataflow.express)

```python
db = engine.dataflow

# Verified methods:
# .create(model_name, {fields}) -> dict
# .read(model_name, id) -> dict | None
# .find_one(model_name, {filter}) -> dict | None
# .update(model_name, {filter}, {fields}) -> dict
# .delete(model_name, id) -> dict
# .list(model_name, {filter}, limit=N) -> list[dict]
# .count(model_name, {filter}) -> int
# .upsert(model_name, {fields}) -> dict
# .upsert_advanced(...)
# .bulk_create(model_name, [...]) -> list
# .bulk_update(model_name, {...}) -> dict
# .bulk_delete(model_name, {...}) -> dict
# .clear_cache()
# .get_cache_stats() -> dict
# .get_performance_stats() -> dict
# .warm_schema_cache()
# .reset_stats()
```

### End-to-end verification

```
# Tested: DataFlowEngine + Express with string IDs (pact's pattern)
# Model: id: str, name: str (explicit string primary key)

Created: {'id': 'item-xyz', 'name': 'Widget', 'rows_affected': 1}  # OK
List:    [{'id': 'item-xyz', 'name': 'Widget', ...}]               # OK
Read:    {'id': 'item-xyz', 'name': 'Widget', 'found': True}       # OK
Count:   1                                                           # OK
```

### Issues found

**Issue 1: Express create does NOT return auto-generated ID**

When using default `@db.model` (auto-increment integer ID), `express.create()` returns `{'title': 'Test', 'rows_affected': 1}` — no `id` field. The auto-generated ID is only visible via a subsequent `list()` or `find_one()`.

**Workaround**: Use explicit `id: str` in models and pass the ID at creation time. This is already pact's pattern (`uuid4().hex[:12]`).

**Recommendation for SDK**: `express.create()` should return the full record including auto-generated fields (id, created_at, updated_at). This matches ORM conventions (Django's `save()`, SQLAlchemy's `flush()`) and eliminates the need for a follow-up query.

**Issue 2: SQLite :memory: fails in async context**

`DataFlowEngine.builder(':memory:').build()` in async context fails with migration lock errors due to SQLite thread-affinity:

```
Failed to create model registry table: AsyncLocalRuntime.execute() called from async context.
Error acquiring lock for schema :memory:: no such table: dataflow_migration_locks
```

**Workaround**: Use file-based SQLite (`sqlite:///./test.db`) for async tests.

**Recommendation for SDK**: Either document this limitation prominently in the express/engine quickstart, or detect `:memory:` in async context and auto-switch to a temp file with cleanup.

**Issue 3: Express is async-only**

All Express methods are `async`. There is no sync Express API. USE repos with sync FastAPI endpoints (like pact-platform) must convert handlers to `async def` before using Express.

**Recommendation for SDK**: Consider a `db.express_sync.*` companion or document that sync-to-async bridging requires `asyncio.run()` or converting handlers to async.

**Issue 4: Noisy startup logging**

`DataFlow(':memory:')` and `DataFlowEngine.builder()` produce multiple warnings even on successful initialization:

```
Using SQLite :memory: database for testing. Production requires PostgreSQL.
Could not validate pool config (probe failed). Configured: pool_size=5 + max_overflow=2 x 1 workers = 7 connections
DDL execution failed: no such table: main.dataflow_migration_history
DDL execution failed: no such table: main.dataflow_migration_history
Failed to create index: no such table: main.dataflow_migration_history
```

These are expected on first run (before migration tables are created) but look like errors. Users cannot distinguish "expected first-run noise" from "actual failure."

**Recommendation for SDK**: Suppress expected first-run migration messages or use DEBUG level instead of WARNING. Add a `quiet=True` builder option for test environments.

**Issue 5: `__del__` import errors on Python shutdown**

Multiple `__del__` finalizers raise `ImportError: sys.meta_path is None, Python is likely shutting down` when the process exits. These are harmless but noisy:

```
Exception ignored in: <function LocalRuntime.__del__ at 0x10bd76ac0>
Exception ignored in: <function ModelRegistry.__del__ at 0x10e4cd8a0>
Exception ignored in: <function AutoMigrationSystem.__del__ at 0x10e06b920>
Exception ignored in: <function ConnectionManagerAdapter.__del__ at 0x10e53b4c0>
```

**Recommendation for SDK**: Guard `__del__` methods with `if sys is not None and sys.meta_path is not None` checks, or suppress `ImportError` in finalizers.

---

## 2. NexusEngine

### What it is

`NexusEngine` (`nexus.engine`) is a builder-pattern wrapper around the core `Nexus` class. It provides middleware presets (NONE, SAAS, ENTERPRISE) with built-in CSRF, audit, metrics, security headers, structured logging, rate limiting, and CORS.

### Verified API

```python
from nexus import NexusEngine, Preset

# Import and builder verified:
engine = NexusEngine.builder()        # Returns NexusEngineBuilder
engine.preset(Preset.SAAS)            # Set middleware stack
engine.bind("0.0.0.0:8080")          # Set listen address
engine.config(cors_origins=[...])     # Additional kwargs
built = engine.build()                # Returns NexusEngine

# Engine methods:
# .register(name, workflow)
# .start()
# .start_async()
# .close()
# .nexus -> Nexus (underlying instance)
```

### Assessment for pact-platform

**NOT suitable.** Nexus is designed for exposing Kailash workflows as multi-channel APIs (REST + CLI + MCP from one workflow registration). Pact-platform has 62+ custom endpoints with complex business logic, governance engine integration, WebSocket authentication, and custom middleware. These don't map to Nexus's workflow-registration model.

**Recommendation**: Keep FastAPI for pact-platform. Nexus is the right choice for simpler workflow-based APIs (e.g., a data pipeline that needs REST + CLI exposure).

---

## 3. Kaizen Engines (Delegate + GovernedSupervisor)

### What exists

Two engine-level entry points in `kaizen-agents` v0.5.0:

**Delegate** — single-agent autonomous execution with streaming events:

```python
from kaizen_agents.delegate import Delegate

delegate = Delegate(model="claude-sonnet-4-6", budget_usd=10.0, tools=[...])
async for event in delegate.run("objective"):
    match event:
        case TextDelta(text=t): ...
        case ToolCallStart(name=n): ...
        case BudgetExhausted(): ...
```

**GovernedSupervisor** — multi-agent orchestration with PACT governance:

```python
from kaizen_agents import GovernedSupervisor

supervisor = GovernedSupervisor(
    model="claude-sonnet-4-6",
    budget_usd=25.0,
    data_clearance="restricted",
    max_children=10,
    max_depth=5,
)
result = await supervisor.run(objective="...", execute_node=delegate_fn)
```

### Assessment for pact-platform

**GovernedSupervisor already correctly used** in `pact_platform/engine/orchestrator.py`. No migration needed.

**Delegate** could simplify single-agent tasks but is not currently needed — pact uses GovernedSupervisor for all agent execution.

---

## 4. COC Artifact Gap — Root Cause of Primitive Usage

### The problem

Pact-platform has **83 DataFlow primitive call sites** across 15 files — all `db.create_workflow()` / `db.add_node()` / `db.execute_workflow()` chains for simple single-record CRUD. Every one of these should be an Express call.

### Why this happened

The COC artifacts (the institutional knowledge that guides agent behavior) teach ONLY primitives:

| Artifact (loaded when)                                      | What it teaches                                        | Express mentioned? |
| ----------------------------------------------------------- | ------------------------------------------------------ | ------------------ |
| **CLAUDE.md** "Critical Execution Rules" (every turn)       | `runtime.execute(workflow.build())`                    | No                 |
| **rules/patterns.md** (every .py edit)                      | `workflow.add_node()`, `LocalRuntime()`                | No                 |
| **skills/02-dataflow/quickstart** (DataFlow questions)      | `WorkflowBuilder` → `add_node()` → `runtime.execute()` | No                 |
| **skills/02-dataflow/express** (only if specifically asked) | `db.express.create()` etc.                             | Yes (but buried)   |

The Express skill exists but is never referenced by the three artifacts above it in the loading hierarchy. An agent following COC guidance reaches for primitives every time.

### Recommendation

1. **CLAUDE.md "Critical Execution Rules"** — Add DataFlow Express as the DEFAULT pattern, keep workflow as the multi-node fallback
2. **rules/patterns.md** — Add "DataFlow Express" section BEFORE the workflow section
3. **skills/02-dataflow/quickstart** — Lead with Express, not WorkflowBuilder
4. **skills/02-dataflow/dataflow-crud-operations.md** — Show Express for single-record ops, workflow only for multi-record transactions

This is convention drift (COC Fault Line 2) — the SDK evolved engine APIs but the COC artifacts weren't updated. Every downstream USE repo inherits the same primitive-first pattern until the COC template is fixed.

---

## 5. Migration Readiness Summary

| Component              | Engine                     | Ready?             | Blockers                                      |
| ---------------------- | -------------------------- | ------------------ | --------------------------------------------- |
| **DataFlowEngine**     | `DataFlowEngine.builder()` | Yes                | None — init wrapper only                      |
| **Express CRUD**       | `db.express.*`             | Yes (with caveats) | Async-only; `create()` doesn't return auto-ID |
| **NexusEngine**        | `NexusEngine.builder()`    | N/A                | Not suitable for pact's custom API layer      |
| **Delegate**           | `Delegate(model=...)`      | Available          | Not currently needed                          |
| **GovernedSupervisor** | `GovernedSupervisor(...)`  | Already used       | None                                          |

### Recommended migration order for pact-platform

1. **Phase 0**: Switch DataFlow initialization to `DataFlowEngine.builder()` (adds validation, classification, health checks)
2. **Phase 1**: Convert 8 API router files to `async def` + `db.express.*` (~38 call sites)
3. **Phase 2**: Convert 4 service files to Express (~34 call sites)
4. **Phase 3**: Keep engine/orchestrator/seed files on workflow primitives (legitimate multi-step use)
5. **Phase 4**: Update COC artifacts to teach engine-first patterns

---

## 6. Issues to File on kailash-py

| #   | Title                                                                        | Severity    | Description                                                                                                                                                                       |
| --- | ---------------------------------------------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `express.create()` should return full record including auto-generated fields | Medium      | Currently returns `{fields..., rows_affected: 1}` without auto-generated `id`, `created_at`, `updated_at`. Forces follow-up query.                                                |
| 2   | SQLite `:memory:` fails in async context with migration lock errors          | Medium      | `DataFlowEngine.builder(':memory:').build()` in async fails. File-based SQLite works. Document or auto-detect.                                                                    |
| 3   | Noisy startup logging on first run (DDL/migration table warnings)            | Low         | Expected first-run messages logged at WARNING level look like errors. Use DEBUG or add `quiet` option.                                                                            |
| 4   | `__del__` finalizers raise ImportError on Python shutdown                    | Low         | Multiple classes (`LocalRuntime`, `ModelRegistry`, `AutoMigrationSystem`, `ConnectionManagerAdapter`) have `__del__` that fails when `sys.meta_path` is None. Harmless but noisy. |
| 5   | No sync Express API                                                          | Enhancement | All Express methods are async. USE repos with sync handlers need `asyncio.run()` bridging or handler conversion. Consider `express_sync` companion.                               |
| 6   | COC artifacts teach primitives, not engines (convention drift)               | COC         | CLAUDE.md, patterns.md, and quickstart all teach `WorkflowBuilder` as the primary pattern. Express skill exists but is not referenced by any higher-priority artifact.            |
