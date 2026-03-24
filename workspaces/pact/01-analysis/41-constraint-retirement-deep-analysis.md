# Deep Analysis: Constraint Pipeline Retirement

**Date**: 2026-03-24
**Complexity Score**: 23 (Complex) -- Governance: 9, Legal: 3, Strategic: 11
**Analyst**: deep-analyst
**Branch**: `feat/v0.3.0-platform-repivot`

## Executive Summary

The constraint pipeline retirement deleted 7 modules from `src/pact_platform/trust/constraint/` and migrated consumers to the upstream `GovernanceEngine` from `kailash-pact`. The migration introduces three categories of risk: (1) behavioral divergence between the old `fnmatch`-based gradient classification and the upstream `verify_action()` multi-dimensional evaluation, (2) orphaned infrastructure where 4 kept modules (`cache.py`, `circuit_breaker.py`, `signing.py`, `bridge_envelope.py`) are exported but 3 of them have zero production consumers, and (3) a test coverage gap where 321 tests were deleted but several edge-case behaviors -- particularly around cumulative spend tracking, per-agent rate limiting, proximity alerts, and the emergency halt mechanism -- have no equivalent tests or implementation in the new path.

## 1. Behavioral Divergence Risk

### 1.1 Old Path: fnmatch Pattern Matching

The old `GradientEngine` (deleted `gradient.py`) used `fnmatch.fnmatch(action, pattern)` against a list of `GradientRuleConfig` rules. Key characteristics:

- **First-match wins**: Rules were evaluated in order; the first matching pattern determined the level.
- **Default fallback**: If no pattern matched, `default_level` applied (typically `FLAGGED`).
- **Pattern syntax**: Unix shell patterns (`*`, `?`, `[seq]`, `[!seq]`). Example: `read_*` matches `read_metrics`, `read_config`, but NOT `unread_items`.
- **No dimensional evaluation**: The gradient classified actions purely by name pattern. It did not check financial limits, operational constraints, temporal windows, or data access permissions.
- **No cost awareness**: An action classified as `AUTO_APPROVED` by pattern would proceed regardless of cost.

This exact behavior is preserved in `_DemoGovernanceEngine` within `dm_runner.py` (line 215-236) and in `_SeedGovernanceEngine` within `seed_demo.py`.

### 1.2 New Path: GovernanceEngine.verify_action()

Per the kailash-pact v0.3.0 API reference (`pact-governance-engine.md`), `verify_action()` performs:

1. Compute effective envelope (with version hash for TOCTOU defense)
2. Evaluate action against envelope dimensions (operational, financial)
3. Multi-level verify: walk accountability chain, most restrictive wins
4. If `context["resource"]` is a `KnowledgeItem`, run `check_access()`
5. Combine verdicts (most restrictive wins)
6. Emit audit anchor

This is fundamentally different from the old path.

### 1.3 Divergence Scenarios

| Scenario                                                  | Old Path (fnmatch)                         | New Path (GovernanceEngine)                          | Risk                    |
| --------------------------------------------------------- | ------------------------------------------ | ---------------------------------------------------- | ----------------------- |
| `draft_post` with $0 cost                                 | AUTO_APPROVED (pattern match)              | AUTO_APPROVED (action allowed + cost 0)              | **No divergence**       |
| `draft_post` with $5000 cost                              | AUTO_APPROVED (pattern match ignores cost) | HELD or BLOCKED (financial dimension triggers)       | **BEHAVIORAL CHANGE**   |
| `unknown_action` not in any pattern                       | FLAGGED (default_level)                    | BLOCKED (action not in `allowed_actions`)            | **BEHAVIORAL CHANGE**   |
| `read_metrics` by agent without that in `allowed_actions` | AUTO_APPROVED (pattern match only)         | BLOCKED (operational dimension blocks)               | **BEHAVIORAL CHANGE**   |
| `delete_old_posts`                                        | BLOCKED (pattern match `delete_*`)         | BLOCKED (both paths agree)                           | **No divergence**       |
| `approve_publication`                                     | HELD (pattern match `approve_*`)           | Depends on envelope config                           | **POSSIBLE DIVERGENCE** |
| Cross-team action via bridge                              | Not evaluated by gradient                  | Evaluated through bridge trust pipeline + governance | **New capability**      |

### 1.4 Risk Assessment

