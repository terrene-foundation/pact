---
type: GAP
date: 2026-04-03
created_at: 2026-04-03T22:50:00+08:00
author: co-authored
session_turn: 1
project: pact
topic: RT31 architectural red team reveals PactEngine (L1) has 12 gaps vs SupervisorOrchestrator (L3)
phase: redteam
tags:
  [
    pact-engine,
    L1-L3-gap,
    architecture,
    red-team,
    governance,
    upstream,
    kailash-pact-0.6.0,
  ]
---

# RT31: PactEngine L1 Architectural Red Team

## Context

PactEngine (kailash-pact 0.6.0) is the L1 dual-plane facade that bridges GovernanceEngine (Trust Plane) with GovernedSupervisor (Execution Plane). SupervisorOrchestrator (pact-platform L3) is the production execution pipeline. This analysis compared the two source files line-by-line to identify what L3 had to build that L1 should have provided.

The user provided a detailed feature comparison as input; the agent performed source-level verification against the actual installed kailash-pact 0.6.0 code and the L3 orchestrator plus all its dependencies (delegate, adapter, bridge, settings, posture assessor -- 1,490 lines of L3 code total).

## Findings

12 gaps identified. 9 should be upstreamed to L1. 3 are correctly L3-only.

### Critical (2)

1. **Single-gate governance** -- PactEngine calls `verify_action(role, "submit", context)` once. The action is always "submit". After that gate, the supervisor executes unlimited actions with zero governance checks. Every operational constraint in the envelope (allowed_actions, rate limits) is bypassed during execution. L3 solves this with GovernedDelegate which calls `verify_action()` on every node with the real action name.

2. **No NaN-guard on supervisor results** -- `supervisor_result.budget_consumed` flows into CostTracker without `math.isfinite()` validation. While current code accidentally avoids NaN poisoning (the `cost_usd > 0` comparison skips NaN), this is not intentional and would break on any refactoring. Per pact-governance.md Rule 6, all numeric values crossing trust boundaries must be explicitly validated.

### High (5)

3. **No envelope dimension mapping** -- PactEngine never calls `compute_envelope()`. It passes through the constructor's raw budget and clearance string. The five constraint dimensions (Financial, Operational, Temporal, Data Access, Communication) are never resolved or mapped to supervisor parameters. Tools list, timeout, delegation depth, and rate limits are all ignored.

4. **Stale budget from lazy supervisor** -- `_get_or_create_supervisor()` creates a singleton supervisor with the budget at first-call time. Subsequent calls reuse the same supervisor with the original budget, not the current remaining budget. Also has a race condition under concurrent access (no locking on lazy init).

5. **No HELD verdict handling** -- HELD and BLOCKED are both treated as `success=False`. No distinction, no approval queue, no human review path. HELD verdicts (soft limits requiring judgment) become hard blocks.

6. **No enforcement modes** -- Always enforce. No shadow mode for progressive rollout, no disabled mode for emergencies. L3 provides enforce/shadow/disabled with PACT_ALLOW_DISABLED_MODE safety guard.

7. **No read-only verifier wrapper** -- `engine.governance` property returns the mutable GovernanceEngine with a docstring warning. No code-level enforcement. L3's GovernedDelegate uses a `_VerifierWrapper` with `__slots__` that exposes only `verify_action()`.

### Medium (3)

8. **No persistent run records** -- WorkResult is returned and forgotten. No audit trail persistence. (Correctly L3 -- requires database dependency, but L1 should provide a persistence callback hook.)

9. **No degenerate envelope detection** -- Envelopes with zero budget and empty tools are silently accepted. L3 checks at init and warns per-request.

10. **No input validation** -- Empty role and objective strings pass through to governance engine without validation.

### Low (2)

11. **In-memory EventBus vs streaming** -- L1's bounded deque is correct for a library. L3 bridges to SSE/WebSocket. Correctly L3-only.

12. **No posture assessment wiring** -- Platform operational policy. L1 provides Address primitives. Correctly L3-only.

## Consequence

Until gaps 1-7 are resolved, PactEngine is suitable for demos and scripts but not for governed production execution. Any vertical importing kailash-pact directly would need to rebuild approximately 1,000 lines of governance wiring that L3's SupervisorOrchestrator provides.

The 9 upstream-worthy gaps should be filed as a single umbrella issue on terrene-foundation/kailash-py, extending the existing issue #232 from journal entry 0015.

## Full Report

`workspaces/pact/04-validate/rt31-pact-engine-gap-analysis.md`

## For Discussion

1. Gap #1 (single-gate governance) means that PactEngine's `allowed_actions` envelope constraint is effectively dead code during execution -- verified by tracing the action="submit" string through verify_action(). If a vertical discovered this in production (an agent performing a "deploy" action that should have been blocked by `allowed_actions: ["read"]`), how would they diagnose the root cause given that the submit-time governance check passed?

2. If enforcement modes (Gap #5) were upstreamed, should PactEngine's shadow mode persist audit records to the EventBus (L1 boundary) or require a callback for external persistence? The L3 \_ShadowDelegate writes to the audit_chain directly, but L1 has no audit_chain -- only EventBus. Would shadow verdicts on the EventBus be sufficient for shadow-to-enforce transition analysis?

3. The stale budget gap (#4) and the single-gate gap (#1) compound: even if per-node governance were added, the cached supervisor would still carry the wrong budget. Should the fix for #3 (per-request supervisor) be prerequisite for #1 (per-node governance), or can they be addressed independently?
