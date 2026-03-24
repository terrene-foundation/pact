# Final Delegate Integration Analysis (#30)

**Date**: 2026-03-24
**Replaces**: Analysis #29 (delegate synthesis)
**Inputs**: Brief #03, Aegis corrections #04, kailash-pact 0.3.0 source, kaizen-agents 0.1.0 source, full src/pact/ tree audit
**Complexity Score**: 22 (Complex) -- Governance: 8, Legal: 4, Strategic: 10

---

## Executive Summary

PACT Platform v0.3.0 is ready for the namespace rename and parallel build. All upstream dependencies (kailash-pact 0.2.0, kailash-kaizen 2.1.0, kaizen-agents 0.1.0, kailash-dataflow 1.1.0) are production-ready. The pyproject.toml is updated. The critical path is now Phase 0 (rename `src/pact/` to `src/pact_platform/`, rewrite imports, triage trust layer, delete superseded governance modules) followed by Phase 1 (DataFlow models, API routers, CLI, services). Phase 2 (GovernedSupervisor wiring) has a known envelope type mismatch between kailash-pact's `ConstraintEnvelopeConfig` (Pydantic, 5 frozen sub-dataclasses) and kaizen-agents' `ConstraintEnvelope` (frozen dataclass with mutable dict fields) that requires an adapter.

---

## 1. What Is Truly Ready Now

### Upstream Packages (All Production)

| Package          | Version | What PACT Platform Uses                                                                                                     | Blocker? |
| ---------------- | ------- | --------------------------------------------------------------------------------------------------------------------------- | -------- |
| kailash-pact     | 0.2.0+  | GovernanceEngine, D/T/R, envelopes, clearance, bridges, context, audit, stores, YAML loader, governed agent, MCP governance | No       |
| kailash-kaizen   | 2.1.0+  | L3 primitives: EnvelopeTracker, AgentFactory, PlanExecutor, MessageRouter, ContextScope                                     | No       |
| kaizen-agents    | 0.1.0+  | GovernedSupervisor, 7 governance subsystems, Plan DAG, AuditTrail                                                           | No       |
| kailash-dataflow | 1.1.0+  | Zero-config database for work management models                                                                             | No       |
| kailash-nexus    | 1.4.3+  | Multi-channel deployment (optional)                                                                                         | No       |
| kailash[trust]   | 2.0.0+  | Core SDK + EATP trust types (AuditAnchor, CapabilityAttestation, ConfidentialityLevel, TrustPosture)                        | No       |

### What kailash-pact 0.3.0 Exports (Layer 1 -- Governance Primitives)

The kailash-pact package now exports 88 symbols covering:

- **Addressing**: Address, AddressSegment, NodeType, GrammarError, AddressError
- **Compilation**: compile_org, CompiledOrg, OrgNode, RoleDefinition, VacancyStatus, CompilationError
- **Clearance**: RoleClearance, VettingStatus, effective_clearance, POSTURE_CEILING
- **Access**: can_access, AccessDecision, KnowledgeSharePolicy, PactBridge, KnowledgeItem
- **Envelopes**: RoleEnvelope, TaskEnvelope, compute_effective_envelope, intersect_envelopes, check_degenerate_envelope, default_envelope_for_posture, MonotonicTighteningError
- **Engine**: GovernanceEngine (thread-safe, fail-closed, NaN-safe, audit-emitting)
- **Context**: GovernanceContext (frozen, anti-self-modification)
- **Verdict**: GovernanceVerdict
- **Stores**: 4 protocol ABCs + 4 memory implementations + MAX_STORE_SIZE
- **Agent integration**: PactGovernedAgent, GovernanceBlockedError, GovernanceHeldError, MockGovernedAgent
- **Middleware**: PactGovernanceMiddleware, governed_tool decorator
- **Envelope adapter**: GovernanceEnvelopeAdapter, EnvelopeAdapterError
- **YAML**: load_org_yaml, LoadedOrg, ClearanceSpec, EnvelopeSpec, BridgeSpec, KspSpec
- **Config**: 17 config types (ConstraintEnvelopeConfig, 5 sub-configs, OrgDefinition, etc.)
- **Audit**: AuditChain, PactAuditAction, create_pact_audit_details
- **Gradient**: GradientEngine, EvaluationResult
- **MCP**: 10 MCP governance types
- **Trust re-exports**: AuditAnchor, CapabilityAttestation, ConfidentialityLevel, TrustPosture

This is the COMPLETE governance surface. PACT Platform does not need to maintain ANY governance logic locally.

### What kaizen-agents 0.1.0 Exports (Layer 2 -- Delegate Engine)

- **GovernedSupervisor**: Progressive-disclosure entry point (Layer 1/2/3 API)
- **7 governance subsystems**: AccountabilityTracker, BudgetTracker, CascadeManager, ClearanceEnforcer, DerelictionDetector, BypassManager, VacancyManager
- **Plan DAG**: Plan, PlanNode, PlanEdge, PlanState, PlanNodeState, PlanModification
- **Types**: ConstraintEnvelope, AgentSpec, AgentInstance, PlanGradient, GradientZone, L3Message variants
- **Audit**: AuditTrail (EATP-compliant)
- **Planning**: TaskDecomposer, AgentDesigner, PlanComposer (wired but not yet LLM-backed)
- **Recovery**: FailureDiagnoser, Recomposer

