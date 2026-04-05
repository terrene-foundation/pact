---
type: DECISION
date: 2026-04-02
created_at: 2026-04-02T10:30:00+08:00
author: co-authored
session_id: pact-express-migration
session_turn: 15
project: pact
topic: Migrate all service-layer CRUD from workflow primitives to DataFlow Express sync API
phase: implement
tags: [dataflow, express, migration, engine-first, performance]
---

# DECISION: Migrate service layer from workflow primitives to DataFlow Express

## Context

Seven production files in `src/pact_platform/` (3 engine, 4 services) used the verbose
`db.create_workflow()` → `db.add_node()` → `db.execute_workflow()` pattern for every
single-record CRUD operation — 25+ call sites total. Each operation required 5-8 lines
of boilerplate for what Express handles in 1-2 lines. The API routers had already been
migrated to async `db.express.*` in the RT29 session; the services and engine layer
lagged behind.

## Decision

Migrate all 7 files to `db.express_sync.*` (the synchronous variant of DataFlow Express).
Use `express_sync.create/read/update/list` directly — no workflow construction.

### Files migrated

| File                              | Call sites                          | Layer    |
| --------------------------------- | ----------------------------------- | -------- |
| `engine/seed.py`                  | 2 (list + 13 creates via helper)    | Engine   |
| `engine/approval_bridge.py`       | 4 (create, approve, reject, list)   | Engine   |
| `engine/orchestrator.py`          | 1 (record_run)                      | Engine   |
| `services/completion_workflow.py` | 11 (read, update, create, finalize) | Services |
| `services/cost_tracking.py`       | 4 (create, list in loops, read)     | Services |
| `services/approval_queue.py`      | 6 (create, read, update, list)      | Services |
| `services/request_router.py`      | 3 (create, list, update)            | Services |

### Express return type conventions

- `express_sync.list()` returns `list[dict]` directly (not `{"records": [...]}`)
- `express_sync.read()` returns `dict | None` (not `{"found": True, ...}`)
- `express_sync.create()` returns the created dict
- `express_sync.update()` returns the updated dict

Four test files were updated to replace `MockDataFlow` (which tracked workflow calls)
with `MockExpressSync` (which tracks Express API calls with an in-memory store).

## Alternatives considered

1. **Keep primitives** — functional but verbose, violates `rules/framework-first.md` Engine-First rule.
2. **Migrate to async `db.express.*`** — would require converting all service methods to `async def`. Deferred; the sync variant works for the current call patterns.
3. **Mix Express (simple) + primitives (complex)** — rejected; all current call sites are single-operation CRUD with no multi-step transactions.

## Consequences

- Zero `create_workflow`/`add_node`/`execute_workflow` in production code
- ~400 lines of boilerplate removed
- Express is 23x faster than workflow primitives for single-operation CRUD
- Future async migration (services → `async def`) is now simpler since Express API is identical in both sync and async

## For Discussion

- Given that Express `list()` returns `list[dict]` while the old workflow API returned `{"records": [...]}`, what happens if a future DataFlow version changes the Express return shape? The tests would catch it, but should we add an explicit integration test against real DataFlow Express to guard the contract?
- If the services had been async from the start, would the migration have been unnecessary (since the routers already use async Express)?
- What is the threshold for when a multi-step operation should use workflow primitives instead of multiple Express calls? The cost_tracking loop (list requests, then list runs per request) could potentially be a single workflow with connected nodes.
