# Repivot Deep Analysis: PACT Repo Identity After Framework Migration

**Date**: 2026-03-21
**Phase**: 01-analysis
**Complexity Score**: 27/30 (COMPLEX) — Governance: 9, Legal: 8, Strategic: 10

---

## Executive Summary

The migration of kailash-pact governance primitives to kailash-py is **structurally incomplete**. The 31 governance files copied to `kailash-py/packages/kailash-pact/` contain 20 unresolved import dependencies on `pact.build`, `pact.trust`, and `pact.use` modules that do not exist in the target package. The migrated package cannot be imported, installed, or tested in its current state. Before any repivot of this repository can proceed, the kailash-py migration must be completed by either (a) migrating the dependency modules alongside governance, or (b) refactoring governance to be self-contained. This analysis recommends **Option C (Reference Implementation)** as the post-repivot identity, with a phased approach that addresses the broken migration first.

---

## 1. Critical Finding: Broken Migration

### 1.1 The Problem

The governance layer was copied from this repo to `~/repos/kailash/kailash-py/packages/kailash-pact/src/pact/governance/` (31 files). However, those files import from three module families that were NOT copied:

| Import Target                    | Files Importing     | Key Types Used                                                                                                                                                                                                                                                 |
| -------------------------------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pact.build.config.schema`       | 16 governance files | `ConfidentialityLevel`, `TrustPostureLevel`, `VerificationLevel`, `ConstraintEnvelopeConfig`, `DepartmentConfig`, `TeamConfig`, `AgentConfig`, `PactConfig`, `FinancialConstraintConfig`, `GenesisConfig`, `ConstraintDimension`, `VerificationGradientConfig` |
| `pact.build.org.builder`         | 2 governance files  | `OrgDefinition`                                                                                                                                                                                                                                                |
| `pact.trust.constraint.envelope` | 1 governance file   | `ConstraintEnvelope` (used by `envelope_adapter.py`)                                                                                                                                                                                                           |
| `pact.use.api.events`            | 1 governance file   | `EventType`, `PlatformEvent`, `event_bus` (used by `api/events.py`)                                                                                                                                                                                            |

Additionally, the root `__init__.py` imports from `pact.build.config.schema`, `pact.build.workspace.models`, `pact.trust.attestation`, `pact.trust.audit.anchor`, `pact.trust.constraint.envelope`, `pact.trust.constraint.gradient`, `pact.trust.posture`, `pact.trust.scoring`, `pact.use.execution.agent`, `pact.use.execution.approval`, `pact.use.execution.registry`, and `pact.use.execution.session`. None of these modules exist in kailash-py.

### 1.2 Impact

- `pip install kailash-pact` from kailash-py would fail with `ModuleNotFoundError` on first import
- Zero tests exist in kailash-py for kailash-pact (no `tests/` directory at all)
- The package is currently only usable as an editable install alongside this repo

### 1.3 Root Cause (5-Why)

1. **Why** does kailash-pact fail to import? It references modules not in the package.
2. **Why** are those modules missing? Only `governance/` was copied; its dependencies were not.
3. **Why** weren't dependencies copied? The migration plan scoped governance as the movable unit.
4. **Why** did the plan scope it that way? The Option B plan assumed `build/`, `trust/`, `use/` are "platform" code.
5. **Why** is that wrong? `pact.build.config.schema` is not platform code. It is the foundational type system that ALL layers depend on. It defines the vocabulary (enums, config models) that governance, trust, and execution all share.

### 1.4 The Gravity of `pact.build.config.schema`

This single file (`src/pact/build/config/schema.py`, 528 lines) is the gravitational center of the entire PACT codebase. Import counts across all layers:

| Layer         | Files importing from `pact.build.config.schema` |
| ------------- | ----------------------------------------------- |
| `governance/` | 16 files                                        |
| `trust/`      | 24 files                                        |
| `use/`        | 11 files                                        |
| `examples/`   | 7 files                                         |
| **Total**     | **58 files** (37% of all 156 source files)      |

It defines: `ConfidentialityLevel`, `TrustPostureLevel`, `VerificationLevel`, `ConstraintDimension`, `ConstraintEnvelopeConfig` (with all 5 sub-configs), `AgentConfig`, `TeamConfig`, `DepartmentConfig`, `WorkspaceConfig`, `PactConfig`, `GenesisConfig`, `VerificationGradientConfig`, and `GradientRuleConfig`.

Any repivot plan that does not address this file's placement is architecturally unsound.

---

## 2. Layer Disposition Map

### 2.1 `governance/` — 30 files in this repo, 31 in kailash-py

**Disposition: DEAD (in this repo) once migration is completed**

These files are byte-for-byte identical between the two repos. The canonical location is kailash-py. The local copies should be removed after migration completion. However, they CANNOT be removed until the kailash-py package actually works (see Section 1).

**Risk**: Code divergence. If anyone edits the local copy, the kailash-py copy becomes stale (or vice versa). Neither copy currently has CI to detect drift.

### 2.2 `build/` — 29 files

**Disposition: SPLIT**

| Subdirectory                    | Files   | Disposition | Reasoning                                                                       |
| ------------------------------- | ------- | ----------- | ------------------------------------------------------------------------------- |
| `build/config/schema.py`        | 1       | **MIGRATE** | Foundational types used by governance. Must move to kailash-pact.               |
| `build/config/defaults.py`      | 1       | KEEP        | Platform defaults for reference deployment                                      |
| `build/config/env.py`           | 1       | KEEP        | Environment variable loading for the reference server                           |
| `build/config/loader.py`        | 1       | UNCERTAIN   | YAML config loading — could be framework or platform                            |
| `build/org/builder.py`          | 1       | **MIGRATE** | `OrgDefinition` is imported by governance `compilation.py` and `yaml_loader.py` |
| `build/org/generator.py`        | 1       | KEEP        | Auto-generation of org structures (platform tooling)                            |
| `build/org/role_catalog.py`     | 1       | KEEP        | Role catalog (platform/example concern)                                         |
| `build/org/envelope_deriver.py` | 1       | KEEP        | Envelope derivation from org structure                                          |
| `build/org/utils.py`            | 1       | KEEP        | Org builder utilities                                                           |
| `build/workspace/`              | 6 files | KEEP        | Workspace-as-knowledge-base is platform behavior                                |
| `build/templates/`              | 2 files | KEEP        | Org templates are platform/example content                                      |
| `build/verticals/`              | 5 files | **DEAD**    | Re-exports from `examples/foundation/` with `# noqa: F401`. Shim layer.         |
| `build/cli/`                    | 2 files | KEEP        | Platform CLI                                                                    |
| `build/bootstrap.py`            | 1       | KEEP        | Platform bootstrapper                                                           |

