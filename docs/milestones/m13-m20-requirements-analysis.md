# Requirements Analysis: Milestones M13-M20

## Executive Summary

- **Scope**: 6 work streams (A-F), decomposed into 8 milestones (M13-M20), 54 tasks
- **Total Complexity**: High -- touches every module in the codebase plus new frontend
- **Critical Path**: Work Stream A (restructure) unblocks everything; Work Stream D (gap closure) unblocks Work Stream F (validation)
- **Risk Level**: High -- structural move + cryptographic enhancements + frontend scaffold in parallel

---

## Dependency Graph (Milestone Order)

```
M13 (Restructure)
  |
  +--- M14 (Lifecycle State Machines)
  |       |
  +--- M15 (EATP v2.2 Cryptographic Enhancements)
  |       |
  +--- M16 (Gap Closure: Runtime Enforcement)
  |       |
  |       +--- M17 (Gap Closure: Integrity & Resilience)
  |               |
  |               +--- M19 (Constrained Org Validation)
  |
  +--- M18 (Frontend Scaffold & API Layer)
  |       |
  |       +--- M20 (Frontend Dashboard Views)
  |
  (M14, M15, M16 can run in parallel after M13)
```

---

## M13: Project Restructure (Work Stream A)

**Goal**: Move to `src/` layout, scaffold frontend directories, fix naming.

**Risk**: HIGH -- Every import path and test file changes. Must be atomic or nothing works.

### M13-T01: Move care_platform/ to src/care_platform/

| Field            | Value                                                                  |
| ---------------- | ---------------------------------------------------------------------- |
| **What**         | Move the entire `care_platform/` directory to `src/care_platform/`     |
| **Where**        | `src/care_platform/` (new location for all 60 Python modules)          |
| **Evidence**     | `ls src/care_platform/__init__.py` succeeds; `ls care_platform/` fails |
| **Dependencies** | None (first task)                                                      |
| **Effort**       | Small (1 file operation, but high blast radius)                        |

### M13-T02: Update pyproject.toml for src/ layout

| Field            | Value                                                                                                                                                                                                                                                                          |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | Change `[tool.setuptools.packages.find]` from `where = ["."]` to `where = ["src"]`. Update any other paths (e.g. `project.scripts` entry if it references the old location).                                                                                                   |
| **Where**        | `/Users/esperie/repos/terrene/care/pyproject.toml`                                                                                                                                                                                                                             |
| **Evidence**     | `pip install -e .` succeeds; `python -c "import care_platform"` works                                                                                                                                                                                                          |
| **Dependencies** | M13-T01                                                                                                                                                                                                                                                                        |
| **Detail**       | Change line 70-71 from `where = ["."]` / `exclude = ["tests*", ...]` to `where = ["src"]` / `exclude = ["tests*", ...]`. The `project.scripts` entry `care-platform = "care_platform.cli:main"` is fine -- it references the importable package name, not the filesystem path. |

### M13-T03: Update conftest.py for src/ layout

| Field            | Value                                                                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | Verify root `conftest.py` still works. No changes needed unless pytest can no longer find the package (which `pip install -e .` should resolve). |
| **Where**        | `/Users/esperie/repos/terrene/care/conftest.py`                                                                                                  |
| **Evidence**     | `pytest tests/ --co` (collection) succeeds with no import errors                                                                                 |
| **Dependencies** | M13-T01, M13-T02                                                                                                                                 |

### M13-T04: Update all test imports

| Field            | Value                                                                                                                                                                                                                                                                            |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Run the full test suite; fix any import failures caused by the move. With `pip install -e .` and the `where = ["src"]` config, the package is installed in the venv and imports should resolve as `care_platform.*` without change. This task is validation, not bulk rewriting. |
| **Where**        | `tests/**/*.py` (88 test files)                                                                                                                                                                                                                                                  |
| **Evidence**     | `pytest tests/ -x --tb=short` passes (1610 tests, 0 failures)                                                                                                                                                                                                                    |
| **Dependencies** | M13-T01, M13-T02, M13-T03                                                                                                                                                                                                                                                        |

### M13-T05: Scaffold apps/web/ (React/Next.js)

| Field            | Value                                                                                                                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Create the Next.js project skeleton with TypeScript, Tailwind CSS, and basic page structure.                                                                                                            |
| **Where**        | `/Users/esperie/repos/terrene/care/apps/web/`                                                                                                                                                           |
| **Evidence**     | `apps/web/package.json` exists; `cd apps/web && npm run build` succeeds                                                                                                                                 |
| **Dependencies** | None (can run parallel to T01-T04)                                                                                                                                                                      |
| **Detail**       | Scaffold: `package.json`, `tsconfig.json`, `next.config.js`, `tailwind.config.js`, `app/layout.tsx`, `app/page.tsx`, `app/globals.css`, `.gitignore`. No real dashboard content yet -- that is M18/M20. |

### M13-T06: Scaffold apps/mobile/ (Flutter placeholder)

| Field            | Value                                                                                                                              |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Create a minimal Flutter project placeholder with README explaining it is future work.                                             |
| **Where**        | `/Users/esperie/repos/terrene/care/apps/mobile/`                                                                                   |
| **Evidence**     | `apps/mobile/pubspec.yaml` exists; `apps/mobile/lib/main.dart` exists                                                              |
| **Dependencies** | None                                                                                                                               |
| **Detail**       | Minimal files: `pubspec.yaml`, `lib/main.dart` (hello world), `analysis_options.yaml`. Mark as placeholder for future development. |

### M13-T07: Fix eatp-expert.md casing

