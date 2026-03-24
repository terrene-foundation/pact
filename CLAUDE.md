# PACT

This repository is **PACT** — the Terrene Foundation's reference implementation of PACT (Principled Architecture for Constrained Trust), the fourth standard in the Quartet alongside CARE, EATP, and CO. It implements the D/T/R accountability grammar, recursive operating envelope delegation, knowledge clearance framework, and verification gradient for running organizations with AI agents under governed autonomy.

PACT is Foundation-owned, Apache 2.0 licensed, and irrevocably open. Since the standards, SDKs, and reference model are all open, anyone can build commercial implementations on top — the Foundation has no structural relationship with any commercial entity.

## What This Is

A **framework** and **reference implementation** of PACT (Principled Architecture for Constrained Trust). PACT publishes the domain-agnostic governance framework — D/T/R grammar validation, operating envelope composition, knowledge clearance, verification gradient — plus a simple example vertical (e.g., a university or open-source project) that proves the system works without requiring domain expertise. Built on the Kailash Python SDK (Kaizen agent framework, DataFlow persistence, Nexus API layer, EATP SDK trust layer).

**The boundary test**: If you ripped out all domain vocabulary from a vertical's code and replaced it with different domain terms, the `pact` library code wouldn't change at all. Only the configuration and domain layer would change.

**What it is NOT**: A generic agent orchestrator competing with LangChain/CrewAI. It is governed orchestration — an opinionated framework for running organizations with AI agents under PACT architectural governance.

### Framework vs Verticals

| Layer                  | Repository         | Purpose                                           |
| ---------------------- | ------------------ | ------------------------------------------------- |
| **Framework**          | `pact` (this repo) | Domain-agnostic PACT library + example vertical   |
| **Financial vertical** | `astra`            | Production-grade MAS-regulated financial services |
| **HRIS vertical**      | `arbor`            | Production-grade Singapore SME HR governance      |

Verticals `import pact` and define their domain's D/T/R structure, envelope constraints, and clearance mappings as PACT configuration. The framework knows nothing about finance, healthcare, or any other domain.

## Absolute Directives

These override ALL other instructions. They govern behavior before any rule file is consulted.

### 0. Foundation Independence — No Commercial Coupling

PACT is a **Terrene Foundation project**. It is fully independent. There is NO relationship between PACT and any commercial product, proprietary codebase, or commercial entity. Do not reference, compare with, or design against any proprietary product. Do not use language like "open-source version of X." PACT IS the product — not a derivative of anything. See `rules/independence.md` for full policy.

### 1. Framework-First

Never write code from scratch before checking whether the Kailash frameworks already handle it.

- Instead of direct SQL/SQLAlchemy/Django ORM → check with **dataflow-specialist**
- Instead of FastAPI/custom API gateway → check with **nexus-specialist**
- Instead of custom MCP server/client → check with **mcp-specialist**
- Instead of custom agentic platform → check with **kaizen-specialist**

### 2. .env Is the Single Source of Truth

All API keys and model names MUST come from `.env`. Never hardcode model strings like `"gpt-4"` or `"claude-3-opus"`. Root `conftest.py` auto-loads `.env` for pytest.

See `rules/env-models.md` for full details.

### 3. Implement, Don't Document

When you discover a missing feature, endpoint, or record — **implement or create it**. Do not note it as a gap and move on. The only acceptable skip is explicit user instruction.

See `rules/no-stubs.md` for details.

### 4. Standards Alignment

Every implementation decision must align with the CARE, PACT, EATP, and CO specifications. When in doubt, consult the relevant standards expert agent. This repo is the reference implementation of the Quartet — it must embody them correctly.

### 5. Recommended Reviews

- **Code review** (intermediate-reviewer) after file changes — see `rules/agents.md` Rule 1
- **Security review** (security-reviewer) before commits — strongly encouraged — see `rules/agents.md` Rule 2
- **Real infrastructure** in integration/E2E tests is recommended — see `rules/testing.md`

## Architecture Overview