---

## 2. Phase 0: Namespace Rename and Cleanup

### 2.1. What Is Done

- pyproject.toml: `name = "pact-platform"`, `version = "0.3.0"`
- CLI entry point: `pact = "pact_platform.cli:main"`
- Dependencies: all kailash-py packages pinned
- Optional deps: agents, nexus, firebase, postgres

### 2.2. What Remains

#### 2.2.1. Rename `src/pact/` to `src/pact_platform/`

The core filesystem operation. Every `.py` file under `src/pact/` moves to `src/pact_platform/`. This is the single largest change.

**Current `src/pact/` tree** (audited count):

| Subtree                       | Files                                    | Disposition                                                                                   |
| ----------------------------- | ---------------------------------------- | --------------------------------------------------------------------------------------------- |
| `pact/__init__.py`            | 1                                        | Rewrite as `pact_platform/__init__.py` -- all governance imports from `pact.*` (kailash-pact) |
| `pact/governance/`            | 31 files                                 | DELETE ENTIRELY -- superseded by kailash-pact 0.3.0                                           |
| `pact/build/config/schema.py` | 1                                        | DELETE -- superseded by `pact.governance.config` in kailash-pact                              |
| `pact/build/config/` (other)  | 3 files (env.py, defaults.py, loader.py) | KEEP as `pact_platform.config.*` -- platform-specific config loading                          |
| `pact/build/org/`             | 6 files                                  | KEEP as `pact_platform.org.*` -- org builder UX (generator, role catalog, envelope deriver)   |
| `pact/build/workspace/`       | 7 files                                  | KEEP as `pact_platform.workspace.*` -- workspace management                                   |
| `pact/build/verticals/`       | 4 files                                  | EVALUATE -- dm_team, dm_prompts, dm_runner, foundation may contain domain vocabulary          |
| `pact/build/templates/`       | 2 files                                  | KEEP as `pact_platform.templates.*`                                                           |
| `pact/build/cli/`             | 2 files                                  | KEEP as `pact_platform.cli.*` -- admin CLI entry point                                        |
| `pact/build/bootstrap.py`     | 1                                        | KEEP as `pact_platform.bootstrap`                                                             |
| `pact/trust/`                 | 58 files                                 | TRIAGE -- see 2.2.3 below                                                                     |
| `pact/use/execution/`         | 13 files                                 | KEEP as `pact_platform.execution.*` -- platform-specific execution                            |
| `pact/use/api/`               | 5 files                                  | KEEP as `pact_platform.api.*` -- FastAPI server, endpoints, events, shutdown                  |
| `pact/use/observability/`     | 4 files                                  | KEEP as `pact_platform.observability.*`                                                       |
| `pact/examples/`              | 5 files                                  | KEEP as `pact_platform.examples.*`                                                            |

**Total files to move**: ~75 (after deleting 31 governance + 1 schema + trust triage)
**Total files to delete**: 31 (governance) + 1 (schema) + ~15 (superseded trust) = ~47

#### 2.2.2. Delete `src/pact/governance/` Entirely

The local governance layer is NOW 100% redundant with kailash-pact. Verified by comparing exports:

| Local module                   | kailash-pact equivalent                   | Status                                                              |
| ------------------------------ | ----------------------------------------- | ------------------------------------------------------------------- |
| governance/**init**.py         | pact.governance (88 exports)              | Identical exports                                                   |
| governance/addressing.py       | pact.governance.addressing                | Identical                                                           |
| governance/compilation.py      | pact.governance.compilation               | Identical                                                           |
| governance/clearance.py        | pact.governance.clearance                 | Identical                                                           |
| governance/access.py           | pact.governance.access                    | Identical                                                           |
| governance/envelopes.py        | pact.governance.envelopes                 | Identical                                                           |
| governance/engine.py           | pact.governance.engine (GovernanceEngine) | Identical                                                           |
| governance/context.py          | pact.governance.context                   | Identical                                                           |
| governance/verdict.py          | pact.governance.verdict                   | Identical                                                           |
| governance/store.py            | pact.governance.store                     | Identical                                                           |
| governance/audit.py            | pact.governance.audit                     | Identical                                                           |
| governance/knowledge.py        | pact.governance.knowledge                 | Identical                                                           |
| governance/agent.py            | pact.governance.agent                     | Identical                                                           |
| governance/agent_mapping.py    | pact.governance.agent_mapping             | Identical                                                           |
| governance/decorators.py       | pact.governance.decorators                | Identical                                                           |
| governance/middleware.py       | pact.governance.middleware                | Identical                                                           |
| governance/testing.py          | pact.governance.testing                   | Identical                                                           |
| governance/envelope_adapter.py | pact.governance.envelope_adapter          | Identical                                                           |
| governance/explain.py          | pact.governance.explain                   | Identical                                                           |
| governance/yaml_loader.py      | pact.governance.yaml_loader               | Identical                                                           |
| governance/cli.py              | pact.governance (no direct equiv)         | KEEP as pact_platform.cli if it has platform-specific commands      |
| governance/stores/sqlite.py    | (may not be in kailash-pact)              | VERIFY before deleting                                              |
| governance/stores/backup.py    | (may not be in kailash-pact)              | VERIFY before deleting                                              |
| governance/api/\*.py           | (5 files)                                 | KEEP as pact_platform.api.governance -- platform-specific API layer |

**Action**: Delete all governance modules that are duplicated in kailash-pact. Keep governance/cli.py (migrate to pact_platform.cli), governance/stores/sqlite.py and backup.py if they are NOT in kailash-pact (verify), and governance/api/ (migrate to pact_platform.api.governance).

#### 2.2.3. Trust Layer Triage

58 files in `src/pact/trust/`. Classification:

| Category                         | Count | Files                                                                                                                                                                                                                                                                                                            | Action                                                                                   |
| -------------------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Superseded by kailash[trust]** | ~12   | attestation.py, delegation.py, genesis.py, posture.py, scoring.py, lifecycle.py, revocation.py, decorators.py, messaging.py, integrity.py, credentials.py, sd_jwt.py                                                                                                                                             | DELETE -- kailash[trust] provides these                                                  |
| **Superseded by kailash-pact**   | ~5    | constraint/gradient.py, constraint/envelope.py, constraint/enforcement.py, constraint/verification_level.py, constraint/signing.py                                                                                                                                                                               | DELETE -- kailash-pact provides GovernanceEngine + GradientEngine                        |
| **Superseded by kaizen-agents**  | ~3    | shadow_enforcer.py, shadow_enforcer_live.py, reasoning.py                                                                                                                                                                                                                                                        | DELETE -- kaizen-agents provides BudgetTracker, ClearanceEnforcer, AuditTrail            |
| **Platform-specific (KEEP)**     | ~18   | trust/store/store.py, sqlite_store.py, postgresql_store.py, backup.py, health.py, cost_tracking.py, versioning.py, posture_history.py, migrations.py, audit_query.py, auth/firebase_admin.py, bridge_trust.py, bridge_posture.py, eatp_bridge.py, dual_binding.py, uncertainty.py, jcs.py, store_isolation/\*.py | KEEP as pact_platform.trust.\* -- platform-specific persistence, auth, bridge management |
| **Evaluate**                     | ~8    | constraint/cache.py, constraint/resolution.py, constraint/middleware.py, constraint/circuit_breaker.py, constraint/bridge_envelope.py, constraint/enforcer.py, audit/anchor.py, audit/pipeline.py, audit/bridge_audit.py, resilience/failure_modes.py                                                            | CHECK if any are used by kept files                                                      |

**Net trust layer after triage**: ~18-22 files kept, ~30-36 deleted.

#### 2.2.4. Import Rewrite

After the namespace rename and deletion:

| Old import                                                    | New import                                                                         |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `from pact.governance.engine import GovernanceEngine`         | `from pact import GovernanceEngine` (from kailash-pact)                            |
| `from pact.governance.config import ConstraintEnvelopeConfig` | `from pact import ConstraintEnvelopeConfig` (from kailash-pact)                    |
| `from pact.build.config.schema import *`                      | `from pact import *` or `from pact.governance.config import *` (from kailash-pact) |
| `from pact.build.config.env import EnvConfig`                 | `from pact_platform.config.env import EnvConfig`                                   |
| `from pact.build.workspace.models import ...`                 | `from pact_platform.workspace.models import ...`                                   |
| `from pact.use.execution.runtime import ExecutionRuntime`     | `from pact_platform.execution.runtime import ExecutionRuntime`                     |
| `from pact.use.api.server import ...`                         | `from pact_platform.api.server import ...`                                         |
| `from pact.trust.store.store import TrustStore`               | `from pact_platform.trust.store import TrustStore` (if kept)                       |

**Estimated files requiring import changes**: ~65-75 production files + ~191 test files.

**Strategy**: Bulk rewrite (user decision, confirmed). No shim. Search-and-replace with verification.

### 2.3. Phase 0 Deliverable

After Phase 0 completes:

```
src/pact_platform/
    __init__.py          # Re-exports from pact (kailash-pact) + platform-specific
    config/              # env.py, defaults.py, loader.py
    org/                 # builder.py, generator.py, role_catalog.py, envelope_deriver.py, utils.py
    workspace/           # models.py, coordinator.py, discovery.py, bridge.py, knowledge_policy.py, bridge_lifecycle.py
    templates/           # registry.py
    cli/                 # __main__.py (admin CLI)
    bootstrap.py
    execution/           # runtime.py, agent.py, session.py, approval.py, registry.py, lifecycle.py,
                         # kaizen_bridge.py, llm_backend.py, backends/, hook_enforcer.py, posture_enforcer.py, approver_auth.py
    api/                 # server.py, endpoints.py, events.py, shutdown.py
                         # governance/ (from governance/api/ -- router.py, endpoints.py, schemas.py, auth.py, events.py)
    observability/       # logging.py, metrics.py, alerting.py
    trust/               # ~18-22 platform-specific files (stores, auth, bridge management)
    examples/            # university/, foundation/
```

**Test**: `python -c "import pact_platform; print(pact_platform.__version__)"` prints `0.3.0`. `python -c "from pact import GovernanceEngine"` imports from kailash-pact. `pytest` passes.

---

## 3. Phase 1: Parallel Build

Three streams run simultaneously. None depends on Phase 0 conceptually, but the import paths change, so Phase 0 must complete first.

### 3.1. Stream A: Work Management Layer

**DataFlow models** (11, as specified in brief):

| Model                 | Purpose                   | Key Fields                                                     |
| --------------------- | ------------------------- | -------------------------------------------------------------- |
| AgenticObjective      | High-level goal from user | id, title, description, status, created_by, org_id             |
| AgenticRequest        | Decomposed task           | id, objective_id, description, status, assigned_to, pool_id    |
| AgenticWorkSession    | Active work session       | id, request_id, agent_id, start_time, end_time, cost_usd       |
| AgenticArtifact       | Produced deliverable      | id, request_id, content_type, content, version                 |
| AgenticDecision       | Human decision point      | id, objective_id, question, options, chosen_option, decided_by |
| AgenticReviewDecision | Review outcome            | id, request_id, reviewer_id, verdict, comments                 |
| AgenticFinding        | Issue found during review | id, review_id, severity, description, resolution               |
| AgenticPool           | Group of agents/users     | id, name, org_id, capabilities                                 |
| AgenticPoolMembership | Pool member               | id, pool_id, agent_address, capabilities                       |
| Run                   | Execution record          | id, request_id, supervisor_result_json, status                 |
| ExecutionMetric       | Performance metrics       | id, run_id, metric_name, metric_value                          |

**Framework**: DataFlow generates ~11 CRUD node classes per model. Total: ~121 auto-generated nodes.

**API routers** (7, mounted on existing FastAPI server):

1. `/api/v1/objectives` -- create, list, get, decompose, complete
2. `/api/v1/requests` -- create, assign, claim, review, complete
3. `/api/v1/sessions` -- create, list, track, cost
4. `/api/v1/artifacts` -- create, version, retrieve
5. `/api/v1/decisions` -- present, record, list
6. `/api/v1/pools` -- create, manage members, route
7. `/api/v1/runs` -- track, timeline, metrics

**Services** (5):

1. **RequestRouter** -- pool-based task assignment using capabilities matching
2. **ApprovalQueueService** -- DataFlow-backed HELD action management (replaces in-memory ApprovalQueue for persistence)
3. **CompletionWorkflow** -- submission to review to decision lifecycle
4. **CostTracker** -- aggregate costs per objective / agent / org (extends existing trust/store/cost_tracking.py)
5. **NotificationDispatch** -- multi-channel notifications (initially in-app only)

### 3.2. Stream B: Admin CLI

**Commands** (8, using Click + Rich):

| Command                                  | Args                           | What It Does                                                         |
| ---------------------------------------- | ------------------------------ | -------------------------------------------------------------------- |
| `pact org create <yaml>`                 | YAML file path                 | Parse YAML via load_org_yaml, compile, print summary                 |
| `pact org list`                          | --                             | List compiled orgs from store                                        |
| `pact role assign <address> <agent_id>`  | D/T/R address, agent ID        | Create AgentRoleMapping                                              |
| `pact clearance grant <address> <level>` | D/T/R address, clearance level | Call engine.grant_clearance()                                        |
| `pact bridge create <yaml>`              | YAML file path                 | Parse bridge spec, call engine.create_bridge()                       |
| `pact envelope show <address>`           | D/T/R address                  | Compute and display effective envelope                               |
| `pact agent register <config>`           | YAML config                    | Register agent to role (requires kaizen-agents, deferred to Phase 2) |
| `pact audit export <format>`             | json/csv                       | Export audit chain to file                                           |

**6 commands buildable now** (org create/list, role assign, clearance grant, bridge create, envelope show, audit export). 2 wait for Phase 2 (agent register, agent status).

### 3.3. Stream E: Interactive Org Builder (Frontend)

Web page using existing GovernanceEngine + D/T/R addressing + compilation. No kaizen-agents dependency. This is a frontend-only addition to the existing Next.js dashboard.

---

## 4. Phase 2: GovernedSupervisor Wiring

### 4.1. The Envelope Type Mismatch

This is the primary technical challenge. Two envelope types exist:

**kailash-pact `ConstraintEnvelopeConfig`** (used by GovernanceEngine):

```
@dataclass(frozen=True)
class ConstraintEnvelopeConfig:
    financial: FinancialConstraintConfig       # frozen dataclass with typed fields
    operational: OperationalConstraintConfig    # frozen dataclass with typed fields
    temporal: TemporalConstraintConfig          # frozen dataclass with typed fields
    data_access: DataAccessConstraintConfig     # frozen dataclass with typed fields
    communication: CommunicationConstraintConfig # frozen dataclass with typed fields
```

- Fully typed, validated, NaN-safe sub-dataclasses
- Used by GovernanceEngine.verify_action(), compute_effective_envelope()
- Pydantic-compatible (.model_dump() available)

**kaizen-agents `ConstraintEnvelope`** (used by GovernedSupervisor):

```
@dataclass(frozen=True)
class ConstraintEnvelope:
    financial: dict[str, Any]       # {"limit": float}
    operational: dict[str, Any]     # {"allowed": list[str], "blocked": list[str]}
    temporal: dict[str, Any]        # {"limit_seconds": float, ...}
    data_access: dict[str, Any]     # {"ceiling": str, "scopes": list[str]}
    communication: dict[str, Any]   # {"recipients": list[str], "channels": list[str]}
```

- Dict-based dimensions (mutable dicts inside frozen dataclass)
- Used by GovernedSupervisor, Plan, AgentSpec
- Post-init NaN validation on known numeric keys only

### 4.2. Adapter Design

`GovernanceEnvelopeAdapter` already exists in kailash-pact (exported as `pact.GovernanceEnvelopeAdapter`). It needs to be extended or a new `PlatformEnvelopeAdapter` created in `pact_platform` that handles the bidirectional conversion:

**GovernanceEngine to GovernedSupervisor** (policy to execution):

```
ConstraintEnvelopeConfig -> ConstraintEnvelope (dict-based)
    financial: FinancialConstraintConfig.max_spend_usd -> {"limit": max_spend_usd}
    operational: OperationalConstraintConfig.allowed_actions -> {"allowed": [...], "blocked": [...]}
    temporal: TemporalConstraintConfig.max_duration_seconds -> {"limit_seconds": ...}
    data_access: DataAccessConstraintConfig.max_classification -> {"ceiling": ..., "scopes": [...]}
    communication: CommunicationConstraintConfig.allowed_channels -> {"recipients": [...], "channels": [...]}
```

**GovernedSupervisor to GovernanceEngine** (execution results back to governance audit):

```
SupervisorResult.budget_consumed -> cost context for verify_action()
SupervisorResult.events -> PlanEvent stream for WebSocket bridge
GovernedSupervisor.budget.get_snapshot() -> dashboard metrics
```

### 4.3. Wiring Sequence

1. **PlatformEnvelopeAdapter** -- Convert ConstraintEnvelopeConfig to/from ConstraintEnvelope. ~1 file, ~100 lines.

2. **DelegateBridge** -- Replaces KaizenBridge. Wires GovernedSupervisor to GovernanceEngine:
   - On task submission: engine.get_context(address) -> adapter -> GovernedSupervisor(envelope=...)
   - On execution: supervisor.run(objective, execute_node=llm_callback) -> SupervisorResult
   - On HELD: supervisor budget/gradient -> engine.verify_action() -> approval queue
   - On completion: supervisor.audit -> engine audit chain -> EATP anchors

3. **EventBridge** -- PlanEvent emissions to existing WebSocket event_bus for real-time dashboard updates. Maps PlanEventType to existing dashboard event schema.

4. **HELD VerdictBridge** -- GovernedSupervisor's BudgetTracker HELD events -> AgenticDecision (DataFlow model from Phase 1) -> approval queue UI.

5. **Execute callback** -- The `execute_node` callback provided to GovernedSupervisor.run() invokes the existing LLM backends (BackendRouter from `pact_platform.execution.llm_backend`).

### 4.4. What KaizenBridge Becomes

The current `KaizenBridge` (388 lines) handles: trust store validation, cross-team routing, bridge verification, LLM execution, dual audit anchors, lifecycle tracking. In the new architecture:

- Trust store validation: GovernedSupervisor's AccountabilityTracker
- Cross-team routing: GovernedSupervisor's CascadeManager
- Bridge verification: GovernanceEngine.check_access() (via pact.can_access)
- LLM execution: execute_node callback wrapping BackendRouter
- Audit: GovernedSupervisor.audit + GovernanceEngine audit chain
- Lifecycle: GovernedSupervisor's Plan state machine

KaizenBridge is replaced by DelegateBridge (~200 lines, simpler because GovernedSupervisor handles most complexity internally).

---

## 5. The Minimum Credible Demo

### 5.1. The 5-Minute Flow

```
1. pact org create examples/university.yaml
   -> Compiles org: 3 departments, 8 teams, 15 roles
   -> Assigns clearances, creates envelopes, establishes bridges

2. pact envelope show "D1-R1-T1-R1"
   -> Shows effective envelope: $100/day, read+write+review, CONFIDENTIAL ceiling

3. pact agent register --role "D1-R1-T1-R1" --model "claude-sonnet-4-6" --budget 10.0
   -> Registers GovernedSupervisor bound to role envelope

4. curl POST /api/v1/objectives -d '{"title": "Review Q1 report", "description": "..."}'
   -> Creates AgenticObjective, decomposes into AgenticRequests
   -> Routes to appropriate pool, agent claims task

5. Dashboard shows: live execution, budget consumption, gradient zone,
   audit trail, held actions awaiting approval
```

### 5.2. What Exists Today vs What Must Be Built

| Component                    | Exists Today                           | Must Build                   |
| ---------------------------- | -------------------------------------- | ---------------------------- |
| GovernanceEngine             | YES (kailash-pact)                     | --                           |
| D/T/R compilation            | YES (kailash-pact)                     | --                           |
| YAML org loader              | YES (kailash-pact)                     | --                           |
| Envelope computation         | YES (kailash-pact)                     | --                           |
| Clearance enforcement        | YES (kailash-pact)                     | --                           |
| GovernedSupervisor           | YES (kaizen-agents)                    | --                           |
| Budget tracking              | YES (kaizen-agents)                    | --                           |
| Plan DAG execution           | YES (kaizen-agents)                    | --                           |
| Audit trail                  | YES (kaizen-agents + kailash-pact)     | --                           |
| FastAPI server               | YES (src/pact/use/api/)                | Migrate to pact_platform.api |
| WebSocket events             | YES (src/pact/use/api/events.py)       | Migrate                      |
| LLM backends                 | YES (src/pact/use/execution/backends/) | Migrate                      |
| Next.js dashboard            | YES (18 pages)                         | Add 4 new pages              |
| Flutter mobile               | YES (14 screens)                       | Add 3 screens                |
| **Namespace rename**         | --                                     | PHASE 0                      |
| **Import rewrite**           | --                                     | PHASE 0                      |
| **Trust layer triage**       | --                                     | PHASE 0                      |
| **DataFlow work models**     | --                                     | PHASE 1 (11 models)          |
| **Work management API**      | --                                     | PHASE 1 (7 routers)          |
| **Work management services** | --                                     | PHASE 1 (5 services)         |
| **Admin CLI**                | --                                     | PHASE 1 (8 commands)         |
| **PlatformEnvelopeAdapter**  | --                                     | PHASE 2 (~100 lines)         |
| **DelegateBridge**           | --                                     | PHASE 2 (~200 lines)         |
| **EventBridge**              | --                                     | PHASE 2 (~80 lines)          |
| **HELD verdict bridge**      | --                                     | PHASE 2 (~60 lines)          |
| **Execute callback**         | --                                     | PHASE 2 (~50 lines)          |

### 5.3. Minimum Path to Demo

The shortest path to a working demo:

1. Phase 0 (namespace rename + cleanup) -- ~1 autonomous session
2. Phase 1 Stream B (CLI only: org create, envelope show, clearance grant, audit export) -- ~1 session
3. Phase 2 (PlatformEnvelopeAdapter + DelegateBridge + execute callback) -- ~1 session
4. Integration test: YAML org -> CLI -> GovernedSupervisor -> LLM backend -> audit trail -- ~0.5 session

**Total to minimum demo**: ~3.5 autonomous sessions.

**Total to full Phase 1+2**: ~6-8 autonomous sessions (including DataFlow models, all API routers, all services, full CLI, frontend updates).

---

## 6. Risk Register

### 6.1. Resolved Risks (Since Analysis #29)

| Risk                                                        | Previous Status | Current Status | Resolution                                                        |
| ----------------------------------------------------------- | --------------- | -------------- | ----------------------------------------------------------------- |
| R-01: kailash-pact missing config types                     | CRITICAL        | RESOLVED       | pact.governance.config has ALL 17 types. Zero dangling imports.   |
| R-02: kaizen-agents not ready                               | MAJOR           | RESOLVED       | v0.1.0 released. GovernedSupervisor, 7 subsystems, 35 test files. |
| R-03: kailash-dataflow not production-ready                 | MAJOR           | RESOLVED       | v1.2.0, 238 src files, 449 tests.                                 |
| R-04: pyproject.toml not updated                            | SIGNIFICANT     | RESOLVED       | name="pact-platform", v0.3.0, all deps pinned.                    |
| R-05: Package name collision (both publish as kailash-pact) | CRITICAL        | RESOLVED       | This repo is now pact-platform, kailash-pact is separate.         |

### 6.2. Remaining Risks

| ID   | Risk                                                                                                                                                                                            | Likelihood | Impact      | Severity    | Mitigation                                                                                                                                                                                                                            |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-06 | **Envelope type mismatch causes runtime failures** -- ConstraintEnvelopeConfig (frozen Pydantic) vs ConstraintEnvelope (frozen dict-based) conversion loses validation or introduces NaN bypass | Medium     | Critical    | MAJOR       | PlatformEnvelopeAdapter with comprehensive property tests. Test: convert -> reconvert -> assert equality. Test: inject NaN at every field -> assert rejection.                                                                        |
| R-07 | **Namespace rename breaks test suite** -- 191 test files import from pact.\* which will now resolve to kailash-pact instead of local modules                                                    | High       | Significant | MAJOR       | Systematic search-and-replace. Run full test suite after each file batch. Preserve git history with `git mv`.                                                                                                                         |
| R-08 | **Trust layer triage deletes needed files** -- Some files classified as "superseded" may have platform-specific behavior not covered by kailash[trust]                                          | Medium     | Major       | MAJOR       | For each candidate deletion: grep for imports in kept files. If any kept file imports from a deletion candidate, the candidate stays. Dead code only goes.                                                                            |
| R-09 | **governance/stores/sqlite.py not in kailash-pact** -- GovernanceEngine with sqlite backend may rely on local SQLite stores not yet migrated                                                    | Medium     | Significant | SIGNIFICANT | Verify kailash-pact exports SqliteClearanceStore etc. If not, keep in pact_platform.                                                                                                                                                  |
| R-10 | **DataFlow model naming collision** -- AgenticObjective etc. may collide with existing DataFlow models in kailash-dataflow                                                                      | Low        | Minor       | MINOR       | Prefix all models with `Pact` namespace or use unique table names.                                                                                                                                                                    |
| R-11 | **GovernedSupervisor.run() is async but existing execution pipeline is sync** -- KaizenBridge.execute_task() is synchronous, GovernedSupervisor.run() is async                                  | Medium     | Significant | SIGNIFICANT | DelegateBridge must be async. Migrate server to async-first. Existing sync callers use `asyncio.run()` or `loop.run_until_complete()`.                                                                                                |
| R-12 | **build/verticals/ contains domain vocabulary** -- dm_team.py, dm_prompts.py reference "Digital Marketing" which violates boundary-test.md                                                      | High       | Minor       | MINOR       | These files move to pact_platform.examples/ or are deleted. They are example/vertical code, not framework code.                                                                                                                       |
| R-13 | **Tests reference governance internals** -- Some of the 968 governance tests may test local governance modules rather than kailash-pact's copies                                                | High       | Significant | SIGNIFICANT | After deletion, tests that imported from src/pact/governance/ must be updated to import from pact (kailash-pact). Tests that tested local-only behavior (e.g., sqlite stores not in kailash-pact) stay and import from pact_platform. |

### 6.3. Risk Priority Matrix

```
              Minor        Significant      Major          Critical
            +-----------+--------------+-------------+-------------+
  High      | R-12      | R-07, R-13   |             |             |
            +-----------+--------------+-------------+-------------+
  Medium    | R-10      | R-09, R-11   | R-08        | R-06        |
            +-----------+--------------+-------------+-------------+
  Low       |           |              |             |             |
            +-----------+--------------+-------------+-------------+
```

---

## 7. Implementation Roadmap

### Phase 0: Namespace Rename (Target: 1 autonomous session)

| Step | Task                                                                                                                                                                                                                                                                   | Verification                                                         |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| 0.1  | `git mv src/pact src/pact_platform`                                                                                                                                                                                                                                    | Directory exists                                                     |
| 0.2  | Delete `src/pact_platform/governance/` (31 files) except api/, cli.py, stores/sqlite.py (verify first)                                                                                                                                                                 | `from pact import GovernanceEngine` works                            |
| 0.3  | Delete `src/pact_platform/build/config/schema.py`                                                                                                                                                                                                                      | `from pact import ConstraintEnvelopeConfig` works                    |
| 0.4  | Trust layer triage: delete ~30 superseded files                                                                                                                                                                                                                        | Kept files still import correctly                                    |
| 0.5  | Bulk import rewrite: `pact.build.config.schema` -> `pact.governance.config`, `pact.governance.*` -> `pact.*`, `pact.use.*` -> `pact_platform.*`, `pact.build.*` -> `pact_platform.*`, `pact.trust.*` -> `pact_platform.trust.*` (kept) or `kailash.trust` (superseded) | `ruff check` passes                                                  |
| 0.6  | Rewrite `src/pact_platform/__init__.py`                                                                                                                                                                                                                                | `import pact_platform` works, `pact_platform.__version__` == "0.3.0" |
| 0.7  | Update test imports (191 files)                                                                                                                                                                                                                                        | `pytest` full suite passes                                           |
| 0.8  | Flatten directory structure: `build/` and `use/` prefixes removed (org/, workspace/, config/, execution/, api/)                                                                                                                                                        | All imports resolve                                                  |

### Phase 1: Parallel Build (Target: 3-4 autonomous sessions)

| Session | Stream       | Deliverables                                                                                              |
| ------- | ------------ | --------------------------------------------------------------------------------------------------------- |
| 1.1     | B (CLI)      | 6 CLI commands: org create/list, role assign, clearance grant, bridge create, envelope show, audit export |
| 1.2     | A (DataFlow) | 11 DataFlow models, migrations, 121 auto-generated nodes                                                  |
| 1.3     | A (API)      | 7 API routers mounted on existing FastAPI server                                                          |
| 1.4     | A (Services) | 5 services: routing, approval queue, completion, cost tracking, notifications                             |

### Phase 2: Delegate Wiring (Target: 2 autonomous sessions)

| Session | Deliverables                                                               |
| ------- | -------------------------------------------------------------------------- |
| 2.1     | PlatformEnvelopeAdapter, DelegateBridge, execute callback, event bridge    |
| 2.2     | HELD verdict bridge, integration tests, CLI agent register/status commands |

### Phase 3: Frontend + Integration (Target: 2-3 autonomous sessions)

| Session | Deliverables                                                          |
| ------- | --------------------------------------------------------------------- |
| 3.1     | Web: objective management, request queue, pool management pages       |
| 3.2     | Mobile: objective tracking, request claiming, pool management screens |
| 3.3     | Webhook adapters (Slack, Discord, Teams), notification service        |

---

## 8. Decision Points Requiring Stakeholder Input

1. **Trust layer triage confirmation** -- The 58-file trust layer needs ~30 deletions. Should we do a conservative triage (keep anything uncertain, delete later) or aggressive triage (delete everything that has a kailash[trust] equivalent, fix breakage)?

2. **Directory flattening** -- Should `src/pact_platform/` have flat top-level modules (config/, org/, workspace/, execution/, api/, trust/) or preserve the build/use hierarchy (build/config/, build/org/, use/execution/, use/api/)?

3. **SQLite governance stores** -- If kailash-pact does NOT include SqliteClearanceStore/SqliteEnvelopeStore etc., should we keep them in pact_platform or push them upstream to kailash-pact?

4. **DataFlow vs direct SQL for governance stores** -- Phase 1 uses DataFlow for work management (correct). Should governance stores also migrate to DataFlow, or keep the current protocol-based stores (SQLite/PostgreSQL/Memory) that GovernanceEngine already uses?

5. **Async-first migration** -- GovernedSupervisor.run() is async. The existing FastAPI server already handles async. But KaizenBridge.execute_task() and ExecutionRuntime are sync. Should DelegateBridge be async-only (breaking sync callers like CLI), or provide both sync/async interfaces?

---

## 9. Success Criteria

| Criterion                | Measurement                                                                                     | Target                                                       |
| ------------------------ | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Phase 0 complete         | `pytest` passes, no import errors, `from pact import GovernanceEngine` resolves to kailash-pact | 100% pass rate                                               |
| Phase 1 API coverage     | All 7 routers respond to CRUD operations                                                        | Tested via httpx integration tests                           |
| Phase 1 CLI coverage     | All 6 initial commands execute successfully                                                     | Tested via subprocess integration tests                      |
| Phase 2 envelope adapter | Round-trip conversion preserves all dimension values                                            | Property tests with Hypothesis                               |
| Phase 2 delegate bridge  | GovernedSupervisor executes through full pipeline                                               | End-to-end test: YAML org -> supervisor.run() -> audit trail |
| Minimum demo             | 5-minute flow works end-to-end                                                                  | Manual walkthrough documented                                |
| Test count               | Maintained or increased from current 968 governance + existing                                  | >= 968 governance (from kailash-pact) + new platform tests   |
| Boundary test            | Zero domain vocabulary in src/pact_platform/ (excluding examples/)                              | Grep for blacklisted terms returns 0                         |

---

## 10. Cross-Reference Audit

### Documents Affected by This Change

| Document                                             | Impact                                            | Action Required                                                             |
| ---------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------- |
| CLAUDE.md (this repo)                                | Architecture section references `src/pact/` paths | Update after Phase 0                                                        |
| rules/governance.md                                  | References `src/pact/governance/`                 | Update scope to `src/pact_platform/` (for platform-specific governance API) |
| rules/boundary-test.md                               | References `src/pact/`                            | Update to `src/pact_platform/`                                              |
| rules/pact-governance.md                             | References `src/pact/governance/` imports         | Update to `from pact import ...`                                            |
| skills/29-pact/                                      | May reference old import paths                    | Audit after Phase 0                                                         |
| workspaces/briefs/03-delegate-integration-brief.md   | Phase 0 prerequisites section                     | Mark as COMPLETED                                                           |
| workspaces/pact/01-analysis/29-delegate-synthesis.md | Superseded by this document                       | Mark as SUPERSEDED                                                          |
| README.md                                            | Installation and import examples                  | Update after Phase 0                                                        |
| conftest.py                                          | May import from old paths                         | Update in Phase 0 step 0.7                                                  |

### Inconsistencies Found

1. `src/pact/__init__.py` shows `__version__ = "0.2.0"` but pyproject.toml says `"0.3.0"` -- version mismatch (will be resolved by rewrite in Phase 0)
2. `src/pact/governance/__init__.py` (local) lacks `PactError` export that kailash-pact's version has -- confirms local copy is stale
3. `src/pact/use/api/server.py` imports from `pact.build.config.env` -- must become `pact_platform.config.env`
4. `src/pact/use/execution/kaizen_bridge.py` imports from `pact.build.config.schema` -- must become `from pact import VerificationLevel`
5. `src/pact/build/verticals/dm_team.py` contains "Digital Marketing" -- boundary-test violation, must move to examples/ or delete