| Field            | Value                                                                                                                                                                                                                                                                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Audit `.claude/agents/standards/eatp-expert.md` for verification gradient level names and trust posture names. Per `terrene-naming.md`, verification gradient levels must be UPPERCASE (AUTO_APPROVED, FLAGGED, HELD, BLOCKED) and trust postures must be UPPERCASE (PSEUDO_AGENT, SUPERVISED, SHARED_PLANNING, CONTINUOUS_INSIGHT, DELEGATED). |
| **Where**        | `/Users/esperie/repos/terrene/care/.claude/agents/standards/eatp-expert.md`                                                                                                                                                                                                                                                                     |
| **Evidence**     | `grep -i "auto_approved\|flagged\|held\|blocked\|pseudo_agent\|supervised\|shared_planning\|continuous_insight\|delegated" .claude/agents/standards/eatp-expert.md` shows all instances in correct UPPERCASE                                                                                                                                    |
| **Dependencies** | None                                                                                                                                                                                                                                                                                                                                            |

---

## M14: CARE Formal Specifications -- Lifecycle State Machines (Work Stream C)

**Goal**: Implement the three lifecycle state machines and the constraint resolution algorithm, uncertainty classifier, and failure modes defined in the CARE formal specifications.

**Risk**: MEDIUM -- New models and enums, but no structural change to existing code.

### M14-T01: Trust chain lifecycle state machine

| Field            | Value                                                                                                                                                                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Add `TrustChainState` enum with states: DRAFT, PENDING, ACTIVE, SUSPENDED, REVOKED, EXPIRED. Add `TrustChainStateMachine` class with valid transitions and transition enforcement. Integrate with `GenesisManager` and `DelegationManager`. |
| **Where**        | New file: `src/care_platform/trust/lifecycle.py`. Modify: `src/care_platform/trust/genesis.py`, `src/care_platform/trust/delegation.py`                                                                                                     |
| **Evidence**     | Unit tests covering all valid transitions, rejection of invalid transitions, integration with genesis/delegation                                                                                                                            |
| **Dependencies** | M13-T01 through M13-T04 (src layout complete)                                                                                                                                                                                               |
| **Detail**       | Valid transitions: DRAFT->PENDING, PENDING->ACTIVE, PENDING->REVOKED, ACTIVE->SUSPENDED, ACTIVE->REVOKED, ACTIVE->EXPIRED, SUSPENDED->ACTIVE, SUSPENDED->REVOKED                                                                            |

### M14-T02: Bridge lifecycle state machine

| Field            | Value                                                                                                                                                                                                                                                    |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Formalize the existing `BridgeStatus` enum transitions into a proper state machine class. Bridge already has PENDING, NEGOTIATING, ACTIVE, SUSPENDED, EXPIRED, CLOSED, REVOKED. Add `BridgeStateMachine` with explicit transition table and enforcement. |
| **Where**        | New file: `src/care_platform/workspace/bridge_lifecycle.py`. Modify: `src/care_platform/workspace/bridge.py`                                                                                                                                             |
| **Evidence**     | Unit tests for all valid/invalid transitions; existing bridge tests still pass                                                                                                                                                                           |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                  |
| **Detail**       | Transitions already partially enforced in `Bridge._activate()`, `BridgeManager.suspend_bridge()`, etc. Consolidate into a single state machine.                                                                                                          |

### M14-T03: Workspace lifecycle state machine

| Field            | Value                                                                                                                                                                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Add `WorkspaceState` enum (PROVISIONING, ACTIVE, ARCHIVED, DECOMMISSIONED) alongside the existing `WorkspacePhase` (ANALYZE, PLAN, IMPLEMENT, VALIDATE, CODIFY). Phase tracks the CO methodology cycle; State tracks the operational lifecycle. |
| **Where**        | Modify: `src/care_platform/workspace/models.py`                                                                                                                                                                                                 |
| **Evidence**     | Unit tests for workspace state transitions; existing workspace tests still pass                                                                                                                                                                 |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                         |
| **Detail**       | Valid transitions: PROVISIONING->ACTIVE, ACTIVE->ARCHIVED, ARCHIVED->ACTIVE (reactivation), ACTIVE->DECOMMISSIONED, ARCHIVED->DECOMMISSIONED. Phase cycling only allowed when state is ACTIVE.                                                  |

### M14-T04: Constraint resolution algorithm

| Field            | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Implement the formal constraint resolution algorithm that determines the effective constraint when multiple envelopes apply (e.g., agent envelope + team envelope + org envelope). Resolution rule: most restrictive wins per dimension.                                                                                                                                                                                                                             |
| **Where**        | New file: `src/care_platform/constraint/resolution.py`                                                                                                                                                                                                                                                                                                                                                                                                               |
| **Evidence**     | Unit tests: single envelope pass-through, two envelopes pick tightest per dimension, three-level hierarchy (org->team->agent)                                                                                                                                                                                                                                                                                                                                        |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **Detail**       | Input: list of `ConstraintEnvelopeConfig` ordered from broadest to narrowest. Output: a single resolved `ConstraintEnvelopeConfig` representing the effective constraints. Financial: min of max_spend_usd. Operational: intersection of allowed_actions, union of blocked_actions. Temporal: intersection of active windows. Data Access: intersection of read/write paths, union of blocked types. Communication: most restrictive (internal_only if any says so). |

### M14-T05: Uncertainty classifier (5 levels)

| Field            | Value                                                                                                                                                                                                                                                                   |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Implement `UncertaintyLevel` enum (NONE, INFORMATIONAL, INTERPRETIVE, JUDGMENTAL, FUNDAMENTAL) and `UncertaintyClassifier` that categorizes decisions. Each level maps to a minimum verification gradient level.                                                        |
| **Where**        | New file: `src/care_platform/trust/uncertainty.py`                                                                                                                                                                                                                      |
| **Evidence**     | Unit tests for classification of sample decisions, mapping to verification levels                                                                                                                                                                                       |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                 |
| **Detail**       | Mapping: NONE->AUTO_APPROVED, INFORMATIONAL->AUTO_APPROVED, INTERPRETIVE->FLAGGED, JUDGMENTAL->HELD, FUNDAMENTAL->BLOCKED. Classifier takes action metadata (data completeness, precedent availability, reversibility, impact scope) and produces an uncertainty level. |

