# Delegate Integration Requirements Breakdown

**Date**: 2026-03-23
**Context**: PACT Platform repositioned as Layer 3 entrypoint on kailash-py stack
**Depends on**: Brief 03 (delegate-integration-brief.md)

---

## Executive Summary

PACT Platform is a human judgment surface (Layer 3) on top of kaizen-agents (Layer 2) and kailash-pact/eatp/kailash-core (Layer 1). This document breaks down the integration into concrete, implementable requirements organized by what can start NOW versus what MUST WAIT for kaizen-agents completion.

**Key finding**: Approximately 70% of the work is Layer 3-specific (models, API, CLI, frontend) and can proceed immediately. Only Priority 3 (delegate wiring) requires kaizen-agents to be published. Priority 1 and 2 are the critical path.

---

## Phase 0: Immediate Cleanup (CAN DO NOW)

### REQ-000: Assess governance/ Deletion Strategy

| Attribute    | Value                                                                                                                                 |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| What changes | Determine which files in `src/pact/governance/` (30 files) are duplicated in kailash-py's kailash-pact package vs unique to this repo |
| Dependencies | kailash-pact package in kailash-py must be published (currently in worktree, not on main)                                             |
| Risk         | HIGH -- premature deletion breaks 153 existing test collection errors and all governance imports                                      |
| Complexity   | M                                                                                                                                     |
| Can do now?  | PARTIAL -- assess and plan, but do NOT delete until kailash-pact is pip-installable                                                   |

**Analysis**: The kailash-py worktree (`agent-a0b2140b`) already has a kailash-pact package with all governance modules mirrored: `engine.py`, `addressing.py`, `clearance.py`, `compilation.py`, `context.py`, `envelopes.py`, `access.py`, `audit.py`, `store.py`, `stores/sqlite.py`, `api/`, `cli.py`, `yaml_loader.py`, `verdict.py`, `knowledge.py`, `explain.py`, `agent.py`, `agent_mapping.py`, `decorators.py`, `middleware.py`, `envelope_adapter.py`, `testing.py`, plus `stores/backup.py`.

**Decision**: Governance deletion MUST WAIT until kailash-pact >= 0.2.0 is published on PyPI or installable from kailash-py monorepo. Until then, this repo's governance/ is the working copy.

**Immediate actions**:

1. Map file-by-file correspondence between `src/pact/governance/` and kailash-py's kailash-pact package
2. Identify any files unique to this repo that need upstream contribution before deletion
3. Create a migration script that replaces `from pact.governance.X import Y` with `from kailash_pact.governance.X import Y` (or whatever the import path becomes)

### REQ-001: Disposition of trust/ Layer (58 files)

| Attribute    | Value                                                                                                                 |
| ------------ | --------------------------------------------------------------------------------------------------------------------- |
| What changes | Determine where `src/pact/trust/` code belongs -- some into eatp/trust-plane, some into kailash-pact, some stays here |
| Dependencies | eatp >= 0.1.0 and trust-plane >= 0.2.0 package scopes finalized                                                       |
| Risk         | HIGH -- trust/ is deeply entangled with use/execution/ (ExecutionRuntime, KaizenBridge, etc.)                         |
| Complexity   | L                                                                                                                     |
| Can do now?  | Assessment only -- no deletion                                                                                        |

**Analysis**: `src/pact/trust/` contains 58 files across several concerns:

- **EATP protocol primitives** (genesis.py, delegation.py, attestation.py, lifecycle.py, integrity.py) -- should live in eatp/trust-plane
- **Constraint enforcement** (constraint/envelope.py, constraint/gradient.py, constraint/enforcer.py, etc.) -- partially duplicated by GovernanceEngine.verify_action()
- **Store backends** (store/store.py, store/sqlite_store.py, store/postgresql_store.py, etc.) -- infrastructure for trust records
- **Shadow enforcer** (shadow_enforcer.py, shadow_enforcer_live.py) -- should be in kailash-pact or stays here
- **Bridge trust** (bridge_trust.py, bridge_posture.py, constraint/bridge_envelope.py) -- execution-layer concern, may stay
- **Auth** (auth/firebase_admin.py) -- platform-specific, stays here
- **Audit** (audit/anchor.py, audit/pipeline.py, audit/bridge_audit.py) -- partially in eatp, partially platform

**Decision**: Do NOT restructure trust/ now. It works. When kailash-pact is published with full governance + trust integration, migrate in one pass.

### REQ-002: Fix Test Collection Errors (153 errors)

| Attribute    | Value                                                            |
| ------------ | ---------------------------------------------------------------- |
| What changes | Resolve 153 test collection errors so the test suite is runnable |
| Dependencies | None -- can start immediately                                    |
| Risk         | MEDIUM -- tests may reveal broken functionality                  |
| Complexity   | M                                                                |
| Can do now?  | YES -- highest immediate priority                                |

**Immediate action**: Run `pytest --collect-only 2>&1 | head -100` to categorize the 153 errors. Common causes:

- Import errors from missing dependencies (kailash, kailash-kaizen not installed)
- Module-level imports that fail without optional deps
- Test files referencing deleted/moved modules

### REQ-003: build/verticals/ Cleanup

| Attribute    | Value                                                                                                                          |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| What changes | Remove domain-specific vertical code from `src/pact/build/verticals/` (dm_team.py, dm_prompts.py, dm_runner.py, foundation.py) |
| Dependencies | None                                                                                                                           |
| Risk         | LOW -- these violate boundary-test.md (domain vocabulary in framework)                                                         |
| Complexity   | S                                                                                                                              |
| Can do now?  | YES                                                                                                                            |

**Analysis**: The verticals/ directory contains DM (Digital Marketing) specific code and foundation-specific code. Per `rules/boundary-test.md`, domain-specific vocabulary is forbidden in `src/pact/`. These should be moved to `src/pact/examples/` or deleted if they are superseded by the university example.

---

## Phase 1: Work Management Layer (CAN DO NOW -- Priority 1)

This is the largest body of work and has ZERO dependency on kaizen-agents. It is pure Layer 3 platform code.

### REQ-100: Core DataFlow Models -- Work Lifecycle (5 models)

These are the irreducible minimum for work management. Without them, there is nothing to govern operationally.

