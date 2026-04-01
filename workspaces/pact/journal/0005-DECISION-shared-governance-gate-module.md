---
type: DECISION
date: 2026-03-31
created_at: 2026-03-31T18:30:00+08:00
author: co-authored
session_turn: 15
project: pact
topic: Shared governance gate module for API routers
phase: implement
tags: [governance, security, architecture, api]
---

# Shared Governance Gate Module

## Decision

Created `src/pact_platform/use/api/governance.py` as the single shared governance gate for all API routers, rather than duplicating GovernanceEngine wiring in each router.

## Alternatives Considered

1. **Inline governance in each router** — Each mutation endpoint imports and calls GovernanceEngine directly. Rejected: massive duplication, inconsistent verdict handling, easy to miss endpoints.
2. **FastAPI middleware** — Run governance on every request via middleware. Rejected: governance needs action-specific context (cost, resource type) that middleware can't provide. Also blocks read-only endpoints unnecessarily.
3. **Shared module with gateway function** (chosen) — Single `governance_gate(org_address, action, context)` function. Routers call it at the right point with action-specific context. Centralized verdict→HTTP mapping.

## Rationale

- Rules/governance.md Rule 11 requires ALL governance decisions route through verify_action() — a single module ensures consistency.
- Verdict-to-HTTP mapping (BLOCKED→403, HELD→202+decision record, AUTO_APPROVED→proceed) is identical across all endpoints.
- Dev-mode passthrough and engine lifecycle (set/freeze) are module concerns, not router concerns.
- The org.py router already had its own `_engine` reference. The shared module subsumes it while keeping org.py's deploy lock.

## Consequences

- All mutation endpoints now have governance gates (create, update, cancel, pause/resume, add/finalize).
- Multi-hop chain resolution (session→request→objective→org_address) fails closed when governance is active but chain is broken.
- Dev-mode flag is frozen after first set to prevent runtime bypass.

## For Discussion

- If the governance chain resolution (3-hop for sessions/reviews) becomes a performance concern, should we denormalize org_address onto request/session records?
- If DataFlow Express adds conditional update support (`UPDATE WHERE version = ?`), the TOCTOU defense in decisions.py should be upgraded from double-read to atomic CAS.
- What is the boundary between "governance-gated" and "operational" mutations? Currently all mutations are gated; should read-back-only operations like `get_pool_capacity` ever be governed?