**Risk ID**: BDR-1 (Behavioral Divergence - Cost Bypass Removal)

- **Description**: The old gradient path silently approved any action matching `draft_*`, `read_*`, or `analyze_*` patterns regardless of the cost context. The new path evaluates financial constraints. Any code that relied on pattern-only classification for cost-bearing actions will see different results.
- **Likelihood**: MEDIUM. The DM team agents all have $0 financial constraints, so the current example vertical is unaffected. However, any vertical that defines non-zero budgets and relies on pattern classification will break.
- **Impact**: MAJOR. A previously AUTO_APPROVED action becoming BLOCKED or HELD changes the execution flow completely.
- **Mitigation**: The `_DemoGovernanceEngine` in `dm_runner.py` preserves the old fnmatch behavior for the example vertical. Production verticals using the real GovernanceEngine get the correct multi-dimensional evaluation. This is the intended behavior -- the old path was LESS secure. Document the behavioral change in CHANGELOG.

**Risk ID**: BDR-2 (Unknown Action Default Change)

- **Description**: The old gradient defaulted unknown actions to `FLAGGED` (proceed with logging). The new GovernanceEngine defaults unknown actions to `BLOCKED` (action not in `allowed_actions`). Any action string not explicitly listed in the envelope's `operational.allowed_actions` will now be blocked.
- **Likelihood**: HIGH. The default changed from permissive to restrictive. Any agent attempting an action not in its allowed list will be blocked where it was previously flagged.
- **Impact**: SIGNIFICANT. Legitimate actions could be blocked if the envelope's `allowed_actions` list is incomplete.
- **Mitigation**: Audit all envelope configurations to ensure `allowed_actions` lists are comprehensive. The fail-closed behavior is correct per governance rules, but the transition must be managed.

**Risk ID**: BDR-3 (fnmatch Globbing Semantics Lost)

- **Description**: `fnmatch` supports `*` (match everything), `?` (match single char), `[seq]` (character class). The GovernanceEngine's `allowed_actions` list uses exact string matching. A gradient rule like `read_*` matching `read_metrics`, `read_config`, `read_anything` is now replaced by an explicit list `["read_metrics", "read_config"]`. If an action like `read_new_feature` was added, it would have been auto-approved by the old gradient but now requires explicit listing.
- **Likelihood**: MEDIUM. Depends on whether new action strings are introduced that would have matched glob patterns.
- **Impact**: SIGNIFICANT. Actions that "should work" based on naming convention will fail silently until added to the allowed list.
- **Mitigation**: The GovernanceEngine provides pattern-matching via its own rule system. Verify that the upstream engine supports glob patterns in its envelope evaluation. If not, all action patterns must be enumerated. Consider adding a glob-to-explicit expansion step in the platform's org builder.

## 2. Lost Capabilities Analysis

### 2.1 ProximityScanner Integration (Near-Boundary Alerts)

- **What it did**: Detected when an agent's actions were approaching constraint boundaries (e.g., 80% of budget consumed, 90% of daily action limit). Emitted warnings before hard limits were hit.
- **Status in new path**: **NO EQUIVALENT**. The GovernanceEngine evaluates actions as pass/fail at the boundary. There is no "approaching limit" awareness. The `PlatformEnvelopeAdapter` logs rate limits for observability (line 182-188) but does not implement proximity detection.
- **Production dependency**: The seed_demo.py and dashboard pages reference shadow evaluations but not proximity alerts directly. The alerting module (`use/observability/alerting.py`) references rate limits but not proximity scanning of constraint dimensions.
- **Risk**: MEDIUM likelihood, SIGNIFICANT impact. Without proximity alerts, agents will hit hard limits without warning, causing sudden BLOCKED verdicts that could disrupt workflows in progress. The transition from "approaching limit, plan accordingly" to "limit reached, action denied" is abrupt.

### 2.2 VerificationThoroughness (QUICK/STANDARD/FULL)

