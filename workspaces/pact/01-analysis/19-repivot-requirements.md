# Repivot Requirements Breakdown

**Date**: 2026-03-21
**Status**: Proposed
**Context**: This repo (`terrene/pact`) transitions from "source of the kailash-pact framework" to "reference platform that imports kailash-pact."

---

## Executive Summary

- **Feature**: Repivot pact repo from framework publisher to reference platform
- **Complexity**: High
- **Risk Level**: High (namespace collision, import breakage, CI pipeline changes, dangling cross-package imports)
- **Estimated Effort**: 5-8 days across 4 phases

### Critical Finding

The kailash-pact package in kailash-py is **not yet self-contained**. The 31 governance files copied there still import from `pact.build.config.schema`, `pact.build.org.builder`, `pact.trust.constraint.envelope`, and `pact.use.api.events` -- modules that only exist in THIS repo. Until kailash-py resolves those dangling imports (either by internalizing the dependencies or creating stub/shim modules), the kailash-pact package cannot be installed independently. This is a **blocking prerequisite** for the repivot.

---

## Phase 0: Prerequisites (Must Complete Before Repivot Begins)

### REQ-000: Resolve kailash-pact Dangling Imports in kailash-py

**What changes**: The kailash-pact package in kailash-py must become installable without this repo. Currently, its governance modules import from three namespaces that do not exist in that package:

| Import Source                    | Used By (in kailash-py governance/)                                                                                                                                      | Count       |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| `pact.build.config.schema`       | 14 modules (engine, envelopes, access, clearance, context, explain, knowledge, compilation, testing, yaml_loader, envelope_adapter, api/endpoints, api/schemas, stores/) | ~25 imports |
| `pact.build.org.builder`         | compilation.py, yaml_loader.py                                                                                                                                           | 3 imports   |
| `pact.trust.constraint.envelope` | envelope_adapter.py                                                                                                                                                      | 1 import    |
| `pact.use.api.events`            | api/events.py                                                                                                                                                            | 1 import    |

**Why**: If `pip install kailash-pact` fails because `pact.build.config.schema` does not exist in that package, this repo cannot depend on it. The repivot is dead on arrival.

**Resolution options (decided in kailash-py workspace, not here)**:

1. **Extract shared types**: Move `ConfidentialityLevel`, `TrustPostureLevel`, `VerificationLevel`, `ConstraintEnvelopeConfig`, and the Pydantic config models into kailash-pact's own `pact.governance.types` module. This breaks the upward dependency on `pact.build`.
2. **Ship build/trust/use stubs**: Include minimal `pact.build.config.schema` within kailash-pact as a compatibility shim. Fragile and not recommended.
3. **Restructure the kailash-pact **init**.py**: Remove the re-exports from `pact.build`, `pact.trust`, `pact.use` entirely -- those are platform-layer concerns.

**Dependencies**: None (this is the root dependency).

**Risk**: HIGH. If this takes too long, the repivot stalls. Recommend option 1 -- the types are small and well-defined.

---

## Phase 1: Package Identity Change

### REQ-101: New Package Name and Identity

**What changes**: `pyproject.toml` must change from publishing `kailash-pact` (the framework) to a different package that depends on `kailash-pact`.

**Current state**:

```toml
[project]
name = "kailash-pact"
version = "0.2.0"
# ... publishes src/pact/ as the kailash-pact framework
```

**New identity options**:

| Option | Package Name                                 | PyPI Install                 | Import Path                      |
| ------ | -------------------------------------------- | ---------------------------- | -------------------------------- |
| A      | `pact-platform`                              | `pip install pact-platform`  | `from pact_platform import ...`  |
| B      | `pact-reference`                             | `pip install pact-reference` | `from pact_reference import ...` |
| C      | No PyPI publish                              | Not published                | Local `src/pact_platform/`       |
| D      | Keep `pact` repo name, don't publish to PyPI | N/A                          | `from pact_platform import ...`  |

**Recommendation**: Option D. This repo is a **deployment artifact** (Docker container, docker-compose stack), not a library. It should not be published to PyPI. The `pyproject.toml` exists for local `pip install -e .` during development but the package name should change to avoid collision with kailash-pact.

**New pyproject.toml structure**:

