# Phase 4 Implementation Plan

**Date**: 2026-03-14
**Input**: Phase 4 analysis (05-phase4-analysis.md)
**Milestones**: M31–M37

---

## Milestone Overview

| Milestone | Name                        | Tasks | Dependencies    |
| --------- | --------------------------- | ----- | --------------- |
| M31       | Bridge Trust Foundation     | 5     | None            |
| M32       | Constraint Intersection     | 4     | M31             |
| M33       | Cross-Team Execution        | 5     | M31, M32        |
| M34       | Bridge Lifecycle Operations | 4     | M31             |
| M35       | Security Hardening          | 4     | None (parallel) |
| M36       | Bridge API + Dashboard      | 5     | M33, M34        |
| M37       | Red Team (RT12)             | 2     | All             |

**Total**: 29 tasks

---

## M31 — Bridge Trust Foundation

Wire Cross-Functional Bridges into the EATP trust layer.

| Task | What                                                                                                                                                                                                                     | Where                                          |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| 3101 | **BridgeDelegation record** — new dataclass wrapping DelegationRecord with bridge context (bridge_id, source_team, target_team, bridge_type). Create/validate at bridge activation.                                      | `trust/bridge_trust.py`                        |
| 3102 | **Bridge trust root** — bilateral trust establishment. Both teams' authorities sign the bridge agreement, creating a Bridge Trust Record (pair of linked Delegation Records). Integrate with dual-approval in bridge.py. | `trust/bridge_trust.py`, `workspace/bridge.py` |
| 3103 | **Cross-team posture resolution** — `effective_posture(posture_a, posture_b)` returns min(). Bridge verification applies effective posture to determine verification gradient level.                                     | `trust/bridge_posture.py`                      |
| 3104 | **Cross-team audit anchoring** — dual-anchored audit records for bridge actions. Source-side anchor created first (commit point), target-side best-effort. Cross-team reference hash in both.                            | `audit/bridge_audit.py`                        |
| 3105 | **Bridge trust tests** — TDD: tests for bridge delegation, trust root, posture resolution, audit anchoring.                                                                                                              | `tests/unit/trust/test_bridge_trust.py`        |

## M32 — Constraint Intersection

Compute effective constraint envelopes for cross-team actions.

| Task | What                                                                                                                                                                                                                                                                                                                                             | Where                                                           |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| 3201 | **Envelope intersection computation** — `compute_bridge_envelope(source, bridge, target)` returns the most restrictive combination across all five CARE dimensions. Financial: min(). Operational: intersection of allowed, union of blocked. Temporal: overlapping window. Data Access: intersection of paths. Communication: most restrictive. | `constraint/bridge_envelope.py`                                 |
| 3202 | **Information sharing modes** — per-field sharing rules: auto-share, request-share, never-share. Enum + model + enforcement in bridge access control.                                                                                                                                                                                            | `workspace/bridge.py` (extend), `constraint/bridge_envelope.py` |
| 3203 | **Bridge monotonic tightening validation** — verify that bridge constraint envelope is no wider than either team's envelope. Builds on existing `is_tighter_than()`.                                                                                                                                                                             | `constraint/bridge_envelope.py`                                 |
| 3204 | **Constraint intersection tests** — TDD: all five dimensions, edge cases (None financial, overnight temporal windows, path intersection).                                                                                                                                                                                                        | `tests/unit/constraint/test_bridge_envelope.py`                 |

## M33 — Cross-Team Execution

Wire bridge trust into the execution pipeline.

| Task | What                                                                                                                                                                                                                                                                | Where                                           |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| 3301 | **Bridge verification pipeline** — integrate bridge checks into ExecutionRuntime: Is bridge ACTIVE? Is action type allowed by bridge? Compute effective envelope. Apply effective posture. Route via verification gradient.                                         | `execution/runtime.py` (extend)                 |
| 3302 | **Bridge-level revocation** — revoke specific delegation capabilities granted through a bridge without revoking the agents themselves. When a bridge is suspended/closed, revoke all bridge delegations. When an agent is revoked, revoke their bridge delegations. | `trust/revocation.py` (extend)                  |
| 3303 | **Ad-hoc bridge management** — auto-creation of ad-hoc bridges for one-off cross-team requests within constraints. Pattern detection: if ad-hoc bridges between the same teams exceed threshold, suggest standing bridge.                                           | `workspace/bridge.py` (extend)                  |
| 3304 | **KaizenBridge cross-team routing** — extend KaizenBridge to route tasks through bridges when the target agent is on a different team. Apply bridge verification before LLM execution.                                                                              | `execution/kaizen_bridge.py` (extend)           |
| 3305 | **Cross-team execution tests** — TDD: bridge verification pipeline, bridge revocation, ad-hoc management, cross-team routing.                                                                                                                                       | `tests/unit/execution/test_bridge_execution.py` |