### M14-T06: Five failure modes with detection, impact, mitigation, recovery

| Field            | Value                                                                                                                                                                                                                                                                         |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Implement `FailureMode` enum and `FailureDetector` class that monitors for the five CARE-specified failure modes. Each mode has detection criteria, impact assessment, mitigation procedure, and recovery procedure.                                                          |
| **Where**        | New file: `src/care_platform/resilience/failure_modes.py`                                                                                                                                                                                                                     |
| **Evidence**     | Unit tests for each failure mode detection, impact calculation, mitigation invocation                                                                                                                                                                                         |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                       |
| **Detail**       | Five modes: (1) Trust Chain Break -- genesis or delegation invalid, (2) Constraint Violation -- envelope breached, (3) Communication Isolation -- bridge failure, (4) Audit Gap -- missing anchors in chain, (5) Posture Regression -- agent operating above allowed posture. |

### M14-T07: Tests for all M14 features

| Field            | Value                                                                                                                                                                                                                                                                        |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Comprehensive test suite for lifecycle state machines, resolution algorithm, uncertainty classifier, failure modes                                                                                                                                                           |
| **Where**        | `tests/unit/trust/test_lifecycle.py`, `tests/unit/workspace/test_bridge_lifecycle.py`, `tests/unit/workspace/test_workspace_lifecycle.py`, `tests/unit/constraint/test_resolution.py`, `tests/unit/trust/test_uncertainty.py`, `tests/unit/resilience/test_failure_modes.py` |
| **Evidence**     | All new tests pass; existing 1610 tests still pass                                                                                                                                                                                                                           |
| **Dependencies** | M14-T01 through M14-T06                                                                                                                                                                                                                                                      |

---

## M15: EATP v2.2 Alignment (Work Stream B)

**Goal**: Implement the five new EATP v2.2 features.

**Risk**: HIGH -- Cryptographic changes (JCS, SD-JWT, dual-binding) require careful implementation and testing.

### M15-T01: Confidentiality levels -- promote to first-class constraint

| Field            | Value                                                                                                                                                                                                                                                                                                                                                                                   |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | The five confidentiality levels (PUBLIC, RESTRICTED, CONFIDENTIAL, SECRET, TOP_SECRET) already exist in `trust/reasoning.py` as `ConfidentialityLevel`. Promote this to a platform-wide concept: add to `config/schema.py` as a config option, integrate with the constraint envelope (each envelope can have a confidentiality classification), and enforce in data access evaluation. |
| **Where**        | Modify: `src/care_platform/config/schema.py` (add field to DataAccessConstraintConfig), `src/care_platform/constraint/envelope.py` (enforce confidentiality in data access evaluation), `src/care_platform/trust/reasoning.py` (re-export from schema)                                                                                                                                  |
| **Evidence**     | Tests: envelope evaluation denies access to data above the envelope's confidentiality clearance                                                                                                                                                                                                                                                                                         |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                                                                                                                                 |

### M15-T02: SD-JWT selective disclosure

| Field            | Value                                                                                                                                                                                                                                                |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Implement SD-JWT (Selective Disclosure JSON Web Token) based on confidentiality level. Trust chain elements can be serialized as SD-JWTs where fields above the viewer's clearance are disclosed only as hashes.                                     |
| **Where**        | New file: `src/care_platform/trust/sd_jwt.py`                                                                                                                                                                                                        |
| **Evidence**     | Tests: create an SD-JWT from a delegation record, verify disclosure at each confidentiality level, verify that undisclosed fields are hash-only                                                                                                      |
| **Dependencies** | M15-T01                                                                                                                                                                                                                                              |
| **Detail**       | Dependency: `sd-jwt` Python library or implement minimal SD-JWT per IETF draft. Fields to selectively disclose: reasoning traces, constraint details, metadata. Disclosure granularity follows the confidentiality level of the viewer vs the field. |

### M15-T03: REASONING_REQUIRED constraint type

| Field            | Value                                                                                                                                                                                                                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Add `REASONING_REQUIRED` as a meta-constraint that can be attached to any constraint dimension. When present, any action touching that dimension must include a reasoning trace. This is inheritable (if a parent envelope has REASONING_REQUIRED, all child envelopes inherit it).            |
| **Where**        | Modify: `src/care_platform/config/schema.py` (add `reasoning_required: bool` to each dimension config), `src/care_platform/constraint/envelope.py` (check for reasoning trace when REASONING_REQUIRED), `src/care_platform/trust/delegation.py` (enforce inheritance in tightening validation) |
| **Evidence**     | Tests: action without reasoning trace is HELD when REASONING_REQUIRED; action with reasoning trace passes; child envelope inherits REASONING_REQUIRED from parent                                                                                                                              |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                                        |

### M15-T04: JCS canonical serialization (RFC 8785)

| Field            | Value                                                                                                                                                                                                                                                                            |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Replace the current `json.dumps(signable, sort_keys=True, separators=(",", ":"))` approach in `constraint/signing.py` with RFC 8785 JCS (JSON Canonicalization Scheme). JCS handles edge cases that `sort_keys=True` does not: Unicode normalization, number serialization, etc. |
| **Where**        | Modify: `src/care_platform/constraint/signing.py`. New utility: `src/care_platform/trust/jcs.py` (JCS implementation or wrapper around `jcs` PyPI package). Also update `src/care_platform/audit/anchor.py` hash computation.                                                    |
| **Evidence**     | Tests: canonical output matches RFC 8785 test vectors; existing signature tests still pass (backward compat via migration)                                                                                                                                                       |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                          |
| **Detail**       | Add `jcs>=0.2.1` to dependencies in `pyproject.toml`. Replace `_serialize_for_signing()` to use JCS. Add a `canonical_version` field to `SignedEnvelope` to support both old and new serialization during migration.                                                             |

### M15-T05: Dual-binding cryptographic signing for reasoning traces