**Critical migration items**: `schema.py` and `builder.py` must move to kailash-py because the governance layer depends on them at import time.

### 2.3 `trust/` — 58 files

**Disposition: UNCERTAIN trending toward DEPRECATED-IN-PLACE**

Three categories:

**Category A: EATP SDK code (~20 files)** — `genesis.py`, `delegation.py`, `attestation.py`, `lifecycle.py`, `eatp_bridge.py`, `integrity.py`, `revocation.py`, `credentials.py`, `sd_jwt.py`, `messaging.py`, `dual_binding.py`, `authorization.py`, and much of `store/`. Per project notes, "EATP is being merged into kailash core." When that happens, these become dead code.

**Category B: Constraint evaluation engine (~15 files)** — `constraint/envelope.py`, `constraint/gradient.py`, `constraint/enforcement.py`, `constraint/enforcer.py`, `constraint/middleware.py`, `constraint/cache.py`, `constraint/circuit_breaker.py`, `constraint/signing.py`, `constraint/resolution.py`, `constraint/bridge_envelope.py`, `constraint/verification_level.py`. These are the runtime evaluation counterparts to the governance policy layer. The governance layer's `envelope_adapter.py` bridges between the two. They have a legitimate claim to being framework code.

**Category C: Platform-specific trust features (~15 files)** — `posture.py`, `scoring.py`, `shadow_enforcer.py`, `shadow_enforcer_live.py`, `bridge_trust.py`, `bridge_posture.py`, `reasoning.py`, `uncertainty.py`, `decorators.py`, `audit/anchor.py`, `audit/pipeline.py`, `audit/bridge_audit.py`, `store_isolation/`, `resilience/`.