## M34 — Bridge Lifecycle Operations

Complete the bridge lifecycle with EATP integration.

| Task | What                                                                                                                                                                                                       | Where                                                   |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| 3401 | **Bridge approval flow** — when both sides approve (NEGOTIATING → ACTIVE), create EATP trust records. On suspension, invalidate bridge delegations. On closure, revoke all bridge trust and archive audit. | `workspace/bridge.py` (extend), `trust/bridge_trust.py` |
| 3402 | **Bridge modification via replacement** — "modify" flow: suspend current bridge, create new bridge with updated terms, transfer standing status. Preserves audit trail of the original.                    | `workspace/bridge.py` (extend)                          |
| 3403 | **Bridge review cadence** — standing bridges flagged for quarterly review. Scoped bridges flagged at milestones. Ad-hoc bridges reviewed in aggregate.                                                     | `workspace/bridge.py` (extend)                          |
| 3404 | **Bridge lifecycle tests** — TDD: approval flow with trust records, modification via replacement, review cadence.                                                                                          | `tests/unit/workspace/test_bridge_lifecycle_trust.py`   |

## M35 — Security Hardening (RT11 Carry-Forward)

Resolve deferred security findings from Phase 3.

| Task | What                                                                                                                                                                                                                                  | Where                                |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| 3501 | **Prompt injection hardening** — add system prompt to KaizenBridge that separates trusted instructions from untrusted task.action. System prompt establishes role, constraints, and output format. User content is clearly delimited. | `execution/kaizen_bridge.py`         |
| 3502 | **Posture enforcer keyword normalization** — normalize action strings before keyword matching: casefold(), unicodedata.normalize('NFKD'), strip non-alphanumeric. Prevents CamelCase, hyphenation, and homoglyph bypass.              | `execution/posture_enforcer.py`      |
| 3503 | **API rate limiting** — add slowapi middleware to FastAPI. Per-token rate limits: 60/min for GET, 10/min for POST. Configurable via env.                                                                                              | `api/server.py`, `api/rate_limit.py` |
| 3504 | **Security response headers** — add middleware for CSP, X-Frame-Options (DENY), X-Content-Type-Options (nosniff), Referrer-Policy (strict-origin-when-cross-origin), Permissions-Policy.                                              | `api/server.py`                      |

## M36 — Bridge API + Dashboard

Bridge management endpoints and dashboard views.

| Task | What                                                                                                                                                                                               | Where                                 |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| 3601 | **Bridge CRUD endpoints** — POST /bridges (create), GET /bridges/{id} (detail), PUT /bridges/{id}/approve (approve side), POST /bridges/{id}/suspend, POST /bridges/{id}/close. All authenticated. | `api/server.py`, `api/endpoints.py`   |
| 3602 | **Bridge audit endpoint** — GET /bridges/{id}/audit (bridge-specific audit trail). Shows all cross-team actions through this bridge.                                                               | `api/endpoints.py`                    |
| 3603 | **Bridge management dashboard** — extend /bridges page: bridge list with lifecycle badges, bridge detail with constraint intersection visualization, approval flow UI.                             | `apps/web/app/bridges/`               |
| 3604 | **Bridge creation wizard** — multi-step form: select teams, choose bridge type, define constraints, set information sharing modes, submit for bilateral approval.                                  | `apps/web/app/bridges/create/`        |
| 3605 | **Bridge dashboard tests** — API client tests for bridge CRUD, component tests for bridge management UI.                                                                                           | `apps/web/__tests__/bridge-*.test.ts` |

## M37 — Red Team (RT12)

Final validation of Phase 4.

| Task | What                                                                                                                                                                                                                | Where                               |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| 3701 | **RT12 security + compliance audit** — full red team: bridge trust integrity, constraint intersection correctness, cross-team audit completeness, information sharing enforcement, security hardening verification. | `04-validate/rt12-phase4-report.md` |
| 3702 | **RT12 convergence report** — trend analysis RT1–RT12, subsystem confidence, accepted risks, sign-off checklist.                                                                                                    | `04-validate/rt12-phase4-report.md` |

---

## Parallelism Strategy

```
M31 (Bridge Trust) ──→ M32 (Constraint) ──→ M33 (Execution) ──→ M36 (API+Dashboard)
                                              ↑                      ↑
M34 (Lifecycle) ─────────────────────────────┘                      │
                                                                     │
M35 (Security) ─────────────────────────────────────────────────────┘
                                                                     ↓
                                                                  M37 (RT12)
```

- M31 and M34 can run in parallel (bridge trust + bridge lifecycle)
- M35 is fully independent (security hardening)
- M32 depends on M31 (needs bridge delegation records)
- M33 depends on M31 + M32 (needs trust foundation + constraint intersection)
- M36 depends on M33 + M34 (needs execution pipeline + lifecycle operations)
- M37 depends on everything
