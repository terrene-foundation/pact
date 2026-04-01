---
type: DISCOVERY
date: 2026-03-30
project: pact
topic: Kailash SDK three-layer API hierarchy verified by execution
phase: analyze
tags: [dataflow, express, engine, api-layers, verified]
---

# Kailash SDK Three-Layer API Hierarchy

Verified by actual code execution (not code reading):

```
DataFlowEngine.builder(url)     ← Enterprise wrapper (validation, classification, health)
    └─ .dataflow                ← Core DataFlow instance
        ├─ .express.*           ← Async CRUD (23x faster, string IDs work)
        └─ .create_workflow()   ← Multi-node workflows (sync, for orchestration)
```

Express `create()` does NOT return auto-generated ID — only explicitly passed fields + `rows_affected`. Pact's `id: str` models with explicit UUIDs work correctly.

Express is async-only. Pact's sync routers need `async def` conversion.

`NexusEngine.builder()` exists but is NOT suitable for pact (workflow-registration model, not custom endpoints).
