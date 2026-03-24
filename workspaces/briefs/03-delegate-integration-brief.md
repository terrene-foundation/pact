# PACT Platform: Delegate Integration Brief

**Date**: 2026-03-23
**Context**: Architecture consolidation across kailash-rs, kailash-py, Aegis, PACT Platform
**Depends on**: kaizen-agents package completion in kailash-py (in progress)

---

## What Changed

The Delegate architecture has been formalized. PACT Platform is an **entrypoint** (Layer 3) on kailash-py, not a standalone governance framework. The autonomous core (Delegate) lives in `kaizen-agents` package in kailash-py (Layer 2), which PACT Platform should consume.

### The Three-Layer Stack (kailash-py)

```
Layer 3: PACT PLATFORM (this repo)
  Human judgment surface — org definition, envelope config, approval UX,
  clearance management, audit explorer, cost reporting
  Web (Next.js) + Mobile (Flutter)
  BUILDS ON everything below

Layer 2: kaizen-agents package (in kailash-py)
  GovernedSupervisor — TAOD loop, tool execution, sessions, hooks,
  MCP client, governance gate, LLM adapters
  Planning — TaskDecomposer, AgentDesigner, PlanComposer
  Recovery — FailureDiagnoser, Recomposer
  Governance — AccountabilityTracker, BudgetTracker, ClearanceEnforcer,
               CascadeManager, VacancyManager, DerelictionDetector, BypassManager
  Audit — AuditTrail (EATP-compliant)

Layer 1: Primitives (in kailash-py)
  kailash-kaizen L3 — EnvelopeTracker, AgentFactory, PlanExecutor,
                      MessageRouter, ContextScope
  kailash-pact    — GovernanceEngine, D/T/R, envelopes, clearance, bridges
  eatp + trust-plane — Trust records, delegation, constraints
  kailash core    — Runtime, 140+ nodes, workflows, infrastructure
  kailash-dataflow — Zero-config database
  kailash-nexus   — Multi-channel deployment
```

### What PACT Platform Already Has (Strong)

| Area | Status | Notes |
|---|---|---|
| GovernanceEngine | Production-ready | Thread-safe, frozen context, 3-layer envelopes — MORE mature than Aegis |
| D/T/R compilation | Production-ready | Grammar validation, cycle detection, address resolution |
| Knowledge clearance | Production-ready | 5 levels + compartments + posture ceiling |
| Cross-functional bridges | Production-ready | Standing/Scoped/Ad-Hoc + KSPs |
| Verification gradient | Production-ready | 4 zones with per-dimension thresholds |
| EATP audit anchors | Production-ready | Tamper-evident hash chains |
| Trust posture evolution | Functional | 5 levels, posture ceiling, EATP-backed |
| Constraint enforcement | Functional | 5 dimensions, circuit breaker, gradient proximity |
| Web dashboard | Functional | 18 pages (Next.js) |
| Mobile app | Functional | 14 screens (Flutter) |
| LLM backends | Functional | Anthropic + OpenAI |
| Tests | 191 files | 968 governance tests |

### What PACT Platform Gets For Free (Once Delegate Is Wired)

| Capability | Source | Status |
|---|---|---|
| GovernedSupervisor | kaizen-agents | In kailash-py, needs wiring |
| TAOD loop + tool execution | kaizen-agents delegate | In kailash-py |
| Task decomposition | kaizen-agents planner | In kailash-py |
| Plan DAG execution | kailash-kaizen L3 | In kailash-py |
| Failure recovery | kaizen-agents recovery | In kailash-py |
| 7 governance subsystems | kaizen-agents governance | In kailash-py |
| MCP client | kaizen-agents delegate | In kailash-py |
| Session management | kaizen-agents delegate | In kailash-py |
| Hook system | kaizen-agents delegate | In kailash-py |
| Budget tracking | kaizen-agents governance | In kailash-py |
| Agent factory + spawning | kailash-kaizen L3 | In kailash-py |
| Message routing | kailash-kaizen L3 | In kailash-py |
| Multi-channel deploy | kailash-nexus | In kailash-py |
| Database operations | kailash-dataflow | In kailash-py |

---

## What PACT Platform Needs to Build (Entrypoint-Specific)

### Priority 1: Work Management Layer

PACT's governance engine is mature but has nothing to govern operationally. The "work gets done" layer is missing.

**DataFlow models to create** (~15):

```python
# Work lifecycle
AgenticObjective      # High-level goal (user intent)
AgenticRequest        # Decomposed task (assigned to agent/human)
AgenticWorkSession    # Active work session with cost tracking
AgenticArtifact       # Produced deliverable with versioning
AgenticDecision       # Owner decision point (approve/revise/reject)
AgenticReviewDecision # Review outcome on a request
AgenticFinding        # Issue found during review

# Work allocation
AgenticPool           # Group of agents/users who can claim tasks
AgenticPoolMembership # Pool member with capabilities

# Execution tracking
Run                   # Execution record
ExecutionMetric       # Performance metrics per run
```