### Three-Layer Stack

| Layer  | Package                     | What                                                             | Version |
| ------ | --------------------------- | ---------------------------------------------------------------- | ------- |
| **L3** | `pact-platform` (this repo) | Org builder, approval UX, work management, dashboard, deployment | 0.3.0   |
| **L2** | `kaizen-agents`             | GovernedSupervisor, progressive disclosure, autonomous execution | 0.1.0   |
| **L1** | `kailash-pact`              | GovernanceEngine, D/T/R grammar, envelopes, clearance, gradient  | 0.3.0   |
| **L1** | `kailash[trust]`            | EATP SDK, trust chains, signing, postures, enforcement           | 2.0.0+  |
| **L1** | `kailash-dataflow`          | Auto-generated CRUD nodes (11 per model)                         | 1.2.0   |
| **L0** | `kailash`                   | Core SDK, workflow runtime, 140+ nodes                           | 2.0.0+  |

### Platform Components (v0.3.0)

| Component              | Location                         | What                                                                                                                            |
| ---------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| DataFlow Models (11)   | `pact_platform/models/`          | AgenticObjective, Request, WorkSession, Artifact, Decision, ReviewDecision, Finding, Pool, PoolMembership, Run, ExecutionMetric |
| API Routers (7)        | `pact_platform/use/api/routers/` | objectives, requests, sessions, decisions, pools, reviews, metrics (42+ endpoints)                                              |
| Services (5)           | `pact_platform/use/services/`    | RequestRouter, ApprovalQueue, CompletionWorkflow, CostTracking, NotificationDispatch                                            |
| Engine (6)             | `pact_platform/engine/`          | EnvelopeAdapter, GovernedDelegate, ApprovalBridge, EventBridge, SupervisorOrchestrator, AutoSeed                                |
| Integrations (6)       | `pact_platform/integrations/`    | NotificationAdapter, Slack/Discord/Teams webhooks, LLMProviderManager                                                           |
| CLI (10 commands)      | `pact_platform/cli.py`           | quickstart, org, role, clearance, bridge, envelope, agent, audit, validate, status                                              |
| Web Dashboard (4 new)  | `apps/web/app/`                  | objectives, requests, pools, org-builder pages                                                                                  |
| Mobile Screens (3 new) | `apps/mobile/lib/features/`      | objectives, requests, pools screens                                                                                             |
| Existing Frontend      | `apps/web/`, `apps/mobile/`      | approvals, agents, bridges, trust-chains, envelopes, cost, audit, shadow, verification                                          |

### Import Patterns

```python
# Governance (from kailash-pact — L1)
from pact.governance import GovernanceEngine, GovernanceVerdict
from pact.governance import compile_org, load_org_yaml

# Config types (from this repo — L3)
from pact_platform.build.config.schema import OrgDefinition, AgentConfig, ConstraintEnvelopeConfig

# Work management models (from this repo — L3)
from pact_platform.models import db, validate_finite

# Engine wiring (from this repo — L3)
from pact_platform.engine import SupervisorOrchestrator, PlatformEnvelopeAdapter

# Trust layer (kailash[trust] — L1)
from kailash.trust import TrustOperations, generate_keypair
from kailash.trust.chain import VerificationLevel, VerificationResult
```

## Workspace Commands

| Command      | Phase | Purpose                                         |
| ------------ | ----- | ----------------------------------------------- |
| `/start`     | —     | New user orientation; explains the workflow     |
| `/analyze`   | 01    | Research and validate the project idea          |
| `/todos`     | 02    | Create project roadmap; stops for your approval |
| `/implement` | 03    | Build one task at a time; repeat                |
| `/redteam`   | 04    | Test from adversarial angles                    |
| `/codify`    | 05    | Capture knowledge for future sessions           |
| `/deploy`    | —     | Get the project live (standalone)               |
| `/ws`        | —     | Check project status anytime                    |
| `/wrapup`    | —     | Save progress before ending a session           |

**Workspace detection**: Hooks automatically detect the active workspace and inject context.