- **What it did**: Provided three levels of verification depth. QUICK (~1ms) used the `VerificationCache` for recently-verified actions. STANDARD ran the full gradient + envelope check. FULL added cryptographic signature verification of the signed envelope.
- **Status in new path**: **PARTIALLY REPLACED**. The GovernanceEngine runs a single verification path (equivalent to STANDARD). The `VerificationCache` module is retained in the `constraint/` package but is **not wired to any consumer**. The `SignedEnvelope` signing module is retained but also **not wired to any consumer**.
- **Production dependency**: The cache and signing modules are exported from `constraint/__init__.py` but have zero production consumers outside their own package. The only consumers are their respective test files.
- **Risk**: LOW likelihood, MINOR impact. The QUICK path optimization is lost, but GovernanceEngine latency is sub-millisecond for in-memory stores. The FULL path (cryptographic verification) is now handled by the upstream trust layer (kailash.trust envelope signing). No production code depended on the three-tier thoroughness model.

### 2.3 Cumulative Spend Tracking Per Agent

- **What it did**: The old constraint evaluation tracked cumulative cost per agent session, preventing an agent from exceeding its budget through many small actions that individually pass the limit but cumulatively exceed it.
- **Status in new path**: **PARTIALLY REPLACED**. The `CostTracker` in `trust/store/cost_tracking.py` still exists and tracks API costs per agent. However, the enforcement loop in `_run_governance_verification()` (runtime.py, line 984-1071) only passes `task.metadata.get("cost")` as a single-action cost. There is no cumulative budget check. The GovernanceEngine's `verify_action()` evaluates the cost field against the envelope's `max_spend_usd` per-action, but does not maintain session-level cumulative state.
- **Production dependency**: The `CostTracker` records costs after execution. The pre-execution budget check does not accumulate.
- **Risk**: HIGH likelihood, MAJOR impact. An agent with a $100 budget limit making 50 actions at $5 each will pass all 50 individually ($5 < $100) but spend $250 total. The old enforcement tracked this; the new path does not. This is a **governance bypass vulnerability**.

### 2.4 Emergency Halt Mechanism

- **What it did**: A global `halted_check` callback that, when returning `True`, caused all enforcers to block all actions immediately. Used for crisis response (e.g., security breach, compliance incident).
- **Status in new path**: **PARTIALLY PRESERVED**. The `HookEnforcer` (line 79, 108-118) and `ShadowEnforcer` (line 126, 194-208) still accept and honor `halted_check`. However, the `ExecutionRuntime` (the primary task execution path) does **NOT** accept or check a `halted_check` parameter. It has no emergency halt mechanism.
- **Production dependency**: The `ExecutionRuntime` is the main execution entry point. Without halt support, there is no way to emergency-stop all task processing short of killing the process.
- **Risk**: HIGH likelihood (runtime is the primary path), CRITICAL impact (inability to halt rogue agents during a security incident). The HookEnforcer retains halt support, but the runtime -- where tasks are actually dequeued and executed -- does not.

### 2.5 Per-Agent Rate Limiting

- **What it did**: Tracked action counts per agent per time window (daily/hourly) and blocked actions that exceeded the configured rate.
- **Status in new path**: **LOGGED BUT NOT ENFORCED**. The `PlatformEnvelopeAdapter._convert()` method reads `max_actions_per_day` and `max_actions_per_hour` from the envelope and logs them (lines 178-188) but does not enforce them. The values are not passed to the GovernanceEngine, not tracked in the runtime, and not checked before execution.
- **Production dependency**: The DM team envelopes define `max_actions_per_day` and `max_actions_per_hour` in their `OperationalConstraintConfig`. These values are read, logged, and discarded.
- **Risk**: HIGH likelihood, SIGNIFICANT impact. Rate limits defined in envelope configurations are silently ignored. An agent can exceed its configured daily/hourly action limits without any enforcement. This is a **configuration lie** -- the config suggests protection that does not exist.

### 2.6 Signed Envelope Verification in Middleware

- **What it did**: The old constraint middleware (`middleware.py`, deleted) verified the Ed25519 signature of the `SignedEnvelope` before every action evaluation. This ensured that the envelope had not been tampered with since the supervisor signed it.
- **Status in new path**: **MODULE RETAINED, NOT WIRED**. `signing.py` is kept in the `constraint/` package with `SignedEnvelope` and `EnvelopeVersionHistory` classes. However, no production code imports or uses them. The GovernanceEngine uses its own envelope integrity mechanism (version hashing via SHA-256, per the `envelope_version` field in `GovernanceVerdict`).
- **Production dependency**: Zero. The signing module is dead code.
- **Risk**: LOW likelihood, MINOR impact. The upstream GovernanceEngine provides TOCTOU defense via envelope version hashing, which serves the same purpose (detecting envelope changes between check and use). The Ed25519 signing provided stronger cryptographic guarantees but is replaced by the upstream mechanism.