#### REQ-100a: AgenticObjective Model

| Attribute    | Value                                                                       |
| ------------ | --------------------------------------------------------------------------- |
| What changes | New DataFlow model: high-level goal submitted by a human or upstream system |
| Dependencies | kailash-dataflow installed (optional dep)                                   |
| Risk         | LOW                                                                         |
| Complexity   | M                                                                           |
| Can do now?  | YES                                                                         |

**Fields**:

```
objective_id: str (PK, uuid)
org_id: str (FK to compiled org)
title: str (max 200 chars)
description: str (max 5000 chars)
submitted_by: str (user identity or role address)
status: enum (DRAFT, ACTIVE, DECOMPOSING, IN_PROGRESS, REVIEW, COMPLETED, CANCELLED)
priority: enum (LOW, NORMAL, HIGH, CRITICAL)
budget_usd: float (nullable, NaN-guarded per governance.md Rule 4)
deadline: datetime (nullable)
parent_objective_id: str (nullable, for sub-objectives)
metadata: json dict
created_at: datetime
updated_at: datetime
completed_at: datetime (nullable)
```

**Relationships**: One-to-many with AgenticRequest. Optional parent-child for sub-objectives.

**Key constraints**:

- `math.isfinite()` on budget_usd (governance.md Rule 4)
- Status transitions are monotonic for terminal states (COMPLETED/CANCELLED cannot revert)
- `validate_id()` on objective_id before storage (trust-plane-security.md Rule 2)

#### REQ-100b: AgenticRequest Model

| Attribute    | Value                                                       |
| ------------ | ----------------------------------------------------------- |
| What changes | New DataFlow model: decomposed task assigned to agent/human |
| Dependencies | AgenticObjective model                                      |
| Risk         | LOW                                                         |
| Complexity   | M                                                           |
| Can do now?  | YES                                                         |

**Fields**:

```
request_id: str (PK, uuid)
objective_id: str (FK to AgenticObjective)
title: str
description: str
assigned_to: str (nullable, role address or agent ID)
assigned_pool_id: str (nullable, FK to AgenticPool)
status: enum (PENDING, CLAIMED, IN_PROGRESS, SUBMITTED, REVIEW, APPROVED, REJECTED, CANCELLED)
request_type: enum (AUTONOMOUS, HUMAN_REQUIRED, HYBRID)
priority: enum (LOW, NORMAL, HIGH, CRITICAL)
role_address: str (nullable, D/T/R address for governance)
estimated_cost_usd: float (nullable, NaN-guarded)
actual_cost_usd: float (nullable, NaN-guarded)
deadline: datetime (nullable)
parent_request_id: str (nullable, for sub-tasks)
metadata: json dict
created_at: datetime
updated_at: datetime
claimed_at: datetime (nullable)
completed_at: datetime (nullable)
```

**Relationships**: Many-to-one with AgenticObjective. One-to-many with AgenticArtifact, AgenticWorkSession, AgenticDecision, AgenticFinding.

#### REQ-100c: AgenticWorkSession Model

| Attribute    | Value                                                      |
| ------------ | ---------------------------------------------------------- |
| What changes | New DataFlow model: active work session with cost tracking |
| Dependencies | AgenticRequest model                                       |
| Risk         | LOW                                                        |
| Complexity   | S                                                          |
| Can do now?  | YES                                                        |

**Fields**:

```
session_id: str (PK, uuid)
request_id: str (FK to AgenticRequest)
agent_id: str (who is doing the work)
role_address: str (D/T/R address for governance context)
status: enum (ACTIVE, PAUSED, COMPLETED, ABANDONED)
started_at: datetime
ended_at: datetime (nullable)
cost_usd: float (accumulated cost, NaN-guarded)
token_count: int (LLM tokens consumed)
tool_calls: int (tools invoked)
checkpoint_data: json dict (for session resumption)
```

**Key behavior**: Cost is accumulated incrementally. Each tool call or LLM invocation adds to cost_usd. This feeds into the GovernanceEngine's financial constraint evaluation.

#### REQ-100d: AgenticArtifact Model

| Attribute    | Value                                                    |
| ------------ | -------------------------------------------------------- |
| What changes | New DataFlow model: produced deliverable with versioning |
| Dependencies | AgenticRequest model                                     |
| Risk         | LOW                                                      |
| Complexity   | S                                                        |
| Can do now?  | YES                                                      |

**Fields**:

```
artifact_id: str (PK, uuid)
request_id: str (FK to AgenticRequest)
name: str
artifact_type: enum (DOCUMENT, CODE, DATA, REPORT, IMAGE, OTHER)
version: int (monotonically increasing)
content_ref: str (URL, file path, or inline for small content)
content_hash: str (SHA-256 for integrity)
classification: enum (PUBLIC, RESTRICTED, CONFIDENTIAL, SECRET, TOP_SECRET)
created_by: str (agent ID or user)
created_at: datetime
size_bytes: int (nullable)
metadata: json dict
```

**Key constraint**: Classification must be validated against the creating agent's clearance level. An agent with RESTRICTED clearance cannot produce a SECRET artifact.

#### REQ-100e: AgenticDecision Model

| Attribute    | Value                                                            |
| ------------ | ---------------------------------------------------------------- |
| What changes | New DataFlow model: owner decision point (approve/revise/reject) |
| Dependencies | AgenticRequest model                                             |
| Risk         | LOW                                                              |
| Complexity   | S                                                                |
| Can do now?  | YES                                                              |

**Fields**:

```
decision_id: str (PK, uuid)
request_id: str (FK to AgenticRequest)
decision_type: enum (APPROVAL, REVISION, REJECTION, ESCALATION)
decided_by: str (user identity)
reason: str
options_presented: json list (what choices were available)
option_selected: str
governance_verdict: str (nullable, the GovernanceVerdict.level that triggered this)
created_at: datetime
```

**Relationship to ApprovalQueue**: When GovernanceEngine returns HELD, an AgenticDecision is created with decision_type=APPROVAL and enters the approval queue. The existing `ApprovalQueue` class in `use/execution/approval.py` can be adapted to create AgenticDecision records on resolution.

### REQ-101: Supporting DataFlow Models (4 models)

#### REQ-101a: AgenticReviewDecision Model

