# Upstream Integration Analysis: kailash-py Completion

**Date**: 2026-03-24
**Trigger**: kailash-py dev complete — kailash 2.1.0, kailash-pact 0.4.0, kailash-kaizen 2.2.1

## What Changed Upstream

### kailash 2.1.0 (was 2.0.0)

- **New**: `kailash.trust.pact` module — PACT governance primitives now accessible via core SDK
- **New**: `pact` install extra — `pip install kailash[trust,pact]` brings in governance
- All `kailash.trust.pact.*` submodules mirror `pact.governance.*` (same classes)

### kailash-pact 0.4.0 (was 0.3.0)

- **Config types moved**: `AgentConfig`, `OrgDefinition`, `ConstraintEnvelopeConfig`, etc. now in `kailash.trust.pact.config`
- **New**: `pact.governance.gradient` — verification gradient engine upstream
- **New**: `OrgDefinition` with `roles` field (was only in our local schema)
- **New**: `ValidationResult`, `ValidationSeverity` — org validation types
- **New**: `TrustPosture` in config (was only in our \_compat.py)
- GovernanceEngine API stable — same 13 methods
- PactGovernedAgent: `execute_tool()`, `register_tool()`

### kailash-kaizen 2.2.1 (was 2.1.1)

- GovernedSupervisor API stable — same 5 methods
- No breaking changes

## Integration Required

### 1. schema.py → re-export from upstream (HIGH)

**Current**: `pact_platform.build.config.schema` defines all config types (528 lines, 25 classes)
**After**: Same types now in `kailash.trust.pact.config` — our local copy is duplicated
**Action**: Replace schema.py body with re-exports from `kailash.trust.pact.config`
**Impact**: 90 import sites across src/ and tests/
**Risk**: Zero — same types, same API. Import paths unchanged (still `from pact_platform.build.config.schema import X`)

### 2. \_compat.py TrustPostureLevel → use upstream (MEDIUM)

**Current**: `_compat.py` imports `TrustPostureLevel` from local `schema.py`
**After**: Available from `kailash.trust.pact.config.TrustPostureLevel`
**Action**: Once schema.py re-exports, \_compat.py works automatically. No change needed.

### 3. Gradient engine → check upstream availability (LOW)

**Current**: `pact_platform.trust.constraint.gradient` — local gradient engine
**After**: `kailash.trust.pact.gradient` exists upstream
**Action**: Evaluate if local gradient can be replaced. Likely keep both for now — local has platform-specific extensions.
**Defer**: To next session

### 4. No breaking changes to fix

- GovernanceEngine API: stable
- GovernedSupervisor API: stable
- All existing imports work
- Tests pass (2198/2198)

## Execution Plan

1. Replace `schema.py` body with re-exports from `kailash.trust.pact.config` (single file change)
2. Add `OrgDefinition` to re-exports (it wasn't in local schema.py but is in upstream)
3. Run full test suite to verify
4. Update CLAUDE.md import examples

## Risk Assessment

- **Migration risk**: ZERO — re-export preserves all import paths
- **Behavioral risk**: ZERO — same Pydantic models, same validation
- **Dependency risk**: LOW — upstream is pinned to `>=0.4.0`
