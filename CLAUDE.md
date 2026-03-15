# CARE Platform

This repository is the **CARE Platform** — the Terrene Foundation's open-source governed operational model for running organizations with AI agents under EATP trust governance, CO methodology, and CARE philosophy.

The CARE Platform is Foundation-owned, Apache 2.0 licensed, and irrevocably open. Since the standards, SDKs, and reference model are all open, anyone can build commercial implementations on top — the Foundation has no structural relationship with any commercial entity.

## What This Is

A governed operational model that operationalizes the Terrene Foundation as an agent-orchestrated organization. Each Foundation workspace becomes the knowledge base for an agent team. The platform is built on the Kailash Python SDK (Kaizen agent framework, DataFlow persistence, Nexus API layer, EATP SDK trust layer).

**What it is NOT**: A generic agent orchestrator competing with LangChain/CrewAI. It is governed orchestration — an opinionated framework for running organizations with AI agents under EATP trust governance.

## Absolute Directives

These override ALL other instructions. They govern behavior before any rule file is consulted.

### 0. Foundation Independence — No Commercial Coupling

CARE Platform is a **Terrene Foundation project**. It is fully independent. There is NO relationship between CARE Platform and any commercial product, proprietary codebase, or commercial entity. Do not reference, compare with, or design against any proprietary product. Do not use language like "open-source version of X." CARE Platform IS the product — not a derivative of anything. See `rules/independence.md` for full policy.

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

Every implementation decision must align with the CARE, EATP, and CO specifications. When in doubt, consult the relevant standards expert agent. The CARE Platform is the reference implementation of these standards — it must embody them correctly.

### 5. Recommended Reviews

- **Code review** (intermediate-reviewer) after file changes — see `rules/agents.md` Rule 1
- **Security review** (security-reviewer) before commits — strongly encouraged — see `rules/agents.md` Rule 2
- **Real infrastructure** in integration/E2E tests is recommended — see `rules/testing.md`

## Architecture Overview

### Product Stack

| Layer        | Foundation (Open)                     |
| ------------ | ------------------------------------- |
| Specs        | CARE, EATP, CO, CDI (CC BY 4.0)       |
| SDKs         | Kailash Python, EATP SDK (Apache 2.0) |
| **Platform** | **CARE Platform** (Apache 2.0)        |

### Five Architecture Gaps (COC Setup → CARE Platform)

| Gap                       | Current (COC)                          | Needed (CARE Platform)                        |
| ------------------------- | -------------------------------------- | --------------------------------------------- |
| Multi-user runtime        | Single Claude Code session             | Multiple humans, multiple agent teams         |
| Persistence               | Filesystem (markdown, git)             | Cryptographic trust chains, auditable history |
| Cryptographic enforcement | Rules Claude reads + lightweight hooks | Signed constraint envelopes, audit anchors    |
| Runtime independence      | Claude Code only (Anthropic)           | Multiple LLM backends, local models           |
| Workspace coordination    | Isolated directories                   | Cross-Functional Bridges between teams        |

### Implementation Phases

| Phase | What                                    | Builds On                  |
| ----- | --------------------------------------- | -------------------------- |
| 1     | Package COC setup as reusable framework | Existing COC setup         |
| 2     | Add persistence (EATP SDK + DataFlow)   | EATP SDK Phase 1           |
| 3     | Add multi-team runtime (Kaizen agents)  | Kaizen framework           |
| 4     | Add Cross-Functional Bridges            | EATP cross-team delegation |
| 5     | Organization Builder                    | All previous phases        |

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

## The Trinity

| Standard | Full Name                                      | Type        | License   |
| -------- | ---------------------------------------------- | ----------- | --------- |
| **CARE** | Collaborative Autonomous Reflective Enterprise | Philosophy  | CC BY 4.0 |
| **EATP** | Enterprise Agent Trust Protocol                | Protocol    | CC BY 4.0 |
| **CO**   | Cognitive Orchestration                        | Methodology | CC BY 4.0 |

- **COC** = CO for Codegen (first domain application of CO)
- CARE planes: **Trust Plane** + **Execution Plane**
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

The CARE Platform is informed by the Terrene Foundation knowledge base at `~/repos/terrene/terrene/`:

| Content                    | Location                                                                  |
| -------------------------- | ------------------------------------------------------------------------- |
| Foundation truths          | `~/repos/terrene/terrene/docs/00-anchor/`                                 |
| Standards (CARE, EATP, CO) | `~/repos/terrene/terrene/docs/02-standards/`                              |
| Constitution               | `~/repos/terrene/terrene/docs/06-operations/constitution/`                |
| Publications (theses)      | `~/repos/terrene/terrene/docs/02-standards/publications/`                 |
| EATP SDK                   | `eatp>=0.1.0` package (standalone); `trust-plane>=0.2.0` (reference impl) |