| Attribute    | Value                                                      |
| ------------ | ---------------------------------------------------------- |
| What changes | Review outcome on a request (distinct from owner decision) |
| Dependencies | AgenticRequest, AgenticFinding                             |
| Risk         | LOW                                                        |
| Complexity   | S                                                          |
| Can do now?  | YES                                                        |

**Fields**:

```
review_id: str (PK, uuid)
request_id: str (FK to AgenticRequest)
reviewer: str (role address or user)
outcome: enum (APPROVED, CHANGES_REQUESTED, REJECTED)
comments: str
findings: list[str] (FK references to AgenticFinding)
reviewed_at: datetime
```

#### REQ-101b: AgenticFinding Model

| Attribute    | Value                     |
| ------------ | ------------------------- |
| What changes | Issue found during review |
| Dependencies | AgenticRequest            |
| Risk         | LOW                       |
| Complexity   | S                         |
| Can do now?  | YES                       |

**Fields**:

```
finding_id: str (PK, uuid)
request_id: str (FK to AgenticRequest)
review_id: str (nullable FK to AgenticReviewDecision)
severity: enum (INFO, LOW, MEDIUM, HIGH, CRITICAL)
category: str (e.g., "governance_violation", "quality", "security")
title: str
description: str
found_by: str (agent or reviewer)
found_at: datetime
resolved: bool
resolved_at: datetime (nullable)
```

#### REQ-101c: AgenticPool Model

| Attribute    | Value                                     |
| ------------ | ----------------------------------------- |
| What changes | Group of agents/users who can claim tasks |
| Dependencies | None                                      |
| Risk         | LOW                                       |
| Complexity   | S                                         |
| Can do now?  | YES                                       |

**Fields**:

```
pool_id: str (PK, uuid)
name: str
description: str
pool_type: enum (AGENT_ONLY, HUMAN_ONLY, MIXED)
routing_strategy: enum (ROUND_ROBIN, LEAST_LOADED, CAPABILITY_MATCH, MANUAL)
max_concurrent: int (max tasks a member can hold simultaneously)
org_id: str (scoped to organization)
created_at: datetime
active: bool
```

#### REQ-101d: AgenticPoolMembership Model

| Attribute    | Value                         |
| ------------ | ----------------------------- |
| What changes | Pool member with capabilities |
| Dependencies | AgenticPool                   |
| Risk         | LOW                           |
| Complexity   | S                             |
| Can do now?  | YES                           |

**Fields**:

```
membership_id: str (PK, uuid)
pool_id: str (FK to AgenticPool)
member_id: str (agent ID or user identity)
member_type: enum (AGENT, HUMAN)
role_address: str (nullable, D/T/R address)
capabilities: json list (what the member can do)
current_load: int (current active tasks)
joined_at: datetime
active: bool
```

### REQ-102: Execution Tracking Models (2 models)

#### REQ-102a: Run Model

| Attribute    | Value                                                          |
| ------------ | -------------------------------------------------------------- |
| What changes | Execution record linking a request to a GovernedSupervisor run |
| Dependencies | AgenticRequest model                                           |
| Risk         | LOW                                                            |
| Complexity   | S                                                              |
| Can do now?  | YES                                                            |

**Fields**:

```
run_id: str (PK, uuid)
request_id: str (FK to AgenticRequest)
session_id: str (FK to AgenticWorkSession)
agent_id: str
role_address: str
status: enum (PENDING, RUNNING, COMPLETED, FAILED, HELD, CANCELLED)
plan_id: str (nullable, GovernedSupervisor Plan ID)
started_at: datetime
ended_at: datetime (nullable)
budget_allocated_usd: float (NaN-guarded)
budget_consumed_usd: float (NaN-guarded)
node_count: int (plan nodes)
nodes_completed: int
nodes_failed: int
governance_verdicts: json list (gradient verdicts during run)
error: str (nullable)
metadata: json dict
```

#### REQ-102b: ExecutionMetric Model

| Attribute    | Value                       |
| ------------ | --------------------------- |
| What changes | Performance metrics per run |
| Dependencies | Run model                   |
| Risk         | LOW                         |
| Complexity   | S                           |
| Can do now?  | YES                         |

**Fields**:

```
metric_id: str (PK, uuid)
run_id: str (FK to Run)
metric_type: enum (LATENCY, TOKEN_USAGE, TOOL_CALLS, COST, ERROR_RATE)
dimension: str (e.g., "financial", "temporal")
value: float (NaN-guarded)
unit: str (e.g., "ms", "usd", "tokens")
recorded_at: datetime
```

### REQ-103: DataFlow Model Implementation Approach

| Attribute    | Value                                            |
| ------------ | ------------------------------------------------ |
| What changes | Architecture decision: how to implement models   |
| Dependencies | kailash-dataflow availability assessment         |
| Risk         | MEDIUM -- DataFlow may not be available/suitable |
| Complexity   | Decision point                                   |

**ADR: DataFlow vs Pydantic + SQLAlchemy vs Pydantic + Raw SQL**

**Option A: kailash-dataflow** (preferred if available)

- Pro: Zero-config CRUD, auto-generated nodes, consistent with kailash ecosystem
- Pro: Migration support via DataFlow patterns
- Con: Requires `pip install kailash-dataflow`, adds dependency
- Con: DataFlow may not support all field types (json dict, enum)

**Option B: Pydantic models + SQLite (current pattern)**

- Pro: No new dependency, consistent with existing governance SQLite stores
- Pro: Already proven in governance/stores/sqlite.py
- Con: Manual CRUD, manual migrations
- Con: Not scalable to PostgreSQL without rewrite

**Option C: Pydantic models + SQLAlchemy**

- Pro: Full ORM, migration support (Alembic already a dependency)
- Pro: Supports SQLite for dev, PostgreSQL for production
- Con: Heavier dependency, more boilerplate

**Recommendation**: Option B for immediate implementation (consistency with existing patterns), with migration path to Option A when DataFlow supports the field types needed. The existing `stores/sqlite.py` pattern (thread-safe, bounded, `validate_id()`) is proven and secure.

### REQ-110: Services Layer (5 services)

#### REQ-110a: RequestRoutingService

