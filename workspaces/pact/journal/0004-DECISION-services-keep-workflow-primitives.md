---
type: DECISION
date: 2026-03-31
project: pact
topic: Services keep workflow primitives — Express migration Phase 2 cancelled
phase: todos
tags: [express, dataflow, services, migration]
---

# Services Keep Workflow Primitives

## Decision

Cancel Express migration Phase 2 (services). All 4 DataFlow-using services correctly use
workflow primitives for multi-step operations. Express is only appropriate for single-operation
CRUD (routers), not for services with read-before-write, cascading updates, or cross-model
atomicity.

## Alternatives considered

1. **Migrate everything to Express** — rejected. Services need multi-step transaction semantics
   that Express doesn't provide (no order_by, no atomic read-modify-write, no multi-node).
2. **Hybrid (Express for simple ops, workflow for complex)** — rejected for services.
   The simple ops in services are interleaved with complex ones — splitting would make the
   code harder to follow for no performance benefit.
3. **Keep workflow primitives** — chosen. Services are the correct use case for workflow
   primitives per the Engine-over-Primitives 3-layer model.

## Consequences

- Phase 1 (routers) is complete: 38 call sites migrated to Express
- Phase 2 (services) is cancelled: 38 call sites stay on workflow primitives
- Phase 3 (engine) was already "leave as-is" — correct for seeding and orchestration
- Total migration: 38/83 call sites (46%) — the right 46%