```toml
[project]
name = "pact-platform"  # Not published to PyPI -- deployment artifact
version = "0.3.0"       # Bump to signal the repivot
dependencies = [
    "kailash-pact>=0.2.0",     # The governance framework (from kailash-py)
    "eatp>=0.1.0",             # EATP trust protocol
    "trust-plane>=0.2.0",      # EATP reference implementation
    "pydantic>=2.0",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "click>=8.0",
    "rich>=13.0.0",
    "alembic>=1.12.0",
    "cryptography>=41.0.0",
    "jcs>=0.2.1",
    "slowapi>=0.1.9",
    "prometheus-client>=0.20.0",
    "python-dotenv>=1.0.0",
    "structlog>=23.1.0",
    "pyyaml>=6.0",
]
```

**Dependencies**: REQ-000 (kailash-pact must be installable first).

**Risk**: MEDIUM. The `name = "kailash-pact"` currently means `pip install -e .` provides the `pact` namespace from `src/pact/`. Changing to `pact-platform` with `src/pact_platform/` would break every import in the repo. See REQ-102 for namespace strategy.

### REQ-102: Python Namespace Strategy

**What changes**: Decide how the platform code coexists with the governance framework code, given both use the `pact` namespace.

**The core problem**: kailash-pact installs as `pact.governance.*`. This repo currently has `src/pact/` which also provides `pact.governance.*` locally. When kailash-pact is installed as a dependency, Python will see two `pact` packages -- one from kailash-pact (site-packages) and one from `src/pact/` (editable install). Only one wins.

**Options**:

| Option                                            | How It Works                                                                                                                                                                                                                                        | Pros                                                                                                               | Cons                                                                                                                                                                                                                 |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A: Namespace package                              | Both kailash-pact and this repo contribute to the `pact` namespace using PEP 420 implicit namespace packages. kailash-pact provides `pact.governance`, this repo provides `pact.platform`, `pact.trust`, `pact.build`, `pact.use`, `pact.examples`. | Clean imports (`from pact.platform import ...`). Both packages share `pact.*`.                                     | Requires both packages to omit `__init__.py` in their root `pact/` directory. Namespace packages have subtle behavior with editable installs. kailash-pact already has `src/pact/__init__.py` -- would need removal. |
| B: Separate top-level                             | Rename `src/pact/` to `src/pact_platform/`. All platform code imports become `from pact_platform.use.api import ...`. Governance imports come from `from pact.governance import ...` via kailash-pact.                                              | No namespace collision. Clean separation.                                                                          | 1500+ import rewrites across ~150 source files and ~120 test files. Massive mechanical change.                                                                                                                       |
| C: Delete local governance, keep `pact` namespace | Remove `src/pact/governance/` entirely. Keep `src/pact/__init__.py` but don't re-export governance. Install kailash-pact as dependency. Platform code imports governance from the installed package.                                                | Minimal import changes -- only governance imports change from local to package. Trust/build/use imports unchanged. | Relies on Python's package resolution merging `pact` from two sources (editable install + site-packages). Can work with careful `__init__.py` management but fragile.                                                |
| D: Shim module                                    | Keep `src/pact/governance/__init__.py` as a thin re-export: `from kailash_pact.governance import *`. Platform code continues to use `from pact.governance import ...`.                                                                              | Zero import changes.                                                                                               | kailash-pact imports as `kailash_pact`, not `pact`. But kailash-pact actually uses `pact.governance` as its namespace -- so this does not work.                                                                      |

**Recommendation**: Option C, with a phased approach. Delete `src/pact/governance/` (it is now in kailash-pact). The remaining `src/pact/` directories (build, trust, use, examples) continue to provide the platform layer under the `pact` namespace. When kailash-pact is installed, `pact.governance` comes from it. When the platform is installed in editable mode (`pip install -e .`), `pact.build`, `pact.trust`, `pact.use` come from local source.

**Critical caveat**: This only works if kailash-pact's `src/pact/__init__.py` does NOT eagerly import from `pact.build`, `pact.trust`, or `pact.use` (because those would not exist in kailash-pact's package). See REQ-000 -- that cleanup must happen first.

**Dependencies**: REQ-000, REQ-101.

**Risk**: HIGH. Python namespace merging from two packages is fragile. Must test with both `pip install -e .` and `pip install kailash-pact` simultaneously. If Python resolves `pact` from only one source, the other's subpackages become invisible.