| Field            | Value                                                                                                                                                                                                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Enhance reasoning trace signing so that each trace is cryptographically bound both to its parent record (delegation/audit anchor) AND to the trust chain genesis. This creates a dual binding that prevents reasoning traces from being moved between trust chains. |
| **Where**        | Modify: `src/care_platform/trust/reasoning.py` (add `genesis_binding_hash` field, update `compute_hash()` to include genesis reference). New: `src/care_platform/trust/dual_binding.py` (binding verification logic).                                               |
| **Evidence**     | Tests: reasoning trace bound to genesis A fails verification against genesis B; reasoning trace bound to delegation D1 fails verification against delegation D2                                                                                                     |
| **Dependencies** | M15-T04 (JCS for canonical hash computation)                                                                                                                                                                                                                        |

### M15-T06: Tests for all EATP v2.2 features

| Field            | Value                                                                                                                                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Comprehensive tests for SD-JWT, REASONING_REQUIRED, JCS, dual-binding                                                                                          |
| **Where**        | `tests/unit/trust/test_sd_jwt.py`, `tests/unit/constraint/test_reasoning_required.py`, `tests/unit/trust/test_jcs.py`, `tests/unit/trust/test_dual_binding.py` |
| **Evidence**     | All new tests pass; existing tests pass                                                                                                                        |
| **Dependencies** | M15-T01 through M15-T05                                                                                                                                        |

---

## M16: Gap Closure -- Runtime Constraint Enforcement (Work Stream D, Part 1)

**Goal**: Address the CRITICAL and HIGH gaps: runtime enforcement, capability model, fail-closed behavior.

**Risk**: CRITICAL -- These are the most impactful gaps. Runtime enforcement touches the middleware, execution runtime, and approval flow.

### M16-T01: Runtime constraint enforcement -- ConstraintEnforcer

| Field            | Value                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Create a `ConstraintEnforcer` that wraps the `VerificationMiddleware` and is injected into the `ExecutionRuntime`. Currently, the middleware exists but the runtime can bypass it. The enforcer makes constraint checking mandatory: every `runtime.submit()` / `runtime.process_next()` call must pass through the enforcer.                                               |
| **Where**        | New file: `src/care_platform/constraint/enforcer.py`. Modify: `src/care_platform/execution/runtime.py` (inject enforcer into the execution pipeline).                                                                                                                                                                                                                       |
| **Evidence**     | Test: agent action that violates a constraint is blocked even without explicit middleware call; test: removing the enforcer causes a clear error, not silent bypass                                                                                                                                                                                                         |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                                                                                                                     |
| **Detail**       | The enforcer wraps the middleware and makes it impossible to execute an action without constraint evaluation. It integrates at the `ExecutionRuntime` level via a required constructor parameter. The runtime's `_execute_task()` method must call `enforcer.check(action, agent_id, ...)` before executing. If the enforcer is None, the runtime refuses to process tasks. |

### M16-T02: Capability attestation model -- separate authorization from capability

| Field            | Value                                                                                                                                                                                                                                                                                                                                                                   |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Currently `CapabilityAttestation.has_capability()` conflates "is authorized" with "has the capability". Separate these: (a) Authorization = "this agent is permitted to attempt this action" (constraint envelope check), (b) Capability = "this agent is able to perform this action" (attestation check). Add `AuthorizationCheck` that evaluates both independently. |
| **Where**        | Modify: `src/care_platform/trust/attestation.py` (add `has_authorization()` separate from `has_capability()`). New: `src/care_platform/trust/authorization.py` (AuthorizationCheck combining envelope + attestation). Modify: `src/care_platform/constraint/middleware.py` (use `AuthorizationCheck` instead of separate checks).                                       |
| **Evidence**     | Test: agent with capability but no envelope authorization is blocked; agent with envelope authorization but no capability attestation is blocked; agent with both passes                                                                                                                                                                                                |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                                                                                                                 |

### M16-T03: Fail-closed behavior -- TrustStore unreachable

| Field            | Value                                                                                                                                                                                                                                                                                                                                                                                                     |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Define and implement fail-closed behavior when the trust database (TrustStore) is unreachable. Currently, if the SQLite database is locked or the filesystem store is unavailable, behavior is undefined. Implement: (a) `TrustStoreHealthCheck` that validates store connectivity, (b) Automatic circuit-breaker activation when store is unreachable, (c) All actions BLOCKED when trust store is down. |
| **Where**        | Modify: `src/care_platform/persistence/store.py` (add `health_check()` to TrustStore protocol). Modify: `src/care_platform/persistence/sqlite_store.py` (implement health_check). New: `src/care_platform/persistence/health.py` (TrustStoreHealthCheck with circuit breaker). Modify: `src/care_platform/constraint/middleware.py` (check store health before processing).                               |
| **Evidence**     | Test: simulate store failure, verify all actions are BLOCKED; test: store recovery, verify actions resume; test: health check returns correct status                                                                                                                                                                                                                                                      |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                                                                                                                                                   |

### M16-T04: Deployment state persistence -- OrgBuilder state to store

| Field            | Value                                                                                                                                                                                                                                                                    |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | `OrgBuilder` state is currently in-memory only. If the process restarts, the builder state is lost. Persist the `OrgDefinition` to the TrustStore so that the platform can resume from a persisted state.                                                                |
| **Where**        | Modify: `src/care_platform/org/builder.py` (add `save()` and `load()` methods). Modify: `src/care_platform/persistence/store.py` (add `store_org_definition()` / `get_org_definition()` to protocol). Implement in `MemoryStore`, `FilesystemStore`, `SQLiteTrustStore`. |
| **Evidence**     | Test: build org, save, load, verify roundtrip equality; test: bootstrap from persisted org definition                                                                                                                                                                    |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                  |

### M16-T05: Tests for M16 features

| Field            | Value                                                                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Tests for constraint enforcer, authorization model, fail-closed, deployment persistence                                                                                   |
| **Where**        | `tests/unit/constraint/test_enforcer.py`, `tests/unit/trust/test_authorization.py`, `tests/unit/persistence/test_health.py`, `tests/unit/org/test_builder_persistence.py` |
| **Evidence**     | All new tests pass; existing tests pass                                                                                                                                   |
| **Dependencies** | M16-T01 through M16-T04                                                                                                                                                   |