**Session continuity**: Run `/wrapup` before ending a session to write `.session-notes`. The next session reads these notes automatically.

## Rules Index

| Concern                           | Rule File                    | Scope                                               |
| --------------------------------- | ---------------------------- | --------------------------------------------------- |
| **Foundation independence**       | `rules/independence.md`      | **Global — overrides all**                          |
| Plain-language communication      | `rules/communication.md`     | Global                                              |
| Agent orchestration & reviews     | `rules/agents.md`            | Global                                              |
| E2E god-mode testing              | `rules/e2e-god-mode.md`      | `tests/e2e/**`, `**/*e2e*`, `**/*playwright*`       |
| API keys & model names            | `rules/env-models.md`        | `**/*.py`, `**/*.ts`, `**/*.js`, `.env*`            |
| Deployment operations             | `rules/deployment.md`        | Global                                              |
| Git commits, branches, PRs        | `rules/git.md`               | Global                                              |
| No stubs or placeholders          | `rules/no-stubs.md`          | Global                                              |
| Kailash SDK execution patterns    | `rules/patterns.md`          | `**/*.py`, `**/*.ts`, `**/*.js`                     |
| Security (secrets, injection)     | `rules/security.md`          | Global                                              |
| 3-tier testing strategy           | `rules/testing.md`           | `tests/**`, `**/*test*`, `**/*spec*`, `conftest.py` |
| Terrene naming & terminology      | `rules/terrene-naming.md`    | Global                                              |
| Documentation & version accuracy  | `rules/documentation.md`     | `README.md`, `docs/**`, `CHANGELOG.md`              |
| Constitution consistency          | `rules/constitution.md`      | Scoped                                              |
| Boundary test (domain vocabulary) | `rules/boundary-test.md`     | `src/pact_platform/**` (excluding `examples/`)      |
| Auto-generated workflow instincts | `rules/learned-instincts.md` | Global                                              |

## Agents

### Analysis & Planning

- **deep-analyst** — Failure analysis, complexity assessment, risk identification
- **requirements-analyst** — Requirements breakdown, ADR creation
- **sdk-navigator** — Find SDK patterns before coding
- **framework-advisor** — Choose Core SDK, DataFlow, Nexus, or Kaizen

### Framework Specialists (`agents/frameworks/`)

- **dataflow-specialist** — Database operations, auto-generated nodes
- **nexus-specialist** — Multi-channel platform (API/CLI/MCP)
- **kaizen-specialist** — AI agents, signatures, multi-agent coordination
- **mcp-specialist** — MCP server implementation

### Standards Experts (`agents/standards/`)

- **care-expert** — CARE governance framework (Dual Plane Model, Mirror Thesis)
- **eatp-expert** — EATP trust protocol (trust lineage, verification gradient)
- **co-expert** — CO methodology (7 principles, 5 layers)
- **coc-expert** — COC: CO applied to Codegen (5-layer architecture, anti-amnesia)
- **constitution-expert** — Terrene Foundation constitution (77 clauses, 11 EPs, phased governance)

### Strategy

- **open-source-strategist** — Open-core strategy, licensing, community building, competitive positioning

### Core Implementation

- **pattern-expert** — Workflow patterns, nodes, parameters
- **tdd-implementer** — Test-first development
- **intermediate-reviewer** — Code review after changes
- **gold-standards-validator** — Compliance checking
- **build-fix** — Fix build/type errors with minimal changes
- **security-reviewer** — Security audit before commits

### Frontend & Design (`agents/frontend/`)

- **react-specialist** — React/Next.js frontends
- **flutter-specialist** — Flutter mobile/desktop apps
- **frontend-developer** — Responsive UI components
- **uiux-designer** — Enterprise UI/UX design
- **ai-ux-designer** — AI interaction patterns

### Testing & QA

- **testing-specialist** — 3-tier strategy with real infrastructure
- **documentation-validator** — Test code examples
- **e2e-runner** — Playwright E2E test generation
- **value-auditor** — Enterprise demo QA from buyer perspective

