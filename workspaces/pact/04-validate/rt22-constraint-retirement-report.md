# RT22: Constraint Pipeline Retirement — Red Team Report

**Date**: 2026-03-24
**Scope**: Retirement of 7 legacy constraint/ modules, migration to GovernanceEngine
**Commit**: ed17912 (refactor) → aa7e4ad (security fixes)

## Context

7 legacy modules deleted from `src/pact_platform/trust/constraint/`:

- gradient.py, envelope.py, middleware.py (core evaluation)
- enforcement.py, enforcer.py, resolution.py, verification_level.py (supporting)

Consumers migrated to `GovernanceEngine.verify_action()` (upstream kailash-pact):

- HookEnforcer, ShadowEnforcer, ExecutionRuntime, signing, bridge_envelope, dm_runner, seed_demo

## Findings

### CRITICAL (Fixed)

| ID  | Finding                                                            | Fix                                         |
| --- | ------------------------------------------------------------------ | ------------------------------------------- |
| C1  | HookEnforcer didn't catch GovernanceEngine exceptions — fails OPEN | Added try/except → BLOCK on error (aa7e4ad) |
| C2  | HookEnforcer `_results` list unbounded — OOM risk                  | Added maxlen=10,000 + trimming (aa7e4ad)    |

### HIGH (Fixed)

| ID  | Finding                                                                       | Fix                                                   |
| --- | ----------------------------------------------------------------------------- | ----------------------------------------------------- |
| H1  | Runtime defaults AUTO_APPROVED when governance configured but no role_address | Added fail-closed BLOCK for unmapped agents (aa7e4ad) |
| H2  | HookEnforcer has no thread safety                                             | Added threading.Lock on \_results (aa7e4ad)           |

### MEDIUM (Accepted)

| ID  | Finding                                                          | Status                                                 |
| --- | ---------------------------------------------------------------- | ------------------------------------------------------ |
| M1  | signing.py catches bare Exception in verify_signature            | Acceptable — crypto lib raises various exception types |
| M2  | \_DemoGovernanceEngine in dm_runner.py lacks **all** enforcement | Private by convention (underscore prefix)              |
| M3  | runtime.py exposes raw exception in TaskResult.error             | Pre-existing pattern — not introduced by this refactor |
| M4  | ShadowEnforcer uses list + manual trim instead of deque(maxlen)  | Performance optimization — not a correctness issue     |

### LOW

| ID  | Finding                                                       | Status             |
| --- | ------------------------------------------------------------- | ------------------ |
| L1  | HookEnforcer docstring references "COC hook validation"       | Documentation only |
| L2  | SignedEnvelope canonical_version not validated on deserialize | Pre-existing       |

### PASSED

- Import chain completeness: zero dangling imports from deleted modules
- Signing integrity: ConstraintEnvelopeConfig covers all 5 dimensions (verified)
- Bridge envelope: helper functions correctly inlined
- ShadowEnforcer crash safety: try/except + bounded memory (verified)
- Mock governance engine scope: all private/function-scoped
- Approval queue routing: HELD → approval queue preserved in all paths
- Fail-closed in runtime governance path: catches Exception → BLOCKED
- Secrets detection: no hardcoded credentials
- Key material zeroization: del priv in finally blocks
- Frozen ConstraintEnvelopeConfig: model_config = ConfigDict(frozen=True)
- Monotonic tightening in bridge envelope: min/intersection preserved

## Docker Validation

- API image builds successfully
- Seed data populates on startup
- 62 endpoints serving
- Health check passes at /health
- Missing runtime deps fixed: numpy, requests, fastapi, uvicorn

## Test Status

- 1877 tests pass (post-retirement)
- 321 tests removed with deleted modules
- 16 new hook enforcer tests pass
- DataFlow model tests need Rust-backend SQLite path fix (tracked separately — kailash 2.1.0 compatibility)

## Verdict

**CONVERGED** — 2 CRITICAL and 2 HIGH findings all fixed. 4 MEDIUM findings accepted (pre-existing patterns or minor). No remaining actionable gaps from the constraint retirement refactor.
