# Delegate Integration Synthesis

**Date**: 2026-03-23
**Inputs**: Deep analysis (#25), Requirements (#26), Value audit (#27), Framework advice (#28)
**Brief**: `workspaces/briefs/03-delegate-integration-brief.md`

---

## What We're Building

PACT Platform is the **human judgment surface** for governed AI operations. It sits on top of kaizen-agents (autonomous agent core) and kailash-pact (governance primitives). Users define org structures, configure envelopes, manage clearances, approve held actions, review work, and monitor costs. Agents do the work. PACT ensures the work happens within governed boundaries.

The three-layer stack:

- **Layer 1** (kailash-pact): GovernanceEngine, D/T/R, envelopes, clearance, bridges
- **Layer 2** (kaizen-agents): GovernedSupervisor, TAOD loop, planning, recovery, 7 governance subsystems
- **Layer 3** (this repo): Org definition, approval UX, work management, dashboard, mobile, deployment

## Who It's For

- **Operators** who define organizational structures and governance policies (YAML + CLI + dashboard)
- **Humans in the loop** who approve held actions, review agent work, make decisions
- **Evaluators** who clone the repo, run `docker compose up`, and see governance working end-to-end

## Critical Update

**The kailash-pact migration is now complete.** The kailash-py package has zero dangling imports — `pact.governance.config` contains all the types that were in `pact.build.config.schema`. The Phase 0 blocker from the previous analysis session is resolved.

**kaizen-agents is substantially complete.** GovernedSupervisor (685 lines), all 7 governance subsystems, full orchestration pipeline, and delegate loop are implemented with 32 test files. It is NOT a blocker — only the delegate loop's OpenAI coupling needs refactoring, which doesn't block GovernedSupervisor integration.

## What to Build

### Phase 0: Prerequisites (1 week) — CRITICAL PATH

Three things must happen before new features can be built:

1. **Resolve package name collision** — This repo and kailash-py both publish as `kailash-pact` under `pact.*`. Rename this repo's package to `pact-platform` (or stop publishing to PyPI entirely).

2. **Rewrite 73 imports** — `pact.build.config.schema` is imported by 64 files. These must point to `pact.governance.config` (from kailash-pact) or use a compatibility shim.

3. **Classify trust layer** — 58 files need disposition: ~15 superseded by kailash-pact, ~12 by kaizen-agents, ~15 platform-specific (keep), ~16 EATP wrappers (keep until EATP merge).

### Phase 1: Parallel Build (2-3 weeks)

Three streams run simultaneously:

**Stream A — Work Management Layer** (the brief's Priority 1):

- 11 DataFlow models: AgenticObjective, AgenticRequest, AgenticWorkSession, AgenticArtifact, AgenticDecision, AgenticReviewDecision, AgenticFinding, AgenticPool, AgenticPoolMembership, Run, ExecutionMetric
- 7 API routers mounted on existing FastAPI server
- 5 services: request routing, approval queue (DataFlow-backed), completion workflow, cost tracking, notification dispatch
- **Framework choice**: DataFlow for work management (121 auto-generated nodes), keep direct SQLite for governance stores (different security profile)

**Stream B — Admin CLI** (Priority 2):

- 6 commands buildable now: org create/list, role assign, clearance grant, bridge create, envelope show, audit export
- 2 commands wait for delegate wiring: agent register, agent status

**Stream E — Interactive Org Builder** (Priority 5, partial):

- Frontend page using existing GovernanceEngine + D/T/R addressing + compilation
- No kaizen-agents dependency

### Phase 2: Delegate Wiring (1-2 weeks)

Once Phase 0 prerequisites are resolved:

1. **DelegateProtocol interface** — Abstract the boundary between Layer 2 and Layer 3
2. **SimpleDelegateExecutor** — Immediate fallback using existing ExecutionRuntime + LLM backends (works without kaizen-agents)
3. **GovernedSupervisor adapter** — Converts GovernanceEngine's `ConstraintEnvelopeConfig` (Pydantic) to kaizen-agents' `ConstraintEnvelope` (dataclass with dict fields)
4. **Event bridge** — PlanEvent emissions → WebSocket for real-time dashboard updates
5. **HELD verdict bridge** — GovernedSupervisor's BudgetTracker → AgenticDecision in DataFlow → approval queue UI

### Phase 3: Integration + Frontend (2-3 weeks)

- Webhook adapters (Slack, Discord, Teams — implement independently)
- Notification service (multi-channel)
- LLM provider management (BYO API keys via .env)
- Frontend pages: objective management, request queue, pool management

## Key Architecture Decisions

| Decision                    | Choice                           | Rationale                                              |
| --------------------------- | -------------------------------- | ------------------------------------------------------ |
| Storage for work management | DataFlow (11 models)             | 121 auto-generated nodes vs ~3K lines hand-rolled SQL  |
| Storage for governance      | Keep direct SQLite               | Trust-critical, red-team validated, protocol-based     |
| API framework               | Extend existing FastAPI          | Production-hardened middleware; Nexus later for MCP    |
| PostgreSQL                  | Via DataFlow native support      | Zero-code-change path from SQLite to production        |
| Delegate fallback           | SimpleDelegateExecutor           | Unblocks demos while kaizen-agents integration matures |
| Package name                | `pact-platform` (or unpublished) | Resolves namespace collision with kailash-pact         |

## The Minimum Credible Demo

A 5-minute flow that proves the system works:

1. Submit an objective ("Analyze Q3 trading positions")
2. Watch it decompose into requests (via GovernedSupervisor or SimpleDelegateExecutor)
3. See governance intervene — clearance check fails on CONFIDENTIAL data, action is HELD
4. Approve the held action in the dashboard
5. Agent resumes, produces an artifact
6. Review the audit trail showing the full governance chain

PACT has 80% of the machinery for this today. The missing 20%: objective submission UI, a simple decomposition service, and WebSocket event wiring to the execution lifecycle.

## Risks

| Risk                                  | Severity    | Mitigation                                            |
| ------------------------------------- | ----------- | ----------------------------------------------------- |
| Package name collision                | CRITICAL    | Rename in Phase 0                                     |
| 73 import rewrites                    | CRITICAL    | Bulk rewrite or compatibility shim                    |
| Envelope type fragmentation (3 types) | MAJOR       | Adapter in delegate wiring layer                      |
| Trust layer (58 files) disposition    | MAJOR       | Classify in Phase 0, triage incrementally             |
| Frontend-backend timing               | SIGNIFICANT | Build backend first; org builder starts independently |

## Decisions Needed

1. **Package name**: `pact-platform`, unpublished, or something else?
2. **Import strategy**: Bulk rewrite 73 imports to `pact.governance.config`, or create a compatibility shim at `pact.build.config.schema`?
3. **DataFlow dependency**: Add `kailash-dataflow>=1.0.0` as required or optional?
4. **Delegate entry point**: Start with GovernedSupervisor (simple, progressive disclosure) or PlanMonitor (full decompose→design→compose→execute→recover)?
5. **Trust layer**: Delete superseded files now, or deprecate and clean up later?

## Analysis Documents Produced

| #   | Title                             | Focus                                                   |
| --- | --------------------------------- | ------------------------------------------------------- |
| 25  | Delegate Integration Analysis     | Architecture validation, risk register, parallelization |
| 26  | Delegate Integration Requirements | Concrete requirements, phases, what NOW vs what WAITS   |
| 27  | Delegate Value Audit              | Enterprise buyer perspective, minimum credible demo     |
| 28  | Delegate Framework Advice         | DataFlow vs SQL, Nexus vs FastAPI, model design         |
| 29  | This synthesis                    | Unified recommendation                                  |