## 3. Test Coverage Gap

### 3.1 Tests Deleted (321 tests)

The 321 deleted tests covered behaviors in the 7 deleted modules:

- `gradient.py`: Pattern matching, default levels, multi-rule evaluation, edge cases (empty patterns, overlapping patterns, case sensitivity)
- `evaluation.py`: 5-dimension envelope evaluation (financial, operational, temporal, data access, communication)
- `enforcement.py`: Cumulative spend tracking, rate limiting, budget exhaustion, session state management
- `middleware.py`: Signed envelope verification, middleware chain, tamper detection
- `proximity.py`: Near-boundary detection, threshold alerts, multi-dimension proximity scoring
- `context.py`: Verification context construction, agent state injection, immutability enforcement

### 3.2 Tests Retained

| Test File                 | Count        | Covers                                  |
| ------------------------- | ------------ | --------------------------------------- |
| `test_hook_enforcer.py`   | 14           | HookEnforcer with mock GovernanceEngine |
| `test_circuit_breaker.py` | ~20          | CircuitBreaker state machine            |
| `test_bridge_envelope.py` | ~30          | Bridge envelope intersection            |
| `test_cache.py`           | ~25          | VerificationCache LRU/TTL               |
| `test_m42_data_wiring.py` | ~10 (shadow) | ShadowEnforcer via API wiring           |

### 3.3 Missing Test Coverage (Behaviors Without Equivalents)

| Behavior                                              | Old Test Coverage | New Test Coverage                      | Gap                                                                                              |
| ----------------------------------------------------- | ----------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Cumulative budget tracking across actions             | ~15 tests         | **ZERO**                               | **CRITICAL** -- no test AND no implementation                                                    |
| Per-agent rate limit enforcement (daily/hourly)       | ~10 tests         | **ZERO**                               | **CRITICAL** -- no test AND no implementation                                                    |
| Emergency halt blocks all actions                     | ~5 tests          | Partial (HookEnforcer only)            | **HIGH** -- runtime path untested and unimplemented                                              |
| Proximity/near-boundary alerts                        | ~12 tests         | **ZERO**                               | **SIGNIFICANT** -- feature removed                                                               |
| Signed envelope tamper detection                      | ~8 tests          | **ZERO** (signing module is dead code) | LOW -- upstream handles differently                                                              |
| Unknown action defaults to FLAGGED vs BLOCKED         | ~5 tests          | **ZERO**                               | **HIGH** -- behavioral change undocumented and untested                                          |
| fnmatch globbing edge cases (?, [seq], [!seq])        | ~10 tests         | **ZERO**                               | MEDIUM -- upstream may handle differently                                                        |
| Multi-dimension interaction (financial + temporal)    | ~15 tests         | **ZERO** locally                       | MEDIUM -- upstream engine handles this but no platform-level tests                               |
| ShadowEnforcer standalone (not via API)               | ~20 tests         | **ZERO**                               | **HIGH** -- ShadowEnforcer is a core component with no unit tests                                |
| GovernanceEngine error path -> fail-closed in runtime | Implicit          | **ZERO**                               | **HIGH** -- `_run_governance_verification()` has fail-closed logic (line 1053-1071) but no tests |

### 3.4 Test Debt Summary

- **CRITICAL gaps** (no test AND no implementation): 2 (cumulative budget, rate limiting)
- **HIGH gaps** (no tests for existing logic): 4 (emergency halt in runtime, unknown action default, ShadowEnforcer standalone, governance error fail-closed)
- **MEDIUM gaps** (behavioral changes untested): 2
- **LOW gaps** (replaced by upstream): 1

## 4. API Contract Changes

### 4.1 HookEnforcer Constructor Change

**Old signature** (pre-retirement):

```python
HookEnforcer(
    gradient_engine: GradientEngine | None = None,
    envelope: ConstraintEnvelopeConfig | None = None,
    role_address: str | None = None,
    *,
    halted_check: Callable[[], bool] | None = None,
)
```

**New signature**:

```python
HookEnforcer(
    governance_engine: GovernanceEngine | None = None,
    role_address: str | None = None,
    *,
    halted_check: Callable[[], bool] | None = None,
)
```