**Verdict**: Keep in this repo, mark as deprecated, let EATP absorption handle its lifecycle. The pragmatic path is not to fight the 135 internal imports.

### 2.4 `use/` — 25 files

**Disposition: KEEP**

This is the execution plane — the runtime that actually runs PACT-governed agents. Definitively platform code.

- `use/api/` (5 files): FastAPI server, endpoints, events, shutdown
- `use/execution/` (14 files): Agent runtime, approval queue, sessions, LLM backends, Kaizen bridge, hook enforcer, posture enforcer
- `use/observability/` (4 files): Logging, metrics, alerting

### 2.5 `examples/` — 13 files

**Disposition: KEEP**

Two example verticals demonstrating how to USE kailash-pact:

- `university/` (6 files): D/T/R structure, clearances, barriers, envelopes, demo
- `foundation/` (7 files): DM team structure, prompts, runner, org, templates

### 2.6 Summary

| Layer         | Files   | KEEP   | MIGRATE | DEAD   | UNCERTAIN |
| ------------- | ------- | ------ | ------- | ------ | --------- |
| `governance/` | 30      | 0      | 0       | 30     | 0         |
| `build/`      | 29      | 16     | 2       | 5      | 6         |
| `trust/`      | 58      | 0      | 0       | 0      | 58        |
| `use/`        | 25      | 25     | 0       | 0      | 0         |
| `examples/`   | 13      | 13     | 0       | 0      | 0         |
| **Total**     | **155** | **54** | **2**   | **35** | **64**    |

64 files (41%) have uncertain disposition, all in the `trust/` layer.

---

## 3. Risk Register (Top 5)

| #      | Risk                                                                                                                                                                                              | Likelihood | Impact      | Severity        | Mitigation                                                                                                                                                                                   |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R1** | **Broken kailash-py package ships** — kailash-pact in kailash-py cannot import due to missing `pact.build` and `pact.trust` dependencies                                                          | CERTAIN    | CRITICAL    | **CRITICAL**    | Complete the migration before any kailash-pact release from kailash-py. Migrate `schema.py` and `builder.py`; refactor or stub the `trust.constraint.envelope` and `use.api.events` imports. |
| **R2** | **Circular dependency trap** — if this repo depends on kailash-pact (from kailash-py), but kailash-pact depends on types in `pact.build.config.schema` (in this repo), installation is impossible | HIGH       | CRITICAL    | **CRITICAL**    | The schema types MUST live in one place. Either in kailash-pact (recommended) or as a separate `pact-types` package. They cannot live in both repos.                                         |
| **R3** | **Code divergence between repos** — 30 governance files exist in both repos, no CI guards against drift                                                                                           | HIGH       | HIGH        | **MAJOR**       | Delete local `governance/` once kailash-py package is importable; add CI check.                                                                                                              |
| **R4** | **Test rot** — 230 governance tests in this repo test code that canonically lives in kailash-py; 0 tests exist in kailash-py                                                                      | HIGH       | HIGH        | **MAJOR**       | Migrate governance tests to kailash-py as part of migration completion.                                                                                                                      |
| **R5** | **Identity confusion** — pyproject.toml still publishes as `kailash-pact` v0.2.0, creating a name collision with the kailash-py package                                                           | CERTAIN    | SIGNIFICANT | **SIGNIFICANT** | Change package identity: stop publishing as kailash-pact; become a consumer.                                                                                                                 |

Additional risks (6-10):

| #   | Risk                                                          | Severity    |
| --- | ------------------------------------------------------------- | ----------- |
| R6  | Trust layer limbo — 58 files neither maintained nor removed   | SIGNIFICANT |
| R7  | `schema.py` extraction breaks 58 import sites in this repo    | SIGNIFICANT |
| R8  | Dashboard orphaned if API contracts change during repivot     | SIGNIFICANT |
| R9  | Vertical consumers (astra/arbor) confused about import source | MODERATE    |
| R10 | Dead code accumulation without active cleanup                 | MODERATE    |