---

## M17: Gap Closure -- Integrity & Resilience (Work Stream D, Part 2)

**Goal**: Address HIGH and MEDIUM gaps: cryptographic integrity, knowledge policy enforcement, verification caching, plane isolation.

**Risk**: HIGH -- Cryptographic hash-chaining and plane isolation are architectural changes.

### M17-T01: Cryptographic integrity -- hash-chain trust records

| Field            | Value                                                                                                                                                                                                                                                                                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Trust chain records (genesis, delegations) are currently plain database rows with no chaining or tamper detection. Add hash chaining: each delegation record includes the hash of the previous record in the chain, forming a Merkle-like structure. Add tamper detection via periodic integrity verification. |
| **Where**        | Modify: `src/care_platform/trust/delegation.py` (add `previous_record_hash` to delegation data). Modify: `src/care_platform/persistence/sqlite_store.py` (store and verify hashes). New: `src/care_platform/trust/integrity.py` (TrustChainIntegrity verifier).                                                |
| **Evidence**     | Test: tamper with a delegation record, verify integrity check catches it; test: append a new delegation, verify hash chain is valid                                                                                                                                                                            |
| **Dependencies** | M16-T01 through M16-T05 (runtime enforcement in place)                                                                                                                                                                                                                                                         |

### M17-T02: Knowledge policy enforcement

| Field            | Value                                                                                                                                                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Knowledge policies are generated during workspace setup but never enforced at query time. Implement a `KnowledgePolicyEnforcer` that checks data access against workspace knowledge policies before allowing reads. |
| **Where**        | New: `src/care_platform/workspace/knowledge_policy.py`. Modify: `src/care_platform/workspace/bridge.py` (integrate policy check into `access_through_bridge()`).                                                    |
| **Evidence**     | Test: access via bridge that violates knowledge policy is denied; test: access that complies with policy is allowed                                                                                                 |
| **Dependencies** | M16-T01 through M16-T05                                                                                                                                                                                             |

### M17-T03: Trust verification caching enhancement

| Field            | Value                                                                                                                                                                                                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | The existing `VerificationCache` in `constraint/cache.py` is functional but not integrated into the middleware pipeline. Integrate it so that repeat verifications for the same agent+envelope within the TTL use the cached result. Target: sub-35ms for cached verifications. |
| **Where**        | Modify: `src/care_platform/constraint/middleware.py` (add cache lookup before full verification). Modify: `src/care_platform/constraint/cache.py` (add cache key generation from middleware context).                                                                           |
| **Evidence**     | Performance test: 1000 repeat verifications for same agent complete in <35ms total; cache hit rate >90% in steady state                                                                                                                                                         |
| **Dependencies** | M16-T01 through M16-T05                                                                                                                                                                                                                                                         |

### M17-T04: Management/data plane isolation

| Field            | Value                                                                                                                                                                                                                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Currently, the management plane (config, bootstrap, org builder) and data plane (runtime, middleware, audit) share everything -- same store, same models, same thread. Introduce logical plane isolation: separate store interfaces for management operations vs data operations, with explicit boundary crossing points. |
| **Where**        | New: `src/care_platform/planes/__init__.py`, `src/care_platform/planes/management.py`, `src/care_platform/planes/data.py`. Modify: `src/care_platform/bootstrap.py` (use management plane). Modify: `src/care_platform/execution/runtime.py` (use data plane).                                                            |
| **Evidence**     | Test: data plane cannot write to management-only tables; management plane cannot bypass data plane constraints                                                                                                                                                                                                            |
| **Dependencies** | M16-T01 through M16-T05                                                                                                                                                                                                                                                                                                   |

### M17-T05: Tests for M17 features

| Field            | Value                                                                                                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Tests for hash-chain integrity, knowledge policy enforcement, cache integration, plane isolation                                                                                |
| **Where**        | `tests/unit/trust/test_integrity.py`, `tests/unit/workspace/test_knowledge_policy.py`, `tests/unit/constraint/test_cache_integration.py`, `tests/unit/planes/test_isolation.py` |
| **Evidence**     | All new tests pass; existing tests pass                                                                                                                                         |
| **Dependencies** | M17-T01 through M17-T04                                                                                                                                                         |

---

## M18: Frontend Scaffold & API Layer (Work Stream E, Part 1)

**Goal**: Create the API backend endpoints and initial frontend infrastructure needed for the dashboard.

**Risk**: MEDIUM -- New technology layer (React/Next.js) but builds on existing `PlatformAPI`.

### M18-T01: Extend PlatformAPI with dashboard-specific endpoints

| Field            | Value                                                                                                                                                                                                                                                                                                                                                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Add new API handler methods to `PlatformAPI` for dashboard views not yet covered: trust chain listing, constraint envelope details, workspace status, bridge status, verification gradient statistics.                                                                                                                                                                                                              |
| **Where**        | Modify: `src/care_platform/api/endpoints.py`                                                                                                                                                                                                                                                                                                                                                                        |
| **Evidence**     | Unit tests for each new endpoint handler method                                                                                                                                                                                                                                                                                                                                                                     |
| **Dependencies** | M13-T01 through M13-T04                                                                                                                                                                                                                                                                                                                                                                                             |
| **Detail**       | New endpoints: `GET /api/v1/trust-chains` (list all trust chains with status), `GET /api/v1/trust-chains/{agent_id}` (chain detail with genesis->delegations), `GET /api/v1/envelopes/{envelope_id}` (all 5 dimensions), `GET /api/v1/workspaces` (all workspaces with state/phase), `GET /api/v1/bridges` (all bridges with status), `GET /api/v1/verification/stats` (AUTO_APPROVED/FLAGGED/HELD/BLOCKED counts). |