| Attribute    | Value                                                     |
| ------------ | --------------------------------------------------------- |
| What changes | Pool-based assignment of requests to agents/humans        |
| Dependencies | AgenticPool, AgenticPoolMembership, AgenticRequest models |
| Risk         | MEDIUM -- routing logic has many edge cases               |
| Complexity   | M                                                         |
| Can do now?  | YES                                                       |

**Responsibilities**:

1. When a request is created, determine the target pool based on request_type and role_address
2. For ROUND_ROBIN: select next member by rotating index
3. For LEAST_LOADED: select member with lowest current_load
4. For CAPABILITY_MATCH: match request requirements to member capabilities
5. For MANUAL: leave unassigned, notify pool members
6. Respect governance: check GovernanceEngine.verify_action() before assignment
7. Handle pool exhaustion (all members at max_concurrent): queue the request

**Integration point**: Calls `GovernanceEngine.verify_action(role_address, "assign_request")` before routing.

#### REQ-110b: ApprovalQueueService (refactor existing)

| Attribute    | Value                                                                     |
| ------------ | ------------------------------------------------------------------------- |
| What changes | Refactor existing `ApprovalQueue` to integrate with AgenticDecision model |
| Dependencies | AgenticDecision model, existing ApprovalQueue                             |
| Risk         | MEDIUM -- existing ApprovalQueue has 968 governance tests relying on it   |
| Complexity   | M                                                                         |
| Can do now?  | YES                                                                       |

**Current state**: `use/execution/approval.py` has a full `ApprovalQueue` with submit/approve/reject/batch/expiry. It uses in-memory `PendingAction` objects.

**Changes needed**:

1. Keep ApprovalQueue as the in-memory fast path
2. Add persistence: when actions are submitted/resolved, write AgenticDecision records
3. Add AgenticFinding creation when HELD verdicts include constraint details
4. Wire to GovernanceEngine audit anchors (already emitting via engine.\_emit_audit)

**Key principle**: The existing ApprovalQueue API is stable. Wrap it, do not replace it.

#### REQ-110c: CompletionWorkflowService

| Attribute    | Value                                                  |
| ------------ | ------------------------------------------------------ |
| What changes | Manages the submission -> review -> decision lifecycle |
| Dependencies | AgenticRequest, AgenticReviewDecision, AgenticDecision |
| Risk         | LOW                                                    |
| Complexity   | M                                                      |
| Can do now?  | YES                                                    |

**Flow**:

1. Agent completes work, creates AgenticArtifact(s), sets request status to SUBMITTED
2. Service routes to reviewer (human or reviewing agent)
3. Reviewer creates AgenticReviewDecision with findings
4. If APPROVED: request -> APPROVED, objective progress updated
5. If CHANGES_REQUESTED: request -> IN_PROGRESS, agent notified
6. If REJECTED: request -> REJECTED, escalate to objective owner

#### REQ-110d: CostTrackingService

| Attribute    | Value                                                                |
| ------------ | -------------------------------------------------------------------- |
| What changes | Aggregate cost per objective/agent/org with governance budget checks |
| Dependencies | AgenticWorkSession, Run, ExecutionMetric models                      |
| Risk         | MEDIUM -- cost accumulation must be NaN-safe and consistent          |
| Complexity   | M                                                                    |
| Can do now?  | YES                                                                  |

**Current state**: `trust/store/cost_tracking.py` has a `CostTracker` that tracks per-agent costs. The governance layer has financial constraint evaluation in `engine._evaluate_against_envelope()`.

**Changes needed**:

1. Add objective-level cost aggregation (sum of all request costs under an objective)
2. Add org-level cost aggregation (sum of all objective costs)
3. Integrate with GovernanceEngine financial constraints: when objective budget_usd is set, create a task envelope with that budget
4. Real-time cost dashboard data: current burn rate, projected completion cost

**Security**: All cost values MUST be validated with `math.isfinite()` at every accumulation point.

#### REQ-110e: NotificationDispatchService

| Attribute    | Value                                         |
| ------------ | --------------------------------------------- |
| What changes | Multi-channel notification routing            |
| Dependencies | None (can use existing EventBus as transport) |
| Risk         | LOW                                           |
| Complexity   | S                                             |
| Can do now?  | YES                                           |

**Channels** (MVP):

1. In-app (via WebSocket EventBus -- already exists in `use/api/events.py`)
2. Email (template-based, configurable SMTP)

**Events to notify on**:

- Request assigned to pool/agent
- HELD verdict requiring approval
- Review completed
- Objective completed/cancelled
- Budget threshold warnings (70%, 90%, 100%)

---

## Phase 2: API Layer (CAN DO NOW)

### REQ-200: Work Management API Routers

| Attribute    | Value                                                 |
| ------------ | ----------------------------------------------------- |
| What changes | REST API endpoints for all work management operations |
| Dependencies | Phase 1 models and services                           |
| Risk         | LOW -- follows existing governance API patterns       |
| Complexity   | M (per router), L (total)                             |
| Can do now?  | YES (after models)                                    |

**Existing API structure**:

- `governance/api/endpoints.py` -- governance decisions (check-access, verify-action, clearances, bridges, KSPs, envelopes)
- `governance/api/router.py` -- mounting logic with rate limiting
- `governance/api/auth.py` -- GovernanceAuth with read/write permissions
- `governance/api/schemas.py` -- Pydantic request/response models
- `use/api/endpoints.py` -- platform API (teams, agents, approvals, cost, bridges, shadow, envelopes)
- `use/api/server.py` -- FastAPI server with CORS, rate limiting, body size limits, WebSocket

**New routers needed**:

#### REQ-200a: Objectives Router

```
POST   /api/v1/objectives                    -- Create objective
GET    /api/v1/objectives                    -- List objectives (with status filter)
GET    /api/v1/objectives/{id}               -- Get objective detail
PATCH  /api/v1/objectives/{id}               -- Update objective (title, priority, budget)
POST   /api/v1/objectives/{id}/decompose     -- Trigger request decomposition
POST   /api/v1/objectives/{id}/cancel        -- Cancel objective
GET    /api/v1/objectives/{id}/cost           -- Cost summary for objective
GET    /api/v1/objectives/{id}/requests       -- List requests under objective
```

#### REQ-200b: Requests Router