**API routers to create** (~10):
- Objectives — create, clarify, decompose, complete
- Requests — assign, claim, review, complete
- Work sessions — create, track, cost accounting
- Artifacts — create, version, retrieve
- Decisions — present options, record choice
- Pools — create, manage membership, routing
- Runs — track execution, timeline

**Services to create** (~10):
- Request routing (pool-based assignment)
- Approval queue (HELD action management)
- Completion workflow (submission → review → decision)
- Cost tracking (aggregate per objective/agent/org)
- Notification dispatch (multi-channel)

### Priority 2: Admin CLI

PACT currently has only `kailash-pact validate`. Operators need:

```
kailash-pact org create <yaml>        # Create org from YAML
kailash-pact org list                 # List orgs
kailash-pact role assign <address> <user>  # Assign user to role
kailash-pact clearance grant <address> <level>  # Grant clearance
kailash-pact bridge create <yaml>     # Create bridge
kailash-pact envelope show <address>  # Show effective envelope
kailash-pact agent register <config>  # Register agent to role
kailash-pact audit export <format>    # Export audit trail
```

### Priority 3: Wire the Delegate

Once kaizen-agents package is complete in kailash-py:

1. Import `GovernedSupervisor` from `kaizen_agents`
2. Shadow agent = `GovernedSupervisor` bound to a role's envelope
3. Wire `execute_node` callback to PACT's execution runtime
4. Connect plan events to WebSocket for real-time dashboard updates
5. Connect HELD verdicts to approval queue UI

### Priority 4: Integration Layer

- Webhook adapters (Slack, Discord, Teams — reuse patterns, implement independently)
- Notification service (email, in-app, push)
- LLM provider management (BYO API keys, provider selection)
- Connector framework (third-party tool integration)

### Priority 5: Frontend Gaps

Web pages to add:
- Objective management (create, track, complete)
- Request queue (claim, review, submit)
- Pool management (create pools, assign members)
- Org builder (interactive D/T/R creation beyond YAML)

Mobile screens to add:
- Objective tracking
- Request claiming/review
- Pool management

---

## Relationship to Aegis

PACT Platform and Aegis are **peer entrypoints** on different SDK stacks:

| | PACT Platform | Aegis |
|---|---|---|
| SDK | kailash-py | kailash-rs |
| License | Apache 2.0 | Proprietary |
| Owner | Terrene Foundation | Integrum Global |
| Governance engine | More mature | Has custom extensions |
| Operational surface | Leaner (in progress) | Full-featured (16K+ tests) |
| Commercial features | None (by design) | Full SaaS (billing, SSO, etc.) |
| Mobile | Flutter (14 screens) | Responsive web only |
| Delegate source | kaizen-agents (kailash-py) | kaizen-agents (kailash-rs) |

Both implement the same governance specification (PACT). Both consume the same Delegate architecture (GovernedSupervisor). They share NO code — independent implementations.

PACT's governance engine is architecturally ahead of Aegis in these areas:
- Thread-safe GovernanceEngine facade (Aegis has per-service locks after RT2, but no unified facade)
- Frozen GovernanceContext (Aegis passes mutable DataFlow record dicts)
- Pure-function governance computation on frozen dataclasses (Aegis uses DataFlow workflows on mutable DB records)
- NaN/Inf protection + bounded store collections (Aegis lacks these guards)
- Compile-once org model as immutable graph (Aegis queries DB per access check)

Aegis has full implementations of features previously reported as missing (corrected post-RT2 2026-03-21):
- 3-layer envelope model: RoleEnvelope + TaskEnvelope + EnvelopeCompositionService (chain intersection). RT2 added bootstrap mode, REVOKED terminal state, fail-closed on corrupted JSON.
- KSPs: DataFlow model + CRUD API + service with evaluate_downward_access(). RT2 hardened with classification whitelist and path traversal protection.

Aegis is ahead in operational breadth:
- 112 DataFlow models vs PACT's direct SQL
- 83 API routers vs PACT's ~30 endpoints
- 60 agentic services vs PACT's ~20
- 5 webhook adapters vs 0
- 6 runtime adapters vs 2

---

## Repo Identity Question (from previous session)

The previous session asked: "What stays here vs what's in kailash-py?"

**Answer**:
- **kailash-pact** (already in kailash-py) = governance primitives (GovernanceEngine, D/T/R, envelopes, clearance, bridges). This is Layer 1.
- **This repo** (terrene-foundation/pact) = the PACT Platform entrypoint. Web dashboard, mobile app, API server, admin CLI, work management, approval UX. This is Layer 3.

This repo should depend on `kailash-pact` (governance primitives) and `kaizen-agents` (Delegate engine). It provides the human judgment surface on top.

The repo name question: `pact-platform` or just `pact` — either works. The key is that it's the **entrypoint**, not the governance engine itself.
