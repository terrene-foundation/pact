# Final Requirements Breakdown: pact-platform v0.3.0

**Date**: 2026-03-24
**Inputs**: Delegate synthesis (#29), Repivot synthesis (#22), Boundary synthesis (#24), full codebase audit
**Status**: Ready for /todos approval

---

## Codebase Metrics (measured)

| Metric                                            | Count                              |
| ------------------------------------------------- | ---------------------------------- |
| Source files under `src/pact/`                    | ~156                               |
| `from pact.build.config.schema` imports in `src/` | 73 occurrences across 64 files     |
| `from pact.governance` imports in `src/`          | 104 occurrences across 29 files    |
| `from pact.trust` imports in `src/`               | ~135 occurrences across ~50 files  |
| `from pact.` imports in `tests/`                  | 1,034 occurrences across 185 files |
| Governance files (to delete, now in kailash-pact) | 30 files                           |
| Trust files (to triage)                           | 58 files                           |
| Test files total                                  | ~185                               |
| Test files importing `pact.governance`            | 37 files (198 occurrences)         |
| Test files importing `pact.build`                 | 142 files (297 occurrences)        |
| Test files importing `pact.trust`                 | 107 files (344 occurrences)        |

---

## M0: Platform Rename and Cleanup

The foundational milestone. Nothing else can proceed until the package namespace is resolved, governance duplication is eliminated, and the trust layer is triaged.

### TODO-0001: Create `src/pact_platform/` directory structure [S]

**What**: Create the new package root at `src/pact_platform/` with `__init__.py`.

**Acceptance criteria**:

- `src/pact_platform/__init__.py` exists with `__version__ = "0.3.0"`, copyright header, and public API exports
- `pyproject.toml` already points to `pact_platform.cli:main` (confirmed)
- `setuptools.packages.find` with `where = ["src"]` discovers `pact_platform`

**Dependencies**: None (first task)

---

### TODO-0002: Move `src/pact/build/` to `src/pact_platform/build/` [M]

**What**: Relocate the entire `build/` subtree. This contains:

- `build/config/` — `schema.py` (528 lines, 73 import sites), `env.py`, `defaults.py`, `loader.py`, `__init__.py`
- `build/org/` — `builder.py`, `generator.py`, `envelope_deriver.py`, `role_catalog.py`, `utils.py`
- `build/workspace/` — `models.py`, `coordinator.py`, `discovery.py`, `bridge.py`, `knowledge_policy.py`, `bridge_lifecycle.py`
- `build/cli/` — `__init__.py` (573+ lines), `__main__.py`
- `build/templates/` — `registry.py`, `__init__.py`
- `build/bootstrap.py`

**Files to move (20 .py files)**:

```
src/pact/build/__init__.py          -> src/pact_platform/build/__init__.py
src/pact/build/bootstrap.py         -> src/pact_platform/build/bootstrap.py
src/pact/build/config/__init__.py   -> src/pact_platform/build/config/__init__.py
src/pact/build/config/schema.py     -> src/pact_platform/build/config/schema.py
src/pact/build/config/env.py        -> src/pact_platform/build/config/env.py
src/pact/build/config/defaults.py   -> src/pact_platform/build/config/defaults.py
src/pact/build/config/loader.py     -> src/pact_platform/build/config/loader.py
src/pact/build/org/__init__.py      -> src/pact_platform/build/org/__init__.py
src/pact/build/org/builder.py       -> src/pact_platform/build/org/builder.py
src/pact/build/org/generator.py     -> src/pact_platform/build/org/generator.py
src/pact/build/org/envelope_deriver.py -> src/pact_platform/build/org/envelope_deriver.py
src/pact/build/org/role_catalog.py  -> src/pact_platform/build/org/role_catalog.py
src/pact/build/org/utils.py         -> src/pact_platform/build/org/utils.py
src/pact/build/workspace/__init__.py -> src/pact_platform/build/workspace/__init__.py
src/pact/build/workspace/models.py  -> src/pact_platform/build/workspace/models.py
src/pact/build/workspace/coordinator.py -> src/pact_platform/build/workspace/coordinator.py
src/pact/build/workspace/discovery.py -> src/pact_platform/build/workspace/discovery.py
src/pact/build/workspace/bridge.py  -> src/pact_platform/build/workspace/bridge.py
src/pact/build/workspace/knowledge_policy.py -> src/pact_platform/build/workspace/knowledge_policy.py
src/pact/build/workspace/bridge_lifecycle.py -> src/pact_platform/build/workspace/bridge_lifecycle.py
src/pact/build/cli/__init__.py      -> src/pact_platform/build/cli/__init__.py
src/pact/build/cli/__main__.py      -> src/pact_platform/build/cli/__main__.py
src/pact/build/templates/__init__.py -> src/pact_platform/build/templates/__init__.py
src/pact/build/templates/registry.py -> src/pact_platform/build/templates/registry.py
```

**Critical decision on `build/config/schema.py`**: This file defines types (`ConfidentialityLevel`, `TrustPostureLevel`, `ConstraintEnvelopeConfig`, `PactConfig`, `PlatformConfig`, etc.) that are now ALSO defined in `pact.governance.config` (from kailash-pact). The platform should import these from kailash-pact where possible, and only keep platform-specific types locally.

**Rewrite strategy for `schema.py`**: Replace the 528-line schema.py with a thin re-export shim:

```python
# src/pact_platform/build/config/schema.py
# Re-export governance config types from kailash-pact
from pact.governance.config import (
    AgentConfig, CONFIDENTIALITY_ORDER, CommunicationConstraintConfig,
    ConfidentialityLevel, ConstraintDimension, ConstraintEnvelopeConfig,
    DataAccessConstraintConfig, DepartmentConfig, FinancialConstraintConfig,
    GenesisConfig, GradientRuleConfig, OperationalConstraintConfig,
    OrgDefinition, PactConfig, PlatformConfig, TeamConfig,
    TemporalConstraintConfig, TrustPostureLevel, VerificationGradientConfig,
    VerificationLevel, WorkspaceConfig,
)
```

This means every file that imports `from pact.build.config.schema import X` changes to `from pact_platform.build.config.schema import X` (which re-exports from kailash-pact). Alternatively, those files can import directly from `pact.governance.config`.

**Acceptance criteria**:

- All 20+ files moved to `src/pact_platform/build/`
- `build/config/schema.py` is a re-export shim from `pact.governance.config`
- Internal imports within `build/` updated to `pact_platform.build.*`
- No governance type definitions duplicated (all come from kailash-pact)

**Dependencies**: TODO-0001

---

### TODO-0003: Move `src/pact/use/` to `src/pact_platform/use/` [M]

**What**: Relocate the entire `use/` subtree. This contains:

- `use/api/` — `server.py`, `endpoints.py` (1500+ lines), `events.py`, `shutdown.py`, `__init__.py`
- `use/execution/` — `runtime.py` (1200+ lines), `session.py`, `agent.py`, `approval.py`, `registry.py`, `lifecycle.py`, `kaizen_bridge.py`, `hook_enforcer.py`, `posture_enforcer.py`, `llm_backend.py`, `approver_auth.py`
- `use/execution/backends/` — `__init__.py`, `openai_backend.py`, `anthropic_backend.py`
- `use/observability/` — `logging.py`, `metrics.py`, `alerting.py`, `__init__.py`

**Files to move (25 .py files)**:

```
src/pact/use/__init__.py                          -> src/pact_platform/use/__init__.py
src/pact/use/api/__init__.py                      -> src/pact_platform/use/api/__init__.py
src/pact/use/api/server.py                        -> src/pact_platform/use/api/server.py
src/pact/use/api/endpoints.py                     -> src/pact_platform/use/api/endpoints.py
src/pact/use/api/events.py                        -> src/pact_platform/use/api/events.py
src/pact/use/api/shutdown.py                      -> src/pact_platform/use/api/shutdown.py
src/pact/use/execution/__init__.py                -> src/pact_platform/use/execution/__init__.py
src/pact/use/execution/runtime.py                 -> src/pact_platform/use/execution/runtime.py
src/pact/use/execution/session.py                 -> src/pact_platform/use/execution/session.py
src/pact/use/execution/agent.py                   -> src/pact_platform/use/execution/agent.py
src/pact/use/execution/approval.py                -> src/pact_platform/use/execution/approval.py
src/pact/use/execution/registry.py                -> src/pact_platform/use/execution/registry.py
src/pact/use/execution/lifecycle.py               -> src/pact_platform/use/execution/lifecycle.py
src/pact/use/execution/kaizen_bridge.py           -> src/pact_platform/use/execution/kaizen_bridge.py
src/pact/use/execution/hook_enforcer.py           -> src/pact_platform/use/execution/hook_enforcer.py
src/pact/use/execution/posture_enforcer.py        -> src/pact_platform/use/execution/posture_enforcer.py
src/pact/use/execution/llm_backend.py             -> src/pact_platform/use/execution/llm_backend.py
src/pact/use/execution/approver_auth.py           -> src/pact_platform/use/execution/approver_auth.py
src/pact/use/execution/backends/__init__.py       -> src/pact_platform/use/execution/backends/__init__.py
src/pact/use/execution/backends/openai_backend.py -> src/pact_platform/use/execution/backends/openai_backend.py
src/pact/use/execution/backends/anthropic_backend.py -> src/pact_platform/use/execution/backends/anthropic_backend.py
src/pact/use/observability/__init__.py            -> src/pact_platform/use/observability/__init__.py
src/pact/use/observability/logging.py             -> src/pact_platform/use/observability/logging.py
src/pact/use/observability/metrics.py             -> src/pact_platform/use/observability/metrics.py
src/pact/use/observability/alerting.py            -> src/pact_platform/use/observability/alerting.py
```

**Acceptance criteria**:

- All 25 files moved to `src/pact_platform/use/`
- Internal imports updated to `pact_platform.use.*`
- All `from pact.build.config.schema` imports rewritten to `from pact_platform.build.config.schema` or `from pact.governance.config`
- All `from pact.trust.*` imports rewritten to `from pact_platform.trust.*` (for kept files) or `from pact.*` (for kailash-pact governance types)

**Dependencies**: TODO-0001

---

### TODO-0004: Move `src/pact/examples/` to `src/pact_platform/examples/` [S]

**What**: Relocate examples. Contains:

- `examples/university/` — `org.py`, `clearance.py`, `barriers.py`, `demo.py`, `envelopes.py`, `__init__.py`
- `examples/foundation/` — `org.py`, `dm_team.py`, `dm_prompts.py`, `dm_runner.py`, `templates/__init__.py`, `__init__.py`

**Files (13 .py files)**: All files under `src/pact/examples/` move to `src/pact_platform/examples/`.

**Acceptance criteria**:

- All example files moved
- Imports within examples updated from `pact.build.*` to `pact_platform.build.*` (or `pact.governance.*` for governance types)
- Examples import governance primitives from `pact.governance` (kailash-pact) and platform services from `pact_platform`

**Dependencies**: TODO-0002 (examples import from build/config/schema)

---

### TODO-0005: Delete `src/pact/governance/` (superseded by kailash-pact) [M]

**What**: Delete the entire `src/pact/governance/` directory. All 30 files are now in kailash-pact and installed via `pip install kailash-pact>=0.2.0`.

**Files to delete (30 files)**:

```
src/pact/governance/__init__.py
src/pact/governance/access.py
src/pact/governance/addressing.py
src/pact/governance/agent.py
src/pact/governance/agent_mapping.py
src/pact/governance/audit.py
src/pact/governance/clearance.py
src/pact/governance/cli.py
src/pact/governance/compilation.py
src/pact/governance/context.py
src/pact/governance/decorators.py
src/pact/governance/engine.py
src/pact/governance/envelopes.py
src/pact/governance/envelope_adapter.py
src/pact/governance/explain.py
src/pact/governance/knowledge.py
src/pact/governance/middleware.py
src/pact/governance/store.py
src/pact/governance/testing.py
src/pact/governance/verdict.py
src/pact/governance/yaml_loader.py
src/pact/governance/api/__init__.py
src/pact/governance/api/auth.py
src/pact/governance/api/endpoints.py
src/pact/governance/api/events.py
src/pact/governance/api/router.py
src/pact/governance/api/schemas.py
src/pact/governance/stores/__init__.py
src/pact/governance/stores/backup.py
src/pact/governance/stores/sqlite.py
```

**Verification**: After deletion, `from pact.governance import GovernanceEngine` must resolve to the kailash-pact package (installed dependency), NOT local code.

**Acceptance criteria**:

- All 30 governance files deleted
- `python -c "from pact.governance import GovernanceEngine"` succeeds (resolves to kailash-pact)
- No remaining `from pact.governance` imports in `src/pact_platform/` that expect local files
- Files that imported from local governance now import from kailash-pact's `pact.governance`

**Dependencies**: TODO-0002, TODO-0003 (build and use must be moved first so their imports don't break)

---

### TODO-0006: Triage and move trust layer — DELETE superseded files [L]

**What**: Classify all 58 trust files. Delete those superseded by kailash-pact or kaizen-agents. Move the rest to `src/pact_platform/trust/`.

**Category 1: DELETE (superseded by kailash-pact governance primitives)**

These files implement concepts now in `pact.governance.*`:

```
src/pact/trust/attestation.py          — CapabilityAttestation (now re-exported from kailash.trust)
src/pact/trust/delegation.py           — DelegationManager (superseded by GovernanceEngine delegation)
src/pact/trust/genesis.py              — GenesisManager (imports pact.build.config.schema.GenesisConfig, superseded)
src/pact/trust/lifecycle.py            — Trust lifecycle (absorbed into GovernanceEngine)
src/pact/trust/posture.py              — TrustPosture (now from kailash.trust.TrustPosture)
src/pact/trust/scoring.py              — TrustScore (behavioral scoring — deprecated per boundary synthesis)
src/pact/trust/reasoning.py            — ReasoningTrace (EATP wrapper, ConfidentialityLevel now from kailash.trust)
src/pact/trust/decorators.py           — care_audited, care_verified, care_shadow (CARE decorators, EATP wrappers)
src/pact/trust/dual_binding.py         — DualBinding (EATP concept, wrapper)
src/pact/trust/revocation.py           — RevocationManager (EATP wrapper)
src/pact/trust/integrity.py            — TrustChainIntegrity (EATP wrapper)
src/pact/trust/messaging.py            — MessageRouter (agent messaging — kaizen-agents handles this)
src/pact/trust/uncertainty.py          — UncertaintyClassifier (behavioral — deprecated)
src/pact/trust/jcs.py                  — canonical_hash (JCS — thin wrapper, available from EATP)
src/pact/trust/sd_jwt.py               — SDJWTBuilder (selective disclosure — EATP feature)
src/pact/trust/eatp_bridge.py          — EATPBridge (bridge to kailash.trust — now direct import)
src/pact/trust/credentials.py          — CredentialManager (EATP concept)
src/pact/trust/bridge_trust.py         — BridgeTrustManager (workspace bridge trust — may keep)
src/pact/trust/bridge_posture.py       — bridge_verification_level (bridge posture helper)
src/pact/trust/authorization.py        — AuthorizationCheck (superseded by GovernanceEngine.verify_action)
```

**Category 2: DELETE (superseded by kaizen-agents governance subsystems)**

```
src/pact/trust/shadow_enforcer.py      — ShadowEnforcer (kaizen-agents has BudgetTracker + GovernedSupervisor)
src/pact/trust/shadow_enforcer_live.py — Live shadow enforcer (kaizen-agents subsystem)
```

**Category 3: KEEP and MOVE to `src/pact_platform/trust/` (platform-specific)**

These files provide platform-specific functionality not in kailash-pact or kaizen-agents:

```
src/pact/trust/constraint/envelope.py      — ConstraintEnvelope runtime evaluation (used by ExecutionRuntime)
src/pact/trust/constraint/gradient.py      — GradientEngine (used by ExecutionRuntime)
src/pact/trust/constraint/enforcement.py   — CareEnforcementPipeline
src/pact/trust/constraint/enforcer.py      — ConstraintEnforcer
src/pact/trust/constraint/middleware.py     — VerificationMiddleware
src/pact/trust/constraint/cache.py         — VerificationCache
src/pact/trust/constraint/circuit_breaker.py — CircuitBreaker
src/pact/trust/constraint/signing.py       — SignedEnvelope
src/pact/trust/constraint/bridge_envelope.py — compute_bridge_envelope
src/pact/trust/constraint/resolution.py    — resolve_constraints
src/pact/trust/constraint/verification_level.py — select_verification_level
src/pact/trust/constraint/__init__.py      — Re-exports
src/pact/trust/audit/anchor.py            — AuditAnchor, AuditChain (platform audit chain)
src/pact/trust/audit/pipeline.py           — Audit pipeline
src/pact/trust/audit/bridge_audit.py       — Bridge audit pairs
src/pact/trust/audit/__init__.py           — Re-exports
src/pact/trust/store/store.py             — TrustStore protocol, MemoryStore, FilesystemStore
src/pact/trust/store/sqlite_store.py      — SQLiteTrustStore
src/pact/trust/store/postgresql_store.py  — PostgreSQLTrustStore
src/pact/trust/store/backup.py            — backup_store, restore_store
src/pact/trust/store/health.py            — TrustStoreHealthCheck
src/pact/trust/store/cost_tracking.py     — CostTracker (used by API server)
src/pact/trust/store/versioning.py        — VersionTracker
src/pact/trust/store/posture_history.py   — PostureHistoryStore
src/pact/trust/store/migrations.py        — Schema migrations
src/pact/trust/store/audit_query.py       — AuditQuery, AuditReport
src/pact/trust/store/__init__.py          — Re-exports
src/pact/trust/store_isolation/            — 4 files (data.py, management.py, violations.py, __init__.py)
src/pact/trust/resilience/                — 2 files (failure_modes.py, __init__.py)
src/pact/trust/auth/                      — 2 files (firebase_admin.py, __init__.py)
src/pact/trust/__init__.py               — Main re-exports (rewrite to only export kept items)
```

**Approximately 22 files to DELETE, ~36 files to KEEP and MOVE.**

**Acceptance criteria**:

- ~22 superseded trust files deleted
- ~36 platform-specific trust files moved to `src/pact_platform/trust/`
- `src/pact_platform/trust/__init__.py` rewritten to only export kept items
- All imports from moved files updated to `pact_platform.trust.*`
- Imports that referenced deleted files rewritten to import from kailash-pact or removed

**Dependencies**: TODO-0002, TODO-0003 (build and use move first)

---

### TODO-0007: Delete `src/pact/build/verticals/` (dead shims) [S]

**What**: Delete the 5 vertical re-export shim files. These are dead code — the verticals now live in `src/pact/examples/`.

**Files to delete**:

```
src/pact/build/verticals/__init__.py
src/pact/build/verticals/dm_team.py
src/pact/build/verticals/dm_prompts.py
src/pact/build/verticals/dm_runner.py
src/pact/build/verticals/foundation.py
```

**Acceptance criteria**:

- All 5 files deleted
- No remaining imports of `pact.build.verticals` anywhere in the codebase

**Dependencies**: TODO-0002 (build move happens first)

---

### TODO-0008: Bulk rewrite imports in source files [L]

**What**: Rewrite ALL `from pact.` imports in `src/pact_platform/` to use the correct new paths. This is a mechanical bulk operation.

**Import rewrite rules** (applied in order):

| Old pattern                                | New pattern                                               | Rationale                          |
| ------------------------------------------ | --------------------------------------------------------- | ---------------------------------- |
| `from pact.build.config.schema import X`   | `from pact.governance.config import X`                    | Config types now from kailash-pact |
| `from pact.build.config.env import X`      | `from pact_platform.build.config.env import X`            | Platform-specific env config       |
| `from pact.build.config.loader import X`   | `from pact_platform.build.config.loader import X`         | Platform-specific config loader    |
| `from pact.build.config.defaults import X` | `from pact_platform.build.config.defaults import X`       | Platform-specific defaults         |
| `from pact.build.config import X`          | `from pact_platform.build.config import X`                | Platform-specific config package   |
| `from pact.build.org.X`                    | `from pact_platform.build.org.X`                          | Platform org builder               |
| `from pact.build.workspace.X`              | `from pact_platform.build.workspace.X`                    | Platform workspace                 |
| `from pact.build.cli.X`                    | `from pact_platform.build.cli.X`                          | Platform CLI                       |
| `from pact.build.bootstrap`                | `from pact_platform.build.bootstrap`                      | Platform bootstrap                 |
| `from pact.build.templates.X`              | `from pact_platform.build.templates.X`                    | Platform templates                 |
| `from pact.use.X`                          | `from pact_platform.use.X`                                | Platform execution/API             |
| `from pact.trust.X` (kept files)           | `from pact_platform.trust.X`                              | Platform trust layer               |
| `from pact.trust.X` (deleted files)        | `from pact.governance.X` or `from kailash.trust import X` | Redirect to kailash-pact           |
| `from pact.governance.X`                   | `from pact.governance.X` (NO CHANGE)                      | Already from kailash-pact          |
| `from pact.examples.X`                     | `from pact_platform.examples.X`                           | Platform examples                  |
| `import pact`                              | `import pact_platform`                                    | Top-level import                   |

**Estimated scope**: ~461 `from pact.` occurrences across 118 source files.

**Acceptance criteria**:

- Zero `from pact.build.` imports remain (all changed to `pact_platform.build.` or `pact.governance.config`)
- Zero `from pact.use.` imports remain (all changed to `pact_platform.use.`)
- Zero `from pact.trust.` imports to deleted files remain
- Kept trust imports changed to `pact_platform.trust.`
- `from pact.governance.` imports unchanged (they resolve to kailash-pact)
- `python -c "import pact_platform"` succeeds

**Dependencies**: TODO-0002 through TODO-0007 (all moves and deletions complete)

---

### TODO-0009: Bulk rewrite imports in test files [L]

**What**: Rewrite ALL `from pact.` imports in `tests/` to use the correct new paths. Same rewrite rules as TODO-0008.

**Estimated scope**: 1,034 `from pact.` occurrences across 185 test files.

**Additional test considerations**:

- Tests for governance modules (`tests/unit/governance/` — 37 files) should NOW import from `pact.governance` (kailash-pact). These tests verify the kailash-pact package works correctly in the platform context.
- Tests for trust modules (kept) should import from `pact_platform.trust.*`
- Tests for build/use modules should import from `pact_platform.build.*` / `pact_platform.use.*`
- `tests/integration/conftest.py` (175 lines) needs special attention — it imports from build, trust, use, and references `scripts/seed_demo.py`

**Acceptance criteria**:

- All 185 test files import from correct packages
- `pytest --collect-only` shows zero collection errors
- No `ModuleNotFoundError` on import

**Dependencies**: TODO-0008

---

### TODO-0010: Delete `src/pact/` remnant and create compatibility shim [S]

**What**: After all moves and deletions, `src/pact/` should be empty except possibly for `__init__.py`. Delete the remnant directory entirely.

Optionally create a thin `src/pact_platform/_compat.py` that provides backward-compatible re-exports for any external consumers (if needed).

**Acceptance criteria**:

- `src/pact/` directory does not exist (or only contains `__init__.py` if needed for Python path reasons)
- The `pact` namespace is entirely owned by kailash-pact (no local code)
- `from pact.governance import GovernanceEngine` resolves to kailash-pact
- `from pact_platform.use.api.server import create_app` works

**Dependencies**: TODO-0008, TODO-0009

---

### TODO-0011: Update `pyproject.toml` and `__init__.py` version consistency [S]

**What**: Ensure version is consistent and entry points are correct.

**Changes**:

- Verify `src/pact_platform/__init__.py` has `__version__ = "0.3.0"` matching pyproject.toml
- Verify `project.scripts.pact = "pact_platform.cli:main"` works
- Create `src/pact_platform/cli.py` that imports from `pact_platform.build.cli`
- Verify `tool.setuptools.packages.find` discovers `pact_platform` (not `pact`)

**Acceptance criteria**:

- `python -c "import pact_platform; print(pact_platform.__version__)"` prints `0.3.0`
- `pact --help` works (via entry point)
- `pip install -e .` installs correctly

**Dependencies**: TODO-0008

---

### TODO-0012: Fix test suite — green on `pytest` [L]

**What**: After all moves, rewrites, and deletions, fix any remaining test failures.

**Expected issues**:

- Fixture imports in conftest files
- Relative import paths in test helpers
- `scripts/seed_demo.py` references to old paths
- Integration test conftest (175 lines) needs thorough rewrite
- Property tests (hypothesis) may need fixture updates
- ~37 governance test files may need to import from kailash-pact instead of local governance

**Acceptance criteria**:

- `pytest` runs with zero collection errors
- All previously-passing tests still pass
- Governance tests import from `pact.governance` (kailash-pact) and verify the installed package
- Platform tests import from `pact_platform` and verify platform-specific code

**Dependencies**: TODO-0009, TODO-0010, TODO-0011

---

### TODO-0013: Update CLAUDE.md and rule files for new paths [S]

**What**: Update all rule files and CLAUDE.md that reference `src/pact/` paths.

**Files to update**:

- `CLAUDE.md` — Architecture overview, module paths, import examples
- `.claude/rules/governance.md` — Scope paths (`src/pact/governance/**` becomes `src/pact_platform/` + kailash-pact references)
- `.claude/rules/boundary-test.md` — Scope path
- `.claude/rules/trust-plane-security.md` — Scope paths
- `.claude/rules/pact-governance.md` — Scope paths and import examples

**Acceptance criteria**:

- All rule files reference correct paths
- CLAUDE.md architecture section reflects `pact_platform` package structure
- No references to deleted `src/pact/governance/` in rules

**Dependencies**: TODO-0010

---

## M1: Work Management DataFlow Models

Build the data persistence layer for the work management system using DataFlow. These models track objectives, requests, work sessions, artifacts, decisions, findings, and pools.

### TODO-1001: DataFlow model — AgenticObjective [S]

**What**: Create `src/pact_platform/models/objective.py` with DataFlow model for high-level objectives submitted by humans.

**Fields**: `id` (UUID), `title` (str), `description` (text), `submitted_by` (str), `status` (enum: draft/active/completed/cancelled), `priority` (enum: low/medium/high/critical), `created_at` (datetime), `updated_at` (datetime), `org_address` (str, D/T/R address of owning unit), `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model generates CRUD nodes (Create/Read/Update/Delete/List)
- Migration script generated via Alembic
- Unit test: create, read, list, update status
- Frozen dataclass for the model schema

**Dependencies**: M0 complete

---

### TODO-1002: DataFlow model — AgenticRequest [S]

**What**: Create `src/pact_platform/models/request.py`. Represents a decomposed work request derived from an objective.

**Fields**: `id` (UUID), `objective_id` (FK to AgenticObjective), `title` (str), `description` (text), `agent_address` (str, assigned D/T/R role), `status` (enum: pending/assigned/in_progress/held/completed/failed), `priority` (enum), `created_at`, `updated_at`, `estimated_cost` (float), `actual_cost` (float), `governance_verdict` (str), `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model with FK relationship to AgenticObjective
- CRUD nodes auto-generated
- Migration generated
- Unit test: create request, link to objective, update status

**Dependencies**: TODO-1001

---

### TODO-1003: DataFlow model — AgenticWorkSession [S]

**What**: Create `src/pact_platform/models/work_session.py`. Tracks an agent's active work session.

**Fields**: `id` (UUID), `request_id` (FK), `agent_id` (str), `started_at` (datetime), `ended_at` (datetime, nullable), `status` (enum: active/paused/completed/failed/held), `trust_posture` (str), `envelope_snapshot` (JSON), `cost_accrued` (float), `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model with FK to AgenticRequest
- Auto-generated nodes
- Migration
- Unit test: start session, track cost, end session

**Dependencies**: TODO-1002

---

### TODO-1004: DataFlow model — AgenticArtifact [S]

**What**: Create `src/pact_platform/models/artifact.py`. Represents output produced by an agent.

**Fields**: `id` (UUID), `request_id` (FK), `session_id` (FK), `title` (str), `artifact_type` (enum: document/code/analysis/report/data), `content` (text), `clearance_level` (str, maps to ConfidentialityLevel), `created_at`, `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model with FKs
- Clearance level stored as string, validated against `ConfidentialityLevel` enum
- Auto-generated nodes
- Migration and unit test

**Dependencies**: TODO-1003

---

### TODO-1005: DataFlow model — AgenticDecision [S]

**What**: Create `src/pact_platform/models/decision.py`. Records governance decisions (HELD actions awaiting human approval).

**Fields**: `id` (UUID), `request_id` (FK), `session_id` (FK), `action_description` (str), `governance_verdict` (enum: auto_approved/flagged/held/blocked), `reason` (text), `constraint_dimension` (str), `envelope_snapshot` (JSON), `decided_by` (str, nullable — human approver), `decided_at` (datetime, nullable), `resolution` (enum: approved/rejected/escalated, nullable), `created_at`, `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model
- Supports the approval queue workflow (decision starts as HELD, gets resolved)
- Auto-generated nodes
- Migration and unit test

**Dependencies**: TODO-1001

---

### TODO-1006: DataFlow model — AgenticReviewDecision [S]

**What**: Create `src/pact_platform/models/review.py`. Human review of agent-produced artifacts.

**Fields**: `id` (UUID), `artifact_id` (FK), `reviewer` (str), `decision` (enum: approved/revision_requested/rejected), `comments` (text), `created_at`, `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model with FK to AgenticArtifact
- Auto-generated nodes
- Migration and unit test

**Dependencies**: TODO-1004

---

### TODO-1007: DataFlow model — AgenticFinding [S]

**What**: Create `src/pact_platform/models/finding.py`. Issues or observations raised during agent execution.

**Fields**: `id` (UUID), `session_id` (FK), `severity` (enum: info/low/medium/high/critical), `category` (str), `description` (text), `resolved` (bool), `resolved_at` (datetime, nullable), `created_at`, `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model
- Auto-generated nodes
- Migration and unit test

**Dependencies**: TODO-1003

---

### TODO-1008: DataFlow model — AgenticPool [S]

**What**: Create `src/pact_platform/models/pool.py`. Agent pools for work distribution.

**Fields**: `id` (UUID), `name` (str), `description` (text), `org_address` (str, D/T/R unit that owns pool), `max_concurrent` (int), `status` (enum: active/paused/draining), `created_at`, `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model
- Auto-generated nodes
- Migration and unit test

**Dependencies**: TODO-1001

---

### TODO-1009: DataFlow model — AgenticPoolMembership [S]

**What**: Create `src/pact_platform/models/pool_membership.py`. Maps agents to pools.

**Fields**: `id` (UUID), `pool_id` (FK to AgenticPool), `agent_id` (str), `role_address` (str, D/T/R address), `joined_at` (datetime), `left_at` (datetime, nullable), `status` (enum: active/suspended/removed)

**Acceptance criteria**:

- DataFlow model with FK to AgenticPool
- Auto-generated nodes
- Migration and unit test

**Dependencies**: TODO-1008

---

### TODO-1010: DataFlow model — Run [S]

**What**: Create `src/pact_platform/models/run.py`. Tracks an execution run (may contain multiple work sessions).

**Fields**: `id` (UUID), `objective_id` (FK), `started_at` (datetime), `ended_at` (datetime, nullable), `status` (enum: running/completed/failed/cancelled), `total_cost` (float), `agent_count` (int), `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model with FK to AgenticObjective
- Auto-generated nodes
- Migration and unit test

**Dependencies**: TODO-1001

---

### TODO-1011: DataFlow model — ExecutionMetric [S]

**What**: Create `src/pact_platform/models/metric.py`. Time-series metrics for dashboard visualization.

**Fields**: `id` (UUID), `run_id` (FK, nullable), `metric_type` (str), `value` (float), `unit` (str), `recorded_at` (datetime), `agent_id` (str, nullable), `metadata` (JSON)

**Acceptance criteria**:

- DataFlow model
- Supports time-range queries for dashboard
- Auto-generated nodes
- Migration and unit test

**Dependencies**: TODO-1001

---

### TODO-1012: Alembic migration infrastructure [M]

**What**: Set up Alembic migration environment for all 11 DataFlow models.

**Components**:

- `alembic.ini` configuration
- `alembic/env.py` with DataFlow model imports
- Initial migration that creates all 11 tables
- SQLite (dev default) + PostgreSQL (production) support

**Acceptance criteria**:

- `alembic upgrade head` creates all tables on fresh SQLite
- `alembic upgrade head` creates all tables on PostgreSQL (when configured)
- `alembic downgrade base` drops all tables cleanly
- Integration test: migrate up, insert data, migrate down

**Dependencies**: TODO-1001 through TODO-1011

---

## M2: Work Management API

FastAPI routers for the work management system, mounted on the existing API server.

### TODO-2001: API router — Objectives [M]

**What**: Create `src/pact_platform/use/api/routers/objectives.py`. CRUD + list + status transitions for objectives.

**Endpoints**:

- `POST /api/v1/objectives` — Create objective
- `GET /api/v1/objectives` — List objectives (with status filter, pagination)
- `GET /api/v1/objectives/{id}` — Get objective detail
- `PATCH /api/v1/objectives/{id}` — Update objective (title, description, priority)
- `POST /api/v1/objectives/{id}/activate` — Activate objective (triggers decomposition)
- `POST /api/v1/objectives/{id}/cancel` — Cancel objective

**Acceptance criteria**:

- All 6 endpoints implemented with Pydantic request/response schemas
- Input validation (title length, priority enum)
- 404 on missing objective
- Integration test with httpx AsyncClient

**Dependencies**: TODO-1001, M0 complete

---

### TODO-2002: API router — Requests [M]

**What**: Create `src/pact_platform/use/api/routers/requests.py`. View and manage work requests.

**Endpoints**:

- `GET /api/v1/requests` — List requests (filter by objective, status, agent)
- `GET /api/v1/requests/{id}` — Get request detail
- `POST /api/v1/requests/{id}/assign` — Assign to agent/pool
- `POST /api/v1/requests/{id}/hold` — Manually hold request
- `POST /api/v1/requests/{id}/resume` — Resume held request

**Acceptance criteria**:

- All 5 endpoints implemented
- Request-objective relationship visible in responses
- Agent assignment validates D/T/R address
- Integration test

**Dependencies**: TODO-1002, TODO-2001

---

### TODO-2003: API router — Approvals [M]

**What**: Create `src/pact_platform/use/api/routers/approvals.py`. Human approval queue for HELD governance decisions.

**Endpoints**:

- `GET /api/v1/approvals` — List pending approvals (filter by urgency, constraint dimension)
- `GET /api/v1/approvals/{id}` — Get approval detail (includes governance context)
- `POST /api/v1/approvals/{id}/approve` — Approve held action
- `POST /api/v1/approvals/{id}/reject` — Reject held action
- `POST /api/v1/approvals/{id}/escalate` — Escalate to higher authority

**Acceptance criteria**:

- All 5 endpoints implemented
- Approval creates audit anchor
- Rejected action transitions to BLOCKED
- Approved action transitions to FLAGGED (re-evaluation) or AUTO_APPROVED
- WebSocket event emitted on approval/rejection
- Integration test

**Dependencies**: TODO-1005, TODO-2001

---

### TODO-2004: API router — Artifacts [M]

**What**: Create `src/pact_platform/use/api/routers/artifacts.py`. View agent-produced work.

**Endpoints**:

- `GET /api/v1/artifacts` — List artifacts (filter by request, type, clearance level)
- `GET /api/v1/artifacts/{id}` — Get artifact detail (respects clearance — 403 if insufficient)
- `POST /api/v1/artifacts/{id}/review` — Submit review decision

**Acceptance criteria**:

- All 3 endpoints implemented
- Clearance enforcement: requester's clearance level checked against artifact's clearance
- Review creates AgenticReviewDecision record
- Integration test

**Dependencies**: TODO-1004, TODO-1006, TODO-2001

---

### TODO-2005: API router — Pools [M]

**What**: Create `src/pact_platform/use/api/routers/pools.py`. Agent pool management.

**Endpoints**:

- `POST /api/v1/pools` — Create pool
- `GET /api/v1/pools` — List pools
- `GET /api/v1/pools/{id}` — Get pool detail (includes members)
- `PATCH /api/v1/pools/{id}` — Update pool config
- `POST /api/v1/pools/{id}/members` — Add agent to pool
- `DELETE /api/v1/pools/{id}/members/{agent_id}` — Remove agent from pool

**Acceptance criteria**:

- All 6 endpoints implemented
- Pool org_address validated against D/T/R grammar
- Max concurrent limit enforced on pool membership
- Integration test

**Dependencies**: TODO-1008, TODO-1009, TODO-2001

---

### TODO-2006: API router — Metrics + Dashboard data [M]

**What**: Create `src/pact_platform/use/api/routers/metrics.py`. Dashboard data endpoints.

**Endpoints**:

- `GET /api/v1/metrics/summary` — Aggregate metrics (total objectives, completion rate, cost, held actions)
- `GET /api/v1/metrics/timeseries` — Time-series data for charts (filter by metric type, time range)
- `GET /api/v1/metrics/cost` — Cost breakdown by agent, pool, objective
- `GET /api/v1/metrics/governance` — Governance verdict distribution

**Acceptance criteria**:

- All 4 endpoints implemented
- Time-series supports hour/day/week granularity
- Cost endpoint respects clearance (redacts agent costs if insufficient clearance)
- Integration test

**Dependencies**: TODO-1011, TODO-2001

---

### TODO-2007: Mount routers on existing API server [M]

**What**: Mount all 6 new routers on the existing FastAPI server in `src/pact_platform/use/api/server.py`.

**Changes**:

- Import and mount objective, request, approval, artifact, pool, and metric routers
- Create `src/pact_platform/use/api/routers/__init__.py`
- Wire DataFlow connection to app lifespan
- Connection pool configuration following `rules/connection-pool.md`

**Acceptance criteria**:

- All new endpoints accessible via the running server
- DataFlow connection established at startup, closed at shutdown
- Pool configuration validates against `rules/connection-pool.md`
- Health endpoint still works
- Existing governance endpoints (from kailash-pact router) still mounted
- Full API test: start server, hit all new endpoints

**Dependencies**: TODO-2001 through TODO-2006

---

### TODO-2008: Service — Approval queue (DataFlow-backed) [M]

**What**: Create `src/pact_platform/services/approval_service.py`. Replaces the in-memory ApprovalQueue with DataFlow-backed persistence.

**Responsibilities**:

- Create AgenticDecision records when governance HOLDS an action
- List pending decisions with filtering
- Process approval/rejection (update decision, emit event, resume execution)
- Escalation logic (move to higher authority in D/T/R hierarchy)

**Acceptance criteria**:

- ApprovalService wraps DataFlow operations for AgenticDecision
- HELD actions create decisions automatically
- Approval/rejection creates audit anchor
- Service is injected via FastAPI dependency injection
- Unit test + integration test

**Dependencies**: TODO-1005, TODO-2003

---

### TODO-2009: Service — Cost tracking (DataFlow-backed) [M]

**What**: Create `src/pact_platform/services/cost_service.py`. Extends existing CostTracker with DataFlow persistence.

**Responsibilities**:

- Record costs per work session
- Aggregate costs by objective, agent, pool, time period
- Budget enforcement (check remaining budget before allowing action)
- NaN/Inf validation on all cost values (per `rules/pact-governance.md` Rule 9)

**Acceptance criteria**:

- CostService wraps DataFlow operations for ExecutionMetric
- All cost values validated with `math.isfinite()`
- Budget check returns BLOCKED if budget exceeded
- Integration test: submit objective, accrue costs, check budget

**Dependencies**: TODO-1011, TODO-1003

---

## M3: Admin CLI

Click-based CLI commands for platform administration.

### TODO-3001: CLI command — `pact org create` [S]

**What**: Create organization from YAML definition file.

**Behavior**: Parse YAML using `load_org_yaml()` (from kailash-pact), compile org tree, persist to DataFlow.

**Acceptance criteria**:

- `pact org create org.yaml` creates org and prints summary
- Validates D/T/R grammar during compilation
- Error messages explain grammar violations clearly
- Unit test with CLI runner

**Dependencies**: M0 complete, TODO-1001

---

### TODO-3002: CLI command — `pact org list` [S]

**What**: List all organizations and their structure.

**Behavior**: Query DataFlow for orgs, display tree structure using `rich` formatting.

**Acceptance criteria**:

- `pact org list` shows all orgs with department/team/role counts
- `pact org list --tree` shows full D/T/R tree
- Unit test

**Dependencies**: TODO-3001

---

### TODO-3003: CLI command — `pact clearance grant` [S]

**What**: Grant knowledge clearance to a role.

**Behavior**: `pact clearance grant <role-address> <level>` — validates address, validates level enum, persists via GovernanceEngine.

**Acceptance criteria**:

- `pact clearance grant D1-R1-T1-R1 CONFIDENTIAL` works
- Invalid address format rejected with grammar explanation
- Invalid clearance level rejected with valid options listed
- Emits audit anchor
- Unit test

**Dependencies**: M0 complete

---

### TODO-3004: CLI command — `pact envelope show` [S]

**What**: Display effective envelope for a role address.

**Behavior**: `pact envelope show <role-address>` — resolves role, task, and effective envelopes using `compute_effective_envelope()` from kailash-pact.

**Acceptance criteria**:

- Shows all 5 constraint dimensions with current values
- Shows monotonic tightening chain (parent -> child)
- Rich table formatting
- Unit test

**Dependencies**: M0 complete

---

### TODO-3005: CLI command — `pact bridge create` [S]

**What**: Create a knowledge sharing bridge between units.

**Behavior**: `pact bridge create <source-address> <target-address> --policy <policy.yaml>` — creates a PactBridge with KnowledgeSharePolicy.

**Acceptance criteria**:

- Creates bridge with validated addresses
- Policy file defines allowed compartments and clearance requirements
- Emits audit anchor
- Unit test

**Dependencies**: M0 complete

---

### TODO-3006: CLI command — `pact audit export` [M]

**What**: Export audit trail for compliance reporting.

**Behavior**: `pact audit export --format json|csv --from <date> --to <date> --output <file>` — queries AuditChain and formats for export.

**Acceptance criteria**:

- JSON and CSV output formats
- Date range filtering
- Includes all governance decisions, clearance grants, envelope changes, bridge operations
- Tamper-evidence verification during export (validates hash chain)
- Unit test

**Dependencies**: M0 complete

---

### TODO-3007: CLI command — `pact agent register` [S]

**What**: Register an agent in the platform.

**Behavior**: `pact agent register <name> --role <role-address> --capabilities <cap1,cap2>` — creates agent record, maps to D/T/R role.

**Acceptance criteria**:

- Creates agent registration with role mapping
- Validates role address exists in compiled org
- Validates capabilities against registered tools
- Unit test

**Dependencies**: M0 complete, TODO-1008

---

### TODO-3008: CLI command — `pact agent status` [S]

**What**: Show agent status and activity.

**Behavior**: `pact agent status [agent-id]` — shows agent status, current work session, trust posture, cost accrued.

**Acceptance criteria**:

- Without agent-id: shows all agents in table format
- With agent-id: shows detailed status including active sessions, governance verdicts, cost history
- Rich formatting
- Unit test

**Dependencies**: TODO-3007, TODO-1003

---

## M4: GovernedSupervisor Wiring

Connect the platform to kaizen-agents' GovernedSupervisor for agent orchestration.

### TODO-4001: DelegateProtocol interface [M]

**What**: Create `src/pact_platform/delegate/protocol.py`. Abstract interface between the platform and agent execution engines.

**Interface**:

```python
class DelegateProtocol(Protocol):
    async def submit_objective(self, objective: AgenticObjective, envelope: ConstraintEnvelopeConfig) -> str:
        """Submit objective for decomposition and execution. Returns run_id."""

    async def get_run_status(self, run_id: str) -> RunStatus:
        """Get current status of an execution run."""

    async def cancel_run(self, run_id: str) -> None:
        """Cancel a running execution."""

    async def resume_held(self, decision_id: str, resolution: str) -> None:
        """Resume a HELD action after human approval."""
```

**Acceptance criteria**:

- Protocol defined with full type annotations
- RunStatus dataclass (frozen) with status, progress, cost, agent states
- SimpleDelegateExecutor implements protocol using existing ExecutionRuntime
- Unit test: submit objective via SimpleDelegateExecutor, verify lifecycle

**Dependencies**: M0 complete, M1 complete (needs DataFlow models)

---

### TODO-4002: GovernedSupervisor adapter [L]

**What**: Create `src/pact_platform/delegate/supervisor_adapter.py`. Adapts GovernedSupervisor (from kaizen-agents) to DelegateProtocol.

**Key challenge**: Type conversion between three envelope representations:

1. `pact.governance.config.ConstraintEnvelopeConfig` (Pydantic, from kailash-pact config)
2. `pact_platform.trust.constraint.envelope.ConstraintEnvelope` (runtime evaluation dataclass)
3. `kaizen_agents.governance.ConstraintEnvelope` (kaizen-agents dataclass with dict fields)

**Adapter responsibilities**:

- Convert ConstraintEnvelopeConfig -> kaizen-agents ConstraintEnvelope at delegation time
- Convert kaizen-agents GovernanceVerdict -> platform AgenticDecision at HELD time
- Convert kaizen-agents PlanEvent -> platform WebSocket events for dashboard
- Map BudgetTracker state -> platform cost tracking

**Acceptance criteria**:

- Adapter converts between all three envelope types correctly
- Monotonic tightening preserved across type boundaries (invariant test)
- NaN/Inf rejected at every type boundary (`math.isfinite()`)
- HELD verdicts create AgenticDecision records in DataFlow
- Unit test: submit objective through adapter, verify governance checks fire
- Integration test: full lifecycle through GovernedSupervisor (requires kaizen-agents optional dep)

**Dependencies**: TODO-4001

---

### TODO-4003: Event bridge — GovernedSupervisor events to WebSocket [M]

**What**: Create `src/pact_platform/delegate/event_bridge.py`. Converts kaizen-agents PlanEvent emissions into WebSocket events for real-time dashboard updates.

**Event mapping**:
| kaizen-agents event | Platform WebSocket event |
|---------------------|--------------------------|
| PlanCreated | `objective.plan_created` |
| StepStarted | `request.step_started` |
| StepCompleted | `request.step_completed` |
| GovernanceHeld | `approval.held` |
| GovernanceResumed | `approval.resumed` |
| BudgetWarning | `cost.warning` |
| RunCompleted | `objective.completed` |
| RunFailed | `objective.failed` |

**Acceptance criteria**:

- Event bridge subscribes to GovernedSupervisor event stream
- Converts each event type to platform WebSocket format
- Events emitted on existing event_bus (from `pact_platform.use.api.events`)
- Dashboard receives real-time updates
- Unit test: emit kaizen event, verify WebSocket event shape

**Dependencies**: TODO-4002

---

### TODO-4004: HELD verdict bridge [M]

**What**: Create `src/pact_platform/delegate/held_bridge.py`. When GovernedSupervisor's BudgetTracker or any governance subsystem issues a HELD verdict, the bridge creates an AgenticDecision in DataFlow and pauses execution until human resolves it.

**Flow**:

1. GovernedSupervisor governance check returns HELD
2. Bridge creates AgenticDecision (status=held, reason, envelope_snapshot)
3. Bridge pauses the GovernedSupervisor's execution loop
4. Human approves/rejects via API (TODO-2003)
5. Bridge resumes GovernedSupervisor with resolution

**Acceptance criteria**:

- HELD verdict creates AgenticDecision automatically
- Execution pauses (not busy-waits) until resolution
- Approval resumes execution within same session
- Rejection cancels the work session
- Timeout configurable (default: held actions expire after 24h -> auto-reject)
- Unit test: trigger HELD, approve, verify resume
- Unit test: trigger HELD, reject, verify cancel

**Dependencies**: TODO-4002, TODO-2008

---

## M5: Frontend Updates

New pages for the work management system.

### TODO-5001: Web page — Objective Management [L]

**What**: Dashboard page for creating, viewing, and managing objectives.

**Components**:

- Objective list with status badges and priority indicators
- Objective detail view with decomposed requests tree
- Create objective form
- Cost tracking per objective
- WebSocket-driven real-time status updates

**Acceptance criteria**:

- Page loads and displays objectives from API
- Create form submits and shows new objective
- Status transitions reflected in real-time
- Cost totals update as work progresses

**Dependencies**: TODO-2001, TODO-4003

---

### TODO-5002: Web page — Approval Queue [L]

**What**: Dashboard page for human approval of HELD governance decisions.

**Components**:

- Pending approvals list with urgency sorting
- Approval detail view with full governance context (which constraint triggered, what the agent attempted, envelope state)
- Approve/Reject/Escalate buttons
- Audit trail for each decision

**Acceptance criteria**:

- Page loads pending approvals
- Detail view shows governance context in understandable format
- Approve/Reject immediately updates state and emits WebSocket event
- Escalate moves decision to next D/T/R authority level

**Dependencies**: TODO-2003, TODO-4004

---

### TODO-5003: Web page — Pool Management [M]

**What**: Dashboard page for managing agent pools.

**Components**:

- Pool list with member counts and status
- Pool detail with member list and activity metrics
- Add/remove agents from pool
- Pool configuration (max concurrent, status)

**Acceptance criteria**:

- Pool CRUD operations work through UI
- Agent membership management works
- Activity metrics displayed correctly

**Dependencies**: TODO-2005

---

### TODO-5004: Web page — Interactive Org Builder [L]

**What**: Visual tool for building organizational structures using drag-and-drop.

**Components**:

- D/T/R tree visualization (departments, teams, roles)
- Drag-and-drop to reorder/restructure
- Envelope configuration per role (sliders for constraint dimensions)
- Clearance level assignment per role
- Export to YAML
- Grammar validation in real-time (highlights violations)

**Acceptance criteria**:

- Visual org tree renders from existing org data
- Drag-and-drop restructuring maintains D/T/R grammar invariant
- Envelope configuration produces valid ConstraintEnvelopeConfig
- Export produces valid YAML that `pact org create` accepts
- Grammar violations highlighted immediately (not on save)

**Dependencies**: M0 complete (uses GovernanceEngine from kailash-pact directly)

---

## M6: Integration Layer

Webhooks, notifications, and LLM management.

### TODO-6001: Webhook adapter — Slack [M]

**What**: Create `src/pact_platform/integrations/slack.py`. Send governance events to Slack channels.

**Events to notify**:

- Objective created/completed
- Action HELD (requires approval)
- Budget warning
- Agent error/failure

**Acceptance criteria**:

- Slack webhook sends formatted messages
- Configurable channel per event type
- Rate limiting (max 1 message/second)
- Unit test with mock webhook

**Dependencies**: TODO-4003

---

### TODO-6002: Webhook adapter — Discord [S]

**What**: Create `src/pact_platform/integrations/discord.py`. Discord webhook notifications.

**Acceptance criteria**: Same structure as Slack adapter, different payload format. Unit test with mock.

**Dependencies**: TODO-6001 (shared base adapter)

---

### TODO-6003: Webhook adapter — Teams [S]

**What**: Create `src/pact_platform/integrations/teams.py`. Microsoft Teams webhook notifications.

**Acceptance criteria**: Same structure as Slack adapter, Adaptive Card format. Unit test with mock.

**Dependencies**: TODO-6001 (shared base adapter)

---

### TODO-6004: Notification service [M]

**What**: Create `src/pact_platform/services/notification_service.py`. Multi-channel notification routing.

**Responsibilities**:

- Route events to configured channels (Slack, Discord, Teams, email)
- User notification preferences (which events, which channels)
- Deduplication (don't spam same event to same user)
- Batch similar events (10 FLAGGED actions -> 1 summary)

**Acceptance criteria**:

- Notification service dispatches to configured adapters
- User preferences respected
- Deduplication works
- Batch mode reduces noise
- Unit test

**Dependencies**: TODO-6001, TODO-6002, TODO-6003

---

### TODO-6005: LLM provider management [M]

**What**: Create `src/pact_platform/services/llm_service.py`. BYO API keys for LLM providers.

**Responsibilities**:

- Provider registry (OpenAI, Anthropic, etc.)
- API key management via `.env` (per `rules/env-models.md`)
- Model selection per agent role
- Cost estimation per model
- Fallback chain (if primary model fails, try secondary)

**Acceptance criteria**:

- At least OpenAI and Anthropic providers supported
- Keys from `.env` only (never hardcoded)
- Model configured per agent in org YAML
- Cost estimation based on token pricing
- Fallback chain configurable
- Unit test

**Dependencies**: M0 complete

---

## Summary

| Milestone                           | Todos    | Effort                                   | Dependencies |
| ----------------------------------- | -------- | ---------------------------------------- | ------------ |
| **M0: Platform Rename and Cleanup** | 13 todos | L (largest milestone)                    | None         |
| **M1: Work Management Models**      | 12 todos | M (mechanical DataFlow work)             | M0           |
| **M2: Work Management API**         | 9 todos  | M (FastAPI routers + services)           | M0, M1       |
| **M3: Admin CLI**                   | 8 todos  | S-M (Click commands)                     | M0           |
| **M4: GovernedSupervisor Wiring**   | 4 todos  | L (type adaptation, async orchestration) | M0, M1, M2   |
| **M5: Frontend Updates**            | 4 todos  | L (full pages)                           | M2, M4       |
| **M6: Integration Layer**           | 5 todos  | M (webhook adapters, services)           | M4           |

**Total**: 55 todos across 7 milestones.

### Parallel Execution Plan

```
Session 1:  M0 (TODO-0001 through TODO-0013) — full platform rename
Session 2:  M1 (all 12 DataFlow models) + M3 (8 CLI commands) — parallel streams
Session 3:  M2 (9 API routers + services)
Session 4:  M4 (4 GovernedSupervisor wiring tasks)
Session 5:  M5 (4 frontend pages) + M6 (5 integration tasks) — parallel streams
```

### Critical Path

```
M0 (rename) -> M1 (models) -> M2 (API) -> M4 (supervisor) -> M5 (frontend)
                                                              -> M6 (integrations)
                M3 (CLI) runs parallel with M1/M2
```

### Risk Register

| Risk                                                        | Severity | Mitigation                                                                |
| ----------------------------------------------------------- | -------- | ------------------------------------------------------------------------- |
| Import rewrite misses a path                                | CRITICAL | Grep-verified rewrite + pytest --collect-only gate                        |
| kailash-pact `pact.*` namespace collision after deletion    | CRITICAL | Verify `from pact.governance` resolves to kailash-pact, not local remnant |
| Trust file triage incorrect (delete something still needed) | HIGH     | Grep all consumers before deleting any trust file                         |
| Envelope type fragmentation (3 types)                       | HIGH     | Adapter with invariant tests for monotonic tightening at type boundary    |
| DataFlow migration breaks on PostgreSQL                     | MEDIUM   | Test both SQLite and PostgreSQL in CI                                     |
| GovernedSupervisor async coordination races                 | MEDIUM   | Lock on HELD verdict resolution + timeout fallback                        |
| `build/config/schema.py` types diverge from kailash-pact    | LOW      | Re-export shim ensures single source of truth                             |