---

## 4. Identity Evaluation

### Option A: "pact-platform" — A reference deployment

Deploys PACT-governed organizations. Framework comes from `pip install kailash-pact`.

- **Pro**: Clear separation, forces migration completion
- **Con**: "Platform" implies production-readiness; loses brand recognition
- **Risk**: MODERATE

### Option B: "pact-examples" — Just examples and docs

Configuration examples, documentation, lightweight demo.

- **Pro**: Smallest surface area, minimal maintenance
- **Con**: Wastes the 25-file `use/` layer, 29-page dashboard, Docker deployment
- **Risk**: LOW (but low value)

### Option C: "pact" — The reference implementation (RECOMMENDED)

Canonical reference implementation of PACT. Imports `kailash-pact` for governance primitives, demonstrates the full stack: API server, execution runtime, dashboard, example organizations, deployment.

- **Pro**: Preserves the name and URL; keeps valuable execution, dashboard, deployment layers; natural ecosystem role ("kailash-pact is the library; pact is the reference app"); CLAUDE.md already describes this identity
- **Con**: Must manage trust layer disposition; carries 58 uncertain files until EATP absorption
- **Risk**: MODERATE

**Recommendation**: Option C. The repo name stays `pact`. The relationship becomes:

```
kailash-pact (in kailash-py)          pact (this repo)
  governance/                           use/ (API server, runtime)
  build/config/schema.py (migrated)     build/ (workspace, templates, config)
  build/org/builder.py (migrated)       trust/ (deprecated, pending EATP merge)
                                        examples/ (university, foundation)
                                        apps/web/ (dashboard)
                                        docker-compose.yml, Dockerfile
```

---

## 5. Test Disposition

### Current State

- 1,115 test functions across 191 files
- 153 collection errors
- 0 tests in kailash-py kailash-pact package

### Category Breakdown

| Category     | Dir                       | Functions | Disposition                           |
| ------------ | ------------------------- | --------- | ------------------------------------- |
| Governance   | `tests/unit/governance/`  | ~230      | **MIGRATE** to kailash-py             |
| Trust (EATP) | `tests/unit/trust/`       | ~124      | UNCERTAIN — move with EATP absorption |
| Constraint   | `tests/unit/constraint/`  | ~95       | UNCERTAIN — framework or platform?    |
| Execution    | `tests/unit/execution/`   | ~69       | **KEEP**                              |
| API          | `tests/unit/api/`         | ~50       | **KEEP**                              |
| Persistence  | `tests/unit/persistence/` | ~65       | KEEP/UNCERTAIN                        |
| Workspace    | `tests/unit/workspace/`   | ~49       | **KEEP**                              |
| Org          | `tests/unit/org/`         | ~44       | **KEEP**                              |
| Config       | `tests/unit/config/`      | ~16       | SPLIT (schema tests migrate)          |
| Integration  | `tests/integration/`      | ~26       | **KEEP**                              |
| Other        | various                   | ~247      | **KEEP**                              |

The 230 governance tests are the urgent migration. The kailash-py package currently has zero test coverage.

---

## 6. Post-Repivot Dependency Graph

### What Must Change in kailash-py kailash-pact

1. **`pact.build.config.schema`** must exist in kailash-py. Recommended: move into kailash-pact as `pact.governance.schema` or `pact.config.schema`. Add backward-compatibility re-export shim in this repo.

2. **`pact.build.org.builder.OrgDefinition`** must be accessible from kailash-pact. Move `builder.py` into kailash-pact.

3. **`pact.trust.constraint.envelope.ConstraintEnvelope`** used by `envelope_adapter.py`. Either move to kailash-pact or make the import optional.

4. **`pact.use.api.events`** used by `governance/api/events.py`. Decouple: define standalone event types or make platform event bus optional.

5. **Root `__init__.py`** must be rewritten. kailash-pact version exports governance types only. This repo's version exports everything.

### Post-Repivot pyproject.toml (this repo)