### M18-T02: FastAPI/Nexus server wiring

| Field            | Value                                                                                                                                                                                                    |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Create a FastAPI application (or Nexus application if using kailash-nexus) that mounts the `PlatformAPI` handler methods as actual HTTP endpoints. This is the runtime server for the dashboard backend. |
| **Where**        | New: `src/care_platform/api/server.py`                                                                                                                                                                   |
| **Evidence**     | `python -m care_platform.api.server` starts a server; `curl http://localhost:8000/api/v1/teams` returns JSON                                                                                             |
| **Dependencies** | M18-T01                                                                                                                                                                                                  |
| **Detail**       | Use FastAPI (already a dependency via kailash). Wire each `PlatformAPI` method to a route. Add CORS middleware for the frontend. Add health check endpoint at `/health`.                                 |

### M18-T03: WebSocket endpoint for real-time updates

| Field            | Value                                                                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | Add a WebSocket endpoint that pushes real-time events (new audit anchors, held actions, posture changes) to connected dashboard clients.         |
| **Where**        | Modify: `src/care_platform/api/server.py` (add WebSocket route). New: `src/care_platform/api/events.py` (event bus for real-time notifications). |
| **Evidence**     | Test: connect via WebSocket, trigger an audit event, verify event received                                                                       |
| **Dependencies** | M18-T02                                                                                                                                          |

### M18-T04: Frontend shared components and layout

| Field            | Value                                                                                                                                                                                                                                         |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Create the shared React component library and layout for the dashboard: navigation sidebar, header, content area, status indicators, data tables.                                                                                             |
| **Where**        | `apps/web/components/layout/`, `apps/web/components/ui/`, `apps/web/lib/api.ts` (API client)                                                                                                                                                  |
| **Evidence**     | `cd apps/web && npm run build` succeeds; layout renders in browser                                                                                                                                                                            |
| **Dependencies** | M13-T05 (web scaffold exists), M18-T02 (API server exists)                                                                                                                                                                                    |
| **Detail**       | Components: Sidebar (navigation), Header (breadcrumbs, user context), StatusBadge (for verification levels, posture levels, bridge status), DataTable (sortable, filterable), ConstraintGauge (utilization visualization for each dimension). |

### M18-T05: API client with TypeScript types

| Field            | Value                                                                                                                                                                   |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Create a TypeScript API client that mirrors the Python `ApiResponse` model. Auto-generate types from the Python Pydantic models or manually define matching interfaces. |
| **Where**        | `apps/web/lib/api.ts`, `apps/web/types/care-platform.ts`                                                                                                                |
| **Evidence**     | TypeScript compilation succeeds; API client can fetch from backend                                                                                                      |
| **Dependencies** | M18-T02, M18-T04                                                                                                                                                        |

### M18-T06: Tests for M18 features

| Field            | Value                                                                    |
| ---------------- | ------------------------------------------------------------------------ |
| **What**         | Python unit tests for new API endpoints; TypeScript tests for API client |
| **Where**        | `tests/unit/api/test_dashboard_endpoints.py`, `apps/web/__tests__/`      |
| **Evidence**     | All tests pass                                                           |
| **Dependencies** | M18-T01 through M18-T05                                                  |

---

## M19: Constrained Organization Validation (Work Stream F)

**Goal**: Prove the CARE Platform IS a Constrained Organization by validating all five constitutive properties and three behavioral tests.

**Risk**: MEDIUM -- Validation, not implementation. But may surface gaps that require fixes.

**Prerequisite**: M16 and M17 must be complete -- runtime enforcement and integrity are preconditions for the behavioral tests.

### M19-T01: Validate five constitutive properties -- test harness

| Field            | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | Create a test harness that systematically verifies each of the five constitutive properties of a Constrained Organization. Each property maps to specific platform capabilities.                                                                                                                                                                                                                                                                                                                       |
| **Where**        | New: `tests/integration/test_constitutive_properties.py`                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| **Evidence**     | All five property tests pass                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **Dependencies** | M16, M17 (enforcement and integrity in place)                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **Detail**       | The five constitutive properties (from the Constrained Organization thesis): (1) Constraint Completeness -- all agent actions are subject to at least one constraint dimension, (2) Trust Verifiability -- every trust claim can be cryptographically verified, (3) Audit Continuity -- no gaps in the audit chain, (4) Knowledge Structurality -- knowledge compounds via workspace-as-knowledge-base, (5) Governance Coherence -- constraint envelopes derive from genesis via monotonic tightening. |

### M19-T02: Property 1 -- Constraint Completeness

| Field            | Value                                                                                                                                                                                    |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Test that proves every agent action in the platform is evaluated against at least one constraint dimension. Enumerate all action types and verify each has a constraint evaluation path. |
| **Where**        | Within `tests/integration/test_constitutive_properties.py`                                                                                                                               |
| **Evidence**     | Test passes: no action can execute without constraint evaluation                                                                                                                         |
| **Dependencies** | M16-T01 (ConstraintEnforcer), M19-T01                                                                                                                                                    |

### M19-T03: Property 2 -- Trust Verifiability

| Field            | Value                                                                                                                                                                |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Test that every trust claim (genesis, delegation, attestation) can be cryptographically verified. Walk the full trust chain and verify each record's signature/hash. |
| **Where**        | Within `tests/integration/test_constitutive_properties.py`                                                                                                           |
| **Evidence**     | Test passes: full chain verification succeeds; tampered record is detected                                                                                           |
| **Dependencies** | M17-T01 (hash-chain integrity), M19-T01                                                                                                                              |

### M19-T04: Property 3 -- Audit Continuity

| Field            | Value                                                                                                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Test that the audit chain has no gaps. Submit a sequence of actions, verify every action produced an audit anchor, verify the chain is contiguous. |
| **Where**        | Within `tests/integration/test_constitutive_properties.py`                                                                                         |
| **Evidence**     | Test passes: chain integrity verification succeeds with zero gaps                                                                                  |
| **Dependencies** | M16-T01 (enforcer ensures audit recording), M19-T01                                                                                                |