**Breaking changes**:

1. `gradient_engine` parameter replaced by `governance_engine` (different type, different name)
2. `envelope` parameter removed entirely (envelope resolution is now internal to GovernanceEngine)
3. The `governance_engine` parameter type is `GovernanceEngine` from `pact.governance.engine`, not the old `GradientEngine` from `pact_platform.trust.constraint.gradient`

**External callers affected**: Any code that constructs `HookEnforcer` with positional arguments or `gradient_engine=` keyword. The test file (`test_hook_enforcer.py`) was updated to use a mock that implements `verify_action()`.

### 4.2 ShadowEnforcer Constructor Change

**Old signature** (pre-retirement):

```python
ShadowEnforcer(
    gradient_engine: GradientEngine,
    envelope: ConstraintEnvelopeConfig,
    role_address: str,
    *,
    halted_check: Callable[[], bool] | None = None,
    maxlen: int = 10_000,
)
```

**New signature**:

```python
ShadowEnforcer(
    governance_engine: GovernanceEngine,
    role_address: str,
    *,
    halted_check: Callable[[], bool] | None = None,
    maxlen: int = 10_000,
)
```

**Breaking changes**:

1. `gradient_engine` parameter replaced by `governance_engine`
2. `envelope` parameter removed
3. `evaluate()` method signature now accepts `**kwargs` for additional context

**External callers affected**: `dm_runner.py` and `seed_demo.py` both construct `ShadowEnforcer` with the new signature, using duck-typed mock engines that implement `verify_action()`. Any vertical that imports and constructs `ShadowEnforcer` directly will break.

### 4.3 ExecutionRuntime Verification Path Change

**Old behavior**: The runtime checked for a standalone gradient engine, constraint enforcer, and middleware pipeline. If none were configured, it defaulted to `AUTO_APPROVED`.

**New behavior**: The runtime checks for `governance_engine` AND `_agent_role_addresses[agent_id]`. If both are present, it calls `_run_governance_verification()`. If the governance engine is not configured OR the agent has no mapped role address, it defaults to `AUTO_APPROVED`.

**Breaking change**: The default path for ungoverned agents is now `AUTO_APPROVED` with no envelope evaluation. Previously, even without a gradient engine, the envelope evaluation path could still classify actions. Now, without a GovernanceEngine, all actions for all agents are `AUTO_APPROVED`.

**Risk**: If a runtime is deployed without a GovernanceEngine (e.g., during development or testing), all actions pass without any governance check. This is a **fail-open default** that contradicts the fail-closed governance principle.

### 4.4 Deleted Module Imports

Any code that imports from these deleted modules will get `ImportError`:

- `pact_platform.trust.constraint.gradient` (GradientEngine, GradientRule)
- `pact_platform.trust.constraint.evaluation` (EnvelopeEvaluator, DimensionResult)
- `pact_platform.trust.constraint.enforcement` (ConstraintEnforcer, SpendTracker)
- `pact_platform.trust.constraint.middleware` (ConstraintMiddleware, MiddlewareChain)
- `pact_platform.trust.constraint.proximity` (ProximityScanner, ProximityAlert)
- `pact_platform.trust.constraint.context` (VerificationContext)
- `pact_platform.trust.constraint.thoroughness` (VerificationThoroughness)

Confirmed: No remaining imports from these modules exist in the codebase (verified via grep).

## 5. Risk Register

