# Definitive Requirements Breakdown: pact-platform v0.3.0

**Date**: 2026-03-24
**Status**: Ready for /todos
**Execution model**: Autonomous (10x multiplier, ~5 sessions)
**Inputs**: All 15 analysis documents (#18-33), full codebase audit, kailash-py package scan, kaizen-agents source review

---

## Codebase Metrics (measured 2026-03-24)

| Metric                                            | Count                              |
| ------------------------------------------------- | ---------------------------------- |
| Source files under `src/pact/`                    | ~156 across 6 packages             |
| `from pact.` imports in `src/`                    | 461 occurrences across 118 files   |
| `from pact.` imports in `tests/`                  | 1,034 occurrences across 185 files |
| `from pact.build.config.schema` imports total     | 233 occurrences across 200 files   |
| Governance files (to delete, now in kailash-pact) | 30 files                           |
| Trust files (to triage)                           | 58 files (22 delete, 36 keep)      |
| Build files (to move)                             | 29 files                           |
| Use files (to move)                               | 25 files                           |
| Example files (to move)                           | 13 files                           |
| Test files total                                  | ~191 files                         |
| Frontend (Next.js at apps/web/)                   | Existing, needs 4 new pages        |
| Mobile (Flutter at apps/mobile/)                  | Existing, needs 3 new screens      |

## Upstream Dependencies (all production-ready)

| Layer | Package          | Version | Status                                       |
| ----- | ---------------- | ------- | -------------------------------------------- |
| L1    | kailash-pact     | 0.3.0   | Production (46 src, 46 tests, 88 exports)    |
| L1    | kailash-kaizen   | 2.1.1   | Production (556 src, 764 tests, L3 complete) |
| L1    | kailash-dataflow | 1.2.0   | Production (238 src, 449 tests)              |
| L1    | kailash-nexus    | 1.4.3   | Production (58 src, 105 tests)               |
| L2    | kaizen-agents    | 0.1.0   | Beta-ready (59 src, 35 tests)                |

## Decisions (locked)

| Decision                      | Choice                                     | Rationale                                             |
| ----------------------------- | ------------------------------------------ | ----------------------------------------------------- |
| Package name                  | `pact-platform`                            | Resolves namespace collision with kailash-pact        |
| Source namespace              | `pact_platform`                            | Python convention for hyphenated package names        |
| Import rewrite strategy       | Bulk rewrite (not shim)                    | Clean separation, no lingering ambiguity              |
| Storage for work management   | DataFlow (11 models)                       | 121 auto-generated nodes vs ~3K lines hand-rolled SQL |
| Storage for governance        | Keep direct SQLite (via kailash-pact)      | Trust-critical, red-team validated, protocol-based    |
| API framework                 | Extend existing FastAPI                    | Production-hardened middleware already in place       |
| Delegate entry point          | GovernedSupervisor                         | Progressive disclosure API, simplest L3 surface       |
| Trust files superseded        | Delete (~22 files)                         | Now in kailash-pact or kaizen-agents                  |
| Trust files platform-specific | Keep and move (~36 files)                  | Platform runtime needs these                          |
| build/verticals/              | Delete (5 dead shims)                      | Boundary-test violation, superseded by examples/      |
| build/config/schema.py        | Thin re-export from pact.governance.config | Single source of truth                                |

---

## M0: Platform Rename and Cleanup

**Priority**: CRITICAL PATH -- nothing else can proceed until this completes
**Effort**: 1 autonomous session
**Todo count**: 13

---

### TODO-0001: Create `src/pact_platform/` directory structure [S]

**Description**: Create the new package root directory with a proper `__init__.py`. This is the first file created and establishes the new namespace.

**What to create**:

- `src/pact_platform/__init__.py` with `__version__ = "0.3.0"`, Apache 2.0 header, module docstring describing the three-layer architecture, and public API exports (populated incrementally as modules move)

**Acceptance criteria**:

- `src/pact_platform/__init__.py` exists with correct version
- `python -c "import pact_platform; print(pact_platform.__version__)"` prints `0.3.0`
- `pyproject.toml` `tool.setuptools.packages.find` `where = ["src"]` discovers `pact_platform`

**Dependencies**: None

---

### TODO-0002: Move `src/pact/build/` to `src/pact_platform/build/` [M]

**Description**: Relocate the entire `build/` subtree (20 .py files). This includes config, org builder, workspace, CLI, templates, and bootstrap.

**Files to move (20)**:

```
build/__init__.py
build/bootstrap.py
build/config/__init__.py
build/config/schema.py        -- becomes re-export shim from pact.governance.config
build/config/env.py
build/config/defaults.py
build/config/loader.py
build/org/__init__.py
build/org/builder.py
build/org/generator.py
build/org/envelope_deriver.py
build/org/role_catalog.py
build/org/utils.py
build/workspace/__init__.py
build/workspace/models.py
build/workspace/coordinator.py
build/workspace/discovery.py
build/workspace/bridge.py
build/workspace/knowledge_policy.py
build/workspace/bridge_lifecycle.py
build/cli/__init__.py          -- 573+ lines, existing CLI
build/cli/__main__.py
build/templates/__init__.py
build/templates/registry.py
```

**Critical**: `build/config/schema.py` (528 lines, 233 import sites) becomes a thin re-export shim:

```python
# src/pact_platform/build/config/schema.py
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

**Acceptance criteria**:

- All 20+ files moved to `src/pact_platform/build/`
- `schema.py` is a re-export shim (no duplicated type definitions)
- Internal imports within build/ updated to `pact_platform.build.*`
- No governance type definitions duplicated

**Dependencies**: TODO-0001

---

### TODO-0003: Move `src/pact/use/` to `src/pact_platform/use/` [M]

**Description**: Relocate the entire `use/` subtree (25 .py files). This includes the API server, execution runtime, LLM backends, approval queue, and observability.

**Files to move (25)**:

```
use/__init__.py
use/api/__init__.py
use/api/server.py              -- 400+ lines, FastAPI server with middleware
use/api/endpoints.py           -- 1500+ lines, PactAPI handler class
use/api/events.py
use/api/shutdown.py
use/execution/__init__.py
use/execution/runtime.py       -- 1200+ lines, ExecutionRuntime
use/execution/session.py
use/execution/agent.py
use/execution/approval.py      -- ApprovalQueue (in-memory, will be DataFlow-backed in M2)
use/execution/registry.py
use/execution/lifecycle.py
use/execution/kaizen_bridge.py
use/execution/hook_enforcer.py
use/execution/posture_enforcer.py
use/execution/llm_backend.py
use/execution/approver_auth.py
use/execution/backends/__init__.py
use/execution/backends/openai_backend.py
use/execution/backends/anthropic_backend.py
use/observability/__init__.py
use/observability/logging.py
use/observability/metrics.py
use/observability/alerting.py
```

**Acceptance criteria**:

- All 25 files moved to `src/pact_platform/use/`
- Internal imports updated to `pact_platform.use.*`
- `from pact.build.config.schema` imports rewritten to `from pact_platform.build.config.schema` or `from pact.governance.config`
- `from pact.trust.*` imports rewritten to `from pact_platform.trust.*` for kept files

**Dependencies**: TODO-0001

---

### TODO-0004: Move `src/pact/examples/` to `src/pact_platform/examples/` [S]

**Description**: Relocate example verticals (13 .py files). The university example is the primary demo.

**Files to move (13)**:

```
examples/__init__.py
examples/university/__init__.py
examples/university/org.py
examples/university/clearance.py
examples/university/barriers.py
examples/university/envelopes.py
examples/university/demo.py
examples/foundation/__init__.py
examples/foundation/org.py
examples/foundation/dm_team.py
examples/foundation/dm_prompts.py
examples/foundation/dm_runner.py
examples/foundation/templates/__init__.py
```

**Acceptance criteria**:

- All example files moved
- Examples import governance primitives from `pact.governance` (kailash-pact)
- Examples import platform services from `pact_platform`
- University demo still runs end-to-end (32/32 checks)

**Dependencies**: TODO-0002

---

### TODO-0005: Delete `src/pact/governance/` (superseded by kailash-pact) [M]

**Description**: Delete the entire `src/pact/governance/` directory. All 30 files are now in kailash-pact and installed via `pip install kailash-pact>=0.2.0`.

**Files to delete (30)**:

```
governance/__init__.py
governance/access.py
governance/addressing.py
governance/agent.py
governance/agent_mapping.py
governance/audit.py
governance/clearance.py
governance/cli.py
governance/compilation.py
governance/context.py
governance/decorators.py
governance/engine.py
governance/envelopes.py
governance/envelope_adapter.py
governance/explain.py
governance/knowledge.py
governance/middleware.py
governance/store.py
governance/testing.py
governance/verdict.py
governance/yaml_loader.py
governance/api/__init__.py
governance/api/auth.py
governance/api/endpoints.py
governance/api/events.py
governance/api/router.py
governance/api/schemas.py
governance/stores/__init__.py
governance/stores/backup.py
governance/stores/sqlite.py
```

**Verification**: `python -c "from pact.governance import GovernanceEngine"` must resolve to the kailash-pact package, NOT local code.

**Acceptance criteria**:

- All 30 governance files deleted
- `from pact.governance import GovernanceEngine` resolves to kailash-pact
- No remaining local governance files in `src/`

**Dependencies**: TODO-0002, TODO-0003 (build and use must be moved first so governance deletion does not break imports during the transition)

---

### TODO-0006: Triage and move trust layer -- delete superseded, keep platform-specific [L]

**Description**: Classify all 58 trust files. Delete ~22 superseded by kailash-pact/kaizen-agents. Move ~36 platform-specific files to `src/pact_platform/trust/`.

**Category 1: DELETE (22 files, superseded by kailash-pact or kaizen-agents)**:

```
trust/attestation.py           -- CapabilityAttestation (now from kailash.trust)
trust/delegation.py            -- DelegationManager (superseded by GovernanceEngine)
trust/genesis.py               -- GenesisManager (superseded)
trust/lifecycle.py             -- Trust lifecycle (absorbed into GovernanceEngine)
trust/posture.py               -- TrustPosture (now from kailash.trust)
trust/scoring.py               -- TrustScore (deprecated per boundary synthesis)
trust/reasoning.py             -- ReasoningTrace (ConfidentialityLevel now from kailash.trust)
trust/decorators.py            -- CARE decorators (EATP wrappers)
trust/dual_binding.py          -- DualBinding (EATP concept)
trust/revocation.py            -- RevocationManager (EATP wrapper)
trust/integrity.py             -- TrustChainIntegrity (EATP wrapper)
trust/messaging.py             -- MessageRouter (kaizen-agents handles this)
trust/uncertainty.py           -- UncertaintyClassifier (deprecated)
trust/jcs.py                   -- canonical_hash (thin JCS wrapper, available from EATP)
trust/sd_jwt.py                -- SDJWTBuilder (EATP feature)
trust/eatp_bridge.py           -- EATPBridge (now direct import)
trust/credentials.py           -- CredentialManager (EATP concept)
trust/bridge_trust.py          -- BridgeTrustManager (absorbed into kailash-pact)
trust/bridge_posture.py        -- bridge_verification_level (absorbed)
trust/authorization.py         -- AuthorizationCheck (superseded by GovernanceEngine.verify_action)
trust/shadow_enforcer.py       -- ShadowEnforcer (kaizen-agents has BudgetTracker)
trust/shadow_enforcer_live.py  -- Live shadow enforcer (kaizen-agents subsystem)
```

**Category 2: KEEP and MOVE (36 files)**:

```
trust/__init__.py              -- Rewrite to only export kept items
trust/constraint/__init__.py
trust/constraint/envelope.py   -- ConstraintEnvelope runtime evaluation
trust/constraint/gradient.py   -- GradientEngine
trust/constraint/enforcement.py
trust/constraint/enforcer.py
trust/constraint/middleware.py
trust/constraint/cache.py
trust/constraint/circuit_breaker.py
trust/constraint/signing.py
trust/constraint/bridge_envelope.py
trust/constraint/resolution.py
trust/constraint/verification_level.py
trust/audit/__init__.py
trust/audit/anchor.py          -- AuditAnchor, AuditChain
trust/audit/pipeline.py
trust/audit/bridge_audit.py
trust/store/__init__.py
trust/store/store.py           -- TrustStore protocol
trust/store/sqlite_store.py
trust/store/postgresql_store.py
trust/store/backup.py
trust/store/health.py
trust/store/cost_tracking.py   -- CostTracker (used by API server)
trust/store/versioning.py
trust/store/posture_history.py
trust/store/migrations.py
trust/store/audit_query.py
trust/store_isolation/__init__.py
trust/store_isolation/data.py
trust/store_isolation/management.py
trust/store_isolation/violations.py
trust/resilience/__init__.py
trust/resilience/failure_modes.py
trust/auth/__init__.py
trust/auth/firebase_admin.py
```

**Procedure**: For each file to delete, grep all consumers first. If any non-test file references it, trace the dependency and either redirect the import or move the file to "keep" category. Do NOT delete a file that has unresolved consumers.

**Acceptance criteria**:

- ~22 superseded trust files deleted
- ~36 platform-specific trust files moved to `src/pact_platform/trust/`
- `src/pact_platform/trust/__init__.py` rewritten to only export kept items
- All imports from moved files updated to `pact_platform.trust.*`
- All imports from deleted files redirected to kailash-pact or removed

**Dependencies**: TODO-0002, TODO-0003

---

### TODO-0007: Delete `src/pact/build/verticals/` (dead shims) [S]

**Description**: Delete 5 vertical re-export shim files. These are dead code and violate `rules/boundary-test.md` (domain vocabulary like "dm_team" in framework code).

**Files to delete (5)**:

```
build/verticals/__init__.py
build/verticals/dm_team.py
build/verticals/dm_prompts.py
build/verticals/dm_runner.py
build/verticals/foundation.py
```

**Acceptance criteria**:

- All 5 files deleted
- No remaining imports of `pact.build.verticals` anywhere
- Grep confirms zero references

**Dependencies**: TODO-0002

---

### TODO-0008: Bulk rewrite imports in source files [L]

**Description**: Rewrite ALL `from pact.` imports in `src/pact_platform/` to use correct new paths. This is a mechanical bulk operation covering ~461 occurrences across 118 files.

**Import rewrite rules (applied in order)**:

| Old pattern                                | New pattern                                                | Rationale                          |
| ------------------------------------------ | ---------------------------------------------------------- | ---------------------------------- |
| `from pact.build.config.schema import X`   | `from pact.governance.config import X`                     | Config types now from kailash-pact |
| `from pact.build.config.env import X`      | `from pact_platform.build.config.env import X`             | Platform-specific                  |
| `from pact.build.config.loader import X`   | `from pact_platform.build.config.loader import X`          | Platform-specific                  |
| `from pact.build.config.defaults import X` | `from pact_platform.build.config.defaults import X`        | Platform-specific                  |
| `from pact.build.config import X`          | `from pact_platform.build.config import X`                 | Platform-specific                  |
| `from pact.build.org.*`                    | `from pact_platform.build.org.*`                           | Platform org builder               |
| `from pact.build.workspace.*`              | `from pact_platform.build.workspace.*`                     | Platform workspace                 |
| `from pact.build.cli.*`                    | `from pact_platform.build.cli.*`                           | Platform CLI                       |
| `from pact.build.bootstrap`                | `from pact_platform.build.bootstrap`                       | Platform bootstrap                 |
| `from pact.build.templates.*`              | `from pact_platform.build.templates.*`                     | Platform templates                 |
| `from pact.use.*`                          | `from pact_platform.use.*`                                 | Platform execution/API             |
| `from pact.trust.X` (kept files)           | `from pact_platform.trust.X`                               | Platform trust layer               |
| `from pact.trust.X` (deleted files)        | `from pact.governance.X` or `from kailash.trust import X`  | Redirect to kailash-pact           |
| `from pact.governance.*`                   | `from pact.governance.*` (NO CHANGE)                       | Already from kailash-pact          |
| `from pact.examples.*`                     | `from pact_platform.examples.*`                            | Platform examples                  |
| `import pact` (top-level)                  | `import pact_platform` or keep if referencing kailash-pact | Context-dependent                  |

**Acceptance criteria**:

- Zero `from pact.build.` imports remain in `src/pact_platform/`
- Zero `from pact.use.` imports remain
- Zero `from pact.trust.` imports to deleted files remain
- `from pact.governance.*` imports unchanged (resolve to kailash-pact)
- `python -c "import pact_platform"` succeeds

**Dependencies**: TODO-0002 through TODO-0007

---

### TODO-0009: Bulk rewrite imports in test files [L]

**Description**: Rewrite ALL `from pact.` imports in `tests/` to use correct new paths. Same rewrite rules as TODO-0008 applied to ~1,034 occurrences across 185 test files.

**Special considerations**:

- `tests/unit/governance/` (37 files, 198 occurrences) -- these tests now validate the kailash-pact package in the platform context; imports should point to `pact.governance` (kailash-pact)
- `tests/integration/conftest.py` (175 lines) -- imports from build, trust, use; needs thorough rewrite
- Tests for deleted trust files -- either delete the test file or rewrite to test the kailash-pact equivalent
- Tests for moved trust files -- update to `pact_platform.trust.*`
- Tests for build/use modules -- update to `pact_platform.build.*` / `pact_platform.use.*`

**Acceptance criteria**:

- All 185 test files import from correct packages
- `pytest --collect-only` shows zero collection errors (down from 153)
- No `ModuleNotFoundError` on any test import
- Governance tests validate kailash-pact package
- Platform tests validate pact_platform code

**Dependencies**: TODO-0008

---

### TODO-0010: Delete `src/pact/` remnant directory [S]

**Description**: After all moves, deletions, and rewrites, `src/pact/` should be empty. Delete it entirely. The `pact` namespace is now exclusively owned by kailash-pact (installed dependency).

**Acceptance criteria**:

- `src/pact/` directory does not exist
- `from pact.governance import GovernanceEngine` resolves to kailash-pact
- `from pact_platform.use.api.server import create_app` works
- No local code shadows kailash-pact's `pact.*` namespace

**Dependencies**: TODO-0008, TODO-0009

---

### TODO-0011: Update `pyproject.toml` and entry points [S]

**Description**: Ensure version consistency, entry points, and package discovery are correct.

**Changes**:

- Verify `src/pact_platform/__init__.py` has `__version__ = "0.3.0"` matching pyproject.toml
- Create `src/pact_platform/cli.py` that imports from `pact_platform.build.cli`
- Verify `project.scripts.pact = "pact_platform.cli:main"` works
- Verify `tool.setuptools.packages.find` discovers `pact_platform` (not `pact`)
- Remove `src/pact/` from any exclude patterns if present

**Acceptance criteria**:

- `python -c "import pact_platform; print(pact_platform.__version__)"` prints `0.3.0`
- `pip install -e .` installs correctly
- `pact --help` works via entry point
- No version mismatch between pyproject.toml and **init**.py

**Dependencies**: TODO-0008

---

### TODO-0012: Fix test suite -- green on `pytest` [L]

**Description**: After all moves, rewrites, and deletions, fix any remaining test failures. This is the quality gate for M0.

**Expected issues**:

- Fixture imports in conftest files referencing old paths
- Relative import paths in test helpers
- `scripts/seed_demo.py` references to old paths
- Integration test conftest (175 lines) needs thorough rewrite
- Property tests (hypothesis) may need fixture updates
- Tests for deleted trust files need deletion or rewrite
- Test fixture factories that construct old-path objects

**Acceptance criteria**:

- `pytest --collect-only` shows zero collection errors
- `pytest` runs with all previously-passing tests still passing
- Any test that tested a deleted file is either deleted or rewritten to test kailash-pact
- Test count documented before and after (expect some reduction from deleted trust tests)

**Dependencies**: TODO-0009, TODO-0010, TODO-0011

---

### TODO-0013: Update CLAUDE.md, rule files, and documentation for new paths [S]

**Description**: Update all documentation and rule files that reference `src/pact/` paths. These files are the institutional knowledge layer for COC.

**Files to update**:

- `CLAUDE.md` -- Architecture overview, module paths, import examples, `runtime.execute()` code block
- `.claude/rules/governance.md` -- Scope paths (remove src/pact/governance references, add pact_platform paths)
- `.claude/rules/boundary-test.md` -- Scope path from `src/pact/` to `src/pact_platform/`
- `.claude/rules/trust-plane-security.md` -- Scope paths
- `.claude/rules/pact-governance.md` -- Scope paths and import examples
- `.claude/rules/learned-instincts.md` -- Any path references
- `docs/quickstart.md` -- Import examples
- `docs/cookbook.md` -- Import examples
- `scripts/seed_demo.py` -- Import paths
- `examples/quickstart.py` -- Import paths

**Acceptance criteria**:

- All rule files reference correct `pact_platform` paths
- CLAUDE.md architecture section reflects new package structure
- No references to deleted `src/pact/governance/` in rules
- No references to `from pact.build.` or `from pact.use.` in documentation
- Documentation examples use correct imports

**Dependencies**: TODO-0010

---

## M1: Work Management DataFlow Models

**Priority**: HIGH -- parallel with M3
**Effort**: 1 autonomous session (part of session with M3)
**Todo count**: 12
**Framework**: kailash-dataflow (auto-generates 11 CRUD nodes per model = 121 total)

All models live in `src/pact_platform/models/`. Each model is a DataFlow model definition that auto-generates Create, Read, Update, Delete, List, Count, Search, Bulk Create, Bulk Update, Bulk Delete, and Exists workflow nodes.

---

### TODO-1001: DataFlow model -- AgenticObjective [S]

**Description**: High-level goal submitted by a human or upstream system. The top of the work hierarchy.

**File**: `src/pact_platform/models/objective.py`

**Fields**:

- `id`: str (UUID, PK)
- `org_address`: str (D/T/R address of owning unit, validated with `Address.parse()`)
- `title`: str (max 200 chars)
- `description`: str (max 5,000 chars)
- `submitted_by`: str (user identity or role address)
- `status`: enum (`DRAFT`, `ACTIVE`, `DECOMPOSING`, `IN_PROGRESS`, `REVIEW`, `COMPLETED`, `CANCELLED`)
- `priority`: enum (`LOW`, `NORMAL`, `HIGH`, `CRITICAL`)
- `budget_usd`: float (nullable, `math.isfinite()` validated)
- `deadline`: datetime (nullable)
- `parent_objective_id`: str (nullable, FK for sub-objectives)
- `metadata`: JSON dict
- `created_at`: datetime
- `updated_at`: datetime
- `completed_at`: datetime (nullable)

**Indexes**: `status`, `org_address`, `submitted_by`, `created_at`

**Constraints**:

- `math.isfinite()` on `budget_usd` (governance.md Rule 4)
- Status transitions: terminal states (`COMPLETED`, `CANCELLED`) cannot revert
- `validate_id()` on `id` before storage

**Acceptance criteria**:

- DataFlow model generates CRUD nodes
- Alembic migration script generated
- Unit test: create, read, list, update status, filter by status
- NaN/Inf rejected on budget_usd

**Dependencies**: M0 complete

---

### TODO-1002: DataFlow model -- AgenticRequest [S]

**Description**: Decomposed task assigned to an agent or human, derived from an objective.

**File**: `src/pact_platform/models/request.py`

**Fields**:

- `id`: str (UUID, PK)
- `objective_id`: str (FK to AgenticObjective)
- `title`: str (max 200 chars)
- `description`: str (max 5,000 chars)
- `assigned_to`: str (nullable, role address or agent ID)
- `assigned_pool_id`: str (nullable, FK to AgenticPool)
- `status`: enum (`PENDING`, `CLAIMED`, `IN_PROGRESS`, `SUBMITTED`, `REVIEW`, `APPROVED`, `REJECTED`, `HELD`, `CANCELLED`)
- `request_type`: enum (`AUTONOMOUS`, `HUMAN_REQUIRED`, `HYBRID`)
- `priority`: enum (`LOW`, `NORMAL`, `HIGH`, `CRITICAL`)
- `role_address`: str (nullable, D/T/R address for governance)
- `estimated_cost_usd`: float (nullable, NaN-guarded)
- `actual_cost_usd`: float (nullable, NaN-guarded)
- `deadline`: datetime (nullable)
- `parent_request_id`: str (nullable, for sub-tasks)
- `governance_verdict`: str (nullable, last verdict level)
- `metadata`: JSON dict
- `created_at`: datetime
- `updated_at`: datetime
- `claimed_at`: datetime (nullable)
- `completed_at`: datetime (nullable)

**Indexes**: `objective_id`, `status`, `assigned_to`, `assigned_pool_id`

**Constraints**:

- FK to AgenticObjective (objective_id must exist)
- `math.isfinite()` on cost fields
- D/T/R grammar validation on role_address if provided

**Acceptance criteria**:

- DataFlow model with FK relationship to AgenticObjective
- CRUD nodes auto-generated
- Migration generated
- Unit test: create request, link to objective, update status, filter by objective

**Dependencies**: TODO-1001

---

### TODO-1003: DataFlow model -- AgenticWorkSession [S]

**Description**: Active work session tracking agent execution with cost accumulation.

**File**: `src/pact_platform/models/work_session.py`

**Fields**:

- `id`: str (UUID, PK)
- `request_id`: str (FK to AgenticRequest)
- `agent_id`: str
- `role_address`: str (D/T/R address for governance context)
- `status`: enum (`ACTIVE`, `PAUSED`, `COMPLETED`, `FAILED`, `HELD`, `ABANDONED`)
- `started_at`: datetime
- `ended_at`: datetime (nullable)
- `cost_usd`: float (accumulated, NaN-guarded)
- `input_tokens`: int (LLM input tokens consumed)
- `output_tokens`: int (LLM output tokens consumed)
- `tool_calls`: int (tools invoked)
- `provider`: str (nullable, LLM provider name)
- `model_name`: str (nullable, LLM model used)
- `envelope_snapshot`: JSON dict (constraint envelope at session start)
- `metadata`: JSON dict

**Indexes**: `request_id`, `agent_id`, `status`, `started_at`

**Acceptance criteria**:

- DataFlow model with FK to AgenticRequest
- Cost accumulated incrementally (not overwritten)
- NaN/Inf rejected on cost_usd
- Unit test: start session, add cost increments, end session

**Dependencies**: TODO-1002

---

### TODO-1004: DataFlow model -- AgenticArtifact [S]

**Description**: Deliverable produced by an agent, with versioning and clearance classification.

**File**: `src/pact_platform/models/artifact.py`

**Fields**:

- `id`: str (UUID, PK)
- `request_id`: str (FK to AgenticRequest)
- `session_id`: str (nullable, FK to AgenticWorkSession)
- `name`: str (max 200 chars)
- `artifact_type`: enum (`DOCUMENT`, `CODE`, `DATA`, `REPORT`, `ANALYSIS`, `IMAGE`, `OTHER`)
- `version`: int (monotonically increasing per request_id + name)
- `content_ref`: str (URL, file path, or inline for small content)
- `content_hash`: str (SHA-256 for integrity)
- `classification`: enum (`PUBLIC`, `RESTRICTED`, `CONFIDENTIAL`, `SECRET`, `TOP_SECRET`)
- `created_by`: str (agent ID or user)
- `created_at`: datetime
- `size_bytes`: int (nullable)
- `metadata`: JSON dict

**Indexes**: `request_id`, `session_id`, `artifact_type`, `classification`

**Constraints**:

- Classification validated against creating agent's clearance level (agent with RESTRICTED clearance cannot produce SECRET artifact)
- Version monotonically increases (never decreases for same name+request)

**Acceptance criteria**:

- DataFlow model with FKs
- Clearance validation on creation
- Version auto-increment logic
- Unit test: create artifact, verify clearance check, test versioning

**Dependencies**: TODO-1002, TODO-1003

---

### TODO-1005: DataFlow model -- AgenticDecision [S]

**Description**: Human decision point recording approval/rejection of HELD governance actions.

**File**: `src/pact_platform/models/decision.py`

**Fields**:

- `id`: str (UUID, PK)
- `request_id`: str (FK to AgenticRequest)
- `session_id`: str (nullable, FK to AgenticWorkSession)
- `action_description`: str (what the agent attempted)
- `governance_verdict`: enum (`AUTO_APPROVED`, `FLAGGED`, `HELD`, `BLOCKED`)
- `constraint_dimension`: str (which dimension triggered: financial, operational, temporal, data_access, communication)
- `reason`: str (why it was held/blocked)
- `envelope_snapshot`: JSON dict (envelope state at decision time)
- `decided_by`: str (nullable, human approver identity)
- `decided_at`: datetime (nullable)
- `resolution`: enum (nullable, `APPROVED`, `REJECTED`, `ESCALATED`, `EXPIRED`)
- `resolution_reason`: str (nullable)
- `created_at`: datetime
- `expires_at`: datetime (nullable, default 24h from creation)
- `metadata`: JSON dict

**Indexes**: `request_id`, `governance_verdict`, `resolution`, `created_at`

**Acceptance criteria**:

- DataFlow model
- Decision starts as HELD, resolved by human action
- Expired decisions auto-resolve to REJECTED (configurable)
- Creates audit anchor on resolution
- Unit test: create HELD decision, approve, reject, escalate, expire

**Dependencies**: TODO-1002

---

### TODO-1006: DataFlow model -- AgenticReviewDecision [S]

**Description**: Human or agent review of produced artifacts (distinct from governance decision).

**File**: `src/pact_platform/models/review.py`

**Fields**:

- `id`: str (UUID, PK)
- `request_id`: str (FK to AgenticRequest)
- `artifact_id`: str (FK to AgenticArtifact)
- `reviewer`: str (role address or user identity)
- `outcome`: enum (`APPROVED`, `CHANGES_REQUESTED`, `REJECTED`)
- `comments`: str (max 5,000 chars)
- `reviewed_at`: datetime
- `metadata`: JSON dict

**Indexes**: `request_id`, `artifact_id`, `outcome`

**Acceptance criteria**:

- DataFlow model with FK to AgenticRequest and AgenticArtifact
- Review creates corresponding AgenticFinding records for specific issues
- Unit test: submit review, verify finding creation

**Dependencies**: TODO-1004

---

### TODO-1007: DataFlow model -- AgenticFinding [S]

**Description**: Specific issue or observation found during review or agent execution.

**File**: `src/pact_platform/models/finding.py`

**Fields**:

- `id`: str (UUID, PK)
- `request_id`: str (FK to AgenticRequest)
- `review_id`: str (nullable, FK to AgenticReviewDecision)
- `session_id`: str (nullable, FK to AgenticWorkSession)
- `severity`: enum (`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
- `category`: str (e.g., "governance_violation", "quality", "security", "budget")
- `title`: str (max 200 chars)
- `description`: str
- `found_by`: str (agent ID or reviewer identity)
- `status`: enum (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`, `WONT_FIX`)
- `resolved_by`: str (nullable)
- `resolved_at`: datetime (nullable)
- `created_at`: datetime
- `metadata`: JSON dict

**Indexes**: `request_id`, `severity`, `status`, `category`

**Acceptance criteria**:

- DataFlow model
- Finding linked to review or session (at least one FK populated)
- Unit test: create finding, resolve finding, filter by severity

**Dependencies**: TODO-1002

---

### TODO-1008: DataFlow model -- AgenticPool [S]

**Description**: Group of agents and/or humans who can claim and execute work requests.

**File**: `src/pact_platform/models/pool.py`

**Fields**:

- `id`: str (UUID, PK)
- `org_address`: str (D/T/R address of owning unit)
- `name`: str (max 100 chars, unique per org)
- `description`: str (max 1,000 chars)
- `pool_type`: enum (`AGENT_ONLY`, `HUMAN_ONLY`, `MIXED`)
- `routing_strategy`: enum (`ROUND_ROBIN`, `LEAST_LOADED`, `CAPABILITY_MATCH`, `MANUAL`)
- `max_concurrent`: int (max tasks a single member can hold)
- `status`: enum (`ACTIVE`, `PAUSED`, `DRAINING`)
- `created_at`: datetime
- `updated_at`: datetime
- `metadata`: JSON dict

**Indexes**: `org_address`, `status`, `name`

**Acceptance criteria**:

- DataFlow model
- D/T/R grammar validation on org_address
- Name unique within org scope
- Unit test: create pool, update status, verify routing strategy

**Dependencies**: TODO-1001

---

### TODO-1009: DataFlow model -- AgenticPoolMembership [S]

**Description**: Association between agents/users and pools with capability metadata.

**File**: `src/pact_platform/models/pool_membership.py`

**Fields**:

- `id`: str (UUID, PK)
- `pool_id`: str (FK to AgenticPool)
- `member_id`: str (agent ID or user identity)
- `member_type`: enum (`AGENT`, `HUMAN`)
- `role_address`: str (nullable, D/T/R address)
- `capabilities`: JSON list (what the member can do)
- `current_load`: int (current active task count)
- `max_concurrent`: int (nullable, member-specific override of pool default)
- `status`: enum (`ACTIVE`, `SUSPENDED`, `REMOVED`)
- `joined_at`: datetime
- `left_at`: datetime (nullable)
- `metadata`: JSON dict

**Indexes**: `pool_id`, `member_id`, `status`

**Constraints**:

- Unique constraint on (pool_id, member_id) for active members
- current_load cannot exceed max_concurrent (pool or member override)

**Acceptance criteria**:

- DataFlow model with FK to AgenticPool
- Unique active membership enforced
- Load tracking works
- Unit test: add member, check load, remove member

**Dependencies**: TODO-1008

---

### TODO-1010: DataFlow model -- Run [S]

**Description**: Execution run linking an objective to a GovernedSupervisor execution.

**File**: `src/pact_platform/models/run.py`

**Fields**:

- `id`: str (UUID, PK)
- `objective_id`: str (FK to AgenticObjective)
- `plan_id`: str (nullable, GovernedSupervisor Plan ID)
- `status`: enum (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `HELD`, `CANCELLED`)
- `started_at`: datetime
- `ended_at`: datetime (nullable)
- `budget_allocated_usd`: float (NaN-guarded)
- `budget_consumed_usd`: float (NaN-guarded)
- `node_count`: int (plan nodes)
- `nodes_completed`: int
- `nodes_failed`: int
- `agent_count`: int
- `governance_verdicts`: JSON list (gradient verdicts during run)
- `error`: str (nullable)
- `metadata`: JSON dict

**Indexes**: `objective_id`, `status`, `started_at`

**Acceptance criteria**:

- DataFlow model with FK to AgenticObjective
- NaN/Inf rejected on budget fields
- Status transitions enforced
- Unit test: create run, update progress, complete run

**Dependencies**: TODO-1001

---

### TODO-1011: DataFlow model -- ExecutionMetric [S]

**Description**: Time-series performance metrics for dashboard visualization and cost reporting.

**File**: `src/pact_platform/models/metric.py`

**Fields**:

- `id`: str (UUID, PK)
- `run_id`: str (nullable, FK to Run)
- `agent_id`: str (nullable)
- `metric_type`: enum (`LATENCY_MS`, `TOKEN_USAGE`, `TOOL_CALLS`, `COST_USD`, `ERROR_RATE`, `THROUGHPUT`)
- `dimension`: str (nullable, constraint dimension: financial, temporal, etc.)
- `value`: float (NaN-guarded)
- `unit`: str (e.g., "ms", "usd", "tokens", "count")
- `recorded_at`: datetime
- `metadata`: JSON dict

**Indexes**: `metric_type`, `recorded_at`, `agent_id`, `run_id`

**Acceptance criteria**:

- DataFlow model
- Supports time-range queries for dashboard charts
- NaN/Inf rejected on value
- Unit test: record metrics, query by time range, aggregate by type

**Dependencies**: TODO-1001

---

### TODO-1012: Alembic migration infrastructure [M]

**Description**: Set up Alembic migration environment for all 11 DataFlow models. Supports both SQLite (dev) and PostgreSQL (production).

**Components to create**:

- `alembic.ini` -- Configuration pointing to DataFlow model metadata
- `alembic/env.py` -- Environment with DataFlow model imports and multi-database support
- `alembic/versions/001_initial_schema.py` -- Initial migration creating all 11 tables
- `src/pact_platform/db.py` -- DataFlow connection factory (singleton per `rules/connection-pool.md` Rule 6)

**Database configuration**:

- Default: SQLite at `data/pact_platform.db`
- Production: PostgreSQL via `DATABASE_URL` environment variable
- Pool size via `DATAFLOW_MAX_CONNECTIONS` (per `rules/connection-pool.md` Rule 1)
- Connection timeout: 5 seconds (per `rules/connection-pool.md` Rule 5)

**Acceptance criteria**:

- `alembic upgrade head` creates all tables on fresh SQLite
- `alembic upgrade head` creates all tables on PostgreSQL (when configured)
- `alembic downgrade base` drops all tables cleanly
- Connection pool configuration follows `rules/connection-pool.md`
- DataFlow connection is application-level singleton (not per-request)
- Integration test: migrate up, insert via DataFlow nodes, query, migrate down

**Dependencies**: TODO-1001 through TODO-1011

---

## M2: Work Management API

**Priority**: HIGH -- depends on M0 and M1
**Effort**: 1 autonomous session
**Todo count**: 9
**Framework**: Extend existing FastAPI server at `src/pact_platform/use/api/server.py`

All routers live in `src/pact_platform/use/api/routers/`. Each router defines Pydantic request/response schemas, input validation, and integration tests.

---

### TODO-2001: API router -- Objectives [M]

**Description**: CRUD and lifecycle management for objectives.

**File**: `src/pact_platform/use/api/routers/objectives.py`

**Endpoints**:

- `POST /api/v1/objectives` -- Create objective (fields: title, description, priority, budget_usd, deadline, org_address)
- `GET /api/v1/objectives` -- List objectives (query params: status, priority, org_address, page, page_size)
- `GET /api/v1/objectives/{id}` -- Get objective detail (includes request count, cost summary)
- `PATCH /api/v1/objectives/{id}` -- Update objective (title, description, priority, deadline)
- `POST /api/v1/objectives/{id}/activate` -- Activate (status DRAFT -> ACTIVE, triggers decomposition)
- `POST /api/v1/objectives/{id}/cancel` -- Cancel (any non-terminal -> CANCELLED, cascades to requests)

**Request/Response schemas**: Pydantic models for each endpoint with proper validation (title length, priority enum, NaN-guard on budget_usd).

**Error handling**: 404 on missing objective, 409 on invalid status transition, 422 on validation failure.

**Acceptance criteria**:

- All 6 endpoints implemented with Pydantic request/response schemas
- Input validation: title max 200 chars, priority from enum, budget NaN-guarded
- 404 on missing, 409 on invalid transition, 422 on validation error
- Pagination on list endpoint (default page_size=20, max 100)
- Integration test with httpx AsyncClient

**Dependencies**: TODO-1001, M0 complete

---

### TODO-2002: API router -- Requests [M]

**Description**: View and manage work requests derived from objectives.

**File**: `src/pact_platform/use/api/routers/requests.py`

**Endpoints**:

- `GET /api/v1/requests` -- List requests (filter: objective_id, status, assigned_to, pool_id; pagination)
- `GET /api/v1/requests/{id}` -- Get request detail (includes sessions, artifacts, findings)
- `POST /api/v1/requests/{id}/assign` -- Assign to agent/pool (body: agent_address or pool_id)
- `POST /api/v1/requests/{id}/hold` -- Manually hold request (body: reason)
- `POST /api/v1/requests/{id}/resume` -- Resume held request (body: resolution reason)

**Acceptance criteria**:

- All 5 endpoints implemented
- Request-objective relationship visible in responses
- Agent assignment validates D/T/R address via `Address.parse()`
- Hold/resume transitions enforced
- Integration test

**Dependencies**: TODO-1002, TODO-2001

---

### TODO-2003: API router -- Approvals [M]

**Description**: Human approval queue for HELD governance decisions. This is the central human-in-the-loop interface.

**File**: `src/pact_platform/use/api/routers/approvals.py`

**Endpoints**:

- `GET /api/v1/approvals` -- List pending approvals (filter: urgency, dimension, status; sort: urgency then created_at)
- `GET /api/v1/approvals/{id}` -- Approval detail (includes full governance context: which constraint triggered, agent role, envelope state, audit trail snippet)
- `POST /api/v1/approvals/{id}/approve` -- Approve held action (body: reason)
- `POST /api/v1/approvals/{id}/reject` -- Reject held action (body: reason)
- `POST /api/v1/approvals/{id}/escalate` -- Escalate to higher D/T/R authority (body: target_address)

**Acceptance criteria**:

- All 5 endpoints implemented
- Approval creates EATP audit anchor via GovernanceEngine
- Rejection transitions decision to REJECTED, action to BLOCKED
- Approval transitions decision to APPROVED, action to FLAGGED (re-evaluation) or AUTO_APPROVED
- Escalation finds next authority in D/T/R hierarchy
- WebSocket event emitted on approval/rejection/escalation
- Integration test

**Dependencies**: TODO-1005, TODO-2001

---

### TODO-2004: API router -- Artifacts [M]

**Description**: View and review agent-produced work products.

**File**: `src/pact_platform/use/api/routers/artifacts.py`

**Endpoints**:

- `GET /api/v1/artifacts` -- List artifacts (filter: request_id, artifact_type, classification; pagination)
- `GET /api/v1/artifacts/{id}` -- Get artifact detail (clearance-enforced: 403 if requester lacks sufficient clearance)
- `POST /api/v1/artifacts/{id}/review` -- Submit review decision (body: outcome, comments)

**Acceptance criteria**:

- All 3 endpoints implemented
- Clearance enforcement: requester's clearance checked against artifact's classification level
- 403 Forbidden with explanation if insufficient clearance
- Review creates AgenticReviewDecision record
- Integration test

**Dependencies**: TODO-1004, TODO-1006, TODO-2001

---

### TODO-2005: API router -- Pools [M]

**Description**: Agent pool lifecycle and membership management.

**File**: `src/pact_platform/use/api/routers/pools.py`

**Endpoints**:

- `POST /api/v1/pools` -- Create pool (body: name, description, pool_type, routing_strategy, max_concurrent, org_address)
- `GET /api/v1/pools` -- List pools (filter: org_address, status; pagination)
- `GET /api/v1/pools/{id}` -- Get pool detail (includes member list with load info)
- `PATCH /api/v1/pools/{id}` -- Update pool config (max_concurrent, routing_strategy, status)
- `POST /api/v1/pools/{id}/members` -- Add member (body: member_id, member_type, capabilities)
- `DELETE /api/v1/pools/{id}/members/{member_id}` -- Remove member

**Acceptance criteria**:

- All 6 endpoints implemented
- Pool org_address validated against D/T/R grammar
- Max concurrent enforced on membership
- Member load visible in pool detail
- Integration test

**Dependencies**: TODO-1008, TODO-1009, TODO-2001

---

### TODO-2006: API router -- Metrics and Dashboard data [M]

**Description**: Aggregated metrics and dashboard data endpoints for visualization.

**File**: `src/pact_platform/use/api/routers/metrics.py`

**Endpoints**:

- `GET /api/v1/metrics/summary` -- Aggregate summary (total objectives, active/completed/cancelled, total cost, held count, average completion time)
- `GET /api/v1/metrics/timeseries` -- Time-series data (query: metric_type, start, end, granularity: hour/day/week)
- `GET /api/v1/metrics/cost` -- Cost breakdown (group by: agent, pool, objective, time_period)
- `GET /api/v1/metrics/governance` -- Governance verdict distribution (counts by verdict level, by dimension, by time period)

**Acceptance criteria**:

- All 4 endpoints implemented
- Time-series supports hour/day/week granularity
- Cost endpoint respects clearance (redacts agent-level costs if requester lacks sufficient clearance)
- All aggregations use DataFlow query nodes (not in-memory computation on full dataset)
- Integration test

**Dependencies**: TODO-1011, TODO-2001

---

### TODO-2007: Mount routers on existing API server [M]

**Description**: Wire all 6 new routers into the existing FastAPI server and configure DataFlow lifecycle.

**Changes to `src/pact_platform/use/api/server.py`**:

- Import and mount objectives, requests, approvals, artifacts, pools, and metrics routers under `/api/v1/`
- Create `src/pact_platform/use/api/routers/__init__.py`
- Add DataFlow connection to app lifespan (startup: create pool, shutdown: close pool)
- Connection pool configuration per `rules/connection-pool.md`
- Health endpoint includes DataFlow connectivity check (lightweight `SELECT 1`, NOT a full DataFlow workflow per `rules/connection-pool.md` Rule 3)

**Acceptance criteria**:

- All 6 new routers accessible via running server
- DataFlow connection established at startup, closed at shutdown
- Pool configuration follows `rules/connection-pool.md` (explicit size, bounded overflow)
- Existing governance endpoints (from kailash-pact router) still mounted and functional
- Health endpoint still works
- Full API smoke test: start server, hit all new endpoints, verify responses

**Dependencies**: TODO-2001 through TODO-2006

---

### TODO-2008: Service -- Approval queue (DataFlow-backed) [M]

**Description**: Replace the existing in-memory `ApprovalQueue` with a DataFlow-backed service that persists decisions to the database.

**File**: `src/pact_platform/services/approval_service.py`

**Responsibilities**:

- Create AgenticDecision records when governance returns HELD verdict
- List pending decisions with filtering (urgency, dimension, age)
- Process approval (update decision, emit WebSocket event, resume agent execution)
- Process rejection (update decision, emit event, cancel work session)
- Escalation logic (find next authority in D/T/R hierarchy using `GovernanceEngine`)
- Expiry handling (decisions older than configured timeout auto-reject)

**Integration with existing code**:

- Wraps DataFlow CRUD operations for AgenticDecision model
- Replaces `pact_platform.use.execution.approval.ApprovalQueue` for new code paths
- Existing ApprovalQueue kept for backward compatibility during transition

**Acceptance criteria**:

- ApprovalService persists decisions to DataFlow
- HELD actions create decisions automatically
- Approval/rejection creates EATP audit anchor via GovernanceEngine
- Expired decisions auto-reject (configurable timeout, default 24h)
- Service injected via FastAPI dependency injection
- Unit test: create HELD decision, approve, reject, escalate, expire
- Integration test: full lifecycle from governance HOLD to human resolution

**Dependencies**: TODO-1005, TODO-2003

---

### TODO-2009: Service -- Cost tracking (DataFlow-backed) [M]

**Description**: Persistent cost tracking service extending the existing CostTracker with DataFlow storage.

**File**: `src/pact_platform/services/cost_service.py`

**Responsibilities**:

- Record costs per work session (token costs from LLM providers)
- Aggregate costs by objective, agent, pool, time period
- Budget enforcement (check remaining budget before allowing execution)
- Real-time budget utilization percentage
- Cost estimation based on model pricing tables
- NaN/Inf validation on ALL cost values (per `rules/pact-governance.md` Rule 9)

**Acceptance criteria**:

- CostService wraps DataFlow operations for ExecutionMetric + AgenticWorkSession cost fields
- All cost values validated with `math.isfinite()` before storage
- Budget check returns HELD if > warning_threshold, BLOCKED if > hold_threshold
- Aggregation queries use DataFlow (not in-memory)
- Integration test: submit objective, accrue costs across sessions, verify budget enforcement

**Dependencies**: TODO-1011, TODO-1003

---

## M3: Admin CLI

**Priority**: HIGH -- parallel with M1
**Effort**: Part of session with M1
**Todo count**: 8
**Framework**: Click (already a dependency) + Rich (already a dependency) for terminal formatting

All commands live in `src/pact_platform/build/cli/`. Extends the existing CLI structure.

---

### TODO-3001: CLI command -- `pact org create <yaml>` [S]

**Description**: Create organization from YAML definition file.

**Behavior**: Parse YAML using `load_org_yaml()` (from kailash-pact), validate D/T/R grammar, compile org tree, persist compiled org. Print summary: department count, team count, role count, address map.

**Arguments**: `yaml_file` (path to YAML definition)
**Options**: `--dry-run` (validate without persisting), `--format json|table` (output format)

**Error handling**: Grammar violations printed with line number and explanation. Missing required fields listed with examples.

**Acceptance criteria**:

- `pact org create university.yaml` creates org and prints summary table
- D/T/R grammar validated during compilation
- Grammar violations produce clear, actionable error messages
- `--dry-run` validates without side effects
- Unit test with Click's CliRunner

**Dependencies**: M0 complete

---

### TODO-3002: CLI command -- `pact org list` [S]

**Description**: List all organizations with structure summary.

**Behavior**: Query DataFlow (or compiled orgs from store) for all organizations. Display as table or tree.

**Options**: `--tree` (show full D/T/R tree), `--format json|table`

**Output (table mode)**:

```
Name              Departments  Teams  Roles  Created
university-demo   3           5      8      2026-03-24
```

**Output (tree mode)**:

```
university-demo
  D:research
    R:research-lead
    T:physics
      R:physics-researcher
    T:biology
      R:biology-researcher
  D:admin
    R:admin-lead
```

**Acceptance criteria**:

- `pact org list` shows all orgs with counts
- `pact org list --tree` shows full D/T/R hierarchy
- Empty state handled gracefully ("No organizations found")
- Unit test

**Dependencies**: TODO-3001

---

### TODO-3003: CLI command -- `pact clearance grant <address> <level>` [S]

**Description**: Grant knowledge clearance to a role at a D/T/R address.

**Arguments**: `address` (D/T/R role address), `level` (clearance level: PUBLIC, RESTRICTED, CONFIDENTIAL, SECRET, TOP_SECRET)
**Options**: `--compartments <comp1,comp2>` (optional compartment restrictions)

**Error handling**:

- Invalid address: "Invalid D/T/R address 'X'. Format: D<n>-R<n>-T<n>-R<n>. Run `pact org list --tree` to see valid addresses."
- Invalid level: "Invalid clearance level 'X'. Valid levels: PUBLIC, RESTRICTED, CONFIDENTIAL, SECRET, TOP_SECRET"

**Acceptance criteria**:

- `pact clearance grant D1-R1-T1-R1 CONFIDENTIAL` works
- Invalid address format rejected with grammar explanation
- Invalid clearance level rejected with valid options
- Emits EATP audit anchor
- Posture ceiling enforced (cannot grant above posture ceiling)
- Unit test

**Dependencies**: M0 complete

---

### TODO-3004: CLI command -- `pact envelope show <address>` [S]

**Description**: Display the effective constraint envelope for a role, showing all 5 dimensions and the monotonic tightening chain.

**Arguments**: `address` (D/T/R role address)
**Options**: `--json` (raw JSON output), `--diff` (show parent vs effective, highlighting tightened dimensions)

**Output (table mode)**:

```
Effective Envelope for D1-R1-T1-R1 (Research Lead > Physics Researcher)

Dimension       Parent          Effective       Status
Financial       $10,000/day     $2,500/day      Tightened
Operational     15 tools        8 tools         Tightened
Temporal        24h             8h              Tightened
Data Access     CONFIDENTIAL    RESTRICTED      Tightened
Communication   5 channels      3 channels      Tightened
```

**Acceptance criteria**:

- Shows all 5 constraint dimensions with current values
- Shows monotonic tightening chain (parent -> effective)
- Highlights which dimensions were tightened
- Rich table formatting
- `--json` outputs machine-readable JSON
- Unit test

**Dependencies**: M0 complete

---

### TODO-3005: CLI command -- `pact bridge create <source> <target>` [S]

**Description**: Create a knowledge sharing bridge between two D/T/R units.

**Arguments**: `source` (source D/T/R address), `target` (target D/T/R address)
**Options**: `--type standing|scoped|ad_hoc`, `--policy <policy.yaml>` (KSP policy file), `--expires <datetime>` (for scoped/ad_hoc)

**Policy YAML format**:

```yaml
allowed_compartments: [research-data, publications]
clearance_required: RESTRICTED
direction: bidirectional
```

**Acceptance criteria**:

- Creates bridge with validated addresses
- Policy file parsed and validated
- Emits EATP audit anchor
- Bridge type defaults to STANDING if not specified
- Unit test

**Dependencies**: M0 complete

---

### TODO-3006: CLI command -- `pact audit export` [M]

**Description**: Export audit trail for compliance reporting.

**Options**: `--format json|csv`, `--from <date>`, `--to <date>`, `--output <file>` (default: stdout), `--verify` (validate hash chain integrity during export)

**Export includes**: All governance decisions, clearance grants, envelope changes, bridge operations, agent registrations, approval resolutions.

**Acceptance criteria**:

- JSON and CSV output formats
- Date range filtering
- Hash chain verification during export (reports broken chains)
- Output to file or stdout
- Includes complete governance event history
- Unit test

**Dependencies**: M0 complete

---

### TODO-3007: CLI command -- `pact agent register` [S]

**Description**: Register an agent in the platform and map it to a D/T/R role.

**Arguments**: `name` (agent display name)
**Options**: `--role <address>` (D/T/R role address, required), `--capabilities <cap1,cap2>`, `--model <model-id>` (LLM model), `--pool <pool-id>` (assign to pool)

**Acceptance criteria**:

- Creates agent registration with role mapping
- Validates role address exists in compiled org
- Validates capabilities against registered tool list
- Optional pool assignment validated
- Unit test

**Dependencies**: M0 complete, TODO-1008

---

### TODO-3008: CLI command -- `pact agent status` [S]

**Description**: Show agent status, activity, and governance state.

**Arguments**: `agent_id` (optional -- if omitted, shows all agents)

**Output (all agents)**:

```
Agent           Role              Posture       Active Sessions  Cost ($)  Status
research-ai     D1-R1-T1-R1      SUPERVISED    2                12.50     ACTIVE
admin-ai        D2-R1             DELEGATED     0                3.20      IDLE
```

**Output (single agent)**:

```
Agent: research-ai
Role: D1-R1-T1-R1 (Research Lead > Physics Researcher)
Posture: SUPERVISED
Active Sessions: 2
Total Cost: $12.50
Governance Verdicts: 15 AUTO_APPROVED, 3 FLAGGED, 1 HELD
Last Activity: 2026-03-24T10:30:00Z
```

**Acceptance criteria**:

- Without agent_id: table of all agents with summary
- With agent_id: detailed status with sessions, verdicts, cost history
- Rich formatting
- Unit test

**Dependencies**: TODO-3007, TODO-1003

---

## M4: GovernedSupervisor Wiring

**Priority**: HIGH -- technical crux
**Effort**: 1 autonomous session
**Todo count**: 4
**Key challenge**: Three envelope type representations must be bridged correctly while preserving monotonic tightening invariant and NaN/Inf safety across all type boundaries.

---

### TODO-4001: DelegateProtocol interface [M]

**Description**: Abstract interface between the platform (L3) and agent execution engines (L2). Allows swapping between SimpleDelegateExecutor (uses existing ExecutionRuntime) and GovernedSupervisorAdapter (uses kaizen-agents).

**File**: `src/pact_platform/delegate/protocol.py`

**Interface**:

```python
class DelegateProtocol(Protocol):
    async def submit_objective(
        self,
        objective: AgenticObjective,
        envelope: ConstraintEnvelopeConfig,
    ) -> str:
        """Submit objective for decomposition and execution. Returns run_id."""

    async def get_run_status(self, run_id: str) -> RunStatus:
        """Get current status of an execution run."""

    async def cancel_run(self, run_id: str) -> None:
        """Cancel a running execution."""

    async def resume_held(self, decision_id: str, resolution: str) -> None:
        """Resume a HELD action after human approval."""

    def subscribe_events(self, callback: Callable[[PlatformEvent], None]) -> None:
        """Subscribe to execution events for real-time updates."""
```

**Supporting types**:

- `RunStatus` (frozen dataclass): status, progress_pct, cost_consumed, cost_allocated, active_agents, held_count, events
- `PlatformEvent` (frozen dataclass): event_type, timestamp, node_id, details
- `SimpleDelegateExecutor` implementing the protocol using existing ExecutionRuntime + LLM backends

**Acceptance criteria**:

- Protocol defined with full type annotations
- RunStatus and PlatformEvent are frozen dataclasses
- SimpleDelegateExecutor implements the protocol completely
- Unit test: submit objective via SimpleDelegateExecutor, verify full lifecycle (submit -> running -> complete)
- Unit test: submit objective that triggers HELD, verify pause/resume

**Dependencies**: M0 complete, M1 complete

---

### TODO-4002: GovernedSupervisor adapter [L]

**Description**: Adapts kaizen-agents' `GovernedSupervisor` to the `DelegateProtocol`. This is the technically hardest todo in the project due to three envelope type representations.

**File**: `src/pact_platform/delegate/supervisor_adapter.py`

**Type conversion map**:

| Source                                                                                      | Target                                                                       | Where                           |
| ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------- |
| `pact.governance.config.ConstraintEnvelopeConfig` (Pydantic, from kailash-pact YAML config) | `kaizen_agents.types.ConstraintEnvelope` (frozen dataclass with dict fields) | At delegation time              |
| `kaizen_agents.types.ConstraintEnvelope`                                                    | `pact_platform.trust.constraint.envelope.ConstraintEnvelope`                 | For platform runtime evaluation |
| Platform `GovernanceVerdict`                                                                | kaizen-agents `GradientZone`                                                 | At governance check             |
| kaizen-agents `SupervisorResult`                                                            | Platform `RunStatus`                                                         | At status query                 |
| kaizen-agents `PlanEvent`                                                                   | Platform `PlatformEvent`                                                     | At event emission               |

**Adapter class**: `GovernedSupervisorAdapter(DelegateProtocol)`

**Key methods**:

- `submit_objective()`: Convert envelope, create GovernedSupervisor, call `supervisor.run()`, store Run record in DataFlow
- `_convert_envelope()`: ConstraintEnvelopeConfig -> kaizen-agents ConstraintEnvelope (static method, ~50 lines)
- `_on_plan_event()`: Convert PlanEvent to PlatformEvent, update Run record, emit to subscribers
- `resume_held()`: Look up decision, convert resolution, call supervisor governance subsystem

**Security invariants** (every conversion must verify):

- Monotonic tightening preserved across type boundaries
- `math.isfinite()` on every numeric field at every conversion point
- Budget limits in target never exceed source
- Allowed tools in target are subset of source

**Acceptance criteria**:

- Adapter converts between all three envelope types correctly
- Monotonic tightening invariant tested with property test (hypothesis)
- NaN/Inf rejected at every type boundary
- HELD verdicts create AgenticDecision records in DataFlow
- Budget from kaizen-agents BudgetTracker synced to platform cost tracking
- Unit test: submit objective through adapter, verify governance checks fire
- Integration test: full lifecycle through GovernedSupervisor (requires `pip install pact-platform[agents]`)

**Dependencies**: TODO-4001

---

### TODO-4003: Event bridge -- GovernedSupervisor events to WebSocket [M]

**Description**: Converts kaizen-agents PlanEvent emissions into WebSocket events for real-time dashboard updates.

**File**: `src/pact_platform/delegate/event_bridge.py`

**Event mapping**:

| kaizen-agents PlanEventType | Platform WebSocket event | Payload                        |
| --------------------------- | ------------------------ | ------------------------------ |
| `NODE_STARTED`              | `request.step_started`   | node_id, agent_spec.name       |
| `NODE_COMPLETED`            | `request.step_completed` | node_id, output summary, cost  |
| `NODE_FAILED`               | `request.step_failed`    | node_id, error                 |
| `NODE_HELD`                 | `approval.held`          | node_id, reason, dimension     |
| `ENVELOPE_WARNING`          | `cost.warning`           | dimension, usage_pct           |
| `PLAN_COMPLETED`            | `objective.completed`    | results summary, total cost    |
| `PLAN_FAILED`               | `objective.failed`       | failed nodes, error summary    |
| `NODE_RETRYING`             | `request.retrying`       | node_id, attempt, max_attempts |

**Architecture**:

- EventBridge subscribes to GovernedSupervisor event callback
- Converts each PlanEvent to JSON-serializable WebSocket message
- Emits on existing `event_bus` (from `pact_platform.use.api.events`)
- Connected WebSocket clients receive events in real-time

**Acceptance criteria**:

- Event bridge subscribes to GovernedSupervisor events
- Each kaizen-agents event type maps to a platform WebSocket event
- Events are JSON-serializable with standardized shape: `{type, timestamp, data}`
- Dashboard receives real-time updates via existing WebSocket infrastructure
- Unit test: emit kaizen event, verify WebSocket message shape
- Unit test: verify all PlanEventType values have a mapping (no silent drops)

**Dependencies**: TODO-4002

---

### TODO-4004: HELD verdict bridge [M]

**Description**: When GovernedSupervisor's governance subsystems issue a HELD verdict, this bridge creates an AgenticDecision in DataFlow, pauses execution, and waits for human resolution before resuming.

**File**: `src/pact_platform/delegate/held_bridge.py`

**Flow**:

1. GovernedSupervisor governance check returns HELD (from BudgetTracker, ClearanceEnforcer, or any governance subsystem)
2. Bridge creates AgenticDecision record (status=held, reason, envelope_snapshot, constraint_dimension)
3. Bridge pauses the GovernedSupervisor execution (asyncio.Event wait, NOT busy-wait)
4. WebSocket event emitted: `approval.held`
5. Human approves/rejects via approval API (TODO-2003)
6. Approval service calls `bridge.resolve(decision_id, resolution)`
7. Bridge resumes GovernedSupervisor with resolution
8. If rejected: cancel the work session, mark as BLOCKED
9. If expired (default 24h): auto-reject

**Concurrency safety**:

- asyncio.Event for pause/resume (no polling)
- Lock on resolution (prevent double-approve)
- Timeout with configurable expiry (default 24h)

**Acceptance criteria**:

- HELD verdict creates AgenticDecision automatically
- Execution pauses (asyncio.Event, not busy-wait)
- Approval resumes execution within same GovernedSupervisor session
- Rejection cancels execution, creates audit anchor
- Timeout auto-rejects after configurable period
- Unit test: trigger HELD, approve, verify resume
- Unit test: trigger HELD, reject, verify cancel
- Unit test: trigger HELD, timeout, verify auto-reject
- Concurrent approval test (two approvers, only first succeeds)

**Dependencies**: TODO-4002, TODO-2008

---

## M5: Frontend Updates

**Priority**: MEDIUM -- depends on M2 and M4
**Effort**: Part of session 5 (parallel with M6)
**Todo count**: 4
**Stack**: Next.js (existing at `apps/web/`), Flutter (existing at `apps/mobile/`)

---

### TODO-5001: Web page -- Objective Management [L]

**Description**: Dashboard page for creating, viewing, and tracking objectives. The primary entry point for the work management system.

**File**: New page in `apps/web/`

**Components**:

- **Objective list**: Table with status badges (color-coded), priority indicators, cost summation, pagination
- **Objective detail**: Expandable view showing decomposed requests as tree, cost per request, governance verdicts
- **Create form**: Title, description, priority selector, budget input (with NaN guard on client), deadline picker, org unit selector
- **Status timeline**: Visual timeline of objective lifecycle (draft -> active -> in_progress -> completed)
- **Real-time updates**: WebSocket subscription for live status changes and cost updates

**API contracts**:

- `GET /api/v1/objectives` (list)
- `GET /api/v1/objectives/{id}` (detail)
- `POST /api/v1/objectives` (create)
- `PATCH /api/v1/objectives/{id}` (update)
- `POST /api/v1/objectives/{id}/activate` (activate)
- `POST /api/v1/objectives/{id}/cancel` (cancel)
- WebSocket: `objective.*` events

**Acceptance criteria**:

- Page loads and displays objectives from API
- Create form submits and shows new objective
- Status transitions reflected in real-time via WebSocket
- Cost totals update as work progresses
- Responsive layout (desktop and mobile-friendly)
- Error states handled (API down, validation errors)

**Dependencies**: TODO-2001, TODO-4003

---

### TODO-5002: Web page -- Approval Queue [L]

**Description**: Human approval interface for HELD governance decisions. This is the most critical UX page -- it is where humans exercise judgment.

**File**: New page in `apps/web/`

**Components**:

- **Pending list**: Sorted by urgency (IMMEDIATE first), then creation time. Status badges for urgency level. Count badge in sidebar navigation.
- **Decision detail panel**: Full governance context rendered in understandable format:
  - What the agent tried to do (action description)
  - Which constraint triggered (dimension name + current value vs limit)
  - Agent's role and envelope (visual constraint display)
  - Relevant audit trail entries
  - Time remaining before expiry
- **Action buttons**: Approve (green), Reject (red), Escalate (yellow) with required reason field
- **Batch mode**: Select multiple similar decisions and approve/reject in batch
- **Real-time**: New HELD actions appear without refresh

**API contracts**:

- `GET /api/v1/approvals` (list pending)
- `GET /api/v1/approvals/{id}` (detail)
- `POST /api/v1/approvals/{id}/approve`
- `POST /api/v1/approvals/{id}/reject`
- `POST /api/v1/approvals/{id}/escalate`
- WebSocket: `approval.*` events

**Acceptance criteria**:

- Page loads pending approvals sorted by urgency
- Detail view explains governance context in plain language (not raw JSON)
- Approve/Reject immediately updates state and emits WebSocket event
- Escalate moves to next D/T/R authority level
- Batch operations work for similar decisions
- Count badge updates in real-time

**Dependencies**: TODO-2003, TODO-4004

---

### TODO-5003: Web page -- Pool Management [M]

**Description**: Agent pool configuration and membership management.

**File**: New page in `apps/web/`

**Components**:

- **Pool list**: Cards showing pool name, type badge, member count, active task count, routing strategy
- **Pool detail**: Member table with load indicators (progress bars), capabilities list, activity metrics
- **Create pool form**: Name, description, type selector, routing strategy, max concurrent, org unit selector
- **Member management**: Add agent (search by name/role), remove agent, view member activity

**API contracts**:

- `POST /api/v1/pools` (create)
- `GET /api/v1/pools` (list)
- `GET /api/v1/pools/{id}` (detail)
- `PATCH /api/v1/pools/{id}` (update)
- `POST /api/v1/pools/{id}/members` (add member)
- `DELETE /api/v1/pools/{id}/members/{member_id}` (remove member)

**Acceptance criteria**:

- Pool CRUD operations work through UI
- Agent membership add/remove works
- Load indicators show current utilization
- Activity metrics display correctly

**Dependencies**: TODO-2005

---

### TODO-5004: Web page -- Interactive Org Builder [L]

**Description**: Visual tool for building and editing organizational structures. The most complex frontend component.

**File**: New page in `apps/web/`

**Components**:

- **D/T/R tree visualization**: Interactive tree rendering departments, teams, and roles as nested nodes. Expandable/collapsible.
- **Drag-and-drop editing**: Move roles between teams, teams between departments. Maintains D/T/R grammar invariant (every D or T must have exactly one R).
- **Envelope editor**: Per-role sliders for each constraint dimension (financial limit, tool count, temporal window, clearance ceiling, communication channels). Visual indicators showing parent vs child values (monotonic tightening).
- **Clearance assignment**: Per-role dropdown for clearance level, with posture ceiling warning.
- **Grammar validation**: Real-time validation highlighting grammar violations as user edits. Inline error messages explaining what is wrong.
- **YAML export**: Button to export current org as YAML that `pact org create` accepts.
- **YAML import**: Button to import existing YAML and render as visual tree.

**API contracts**:

- Uses kailash-pact `GovernanceEngine` via local API endpoints
- `POST /api/v1/governance/compile-org` (validate and compile)
- `GET /api/v1/governance/org-tree` (current compiled org)
- Export generates downloadable YAML file

**Acceptance criteria**:

- Visual org tree renders from existing org data
- Drag-and-drop restructuring maintains D/T/R grammar invariant
- Grammar violations highlighted immediately (inline, not on save)
- Envelope sliders produce valid ConstraintEnvelopeConfig
- Monotonic tightening shown visually (child sliders cannot exceed parent)
- Export produces valid YAML that `pact org create` accepts
- Import loads YAML into visual editor

**Dependencies**: M0 complete (uses GovernanceEngine from kailash-pact directly)

---

## M6: Integration Layer

**Priority**: MEDIUM -- final polish
**Effort**: Part of session 5 (parallel with M5)
**Todo count**: 5

---

### TODO-6001: Webhook adapter -- Slack [M]

**Description**: Send governance events to Slack channels via incoming webhooks.

**File**: `src/pact_platform/integrations/slack.py`

**Events to notify**:

- `objective.created` -- New objective submitted
- `objective.completed` -- Objective finished
- `approval.held` -- Action requires human approval (with deep link to approval page)
- `cost.warning` -- Budget threshold exceeded
- `request.step_failed` -- Agent execution error

**Configuration** (via .env):

- `PACT_SLACK_WEBHOOK_URL` -- Incoming webhook URL
- `PACT_SLACK_CHANNEL_MAP` -- JSON mapping event types to channels

**Base adapter**: Create `src/pact_platform/integrations/base.py` with `WebhookAdapter` abstract class that all webhook adapters extend. Common logic: rate limiting (max 1 msg/sec), retry with exponential backoff, payload formatting, error logging.

**Acceptance criteria**:

- Slack webhook sends formatted messages with Block Kit layout
- Configurable channel per event type
- Rate limiting (max 1 message/second per channel)
- Retry with exponential backoff (3 attempts)
- Deep link to approval page in HELD notifications
- Unit test with mock webhook endpoint

**Dependencies**: TODO-4003

---

### TODO-6002: Webhook adapter -- Discord [S]

**Description**: Discord webhook notifications using Discord's embed format.

**File**: `src/pact_platform/integrations/discord.py`

**Extends**: `WebhookAdapter` base class from TODO-6001

**Configuration** (via .env):

- `PACT_DISCORD_WEBHOOK_URL`

**Acceptance criteria**:

- Discord webhook sends formatted embeds (title, description, color-coded by event type, fields for context)
- Same event set as Slack adapter
- Rate limiting and retry from base class
- Unit test with mock webhook endpoint

**Dependencies**: TODO-6001

---

### TODO-6003: Webhook adapter -- Microsoft Teams [S]

**Description**: Microsoft Teams webhook notifications using Adaptive Card format.

**File**: `src/pact_platform/integrations/teams.py`

**Extends**: `WebhookAdapter` base class from TODO-6001

**Configuration** (via .env):

- `PACT_TEAMS_WEBHOOK_URL`

**Acceptance criteria**:

- Teams webhook sends Adaptive Card payloads
- Cards include action buttons for approval deep links
- Same event set as Slack adapter
- Rate limiting and retry from base class
- Unit test with mock webhook endpoint

**Dependencies**: TODO-6001

---

### TODO-6004: Notification service [M]

**Description**: Multi-channel notification routing with user preferences and deduplication.

**File**: `src/pact_platform/services/notification_service.py`

**Responsibilities**:

- Route events to configured channels (Slack, Discord, Teams)
- User notification preferences (which events, which channels per user)
- Deduplication (same event to same user within 5-minute window = skip)
- Batching for high-volume events (e.g., 10 FLAGGED actions in 1 minute -> 1 summary notification instead of 10)
- Event filtering (users only get events for their org unit and below in D/T/R hierarchy)

**Configuration**: Stored in DataFlow (notification preferences model, or metadata on user/agent records).

**Acceptance criteria**:

- Notification service dispatches to all configured adapters
- User preferences respected (per-event, per-channel)
- Deduplication prevents spam (5-minute window)
- Batch mode reduces noise for high-volume events
- Clearance-aware: CONFIDENTIAL events only sent to users with sufficient clearance
- Unit test: route event, verify correct adapters called
- Unit test: verify deduplication
- Unit test: verify batching

**Dependencies**: TODO-6001, TODO-6002, TODO-6003

---

### TODO-6005: LLM provider management [M]

**Description**: BYO API keys for LLM providers, model selection per agent role, cost estimation.

**File**: `src/pact_platform/services/llm_service.py`

**Responsibilities**:

- Provider registry (OpenAI, Anthropic at minimum; extensible for others)
- API key management via `.env` ONLY (per `rules/env-models.md` -- NEVER hardcoded)
- Model selection per agent role (configured in org YAML agent definitions)
- Cost estimation per model (token pricing tables, updated regularly)
- Fallback chain (if primary model/provider fails, try secondary; configurable per role)
- Health check per provider (validate API key on startup)

**Configuration** (via .env):

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
PACT_DEFAULT_MODEL=claude-sonnet-4-6
PACT_FALLBACK_MODEL=gpt-4o
```

**Integration**: Used by `GovernedSupervisorAdapter` (TODO-4002) to create GovernedSupervisor with correct model. Used by `SimpleDelegateExecutor` for existing LLM backends.

**Acceptance criteria**:

- OpenAI and Anthropic providers supported
- Keys sourced from `.env` exclusively
- Model configured per agent in org YAML
- Cost estimation based on current token pricing
- Fallback chain triggers on provider failure
- Health check validates API key format on startup (not an API call, just format validation)
- Unit test: provider registry, model selection, fallback chain
- Integration test: verify cost estimation accuracy

**Dependencies**: M0 complete

---

## Summary

| Milestone                           | Todos  | Size                           | Dependencies | Session              |
| ----------------------------------- | ------ | ------------------------------ | ------------ | -------------------- |
| **M0: Platform Rename and Cleanup** | 13     | L (critical path)              | None         | 1                    |
| **M1: Work Management Models**      | 12     | M (mechanical DataFlow)        | M0           | 2                    |
| **M2: Work Management API**         | 9      | M (FastAPI routers + services) | M0, M1       | 3                    |
| **M3: Admin CLI**                   | 8      | S-M (Click commands)           | M0           | 2 (parallel with M1) |
| **M4: GovernedSupervisor Wiring**   | 4      | L (type adaptation, async)     | M0, M1, M2   | 4                    |
| **M5: Frontend Updates**            | 4      | L (full pages)                 | M2, M4       | 5                    |
| **M6: Integration Layer**           | 5      | M (webhooks, services)         | M4           | 5 (parallel with M5) |
| **TOTAL**                           | **55** |                                |              | **~5 sessions**      |

## Parallel Execution Plan

```
Session 1:  M0 (TODO-0001 through TODO-0013) -- full platform rename and cleanup
Session 2:  M1 (12 DataFlow models) + M3 (8 CLI commands) -- parallel streams
Session 3:  M2 (9 API routers + 2 services)
Session 4:  M4 (4 GovernedSupervisor wiring tasks) -- technical crux
Session 5:  M5 (4 frontend pages) + M6 (5 integration tasks) -- parallel streams
```

## Critical Path

```
M0 (rename) --> M1 (models) --> M2 (API) --> M4 (supervisor wiring) --> M5 (frontend)
                                                                    --> M6 (integrations)
                M3 (CLI) runs parallel with M1/M2
```

## Risk Register

| Risk                                                        | Severity | Mitigation                                                                                                |
| ----------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------- |
| Import rewrite misses a path                                | CRITICAL | Grep-verified rewrite + `pytest --collect-only` zero-error gate before proceeding                         |
| `pact.*` namespace collision after governance deletion      | CRITICAL | Verify `from pact.governance import GovernanceEngine` resolves to kailash-pact immediately after deletion |
| Trust file triage incorrect (delete something still needed) | HIGH     | Grep ALL consumers before deleting ANY trust file. If in doubt, keep and move.                            |
| Envelope type fragmentation (3 types)                       | HIGH     | Adapter (TODO-4002) with property tests for monotonic tightening at every type boundary                   |
| DataFlow migration breaks on PostgreSQL                     | MEDIUM   | Test both SQLite and PostgreSQL in CI. Use `dialect.*()` methods per `rules/infrastructure-sql.md`        |
| GovernedSupervisor async coordination races                 | MEDIUM   | asyncio.Event for HELD pause/resume. Lock on resolution. Timeout fallback (24h default).                  |
| `build/config/schema.py` types diverge from kailash-pact    | LOW      | Re-export shim ensures single source of truth. No local type definitions.                                 |
| Frontend WebSocket disconnection during long approvals      | LOW      | Reconnection logic with exponential backoff. State reconciliation on reconnect.                           |

## Quality Gates

| Gate    | When            | Criteria                                                                                                                                                                      |
| ------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M0 Gate | After TODO-0012 | `pytest --collect-only` = 0 errors. All previously-passing tests pass. `import pact_platform` works. `from pact.governance import GovernanceEngine` resolves to kailash-pact. |
| M1 Gate | After TODO-1012 | All 11 models create tables. `alembic upgrade head` + `alembic downgrade base` clean round-trip. CRUD nodes work for all models.                                              |
| M2 Gate | After TODO-2007 | All API endpoints return correct responses. Integration tests pass with httpx. Existing governance endpoints still work.                                                      |
| M3 Gate | After TODO-3008 | All 8 CLI commands work with Click CliRunner tests. University org YAML loads successfully.                                                                                   |
| M4 Gate | After TODO-4004 | Objective submitted through GovernedSupervisor, governance intervenes, HELD action created, human approves, execution resumes. Full lifecycle works.                          |
| M5 Gate | After TODO-5004 | All 4 pages render and interact with API. WebSocket real-time updates work. Org builder exports valid YAML.                                                                   |
| M6 Gate | After TODO-6005 | Webhook notifications fire for governance events. LLM provider management works.                                                                                              |
