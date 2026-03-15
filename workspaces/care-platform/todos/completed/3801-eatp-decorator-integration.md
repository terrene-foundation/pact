# 3801: EATP Decorator Integration ✓

**Milestone**: 8 — EATP SDK Integration (Tier 1)
**Item**: 1.1 — CONSUME, NOT BUILD
**Status**: COMPLETED
**Completed**: 2026-03-15

## What Was Built

Created `care_platform/trust/decorators.py` with CARE wrappers around EATP SDK enforce operations (VERIFY, AUDIT, shadow check). Key design decision: instead of creating EATP decorator instances per-call (wasteful since EATP decorators take fixed `agent_id` at decoration time), the CARE wrappers call `ops.verify()`, `ops.audit()`, and `shadow.check()` directly — same pipeline, dynamic `agent_id` extraction from function arguments.

### Components

1. **`CareTrustOpsProvider`** — Lazily retrieves `TrustOperations` from `EATPBridge._ensure_initialized()`
2. **`@care_verified(action, provider, agent_id_param="agent_id")`** — Pre-execution VERIFY + StrictEnforcer enforcement
3. **`@care_audited(provider, agent_id_param="agent_id")`** — Post-execution AUDIT anchor creation
4. **`@care_shadow(action, provider, agent_id_param="agent_id")`** — Non-blocking shadow VERIFY with optional CARE ShadowEnforcer forwarding
5. **Migration path** — Documented in module docstring: shadow → audited → verified

### Key Design Decisions

- **Direct ops calls**: CARE decorators call `ops.verify()` / `ops.audit()` directly rather than wrapping EATP decorator instances, since EATP's `@verified(agent_id=...)` takes a fixed agent_id at decoration time, but CARE needs dynamic agent_id from function args
- **Dual shadow layer**: `@care_shadow` has its own EATP `ShadowEnforcer` for protocol-level metrics AND optionally forwards to CARE's governance `ShadowEnforcer` for posture upgrade evidence
- **Fail-safe shadow**: Both EATP verify errors and CARE shadow errors are caught and logged — shadow mode never blocks execution
- **Sync + async auto-detection**: `inspect.iscoroutinefunction()` with `_run_coroutine_sync()` for sync contexts (matches EATP's own pattern)

## Where

- **New**: `src/care_platform/trust/decorators.py` (303 lines)
- **Modified**: `src/care_platform/trust/__init__.py` (4 new exports: `CareTrustOpsProvider`, `care_verified`, `care_audited`, `care_shadow`)
- **New**: `tests/unit/trust/test_decorators.py` (25 tests)
- **New**: `tests/integration/test_decorator_pipeline.py` (10 tests)

## Evidence

- [x] EATP SDK `eatp.enforce.decorators` API validated — read full source at `packages/eatp/src/eatp/enforce/decorators.py`, confirmed signatures for `verified()`, `audited()`, `shadow()`, and the `_run_coroutine_sync()` pattern
- [x] `decorators.py` created with all 3 CARE wrappers + CareTrustOpsProvider + `_extract_agent_id` helper
- [x] `trust/__init__.py` updated — exports `care_verified`, `care_audited`, `care_shadow`, `CareTrustOpsProvider` in both import block and `__all__`
- [x] Unit tests: 25/25 passed — covers provider lifecycle, agent_id extraction (kwargs, positional, custom param, error cases), all 3 decorators (allow/block, metadata preservation, enforcer access, custom param), migration path
- [x] Integration tests: 10/10 passed — full trust chain (genesis → lead → specialist), delegation chain verification, multi-agent same function, shadow metric accumulation, migration path end-to-end
- [x] Regression: 511/511 existing trust tests still pass (zero regressions)
- [x] Migration path documented in module docstring with code examples for all 3 stages
- [x] Security review: completed (background agent)
- [x] Code review: completed (background agent)