### Release & Operations (`agents/management/`)

- **git-release-specialist** — Git workflows, CI, releases
- **deployment-specialist** — Deployment onboarding, Docker/K8s
- **todo-manager** — Project task tracking
- **gh-manager** — GitHub issue/project management

## Skills Navigation

### SDK Skills (01-17)

For Kailash SDK implementation patterns, see `.claude/skills/` — organized by framework (`01-core-sdk` through `05-kailash-mcp`) and topic (`06-cheatsheets` through `17-gold-standards`).

### Standards Reference Skills (26-29)

- **26-eatp-reference** — EATP technical reference (5 elements, verification gradient, trust postures, SDK quickstart, API reference, patterns, reasoning traces)
- **27-care-reference** — CARE framework reference (Dual Plane, Mirror Thesis, governance)
- **28-coc-reference** — COC framework reference (5-layer architecture, anti-amnesia)
- **co-reference** — CO methodology reference (7 principles, 5 layers, domain applications)
- **29-constitution-reference** — Constitution reference (77 clauses, 11 EPs, phased governance)

### Project Skills

- **project** — TrustPlane EATP reference implementation skills (store backends, security patterns, enterprise features)

## The Quartet

| Standard | Full Name                                      | Type         | License   |
| -------- | ---------------------------------------------- | ------------ | --------- |
| **CARE** | Collaborative Autonomous Reflective Enterprise | Philosophy   | CC BY 4.0 |
| **PACT** | Principled Architecture for Constrained Trust  | Architecture | CC BY 4.0 |
| **EATP** | Enterprise Agent Trust Protocol                | Protocol     | CC BY 4.0 |
| **CO**   | Cognitive Orchestration                        | Methodology  | CC BY 4.0 |

- **COC** = CO for Codegen (first domain application of CO)
- CARE planes: **Trust Plane** + **Execution Plane**
- PACT grammar: **D** (Department) + **T** (Team) + **R** (Role) — every D/T must be immediately followed by exactly one R
- Constraint dimensions: Financial, Operational, Temporal, Data Access, Communication
- Foundation owns ALL open-source IP (fully transferred, irrevocable). No structural relationship with any commercial entity.

## Critical Execution Rules

```python
# ALWAYS: runtime.execute(workflow.build())
# NEVER: workflow.execute(runtime)
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())

# Async (Docker/FastAPI):
runtime = AsyncLocalRuntime()
results, run_id = await runtime.execute_workflow_async(workflow.build(), inputs={})

# String-based nodes only
workflow.add_node("NodeType", "node_id", {"param": "value"})

# Return structure is always (results, run_id)
```

## Kailash Platform

| Framework    | Purpose                                | Install                        |
| ------------ | -------------------------------------- | ------------------------------ |
| **Core SDK** | Workflow orchestration, 140+ nodes     | `pip install kailash`          |
| **DataFlow** | Zero-config database operations        | `pip install kailash-dataflow` |
| **Nexus**    | Multi-channel deployment (API+CLI+MCP) | `pip install kailash-nexus`    |
| **Kaizen**   | AI agent framework                     | `pip install kailash-kaizen`   |

All frameworks are built ON Core SDK — they don't replace it.

## Key Reference Locations (Terrene Knowledge Base)

PACT is informed by the Terrene Foundation knowledge base at `~/repos/terrene/terrene/`:

| Content                          | Location                                                                  |
| -------------------------------- | ------------------------------------------------------------------------- |
| Foundation truths                | `~/repos/terrene/terrene/docs/00-anchor/`                                 |
| Standards (CARE, PACT, EATP, CO) | `~/repos/terrene/terrene/docs/02-standards/`                              |
| Constitution                     | `~/repos/terrene/terrene/docs/06-operations/constitution/`                |
| Publications (theses)            | `~/repos/terrene/terrene/docs/02-standards/publications/`                 |
| EATP SDK                         | `eatp>=0.1.0` package (standalone); `trust-plane>=0.2.0` (reference impl) |