```
POST   /api/v1/requests                      -- Create request (manual or from decomposition)
GET    /api/v1/requests                      -- List requests (with status/pool filter)
GET    /api/v1/requests/{id}                 -- Get request detail
POST   /api/v1/requests/{id}/claim           -- Claim request (from pool)
POST   /api/v1/requests/{id}/submit          -- Submit completed work
POST   /api/v1/requests/{id}/cancel          -- Cancel request
GET    /api/v1/requests/{id}/artifacts       -- List artifacts
GET    /api/v1/requests/{id}/sessions        -- List work sessions
```

#### REQ-200c: Work Sessions Router

```
POST   /api/v1/sessions                      -- Start work session
GET    /api/v1/sessions/{id}                 -- Get session detail
POST   /api/v1/sessions/{id}/end             -- End session
GET    /api/v1/sessions/{id}/metrics          -- Session metrics
```

#### REQ-200d: Artifacts Router

```
POST   /api/v1/artifacts                     -- Create artifact
GET    /api/v1/artifacts/{id}                -- Get artifact detail
GET    /api/v1/artifacts/{id}/versions        -- List artifact versions
POST   /api/v1/artifacts/{id}/version         -- Create new version
```

#### REQ-200e: Decisions Router

```
GET    /api/v1/decisions                     -- List pending decisions
GET    /api/v1/decisions/{id}                -- Get decision detail
POST   /api/v1/decisions/{id}/resolve         -- Resolve decision (approve/reject/revise)
GET    /api/v1/decisions/queue                -- Approval queue status (wraps existing ApprovalQueue)
```

#### REQ-200f: Pools Router

```
POST   /api/v1/pools                         -- Create pool
GET    /api/v1/pools                         -- List pools
GET    /api/v1/pools/{id}                    -- Get pool detail
POST   /api/v1/pools/{id}/members            -- Add member
DELETE /api/v1/pools/{id}/members/{member_id} -- Remove member
GET    /api/v1/pools/{id}/workload            -- Pool workload distribution
```

#### REQ-200g: Runs Router

```
GET    /api/v1/runs                          -- List runs (with status filter)
GET    /api/v1/runs/{id}                     -- Get run detail
GET    /api/v1/runs/{id}/events              -- Run event timeline
GET    /api/v1/runs/{id}/metrics             -- Run metrics
```

### REQ-201: Auth Model

| Attribute    | Value                                                   |
| ------------ | ------------------------------------------------------- |
| What changes | Extend GovernanceAuth for work management permissions   |
| Dependencies | Existing GovernanceAuth in governance/api/auth.py       |
| Risk         | MEDIUM -- auth model must integrate with role addresses |
| Complexity   | M                                                       |
| Can do now?  | YES                                                     |

**Current state**: GovernanceAuth provides `require_read` and `require_write` dependency injections. Uses API key auth with optional Firebase SSO (trust/auth/firebase_admin.py).

**Changes needed**:

1. Add role-based permissions: an identity maps to a role_address, role_address maps to allowed operations via GovernanceEngine
2. Add pool-based permissions: pool members can claim/submit within their pool
3. Add objective ownership: only objective owner (or their manager in D/T/R chain) can approve/cancel
4. Keep backward compatibility with existing API key auth

### REQ-202: WebSocket Event Extensions

| Attribute    | Value                                             |
| ------------ | ------------------------------------------------- |
| What changes | Extend EventBus to publish work management events |
| Dependencies | Existing EventBus in use/api/events.py            |
| Risk         | LOW                                               |
| Complexity   | S                                                 |
| Can do now?  | YES                                               |

**New event types**:

```
OBJECTIVE_CREATED, OBJECTIVE_STATUS_CHANGED, OBJECTIVE_COMPLETED
REQUEST_CREATED, REQUEST_CLAIMED, REQUEST_SUBMITTED, REQUEST_REVIEWED
SESSION_STARTED, SESSION_ENDED
ARTIFACT_CREATED, ARTIFACT_VERSIONED
DECISION_PENDING, DECISION_RESOLVED
POOL_WORKLOAD_CHANGED
RUN_STARTED, RUN_COMPLETED, RUN_FAILED, RUN_HELD
COST_THRESHOLD_WARNING
```

---

## Phase 2: Admin CLI (CAN DO NOW -- Priority 2)

### REQ-300: Extend kailash-pact CLI

| Attribute    | Value                                                         |
| ------------ | ------------------------------------------------------------- |
| What changes | Add operational commands to existing `kailash-pact` Click CLI |
| Dependencies | Existing CLI in governance/cli.py, governance engine          |
| Risk         | LOW                                                           |
| Complexity   | S per command, M total                                        |
| Can do now?  | YES                                                           |

**Current state**: CLI has only `kailash-pact validate <yaml>`. Uses Click framework.

#### REQ-300a: org commands (CRITICAL)

```
kailash-pact org create <yaml>           -- Create org from YAML (compile + store)
kailash-pact org list                    -- List stored orgs
kailash-pact org show <org_id>           -- Show org summary
kailash-pact org tree <org_id>           -- Show address tree (--verbose from validate)
```

**Implementation**: `org create` extends the existing `validate` command -- load YAML, compile, then store via GovernanceEngine. Requires a storage backend (SQLite).

#### REQ-300b: role commands (CRITICAL)

```
kailash-pact role assign <address> <identity>    -- Map user/agent to role
kailash-pact role list <org_id>                  -- List role assignments
kailash-pact role unassign <address>             -- Remove role assignment
```

**Implementation**: Requires a new `RoleAssignmentStore` -- maps identities to role addresses. This is a new concept not in the current governance engine.

#### REQ-300c: clearance commands (CRITICAL)

```
kailash-pact clearance grant <address> <level>   -- Grant clearance
kailash-pact clearance show <address>            -- Show current clearance
kailash-pact clearance revoke <address>          -- Revoke clearance
kailash-pact clearance list <org_id>             -- List all clearances
```

**Implementation**: Wraps existing GovernanceEngine.grant_clearance() and revoke_clearance().

#### REQ-300d: envelope commands (IMPORTANT)

```
kailash-pact envelope show <address>             -- Show effective envelope
kailash-pact envelope set <yaml>                 -- Set role/task envelope from YAML
kailash-pact envelope diff <addr1> <addr2>       -- Compare two role envelopes
```