| ID    | Risk                                                                               | Likelihood | Impact      | Score | Mitigation                                                                          |
| ----- | ---------------------------------------------------------------------------------- | ---------- | ----------- | ----- | ----------------------------------------------------------------------------------- |
| BDR-1 | Cost bypass removal: actions classified by pattern now also check financial limits | MEDIUM     | MAJOR       | 12    | Document in CHANGELOG; DM example uses mock engine preserving old behavior          |
| BDR-2 | Unknown action default FLAGGED->BLOCKED                                            | HIGH       | SIGNIFICANT | 15    | Audit all envelope `allowed_actions` lists for completeness                         |
| BDR-3 | fnmatch glob semantics lost in explicit action lists                               | MEDIUM     | SIGNIFICANT | 10    | Verify GovernanceEngine supports patterns; add glob expansion to org builder if not |
| LC-1  | Cumulative spend tracking removed; per-action checks only                          | HIGH       | MAJOR       | 20    | **IMPLEMENT**: Add session-level budget accumulator in runtime or GovernanceEngine  |
| LC-2  | Emergency halt missing from ExecutionRuntime                                       | HIGH       | CRITICAL    | 25    | **IMPLEMENT**: Add `halted_check` parameter to ExecutionRuntime constructor         |
| LC-3  | Per-agent rate limiting logged but not enforced                                    | HIGH       | SIGNIFICANT | 15    | **IMPLEMENT**: Add rate-limit tracking in runtime or delegate to GovernanceEngine   |
| LC-4  | ProximityScanner removed; no near-boundary alerts                                  | MEDIUM     | SIGNIFICANT | 10    | Design phase: decide whether to implement in platform or upstream                   |
| LC-5  | VerificationCache retained but dead code                                           | LOW        | MINOR       | 2     | Either wire to GovernanceEngine call path or delete                                 |
| LC-6  | SignedEnvelope/signing.py retained but dead code                                   | LOW        | MINOR       | 2     | Either wire to envelope adapter or delete                                           |
| TC-1  | ShadowEnforcer has zero unit tests                                                 | HIGH       | SIGNIFICANT | 15    | **IMPLEMENT**: Write ShadowEnforcer unit tests                                      |
| TC-2  | GovernanceEngine fail-closed path in runtime untested                              | HIGH       | MAJOR       | 20    | **IMPLEMENT**: Write tests for `_run_governance_verification()` error handling      |
| TC-3  | No tests for unknown action -> BLOCKED behavior                                    | HIGH       | SIGNIFICANT | 15    | **IMPLEMENT**: Add tests covering unknown action classification                     |
| AC-1  | HookEnforcer constructor changed: `gradient_engine` -> `governance_engine`         | MEDIUM     | SIGNIFICANT | 10    | API documented in docstring; verticals must update                                  |
| AC-2  | ShadowEnforcer constructor changed: `gradient_engine` -> `governance_engine`       | MEDIUM     | SIGNIFICANT | 10    | API documented in docstring; verticals must update                                  |
| AC-3  | ExecutionRuntime defaults to AUTO_APPROVED without GovernanceEngine                | HIGH       | CRITICAL    | 25    | **IMPLEMENT**: Add fail-closed default when no engine is configured                 |
| DC-1  | Orphaned modules: cache.py, circuit_breaker.py, signing.py have no consumers       | LOW        | MINOR       | 2     | Decide: wire them into the new path or remove them                                  |

## 6. Root Cause Analysis (5-Why)

### Why was the constraint pipeline retired?

1. **Why were 7 modules deleted?** Because the GovernanceEngine in kailash-pact v0.3.0 subsumes their functionality.
2. **Why does the GovernanceEngine subsume them?** Because PACT governance (D/T/R grammar, envelopes, clearance, verification) was migrated from this repo to the upstream kailash-pact package.
3. **Why was governance migrated upstream?** Because the PACT spec (L1) should be in the SDK package, not the platform (L3). The boundary test rule requires domain-agnostic governance to live at L1.
4. **Why does this create risk?** Because the old modules provided operational infrastructure (cumulative tracking, rate limiting, proximity alerts, emergency halt) that the upstream governance engine does not provide -- it focuses on per-action policy decisions, not operational state management.
5. **Why was the operational infrastructure not migrated or reimplemented?** Likely because it was assumed that per-action governance covers all cases. The gap between "is this action permitted right now?" (GovernanceEngine) and "has this agent exceeded its cumulative limits?" (old enforcement) was not identified during migration planning.

**Root cause**: The migration treated the constraint pipeline as a monolithic "verification" system and replaced it with another "verification" system. In reality, the old pipeline was layered: (a) action classification (gradient -- replaced), (b) dimensional evaluation (evaluation -- replaced), (c) operational enforcement (enforcement, middleware -- NOT replaced), (d) observability (proximity, cache -- NOT replaced). Layers (c) and (d) were deleted along with (a) and (b) without replacement.

## 7. Decision Points

The following decisions require stakeholder input:

1. **Cumulative budget enforcement (LC-1)**: Should cumulative spend tracking be reimplemented in the platform's runtime, or should the GovernanceEngine be extended with session-level budget state? The upstream engine makes per-action decisions only.

