---
type: GAP
date: 2026-04-03
created_at: 2026-04-03T21:30:00+08:00
author: agent
session_turn: 18
project: pact
topic: PactEngine (L1) missing 13 features that L3 SupervisorOrchestrator implements
phase: redteam
tags: [pact-engine, upstream, L1-gaps, kailash-py-232, architecture]
---

# PactEngine L1 Deficiency Analysis

## Context

PactEngine (L1, kailash-pact 0.6.0) is a dual-plane facade bundling GovernanceEngine + GovernedSupervisor + CostTracker + EventBus. The L3 SupervisorOrchestrator in pact-platform implements 13 additional features that any vertical (astra, arbor, etc.) would need to rebuild independently.

## Gap Summary

### Tier 1 — Security (4 items)

| #   | Gap                                              | Risk                                                     |
| --- | ------------------------------------------------ | -------------------------------------------------------- |
| 1   | No NaN-guard on `verify_action()` context values | NaN in cost context bypasses all budget checks           |
| 2   | No `create_verifier()` read-only wrapper         | Agents with engine reference can self-modify governance  |
| 3   | Lazy supervisor creation race condition          | Two concurrent `submit()` calls double-create supervisor |
| 4   | No input validation in `submit()`                | Empty role/objective accepted silently                   |

### Tier 2 — Architecture (6 items)

| #   | Gap                                            | Impact                                                      |
| --- | ---------------------------------------------- | ----------------------------------------------------------- |
| 5   | No enforcement modes (enforce/shadow/disabled) | Every vertical rebuilds shadow mode from scratch            |
| 6   | No envelope-to-execution adapter               | Every vertical rebuilds dimension-to-param mapping          |
| 7   | No per-node governance callback protocol       | Single-action verify_action, no plan-level enforcement      |
| 8   | No HELD action callback                        | HELD verdict treated same as BLOCKED (no approval workflow) |
| 9   | No `budget_allocated` in WorkResult            | Can't track "given vs spent" budget distinction             |
| 10  | No `audit_trail` in WorkResult                 | No governance transparency in execution results             |

### Tier 3 — Operational (3 items)

| #   | Gap                                      | Impact                                              |
| --- | ---------------------------------------- | --------------------------------------------------- |
| 11  | No degenerate envelope detection at init | Silently operates under over-restrictive envelopes  |
| 12  | No D/T/R assessor validator factory      | Every vertical rebuilds posture independence checks |
| 13  | No shadow evaluation path                | No progressive rollout support                      |

## Upstream Issue

Filed as [terrene-foundation/kailash-py#232](https://github.com/terrene-foundation/kailash-py/issues/232).

## Consequence

Until these gaps are resolved, pact-platform's SupervisorOrchestrator remains the production execution engine. PactEngine is suitable for simple scripts and demos but not for platform-grade governed execution. Verticals importing `pact` directly would need to rebuild these features.

## For Discussion

1. Should Tier 1 security items (NaN-guard, verifier wrapper, race condition) be treated as bugfixes rather than features, given they're security invariants specified in pact-governance.md?
2. If enforcement modes are upstreamed, should PactEngine's `submit()` accept `enforcement_mode` per-call, or should it be set at construction time like in L3's `PlatformSettings` singleton?
3. The per-node governance callback (#7) fundamentally changes PactEngine from a "submit and forget" API to a "supervised execution with governance callbacks" engine — does this scope expansion require a new engine class (e.g., `GovernedPactEngine`) rather than modifying PactEngine?