```toml
[project]
name = "pact-reference"
version = "0.3.0"
dependencies = [
    "kailash-pact>=0.3.0",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "click>=8.0",
    "rich>=13.0.0",
    "eatp>=0.1.0",
    "trust-plane>=0.2.0",
    "cryptography>=41.0.0",
    "jcs>=0.2.1",
    "slowapi>=0.1.9",
    "prometheus-client>=0.20.0",
    "alembic>=1.12.0",
    "python-dotenv>=1.0.0",
    "structlog>=23.1.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
]
```

---

## 7. Implementation Roadmap

### Phase 0: Fix the Broken Migration (PREREQUISITE)

1. Move `schema.py` and `builder.py` into kailash-pact in kailash-py
2. Decouple `governance/api/events.py` from `pact.use.api.events`
3. Make `envelope_adapter.py`'s trust import optional or move the constraint envelope
4. Rewrite kailash-pact root `__init__.py`
5. Migrate governance tests to kailash-py
6. Verify: `pip install kailash-pact && python -c "from pact.governance import GovernanceEngine"`

**Estimated effort**: 2-3 sessions. **Blocks everything.**

### Phase 1: Repivot This Repo

1. Delete local `src/pact/governance/`
2. Add `kailash-pact>=0.3.0` to dependencies
3. Add backward-compatibility shim for old import paths
4. Rename package; update `__init__.py`
5. Fix collection errors; run full test suite

**Estimated effort**: 1-2 sessions

### Phase 2: Trust Layer Triage

1. Annotate every `trust/` file with disposition
2. Add deprecation warnings
3. Decide constraint evaluation engine placement

**Estimated effort**: 1-2 sessions

### Phase 3: Cleanup

1. Delete `build/verticals/` (dead shim)
2. Update all documentation (CLAUDE.md, README.md)
3. Dashboard API contract validation
4. Final red team

**Estimated effort**: 1 session

---

## 8. Decision Points Requiring Stakeholder Input

1. **Package name after repivot**: `pact-reference`, `pact-platform`, or unpublished `pact`?

2. **Where does `schema.py` land in kailash-py?**: `pact.governance.schema`, `pact.config.schema`, or `pact.schema`?

3. **Is the constraint evaluation engine framework or platform?** If framework, `constraint/envelope.py` and `constraint/gradient.py` move to kailash-py.

4. **EATP absorption timeline**: Determines when the 58-file trust layer becomes truly dead.

5. **Dashboard ownership**: Stays here, moves to own repo, or deprecated?

6. **Test migration urgency**: Governance tests move in Phase 0 (blocking) or later?

---

## 9. Cross-Reference Audit

### Inconsistencies Found

- **CLAUDE.md** says "this repo publishes as kailash-pact v0.2.0" but governance now lives in kailash-py. Two packages with the same name would conflict on PyPI.

- **`project.scripts`** points to `pact.governance.cli:main` which is the framework CLI, not a platform CLI. After repivot, this entry point belongs to kailash-pact.

- **Memory file `project_migration_complete.md`** says "37 test files (968 tests)" were migrated but kailash-py has zero test files.

- **`.claude/rules/governance.md`** contains framework-level guidance that should follow the code to kailash-py.

---

## 10. Success Criteria

| #   | Criterion                               | Measurable Outcome                                                  |
| --- | --------------------------------------- | ------------------------------------------------------------------- |
| S1  | kailash-pact importable from kailash-py | `python -c "from pact.governance import GovernanceEngine"` succeeds |
| S2  | This repo imports kailash-pact          | `pyproject.toml` lists `kailash-pact` as dependency, not as name    |
| S3  | No duplicate governance code            | `src/pact/governance/` absent or is thin re-export shim             |
| S4  | Tests pass                              | 0 collection errors, 0 unexpected failures                          |
| S5  | Governance tests in kailash-py          | 200+ governance tests in kailash-py `tests/`                        |
| S6  | Dashboard works                         | All 29 pages load and render                                        |
| S7  | Docker deployment works                 | `docker compose up` starts all services                             |
| S8  | Examples run                            | University and foundation examples execute cleanly                  |
| S9  | Trust layer has clear disposition       | Every `trust/` file annotated                                       |
| S10 | Documentation accurate                  | CLAUDE.md, README.md, pyproject.toml reflect reality                |