### M19-T05: Property 4 -- Knowledge Structurality

| Field            | Value                                                                                                                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | Test that knowledge compounds structurally via the workspace-as-knowledge-base pattern. Verify workspace phase transitions produce artifacts, and those artifacts are accessible in subsequent phases. |
| **Where**        | Within `tests/integration/test_constitutive_properties.py`                                                                                                                                             |
| **Evidence**     | Test passes: artifact from ANALYZE phase is accessible in IMPLEMENT phase                                                                                                                              |
| **Dependencies** | M14-T03 (workspace lifecycle), M19-T01                                                                                                                                                                 |

### M19-T06: Property 5 -- Governance Coherence

| Field            | Value                                                                                                                                                                      |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Test that all constraint envelopes derive from genesis via monotonic tightening. Bootstrap an org, then verify every agent's envelope is a valid tightening of its parent. |
| **Where**        | Within `tests/integration/test_constitutive_properties.py`                                                                                                                 |
| **Evidence**     | Test passes: full tightening chain from genesis to every leaf agent                                                                                                        |
| **Dependencies** | M13-T01 through M13-T04, M19-T01                                                                                                                                           |

### M19-T07: Behavioral test 1 -- Constraints enforced, not advisory

| Field            | Value                                                                                                                                                              |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | Test that constraints are actually enforced at runtime, not just advisory. Submit an action that violates a constraint and verify it is BLOCKED, not just FLAGGED. |
| **Where**        | New: `tests/integration/test_behavioral_tests.py`                                                                                                                  |
| **Evidence**     | Test passes: violating action is BLOCKED; audit shows rejection                                                                                                    |
| **Dependencies** | M16-T01 (ConstraintEnforcer)                                                                                                                                       |

### M19-T08: Behavioral test 2 -- Trust verifiable, not assumed

| Field            | Value                                                                                                                                                                                                    |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Test that trust is verified at action time, not assumed from initial delegation. Revoke an agent's trust chain, then verify subsequent actions are blocked even though the agent was previously trusted. |
| **Where**        | Within `tests/integration/test_behavioral_tests.py`                                                                                                                                                      |
| **Evidence**     | Test passes: post-revocation actions are BLOCKED                                                                                                                                                         |
| **Dependencies** | M16-T01, M16-T02 (authorization model)                                                                                                                                                                   |

### M19-T09: Behavioral test 3 -- Knowledge compounds structurally

| Field            | Value                                                                                                                                                                                                                               |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Test that knowledge from one CO cycle is available in the next. Run a workspace through a full ANALYZE->PLAN->IMPLEMENT->VALIDATE->CODIFY cycle, then start a new cycle and verify knowledge from the previous cycle is accessible. |
| **Where**        | Within `tests/integration/test_behavioral_tests.py`                                                                                                                                                                                 |
| **Evidence**     | Test passes: second-cycle agent can access first-cycle codified knowledge                                                                                                                                                           |
| **Dependencies** | M14-T03 (workspace lifecycle)                                                                                                                                                                                                       |

### M19-T10: End-to-end integration test -- CARE Platform IS a Constrained Organization

| Field            | Value                                                                                                                                                                                                              |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | Single comprehensive E2E test that proves the CARE Platform is a Constrained Organization: bootstrap a full org, execute agent actions, verify all five properties and three behavioral tests hold simultaneously. |
| **Where**        | New: `tests/integration/test_constrained_organization.py`                                                                                                                                                          |
| **Evidence**     | Test passes: comprehensive E2E covering bootstrap -> agent execution -> constraint enforcement -> trust verification -> audit chain verification -> knowledge compounding                                          |
| **Dependencies** | M19-T01 through M19-T09                                                                                                                                                                                            |

---

## M20: Frontend Dashboard Views (Work Stream E, Part 2)

**Goal**: Build the dashboard views that make the platform's trust state visible.

**Risk**: MEDIUM -- UI development with defined API contract from M18.

### M20-T01: Trust chain visualization page

| Field            | Value                                                                                                                                                                                                                       |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Interactive visualization showing genesis -> delegation -> agent trust chains. Nodes represent trust entities, edges represent delegations. Color-coded by trust chain state (ACTIVE=green, SUSPENDED=yellow, REVOKED=red). |
| **Where**        | `apps/web/app/trust-chains/page.tsx`, `apps/web/components/trust/TrustChainGraph.tsx`                                                                                                                                       |
| **Evidence**     | Page renders; API data populates the visualization; click on node shows detail panel                                                                                                                                        |
| **Dependencies** | M18-T04, M18-T05                                                                                                                                                                                                            |

### M20-T02: Constraint envelope dashboard

| Field            | Value                                                                                                                                                                         |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Dashboard showing all five constraint dimensions for a selected agent/envelope. Each dimension shows current utilization as a gauge (0-100%), limits, and boundary proximity. |
| **Where**        | `apps/web/app/envelopes/page.tsx`, `apps/web/app/envelopes/[id]/page.tsx`, `apps/web/components/constraints/DimensionGauge.tsx`                                               |
| **Evidence**     | Page renders; five dimension gauges display; utilization data from API                                                                                                        |
| **Dependencies** | M18-T04, M18-T05                                                                                                                                                              |

### M20-T03: Audit trail viewer

| Field            | Value                                                                                                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Searchable, filterable table of audit anchors. Filters: agent, time range, verification level, action type. Shows chain integrity status (contiguous/gap detected). |
| **Where**        | `apps/web/app/audit/page.tsx`, `apps/web/components/audit/AuditTable.tsx`, `apps/web/components/audit/AuditFilters.tsx`                                             |
| **Evidence**     | Page renders; table populates from API; filters work; chain integrity indicator visible                                                                             |
| **Dependencies** | M18-T04, M18-T05                                                                                                                                                    |

### M20-T04: Agent status and posture dashboard