2. **Emergency halt in runtime (LC-2)**: Should `ExecutionRuntime` accept a `halted_check` parameter like `HookEnforcer` and `ShadowEnforcer` already do? Or should halt be implemented at a higher level (API server shutdown, process signal)?

3. **Rate limit enforcement (LC-3)**: Should the platform enforce `max_actions_per_day` and `max_actions_per_hour` from envelope configs, or should these be removed from the config schema as misleading? Currently they are read, logged, and discarded.

4. **Fail-closed default for ungoverned runtime (AC-3)**: When `ExecutionRuntime` has no `GovernanceEngine`, should all actions be BLOCKED (fail-closed, per governance rules) or AUTO_APPROVED (current behavior, for development convenience)? This is the most critical design decision -- the current fail-open default contradicts every governance rule in the codebase.

5. **Dead code disposition (DC-1)**: Should `VerificationCache`, `CircuitBreaker`, and `SignedEnvelope` be:
   - (a) Wired into the new GovernanceEngine call path as operational infrastructure
   - (b) Moved to a separate `operational/` package for future use
   - (c) Deleted as dead code

6. **Proximity alerts (LC-4)**: Should near-boundary alerting be reimplemented? If so, should it be platform-level (L3) or pushed upstream to kailash-pact (L1)?

## 8. Implementation Roadmap

### Phase 1: Critical Safety (immediate, before merge)

1. Add `halted_check` parameter to `ExecutionRuntime` constructor and `process_next()` -- estimated 1 session
2. Change `ExecutionRuntime` to fail-closed when no `GovernanceEngine` is configured (require explicit `allow_ungoverned=True` to opt into the current behavior) -- estimated 1 session
3. Write tests for `_run_governance_verification()` error handling (fail-closed path) -- estimated 0.5 session

### Phase 2: Enforcement Gaps (next release)

4. Implement cumulative budget tracking in the runtime (session-level spend accumulator per agent, checked before `_run_governance_verification()`) -- estimated 1 session
5. Implement rate-limit enforcement (daily/hourly action counters per agent) -- estimated 1 session
6. Write ShadowEnforcer unit tests -- estimated 0.5 session

### Phase 3: Observability and Cleanup (future)

7. Decide and implement proximity alerts (or document removal decision)
8. Resolve dead code (wire, move, or delete cache/circuit_breaker/signing)
9. Add unknown-action-default tests

### Success Criteria

- All items in Phase 1 have passing tests before merge
- No fail-open defaults in any governance path (measurable: grep for `AUTO_APPROVED` as fallback returns zero results outside explicit opt-in)
- Cumulative budget violation test: 50 actions at $5 each against $100 limit produces BLOCKED on action 21
- Rate limit violation test: 61st action in 1 hour against 60/hour limit produces BLOCKED
- Emergency halt test: `halted_check=lambda: True` causes `process_next()` to return BLOCKED task

## 9. Cross-Reference Audit

### Documents Affected

- `CLAUDE.md` (Architecture Overview table) -- references "verification gradient" but this is now upstream in GovernanceEngine
- `docs/cookbook.md` -- references `GovernanceEngine.verify_action()` correctly; no gradient references
- `docs/quickstart.md` -- references `GovernanceEngine` correctly
- `rules/governance.md` -- references envelope adapter and fail-closed; consistent with new path
- `rules/pact-governance.md` -- Rule 4 (fail-closed) is **violated** by `ExecutionRuntime` defaulting to AUTO_APPROVED without engine
- `.claude/skills/29-pact/pact-governance-engine.md` -- correctly documents upstream API

### Inconsistencies Found

- `rules/pact-governance.md` Rule 4 (fail-closed decisions) contradicts `runtime.py` line 584-586 where ungoverned agents default to `AUTO_APPROVED`
- `rules/governance.md` Rule 5 (thread-safe stores) -- the `ShadowEnforcer._metrics` dict is not bounded by `MAX_STORE_SIZE`; it grows with distinct agent IDs
- `PlatformEnvelopeAdapter` logs rate limits (lines 182-188) but states them as "active" when they are in fact not enforced anywhere
- `VerificationCache` docstring references "QUICK verification (~1ms)" but this verification thoroughness tier no longer exists
- `CircuitBreaker` docstring references "verification system" availability but is not connected to any verification system