**Implementation**: `envelope show` wraps GovernanceEngine.compute_envelope(). `envelope set` wraps set_role_envelope()/set_task_envelope().

#### REQ-300e: bridge commands (IMPORTANT)

```
kailash-pact bridge create <yaml>                -- Create bridge
kailash-pact bridge list <org_id>                -- List bridges
kailash-pact bridge show <bridge_id>             -- Bridge detail
```

#### REQ-300f: agent commands (NICE-TO-HAVE for now)

```
kailash-pact agent register <config_yaml>        -- Register agent to role
kailash-pact agent list <org_id>                 -- List registered agents
kailash-pact agent status <agent_id>             -- Agent status
```

**Note**: Agent registration requires the execution layer. Can be implemented with the existing AgentRegistry in `use/execution/registry.py`.

#### REQ-300g: audit commands (IMPORTANT)

```
kailash-pact audit export <org_id> [--format json|csv]  -- Export audit trail
kailash-pact audit verify <org_id>                       -- Verify chain integrity
kailash-pact audit stats <org_id>                        -- Audit statistics
```

**Implementation**: `audit verify` wraps GovernanceEngine.verify_audit_integrity(). `audit export` reads from SqliteAuditLog.

---

## Phase 3: Delegate Wiring (MUST WAIT for kaizen-agents)

### REQ-400: GovernedSupervisor Integration

| Attribute    | Value                                                              |
| ------------ | ------------------------------------------------------------------ |
| What changes | Import and wire GovernedSupervisor from kaizen-agents              |
| Dependencies | kaizen-agents package published in kailash-py                      |
| Risk         | HIGH -- core integration point, any API mismatch blocks everything |
| Complexity   | L                                                                  |
| Can do now?  | NO -- kaizen-agents in progress                                    |

**Integration surface** (based on reading `kaizen_agents/supervisor.py`):

The GovernedSupervisor has a clean progressive-disclosure API:

1. **Layer 1**: `supervisor = GovernedSupervisor(model="...", budget_usd=10.0)` then `result = await supervisor.run("objective")`
2. **Layer 2**: Add `tools=`, `data_clearance=`, `warning_threshold=`
3. **Layer 3**: Access governance subsystems via `supervisor.audit`, `supervisor.budget`, etc. (read-only views)

**What PACT Platform needs to wire**:

#### REQ-400a: Supervisor Factory

```python
# PACT Platform creates supervisors bound to role envelopes
class PactSupervisorFactory:
    def __init__(self, governance_engine: GovernanceEngine):
        self._engine = governance_engine

    def create_for_role(self, role_address: str, task_id: str | None = None) -> GovernedSupervisor:
        """Create a GovernedSupervisor bound to a role's effective envelope."""
        envelope = self._engine.compute_envelope(role_address, task_id=task_id)
        context = self._engine.get_context(role_address)

        return GovernedSupervisor(
            model=os.environ.get("PACT_DEFAULT_MODEL", "claude-sonnet-4-6"),
            budget_usd=envelope.financial.max_spend_usd if envelope and envelope.financial else 1.0,
            tools=list(envelope.operational.allowed_actions) if envelope else [],
            data_clearance=_map_clearance(context.effective_clearance_level),
            timeout_seconds=_extract_temporal_limit(envelope),
            policy_source=f"governance-engine:{context.org_id}",
        )
```

**Risk**: GovernedSupervisor's `ConstraintEnvelope` (from kaizen-agents types.py) uses a dict-based structure (`{"limit": float}`) while PACT's `ConstraintEnvelopeConfig` (from build/config/schema.py) uses Pydantic models with named fields (`financial.max_spend_usd`). An adapter is needed.

#### REQ-400b: execute_node Callback

| Attribute    | Value                                                                           |
| ------------ | ------------------------------------------------------------------------------- |
| What changes | Provide the execution callback that GovernedSupervisor calls for each plan node |
| Dependencies | GovernedSupervisor API, existing LLM backends                                   |
| Risk         | MEDIUM                                                                          |
| Complexity   | M                                                                               |
| Can do now?  | NO                                                                              |

```python
async def pact_execute_node(spec: AgentSpec, inputs: dict[str, Any]) -> dict[str, Any]:
    """PACT Platform's execute_node callback for GovernedSupervisor.

    1. Look up the agent's role_address from spec metadata
    2. Call GovernanceEngine.verify_action() to get governance verdict
    3. If BLOCKED: raise GovernanceBlockedError
    4. If HELD: submit to ApprovalQueue, await resolution
    5. If AUTO_APPROVED/FLAGGED: invoke LLM via existing BackendRouter
    6. Record Run and ExecutionMetric
    7. Return {"result": ..., "cost": ...}
    """
```

**Key design decision**: The existing `KaizenBridge.execute_task()` already does this flow (steps 1-5). The new callback should delegate to KaizenBridge or replace it. Since KaizenBridge is tightly coupled to the old trust-layer ExecutionRuntime, a NEW callback that uses GovernanceEngine directly is cleaner.

#### REQ-400c: Plan Event -> WebSocket Bridge

| Attribute    | Value                                                                |
| ------------ | -------------------------------------------------------------------- |
| What changes | Forward GovernedSupervisor's PlanEvents to PACT's WebSocket EventBus |
| Dependencies | GovernedSupervisor, EventBus                                         |
| Risk         | LOW                                                                  |
| Complexity   | S                                                                    |
| Can do now?  | NO                                                                   |

```python
# After supervisor.run() completes, publish events
for event in result.events:
    await event_bus.publish(PlatformEvent(
        event_type=_map_plan_event_type(event.event_type),
        data={
            "run_id": run.run_id,
            "node_id": event.node_id,
            "event_type": event.event_type.value,
            ...
        },
    ))
```

**Alternative**: GovernedSupervisor could accept an event callback for real-time streaming. Check if this exists in the API.

#### REQ-400d: HELD Verdict -> Approval Queue Bridge

| Attribute    | Value                                                                   |
| ------------ | ----------------------------------------------------------------------- |
| What changes | When GovernedSupervisor emits NODE_HELD, submit to PACT's ApprovalQueue |
| Dependencies | GovernedSupervisor, ApprovalQueue, AgenticDecision model                |
| Risk         | MEDIUM -- HELD resolution must unblock the supervisor                   |
| Complexity   | M                                                                       |
| Can do now?  | NO                                                                      |