| Field            | Value                                                                                                                                                                                               |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | Overview of all agents: current posture (PSEUDO_AGENT through DELEGATED), health status, last action timestamp, shadow enforcer metrics. Detail view shows posture history and upgrade eligibility. |
| **Where**        | `apps/web/app/agents/page.tsx`, `apps/web/app/agents/[id]/page.tsx`, `apps/web/components/agents/PostureBadge.tsx`                                                                                  |
| **Evidence**     | Page renders; agent cards show posture; detail view shows history                                                                                                                                   |
| **Dependencies** | M18-T04, M18-T05                                                                                                                                                                                    |

### M20-T05: Verification gradient monitoring

| Field            | Value                                                                                                                                      |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | Real-time display of AUTO_APPROVED / FLAGGED / HELD / BLOCKED counts, with trend charts over time. Connects to WebSocket for live updates. |
| **Where**        | `apps/web/app/verification/page.tsx`, `apps/web/components/verification/GradientChart.tsx`                                                 |
| **Evidence**     | Page renders; counts update via WebSocket; chart shows trend                                                                               |
| **Dependencies** | M18-T03 (WebSocket), M18-T04, M18-T05                                                                                                      |

### M20-T06: Workspace status views

| Field            | Value                                                                                                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **What**         | All workspaces with their current state (PROVISIONING/ACTIVE/ARCHIVED) and CO phase (ANALYZE through CODIFY). Bridge connections between workspaces shown as links. |
| **Where**        | `apps/web/app/workspaces/page.tsx`, `apps/web/components/workspaces/WorkspaceCard.tsx`, `apps/web/components/workspaces/BridgeConnections.tsx`                      |
| **Evidence**     | Page renders; workspace cards with state/phase; bridge lines between connected workspaces                                                                           |
| **Dependencies** | M14-T02, M14-T03, M18-T04, M18-T05                                                                                                                                  |

### M20-T07: Approval queue (HELD items)

| Field            | Value                                                                                                                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **What**         | Interactive approval queue showing all HELD actions awaiting human decision. Each item shows: agent, action, reason held, urgency, constraint details. Approve/Reject buttons that call the API. |
| **Where**        | `apps/web/app/approvals/page.tsx`, `apps/web/components/approvals/ApprovalCard.tsx`, `apps/web/components/approvals/ApprovalActions.tsx`                                                         |
| **Evidence**     | Page renders; HELD items display; Approve/Reject buttons call API and item moves to decided state                                                                                                |
| **Dependencies** | M18-T03 (WebSocket for real-time), M18-T04, M18-T05                                                                                                                                              |

### M20-T08: Frontend tests

| Field            | Value                                                                            |
| ---------------- | -------------------------------------------------------------------------------- |
| **What**         | Component tests for each dashboard view, integration tests for API communication |
| **Where**        | `apps/web/__tests__/`                                                            |
| **Evidence**     | `cd apps/web && npm test` passes                                                 |
| **Dependencies** | M20-T01 through M20-T07                                                          |

---

## Cross-Cutting Concerns

### pyproject.toml dependency additions (across milestones)

| Milestone | New Dependency                                   | Purpose                               |
| --------- | ------------------------------------------------ | ------------------------------------- |
| M15       | `jcs>=0.2.1`                                     | RFC 8785 canonical JSON serialization |
| M15       | `sd-jwt>=0.1.0` or `pyjwt[crypto]>=2.8.0`        | SD-JWT selective disclosure           |
| M18       | No new Python deps (FastAPI already via kailash) | --                                    |

### File count estimates

| Milestone | New Python files | Modified Python files | New Frontend files | New Test files |
| --------- | ---------------- | --------------------- | ------------------ | -------------- |
| M13       | 0                | 1 (pyproject.toml)    | ~10 (scaffold)     | 0              |
| M14       | 4                | 2                     | 0                  | 6              |
| M15       | 3                | 4                     | 0                  | 4              |
| M16       | 3                | 4                     | 0                  | 4              |
| M17       | 3                | 4                     | 0                  | 4              |
| M18       | 2                | 1                     | ~8                 | 2              |
| M19       | 0                | 0                     | 0                  | 3              |
| M20       | 0                | 0                     | ~20                | 1              |

---

## Risk Assessment

### Critical Risks

1. **M13 restructure breaks all imports** -- Mitigation: execute as a single atomic commit; run full test suite immediately; `pip install -e .` with `where = ["src"]` should make imports transparent. Prevention: validate with `pytest --co` before running full suite.

2. **M16 runtime enforcement introduces regressions** -- Mitigation: backward-compatible constructor (enforcer optional but logged warning when missing). Prevention: existing 1610 tests must pass after every task.

3. **M15 JCS migration breaks existing signatures** -- Mitigation: versioned serialization (canonical_version field). Prevention: keep old serialization path for verification of existing signatures.

### High Risks

4. **M17 hash-chain integrity on existing data** -- Existing delegation records have no hashes. Migration needed. Mitigation: compute hashes retroactively during bootstrap re-run.

5. **M20 frontend build pipeline** -- New technology layer. Mitigation: minimal scaffold first (M13-T05), iterate.

### Medium Risks

6. **M19 validation tests expose undiscovered gaps** -- This is actually desirable. Mitigation: treat discovered gaps as M16/M17 extensions.

---

## Success Criteria

After all 8 milestones are complete:

- [ ] Project uses Python `src/` layout best practice
- [ ] 1610+ existing tests still pass (plus ~200 new tests)
- [ ] All EATP v2.2 features are implemented with tests
- [ ] All three CARE lifecycle state machines are implemented
- [ ] Runtime constraint enforcement is mandatory (not bypassable)
- [ ] Trust chain records are cryptographically hash-chained
- [ ] Fail-closed behavior when trust store is unreachable
- [ ] Web dashboard renders all seven views
- [ ] The CARE Platform passes all five constitutive property tests
- [ ] The CARE Platform passes all three behavioral tests
- [ ] End-to-end test proves the platform IS a Constrained Organization