### REQ-103: Version Bump and **init**.py Update

**What changes**:

- `pyproject.toml` version: `0.2.0` -> `0.3.0`
- `src/pact/__init__.py` version: `"0.2.0"` -> `"0.3.0"`
- `__init__.py` must stop re-exporting governance types (they come from kailash-pact now)
- `__init__.py` docstring must describe the platform, not the framework

**Dependencies**: REQ-101, REQ-102.

**Risk**: LOW.

---

## Phase 2: Source Code Disposition

### REQ-201: Delete Local Governance Layer (30 files)

**What changes**: Delete `src/pact/governance/` entirely.

**Files to delete** (30 files):

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
src/pact/governance/stores/__init__.py
src/pact/governance/stores/backup.py
src/pact/governance/stores/sqlite.py
src/pact/governance/api/__init__.py
src/pact/governance/api/auth.py
src/pact/governance/api/endpoints.py
src/pact/governance/api/events.py
src/pact/governance/api/router.py
src/pact/governance/api/schemas.py
```

**Why**: These are now in kailash-py. Keeping them creates divergence risk.

**Dependencies**: REQ-000 (kailash-pact must work independently), REQ-102 (namespace strategy confirmed).

**Risk**: MEDIUM. Must verify every consumer of `from pact.governance import X` still resolves after deletion. The platform code (`src/pact/use/execution/runtime.py` line 69) imports `from pact.governance.engine import GovernanceEngine` -- this must resolve to kailash-pact.

### REQ-202: Disposition of Trust Layer (58 files)

**What changes**: The trust layer (`src/pact/trust/`) is being merged into kailash core separately (per memory note). Until that merge completes, these 58 files STAY in this repo.

**Subpackages**:
| Subpackage | Files | Status |
|---|---|---|
| `pact.trust.constraint/` | 12 files | Core EATP constraint evaluation. Stays until kailash core merge. |
| `pact.trust.store/` | 10 files | Trust record persistence (memory, SQLite, PostgreSQL). Stays. |
| `pact.trust.audit/` | 3 files | Audit anchor chain. Stays. |
| `pact.trust.resilience/` | 2 files | Failure mode handling. Stays. |
| `pact.trust.auth/` | 2 files | Firebase admin auth. Stays. |
| `pact.trust.store_isolation/` | 4 files | Store isolation management. Stays. |
| Root trust modules | 25 files | Genesis, delegation, posture, scoring, etc. Stays. |

**Why**: The EATP layer is merging into kailash core on a separate timeline. This repo must continue to function with its own trust layer until that merge lands. Premature deletion would break the platform.

**Dependencies**: None for this phase (it stays).

**Risk**: LOW for now. MEDIUM when kailash core absorbs EATP -- will need a second repivot to delete this layer.

### REQ-203: Disposition of Build Layer (29 files)

**What changes**: The build layer stays but needs audit for governance dependencies.

**Subpackages**:
| Subpackage | Files | Status |
|---|---|---|
| `pact.build.config/` | 4 files (schema.py, env.py, defaults.py, loader.py) | CRITICAL -- `schema.py` defines types used everywhere. Stays. But kailash-pact also needs these types (see REQ-000). |
| `pact.build.org/` | 5 files | Org builder, envelope deriver, role catalog. Stays. |
| `pact.build.workspace/` | 6 files | Workspace management, bridges, knowledge policies. Stays. |
| `pact.build.templates/` | 2 files | Template registry. Stays. |
| `pact.build.verticals/` | 4 files | DM team, foundation vertical. Stays (platform-specific). |
| `pact.build.cli/` | 2 files | Platform CLI. Stays. |
| `pact.build.bootstrap.py` | 1 file | Platform bootstrap. Stays. |

**Key issue**: `pact.build.config.schema` defines `ConfidentialityLevel`, `TrustPostureLevel`, `VerificationLevel`, `ConstraintEnvelopeConfig`, and all Pydantic config models. The governance layer in kailash-pact imports these types from here. When governance moves to kailash-pact, these types must either:

1. Move with it (into kailash-pact), or
2. Be duplicated (fragile), or
3. Live in a third shared package (over-engineering).

This is the same problem as REQ-000. The resolution must be coordinated.

**Dependencies**: REQ-000.

**Risk**: HIGH. The `schema.py` type ownership question is the single hardest technical decision in the repivot.

### REQ-204: Disposition of Use Layer (25 files)

**What changes**: The use layer stays entirely. This IS the platform.

**Subpackages**:
| Subpackage | Files | Purpose |
|---|---|---|
| `pact.use.api/` | 5 files | FastAPI server, endpoints, events, shutdown. Platform API. |
| `pact.use.execution/` | 13 files | Agent runtime, sessions, approval, LLM backends, Kaizen bridge. |
| `pact.use.observability/` | 3 files | Logging, metrics, alerting. |

**Import changes needed**: The use layer imports from `pact.governance` (1 import in runtime.py). After REQ-201, this import must resolve to kailash-pact instead of local source.

**Dependencies**: REQ-201.

**Risk**: LOW. The use layer is the core of what this repo becomes.

### REQ-205: Disposition of Examples (13 files)

**What changes**: Examples stay but may need import updates.

**Files**:
| Directory | Files | Purpose |
|---|---|---|
| `pact.examples.university/` | 6 files | University domain example. Reference vertical. |
| `pact.examples.foundation/` | 5 files + templates | Foundation domain example. Reference vertical. |

**Why**: These are reference configurations that demonstrate how to build a PACT vertical. They import from `pact.governance` and `pact.build` -- the governance imports must resolve to kailash-pact after deletion.

**Dependencies**: REQ-201.

**Risk**: LOW.

---

## Phase 3: Import Path Migration

### REQ-301: Rewrite Governance Imports in Platform Code

**What changes**: Every `from pact.governance import X` in the platform code (build, trust, use, examples) must continue to work after `src/pact/governance/` is deleted. If namespace merging works (REQ-102 Option C), these imports resolve to kailash-pact automatically with zero code changes.

**Import inventory in platform code that references governance**:

| File                                   | Import                                                                                                          |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `src/pact/use/execution/runtime.py:69` | `from pact.governance.engine import GovernanceEngine`                                                           |
| `src/pact/governance/api/events.py:24` | `from pact.use.api.events import ...` (REVERSE -- governance imports from use; this file moves to kailash-pact) |

**If namespace merging does NOT work**: These imports must be rewritten to explicitly reference the installed package. The mechanism depends on how kailash-pact exposes its API.

**Dependencies**: REQ-102, REQ-201.

**Risk**: MEDIUM. Namespace merging is the critical path. If it works, zero code changes. If it does not, imports must be rewritten.

### REQ-302: Resolve Circular Import Between Governance and Platform

**What changes**: One file in the governance package (`pact.governance.api.events`) imports from the platform (`pact.use.api.events`). This creates a circular dependency: kailash-pact (governance) depends on this repo (use.api.events), and this repo depends on kailash-pact (governance).

**Resolution**: The governance API events module should either:

1. Define its own event types (not depend on `pact.use.api.events`).
2. Accept event infrastructure as a dependency injection parameter.
3. Use a thin protocol/interface that both sides implement.

**Dependencies**: REQ-000 (this must be fixed in kailash-py).

**Risk**: HIGH. This circular dependency is a structural flaw that must be resolved before the repivot can work.

---

## Phase 4: Test Migration

### REQ-401: Identify Test Ownership

**Test inventory** (approximate test function counts):

| Test Directory            | Test Count | Belongs To                                                |
| ------------------------- | ---------- | --------------------------------------------------------- |
| `tests/unit/governance/`  | ~1,038     | kailash-pact (already copied as 37 test files, 968 tests) |
| `tests/unit/trust/`       | ~597       | This repo (until EATP merges into kailash core)           |
| `tests/unit/constraint/`  | ~565       | This repo (trust layer)                                   |
| `tests/unit/execution/`   | ~350       | This repo (platform use layer)                            |
| `tests/unit/api/`         | ~218       | This repo (platform API)                                  |
| `tests/unit/config/`      | varies     | This repo (build layer)                                   |
| `tests/unit/org/`         | varies     | This repo (build layer)                                   |
| `tests/unit/workspace/`   | varies     | This repo (build layer)                                   |
| `tests/unit/integration/` | varies     | This repo (cross-layer tests)                             |
| `tests/integration/`      | ~6 files   | This repo (API server, org roundtrip, etc.)               |
| `tests/sdk/`              | 1 file     | This repo (SDK pattern validation)                        |

### REQ-402: Delete Governance Tests (Duplicated)

**What changes**: Delete `tests/unit/governance/` entirely. These tests are now in `kailash-py/packages/kailash-pact/tests/`.

**Files to delete**: 37 test files + conftest.py.

**Why**: Keeping duplicate tests means they diverge. kailash-py is the source of truth for governance tests.

**Dependencies**: REQ-201 (governance source deleted first).

**Risk**: LOW.

### REQ-403: Add Platform Integration Tests

**What changes**: Add new tests that verify the platform correctly imports and uses kailash-pact as a dependency.

**Tests needed**:

1. `test_kailash_pact_import.py` -- verify `from pact.governance import GovernanceEngine` works from the installed package.
2. `test_platform_governance_integration.py` -- verify ExecutionRuntime can use GovernanceEngine from kailash-pact.
3. `test_namespace_coexistence.py` -- verify `pact.governance` (from kailash-pact) and `pact.use` (from local) both work simultaneously.

**Dependencies**: REQ-102, REQ-201, REQ-402.

**Risk**: MEDIUM. These tests validate the namespace strategy.

### REQ-404: Fix Test Collection Errors

**What changes**: The repo currently has 153 collection errors. The repivot will likely fix some (by deleting broken governance tests) but may introduce new ones (from import resolution failures).

**Dependencies**: All Phase 2 and Phase 3 requirements.

**Risk**: MEDIUM. Must achieve a clean test suite after repivot.

---

## Phase 5: Dashboard and Apps

### REQ-501: Web Dashboard (Next.js) -- No Changes Required

**What changes**: None immediately. The dashboard (`apps/web/`) is a Next.js frontend that talks to the FastAPI API server over HTTP. It does not import Python code directly.

**29 pages/components**: Dashboard home, agents, approvals, audit, bridges, cost report, DM team, envelopes, login, org, shadow enforcer, trust chains, verification, workspaces.

**Why**: The frontend-backend boundary is HTTP. The backend API (`pact.use.api.server`) stays in this repo. The frontend does not care whether governance logic comes from a local module or an installed package.

**Dependencies**: None.

**Risk**: LOW. The API contract does not change.

### REQ-502: Mobile App (Flutter) -- No Changes Required

**What changes**: None. The Flutter app (`apps/mobile/`) also communicates via HTTP to the API server.

**Dependencies**: None.

**Risk**: LOW.

### REQ-503: Docker Compose -- Minor Updates

**What changes**: The `Dockerfile` currently does `pip install --no-cache-dir .` which installs from local `src/pact/`. After the repivot, this still works, but the package now has `kailash-pact` as a dependency that must be pulled from PyPI during the Docker build.

**Changes needed**:

- `Dockerfile`: No structural changes, but must ensure `kailash-pact` is available during build. If kailash-pact is not yet on PyPI, the Dockerfile must install from the kailash-py monorepo (requires git clone or wheel copy).
- `docker-compose.yml`: Environment variable names using `CARE_` prefix should be reviewed (some already use `PACT_` -- see `PACT_API_HOST` in Dockerfile).

**Dependencies**: kailash-pact published to PyPI (or alternative install path).

**Risk**: MEDIUM. The Docker build is the deployment path. If kailash-pact is not on PyPI, the build fails. Need a fallback (vendored wheel, git dependency).

---

## Phase 6: CI/CD Changes

### REQ-601: Update CI Pipeline

**What changes**: `.github/workflows/ci.yml` needs several updates:

1. **Lint paths**: Change `ruff check src/pact/` -- still valid but coverage changes (no more governance/).
2. **Test paths**: `pytest tests/unit/` -- still valid but governance tests are deleted. Coverage threshold may need adjustment (currently `--cov-fail-under=85`).
3. **Dependencies**: `pip install -e ".[dev]"` must now also install kailash-pact. If not on PyPI, need alternative install step.
4. **Integration tests**: `pytest tests/integration/` -- verify they still pass with governance from external package.

**Dependencies**: REQ-000 (kailash-pact installable), all Phase 2 requirements.

**Risk**: MEDIUM. CI must pass green before merge.

### REQ-602: Update Publish Pipeline

**What changes**: `.github/workflows/publish.yml` currently publishes `kailash-pact` to PyPI and pushes a Docker image to GHCR.

1. **PyPI publishing**: Remove or disable. This repo no longer publishes `kailash-pact` to PyPI (kailash-py does). If the platform is not published to PyPI either (REQ-101 Option D), remove the PyPI jobs entirely.
2. **Container publishing**: Keep. The Docker image is the deployment artifact.
3. **Container tag**: Change from `ghcr.io/terrene-foundation/pact` to `ghcr.io/terrene-foundation/pact-platform` (optional but clearer).

**Dependencies**: REQ-101.

**Risk**: LOW. Removing PyPI publishing is safe.

### REQ-603: Update COC Validation

**What changes**: `node scripts/ci/run-all.js` -- review whether COC validations need updating for the new package structure.

**Dependencies**: None.

**Risk**: LOW.

---

## Phase 7: Documentation

### REQ-701: Update CLAUDE.md

**What changes**: Complete rewrite of the project description and architecture overview to reflect the repivot.

**Key changes**:

- Description: "Reference platform for PACT governance" (not "reference implementation of PACT")
- Architecture table: Show kailash-pact as an external dependency, not an internal module
- Component table: Remove governance from "this repo" column, add "from kailash-pact"
- Import patterns: Document `from pact.governance import ...` (resolves to kailash-pact)
- Remove governance layer from "Framework Components" table

**Dependencies**: All Phase 2 requirements.

**Risk**: LOW.

### REQ-702: Update README.md

**What changes**: README must describe the repo as a reference platform, not a framework.

**Key changes**:

- Title and description
- Installation: `pip install kailash-pact` for the framework; this repo is for running the reference platform
- Architecture diagram showing the dependency relationship
- Quick start: Docker-compose based, not library import based

**Dependencies**: All Phase 2 requirements.

**Risk**: LOW.

### REQ-703: Update Rule Files

**What changes**: Several `.claude/rules/` files reference `src/pact/governance/` which will no longer exist:

| Rule File                 | Change Needed                                                           |
| ------------------------- | ----------------------------------------------------------------------- |
| `governance.md`           | Update scope -- governance rules now apply to kailash-py, not this repo |
| `boundary-test.md`        | Update scope -- `src/pact/governance/` no longer exists locally         |
| `trust-plane-security.md` | No change -- trust layer stays                                          |

**Dependencies**: REQ-201.

**Risk**: LOW.

---

## Risk Assessment Matrix

### Critical (High Probability, High Impact)

1. **Namespace collision between kailash-pact and local pact package**
   - Probability: HIGH
   - Impact: CRITICAL -- all imports break
   - Mitigation: Test namespace coexistence in an isolated venv before starting
   - Prevention: Choose Option C (REQ-102) only after proving it works

2. **kailash-pact dangling imports prevent installation**
   - Probability: CERTAIN (imports exist today)
   - Impact: CRITICAL -- repivot cannot start
   - Mitigation: Fix in kailash-py workspace first
   - Prevention: REQ-000 is a hard gate

3. **Circular dependency between governance and platform events**
   - Probability: CERTAIN (import exists today)
   - Impact: HIGH -- governance package depends on platform
   - Mitigation: REQ-302 -- decouple events before repivot
   - Prevention: Fix in kailash-py workspace

### Medium Risk (Monitor)

4. **CI coverage threshold fails after governance tests deleted**
   - Mitigation: Adjust `--cov-fail-under` temporarily
   - Prevention: Calculate expected coverage before deletion

5. **Docker build fails because kailash-pact not on PyPI**
   - Mitigation: Vendor a wheel or use git dependency
   - Prevention: Coordinate release timing with kailash-py

6. **153 existing collection errors mask new breakage**
   - Mitigation: Fix collection errors first, then repivot
   - Prevention: Clean test suite baseline

### Low Risk (Accept)

7. **Documentation drift during repivot**
   - Mitigation: Update docs in same PR as code changes
   - Prevention: Automated doc validation

8. **Frontend pages display stale governance data format**
   - Mitigation: API contract is unchanged
   - Prevention: API integration tests

---

## Implementation Roadmap

### Phase 0: Prerequisites (in kailash-py, not here) -- 2-3 days

- [ ] Extract shared types from `pact.build.config.schema` into kailash-pact
- [ ] Remove `pact.use.api.events` import from governance api/events
- [ ] Verify `pip install kailash-pact` works in isolation
- [ ] Publish kailash-pact v0.2.1 to TestPyPI

### Phase 1: Package Identity (this repo) -- 1 day

- [ ] Rename package to `pact-platform` in pyproject.toml
- [ ] Add `kailash-pact>=0.2.1` to dependencies
- [ ] Bump version to 0.3.0
- [ ] Update `__init__.py`

### Phase 2: Source Code Deletion (this repo) -- 1 day

- [ ] Delete `src/pact/governance/` (30 files)
- [ ] Delete `tests/unit/governance/` (38 files)
- [ ] Verify all remaining imports resolve

### Phase 3: Namespace Validation -- 1 day

- [ ] Test namespace coexistence (kailash-pact + local pact.use/build/trust)
- [ ] Write platform integration tests (REQ-403)
- [ ] Fix any import resolution failures
- [ ] Achieve clean `pytest` run

### Phase 4: CI/CD and Docs -- 1-2 days

- [ ] Update CI pipeline
- [ ] Disable PyPI publishing
- [ ] Update Dockerfile (if needed)
- [ ] Rewrite CLAUDE.md, README.md
- [ ] Update relevant rule files

---

## Success Criteria

- [ ] `pip install -e .` in this repo installs `pact-platform` which depends on `kailash-pact`
- [ ] `from pact.governance import GovernanceEngine` resolves to kailash-pact (not local source)
- [ ] `from pact.use.api.server import create_app` resolves to local source
- [ ] `docker compose up` starts all three services (db, api, web)
- [ ] All tests pass (excluding the deleted governance tests)
- [ ] CI pipeline runs green
- [ ] No `src/pact/governance/` directory exists in this repo
- [ ] CLAUDE.md accurately describes the repo as a reference platform

---

## ADR-019: Repivot from Framework Publisher to Reference Platform

### Status

Proposed

### Context

The PACT governance framework (D/T/R grammar, operating envelopes, knowledge clearance, verification gradient) was developed in this repo and has been migrated to `kailash-py/packages/kailash-pact/`. This repo must transition from publishing the framework to consuming it. The repo will become a reference deployment platform -- a Docker-composable stack with FastAPI API server, Next.js dashboard, and Flutter mobile app -- that demonstrates PACT governance in action using kailash-pact as its governance engine.

### Decision

1. Rename the package to `pact-platform` (not published to PyPI).
2. Add `kailash-pact>=0.2.0` as a dependency.
3. Delete `src/pact/governance/` and its tests (now in kailash-py).
4. Keep `src/pact/trust/`, `src/pact/build/`, `src/pact/use/`, `src/pact/examples/` as platform code.
5. Use Python namespace package coexistence: `pact.governance` from kailash-pact, everything else from local source.
6. Disable PyPI publishing; keep Docker container publishing.

### Consequences

#### Positive

- Single source of truth for governance code (kailash-py)
- This repo has a clear identity: reference platform, not framework
- Verticals (astra, arbor) and this repo all depend on the same kailash-pact package
- Reduced maintenance burden (no governance code duplication)

#### Negative

- Python namespace merging adds complexity and fragility
- Requires coordination with kailash-py workspace for shared type ownership
- Trust layer remains local until kailash core absorbs EATP (creates a two-phase repivot)
- `pact.build.config.schema` type ownership is unresolved -- must be settled in Phase 0

### Alternatives Considered

#### Option A: Full rename to `pact_platform` top-level package

All 150+ source files and 120+ test files rewritten to use `from pact_platform import ...`. Clean separation but massive mechanical change with high risk of introducing bugs.

#### Option B: Vendor kailash-pact as a subtree

Copy kailash-pact source into this repo under `vendor/`. Zero namespace issues but defeats the purpose of the migration (still two copies of governance code).

#### Option C (chosen): Namespace coexistence

Delete local governance, install kailash-pact, rely on Python resolving `pact.governance` from the installed package and `pact.use/build/trust` from local source. Requires careful `__init__.py` management but minimal code changes.