**Challenge**: GovernedSupervisor runs async. When a node is HELD, the supervisor pauses that node. PACT Platform needs to:

1. Detect the HELD event
2. Create AgenticDecision(decision_type=APPROVAL)
3. Submit to ApprovalQueue
4. When human resolves (approve/reject), signal the supervisor to continue/cancel

This requires a coordination mechanism (asyncio.Event or callback) between the approval resolution and the supervisor's execution loop.

### REQ-401: Envelope Adapter Consolidation

| Attribute    | Value                                                                                                    |
| ------------ | -------------------------------------------------------------------------------------------------------- |
| What changes | Consolidate the two envelope formats (PACT ConstraintEnvelopeConfig vs kaizen-agents ConstraintEnvelope) |
| Dependencies | Both packages stable                                                                                     |
| Risk         | HIGH -- format mismatch is the #1 integration risk                                                       |
| Complexity   | M                                                                                                        |
| Can do now?  | PARTIAL -- design the adapter now, implement when both packages are stable                               |

**Current situation**:

- PACT's `ConstraintEnvelopeConfig` (Pydantic, named fields: `financial.max_spend_usd`, `operational.allowed_actions`)
- kaizen-agents' `ConstraintEnvelope` (dataclass, dict fields: `financial: {"limit": float}`, `operational: {"allowed": [], "blocked": []}`)
- Existing `GovernanceEnvelopeAdapter` converts PACT -> trust-layer format

**Design**: Create a `PactToKaizenEnvelopeAdapter` that converts `ConstraintEnvelopeConfig` -> kaizen-agents `ConstraintEnvelope`:

```python
def to_kaizen_envelope(config: ConstraintEnvelopeConfig) -> kaizen_agents.ConstraintEnvelope:
    return kaizen_agents.ConstraintEnvelope(
        financial={"limit": config.financial.max_spend_usd} if config.financial else {"limit": 1.0},
        operational={"allowed": list(config.operational.allowed_actions), "blocked": list(config.operational.blocked_actions)},
        temporal={"limit_seconds": ...} if config.temporal else {},
        data_access={"ceiling": ..., "scopes": []} if config.data_access else {"ceiling": "public", "scopes": []},
        communication={"recipients": ..., "channels": []} if config.communication else {"recipients": [], "channels": []},
    )
```

---

## Phase 4: Integration Layer (CAN START NOW, some MUST WAIT)

### REQ-500: Webhook Adapters

| Attribute    | Value                                           |
| ------------ | ----------------------------------------------- |
| What changes | Outbound notifications to Slack, Discord, Teams |
| Dependencies | NotificationDispatchService                     |
| Risk         | LOW per adapter                                 |
| Complexity   | S per adapter                                   |
| Can do now?  | YES                                             |

**MVP**: Slack webhook adapter only. Discord and Teams in Phase 2.

Each adapter implements a `WebhookAdapter` protocol:

```python
class WebhookAdapter(Protocol):
    async def send(self, event: PlatformEvent) -> bool: ...
    async def health_check(self) -> bool: ...
```

**Slack adapter fields**: `webhook_url` (from env), `channel` (configurable), `template` (per event type).

### REQ-501: LLM Provider Management

| Attribute    | Value                                                  |
| ------------ | ------------------------------------------------------ |
| What changes | BYO API key management, provider selection             |
| Dependencies | Existing BackendRouter in use/execution/llm_backend.py |
| Risk         | MEDIUM -- key storage must be secure                   |
| Complexity   | M                                                      |
| Can do now?  | YES                                                    |

**Current state**: BackendRouter supports Anthropic and OpenAI backends. Keys come from .env.

**Changes needed**:

1. Per-org API key storage (encrypted at rest)
2. Provider selection per objective/request
3. Fallback chain (try provider A, fall back to provider B)
4. Cost tracking per provider

**Security**: API keys MUST be stored encrypted. Use the cloud provider's secrets manager in production (deployment.md Rule 4). For local dev, .env is acceptable.

---

## Phase 5: Frontend (CAN START NOW)

### REQ-600: Web Dashboard Pages (Next.js)

| Attribute    | Value                                |
| ------------ | ------------------------------------ |
| What changes | New pages for work management        |
| Dependencies | API endpoints (Phase 2)              |
| Risk         | LOW                                  |
| Complexity   | M per page                           |
| Can do now?  | YES (design), API-dependent for data |

**Existing pages** (18 in apps/web/): org chart, agent status, approval queue, trust chains, envelopes, bridges, cost report, verification stats, etc.

#### REQ-600a: Objective Management Page (CRITICAL)

- Create objective form (title, description, budget, deadline)
- Objective list with status filters
- Objective detail with request breakdown and cost tracking
- Decompose button (triggers request creation)

#### REQ-600b: Request Queue Page (CRITICAL)

- Request list with status/pool/assignee filters
- Claim button (for pool members)
- Review interface (approve/reject/request changes with findings)
- Request detail with artifacts, sessions, decisions timeline

#### REQ-600c: Pool Management Page (IMPORTANT)

- Pool list with workload indicators
- Pool detail: members, active tasks, routing strategy
- Add/remove member interface

#### REQ-600d: Interactive Org Builder (NICE-TO-HAVE)

- Visual D/T/R tree editor
- Drag-and-drop department/team/role creation
- Real-time grammar validation
- Export to YAML

### REQ-601: Mobile App Screens (Flutter)

| Attribute    | Value                           |
| ------------ | ------------------------------- |
| What changes | New screens for work management |
| Dependencies | API endpoints (Phase 2)         |
| Risk         | LOW                             |
| Complexity   | S per screen                    |
| Can do now?  | YES (design)                    |

#### REQ-601a: Objective Tracking Screen (CRITICAL)

- Objective list with status badges
- Pull-to-refresh
- Objective detail with progress bar

#### REQ-601b: Request Claiming/Review Screen (CRITICAL)

- Available requests for the user's pools
- Claim button with governance confirmation
- Simple review interface (approve/reject)

#### REQ-601c: Pool Management Screen (IMPORTANT)

- Pool membership management
- Workload view

---

## Risk Assessment

### Critical Risks

| Risk                                                                     | Probability | Impact   | Mitigation                                                                                                                |
| ------------------------------------------------------------------------ | ----------- | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| R1: kaizen-agents API changes during development                         | HIGH        | HIGH     | Design Phase 3 against the current supervisor.py interface. Use an adapter pattern so PACT is insulated from API changes. |
| R2: Envelope format mismatch causes silent governance bypass             | MEDIUM      | CRITICAL | Write a comprehensive adapter with NaN-guarded conversion tests. Never pass raw dicts -- always go through the adapter.   |
| R3: Premature governance/ deletion breaks test suite                     | MEDIUM      | HIGH     | Do NOT delete until kailash-pact is pip-installable. Assess first, migrate imports, then delete.                          |
| R4: 153 test collection errors mask real failures                        | HIGH        | MEDIUM   | Fix test collection as Phase 0 priority. Categorize errors before fixing.                                                 |
| R5: DataFlow model proliferation (11+ models) creates maintenance burden | MEDIUM      | MEDIUM   | Start with 5 core models (REQ-100). Add supporting models only when needed.                                               |

### Medium Risks

| Risk                                                                | Probability | Impact | Mitigation                                                                                           |
| ------------------------------------------------------------------- | ----------- | ------ | ---------------------------------------------------------------------------------------------------- |
| R6: HELD verdict coordination between supervisor and approval queue | MEDIUM      | MEDIUM | Design the async coordination mechanism (asyncio.Event pattern) before implementing.                 |
| R7: Cost tracking NaN injection via accumulated values              | LOW         | HIGH   | Apply `math.isfinite()` at every accumulation point (governance.md Rule 4).                          |
| R8: Thread safety in new services                                   | MEDIUM      | MEDIUM | Follow existing pattern: threading.Lock on all stores, bounded collections (governance.md Rule 5/7). |

### Low Risks

| Risk                                | Probability | Impact | Mitigation                                            |
| ----------------------------------- | ----------- | ------ | ----------------------------------------------------- |
| R9: Frontend blocked by API changes | LOW         | LOW    | Frontend can use mock data while API stabilizes.      |
| R10: CLI feature creep              | LOW         | LOW    | Strict MVP: only commands marked CRITICAL in Phase 2. |

---

## Implementation Roadmap

### Sprint 1 (NOW): Foundation (est. 3-5 days)

- [ ] REQ-002: Fix test collection errors (153 errors)
- [ ] REQ-003: Clean up build/verticals/ (boundary test violations)
- [ ] REQ-000: Map governance/ files vs kailash-py kailash-pact package (assessment only)
- [ ] REQ-103: ADR on model implementation approach (DataFlow vs Pydantic + SQLite)

### Sprint 2 (NOW): Core Models (est. 5-7 days)

- [ ] REQ-100a: AgenticObjective model
- [ ] REQ-100b: AgenticRequest model
- [ ] REQ-100c: AgenticWorkSession model
- [ ] REQ-100d: AgenticArtifact model
- [ ] REQ-100e: AgenticDecision model

### Sprint 3 (NOW): Supporting Models + Core Services (est. 5-7 days)

- [ ] REQ-101a-d: Supporting models (AgenticReviewDecision, AgenticFinding, AgenticPool, AgenticPoolMembership)
- [ ] REQ-102a-b: Execution tracking models (Run, ExecutionMetric)
- [ ] REQ-110a: RequestRoutingService
- [ ] REQ-110b: ApprovalQueueService refactor

### Sprint 4 (NOW): API + CLI (est. 5-7 days)

- [ ] REQ-200a-g: API routers (objectives, requests, sessions, artifacts, decisions, pools, runs)
- [ ] REQ-201: Auth model extensions
- [ ] REQ-202: WebSocket event extensions
- [ ] REQ-300a-c: CLI commands (org, role, clearance -- CRITICAL)
- [ ] REQ-300d-e: CLI commands (envelope, bridge -- IMPORTANT)

### Sprint 5 (NOW): Remaining Services + Integrations (est. 3-5 days)

- [ ] REQ-110c: CompletionWorkflowService
- [ ] REQ-110d: CostTrackingService
- [ ] REQ-110e: NotificationDispatchService
- [ ] REQ-500: Slack webhook adapter

### Sprint 6 (AFTER kaizen-agents): Delegate Wiring (est. 5-7 days)

- [ ] REQ-400a: PactSupervisorFactory
- [ ] REQ-400b: execute_node callback
- [ ] REQ-400c: Plan Event -> WebSocket bridge
- [ ] REQ-400d: HELD verdict -> Approval Queue bridge
- [ ] REQ-401: Envelope adapter consolidation

### Sprint 7 (PARALLEL with Sprint 6): Frontend MVP (est. 5-7 days)

- [ ] REQ-600a: Objective management page
- [ ] REQ-600b: Request queue page
- [ ] REQ-601a: Objective tracking screen (mobile)
- [ ] REQ-601b: Request claiming/review screen (mobile)

### Sprint 8: Polish + Integration Testing (est. 3-5 days)

- [ ] REQ-300f-g: CLI commands (agent, audit -- NICE-TO-HAVE)
- [ ] REQ-501: LLM provider management
- [ ] REQ-600c-d: Pool management + org builder (web)
- [ ] REQ-601c: Pool management (mobile)
- [ ] End-to-end integration testing: Objective -> Decompose -> Route -> Execute -> Review -> Complete

---

## Success Criteria

- [ ] All 11 DataFlow models implemented with NaN-safe, thread-safe stores
- [ ] 7 API routers operational with auth and rate limiting
- [ ] Admin CLI has at least org create/list, role assign, clearance grant, envelope show
- [ ] ApprovalQueue integrated with AgenticDecision persistence
- [ ] GovernedSupervisor wired with PACT-specific execute_node callback
- [ ] HELD verdicts flow from supervisor -> approval queue -> dashboard -> resolution -> supervisor resumption
- [ ] Web dashboard has objective management and request queue pages
- [ ] Mobile app has objective tracking and request claiming screens
- [ ] All governance operations emit audit anchors
- [ ] Cost tracking accurate to $0.01 across objective/agent/org aggregations
- [ ] Test collection errors reduced to 0
- [ ] Boundary test passes (no domain vocabulary in src/pact/ excluding examples/)
