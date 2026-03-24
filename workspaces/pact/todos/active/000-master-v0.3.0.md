# PACT Platform v0.3.0 — Master Todo List

**Date**: 2026-03-24
**Architecture**: Layer 3 platform on kailash-pact (governance engine, v0.4.0) + kaizen-agents (autonomous core)
**Execution**: 5 autonomous sessions, no human-time estimates
**Analysis**: Documents #18-40 (23 analysis files, red-teamed)
**Upstream**: kailash-py #59-64, kailash-rs #67-71 (being worked on in parallel)

---

## Decisions (Locked)

| Decision               | Choice                                            |
| ---------------------- | ------------------------------------------------- |
| Package name           | `pact-platform` (PyPI) / `pact_platform` (Python) |
| Repo name              | `pact` (unchanged)                                |
| Governance primitives  | Move to `kailash.trust.pact` (kailash-py #63)     |
| kailash-pact v0.4.0    | Becomes the PACT Engine (kailash-py #64)          |
| Governance integration | Option C: policy down, enforcement inside         |
| Storage (work mgmt)    | DataFlow (11 models, 121 auto-nodes)              |
| Storage (governance)   | Keep direct SQLite via kailash-pact               |
| API framework          | Extend existing FastAPI                           |
| Delegate entry         | GovernedSupervisor (progressive disclosure)       |
| Trust layer            | Delete ~22 superseded, keep ~36 platform-specific |

## Execution Plan

```
Session 1: M0 (rename + cleanup + test diagnosis)
Session 2: M1 + M2 + M3 (parallel streams)
Session 3: M4 (PactEngine wiring + auto-seeding)
Session 4: M5 + M6 (frontend + integration, parallel)
Session 5: M7 (red team + hardening + CLAUDE.md rewrite)
```

## Dependency Graph

```
M0 ──→ M1 ──┐
  ├──→ M2 ──┼──→ M4 ──→ M5
  └──→ M3 ──┘      └──→ M6
                         └──→ M7
```

M1/M2/M3 parallel after M0. M4 after M1-M3. M5/M6 parallel after M4. M7 after all.

---

## M0: Platform Rename & Cleanup (Session 1)

Critical path. Nothing else proceeds until this completes.

### 0001 — Diagnose 153 test collection errors [S]

Run `pytest --collect-only 2>&1 | grep ERROR` and categorize every error. Root cause analysis BEFORE the rename — don't rename into a minefield.

**Acceptance**: Root cause documented for every collection error. Categories: missing imports, deleted modules, circular imports, fixture issues.

### 0002 — Catalog at-risk security patterns before trust file deletion [S]

The COC analysis (#36) identified 3 security patterns at risk of silent disappearance: Ed25519 message signing (RT-06), constant-time HMAC comparison (RT-21), key material zeroization. For each of the ~22 trust files being deleted, document what security knowledge they contain. Verify the pattern exists in kailash-pact or kailash[trust] before deletion.

**Acceptance**: Security pattern catalog written. Every pattern mapped to its surviving location. No pattern deleted without a confirmed replacement.

### 0003 — Create `src/pact_platform/` directory + `__init__.py` [S]

Create the new package root. `__version__ = "0.3.0"`, Apache 2.0 header, module docstring describing L3 platform architecture.

**Acceptance**: `python -c "import pact_platform; print(pact_platform.__version__)"` prints `0.3.0`.

### 0004 — Move `src/pact/build/` → `src/pact_platform/build/` [M]

Move 20 files. `build/config/schema.py` becomes a thin re-export shim from `pact.governance.config` (kailash-pact). Delete `build/verticals/` (5 dead shim files, boundary-test violation).

**Acceptance**: 20 files moved. schema.py is re-export only. verticals/ deleted. Internal imports updated.

### 0005 — Move `src/pact/use/` → `src/pact_platform/use/` [M]

Move 25 files (API server, execution runtime, LLM backends, approval queue, observability).

**Acceptance**: 25 files moved. Internal imports updated.

### 0006 — Move `src/pact/examples/` → `src/pact_platform/examples/` [S]

Move 13 files (university + foundation examples).

**Acceptance**: Examples import governance from `pact.governance` (kailash-pact). University demo runs 32/32.

### 0007 — Delete `src/pact/governance/` [M]

Delete all 30 governance files. These are now in kailash-pact (installed via pip). Verify `from pact.governance import GovernanceEngine` resolves to kailash-pact, not local code.

**Acceptance**: 30 files deleted. `from pact.governance import GovernanceEngine` works from kailash-pact.

### 0008 — Triage trust layer: delete ~22 superseded, move ~36 to `pact_platform/trust/` [L]

Per analysis #35 TODO-0006. For each file to delete, grep all consumers first. Redirect or delete consumers before deleting the source.

**Acceptance**: ~22 files deleted, ~36 moved. No dangling imports. Security patterns catalog (0002) confirms no knowledge lost.

### 0009 — Bulk rewrite imports in source files (~461 occurrences) [L]

Mechanical bulk rewrite per the import table in analysis #35 TODO-0008. Key rules:

- `from pact.build.config.schema` → `from pact.governance.config` (or `from pact_platform.build.config.schema` re-export)
- `from pact.use.*` → `from pact_platform.use.*`
- `from pact.trust.X` (kept) → `from pact_platform.trust.X`
- `from pact.governance.*` → unchanged (from kailash-pact)

**Acceptance**: Zero `from pact.build.`, `from pact.use.`, `from pact.examples.` imports remain in src/.

### 0010 — Bulk rewrite imports in test files (~1,034 occurrences) [L]

Same rules as 0009 applied to tests/. Special handling for governance tests (point to kailash-pact) and deleted trust tests (delete or rewrite).

**Acceptance**: `pytest --collect-only` = 0 errors.

### 0011 — Delete `src/pact/` remnant directory [S]

After all moves/deletes, the directory should be empty. Delete it. The `pact` namespace is now exclusively kailash-pact.

**Acceptance**: `src/pact/` does not exist. No local code shadows kailash-pact.

### 0012 — Fix scripts and Docker for new paths [M]

Red team finding RT-R04. Update:

- `scripts/run_seeded_server.py` (2 broken imports)
- `scripts/seed_demo.py` (16 broken imports)
- `scripts/shadow_calibrate.py` (1 broken import)
- `Dockerfile` CMD (references script that imports old paths)
- `docker-compose.yml` env vars: `CARE_*` → `PACT_*`, network `care_net` → `pact_net`
- `apps/web/lib/api.ts`: `CareApiClient` → `PactApiClient`, `CareWebSocketClient` → `PactWebSocketClient`
- All `CARE_` env var references in frontend

**Acceptance**: `docker compose build` succeeds. `docker compose up` starts all services. Frontend connects to API.

### 0013 — Update pyproject.toml and verify entry points [S]

Verify version consistency (`__init__.py` matches pyproject.toml). Create `src/pact_platform/cli.py` entry point. Verify `pact --help` works.

**Acceptance**: `pip install -e .` succeeds. `pact --help` prints CLI help.

### 0014 — Fix test suite — green on pytest [L]

Quality gate for M0. Fix all remaining test failures after the rename. Document test count before and after.

**Acceptance**: `pytest` passes. Test count documented. Zero collection errors.

### 0015 — Update CLAUDE.md, rule files, documentation [M]

COC analysis #36 identified 5 rules needing major rewrite, 6 needing minor updates, 4 new rules needed. Update:

- `CLAUDE.md` — Architecture (L1/L2/L3), package names, import patterns
- `.claude/rules/governance.md` — Scope paths
- `.claude/rules/boundary-test.md` — Scope `src/pact_platform/`
- `.claude/rules/trust-plane-security.md` — Scope paths
- `.claude/rules/pact-governance.md` — Scope paths, import examples
- Create `rules/dataflow-security.md` — NaN/Inf on DataFlow fields, parameterized queries
- Create `rules/delegate-wiring.md` — PactEngine adapter patterns, Option C governance
- Create `rules/webhook-security.md` — SSRF prevention, replay protection

**Acceptance**: All rule files reference correct paths. No stale references to `src/pact/governance/`.

---

## M1: Work Management DataFlow Models (Session 2, parallel with M2/M3)

### 1001 — DataFlow initialization + model base [S]

Create `src/pact_platform/models/__init__.py` with DataFlow initialization. `DATABASE_URL` from env, SQLite default. Connection pool per `rules/dataflow-pool.md`.

**Acceptance**: `from pact_platform.models import db` works. DataFlow connects to SQLite by default.

### 1002 — Model: AgenticObjective [S]

Top-level work unit. Fields: id, org_address, title, description, submitted_by, status, priority, budget_usd (NaN-guarded), deadline, parent_objective_id, metadata, timestamps.

**Acceptance**: CRUD nodes generated. Unit test: create, read, list, filter by status, NaN rejected on budget.

### 1003 — Model: AgenticRequest [S]

Decomposed task. Fields: id, objective_id, title, description, assigned_to, assigned_type, claimed_by, status, priority, sequence_order, depends_on (JSON), envelope_id, deadline, metadata, timestamps.

**Acceptance**: CRUD + filter by objective_id, status, assigned_to.

### 1004 — Model: AgenticWorkSession [S]

Active work period with cost tracking. Fields: id, request_id, worker_address, status, timestamps, input_tokens, output_tokens, cost_usd (NaN-guarded), provider, model_name, tool_calls, verification_verdicts (JSON).

**Acceptance**: CRUD + filter by request_id, worker_address. Cost aggregation query works.

### 1005 — Model: AgenticArtifact [S]

Produced deliverable. Fields: id, request_id, session_id, artifact_type, title, content_ref, content_hash (SHA-256), version, parent_artifact_id, created_by, status, timestamps.

**Acceptance**: CRUD + version chain query via parent_artifact_id.

### 1006 — Model: AgenticDecision [M]

Human judgment point. Created when governance returns HELD. Fields: id, request_id, session_id, agent_address, action, decision_type, status (pending/approved/rejected/expired), reason_held, constraint_dimension, constraint_details (JSON), urgency, decided_by, decided_at, decision_reason, created_at, expires_at, envelope_version (TOCTOU defense).

**Acceptance**: CRUD + pending decisions queue query. Expiry check. Envelope version validation.

### 1007 — Model: AgenticReviewDecision [S]

Review outcome. Fields: id, request_id, artifact_id, reviewer_address, review_type, verdict, findings_count, comments, timestamps.

**Acceptance**: CRUD + filter by request_id, verdict.

### 1008 — Model: AgenticFinding [S]

Issue from review. Fields: id, review_id, request_id, severity, category, title, description, remediation, status, resolved_by, resolved_at, timestamps.

**Acceptance**: CRUD + filter by review_id, severity, status.

### 1009 — Model: AgenticPool [S]

Agent/human group. Fields: id, org_id, name, description, pool_type, routing_strategy, max_concurrent, active_requests, status, timestamps.

**Acceptance**: CRUD + filter by org_id, status.

### 1010 — Model: AgenticPoolMembership [S]

Pool member link. Fields: id, pool_id, member_address, member_type, capabilities (JSON), max_concurrent, active_count, status, joined_at.

**Acceptance**: CRUD + filter by pool_id, member_address.

### 1011 — Model: Run [S]

Execution record. Fields: id, session_id, request_id, agent_address, run_type, status, timestamps, duration_ms, input_tokens, output_tokens, cost_usd (NaN-guarded), verification_level, error_message, metadata.

**Acceptance**: CRUD + filter by session_id, status, verification_level.

### 1012 — Model: ExecutionMetric [S]

Performance metrics. Fields: id, run_id, metric_type, agent_address, pool_id, org_id, value (NaN-guarded), unit, period_start, period_end, dimensions (JSON), created_at.

**Acceptance**: CRUD + time-series query by metric_type + agent_address.

---

## M2: Work Management API + Services (Session 2, parallel with M1/M3)

### 2001 — Service: RequestRouterService [M]

Routes requests to pools/agents. Calls `GovernanceEngine.verify_action()` before dispatch. BLOCKED → reject. HELD → create AgenticDecision. AUTO_APPROVED/FLAGGED → assign to pool.

**Acceptance**: Unit test: route request, governance blocks, governance holds, assignment succeeds.

### 2002 — Service: ApprovalQueueService (DataFlow-backed) [M]

Replaces in-memory ApprovalQueue. Bridges AgenticDecision (DataFlow) with governance verdicts. Approve/reject/expire methods. Emits events via EventBus.

**Acceptance**: Submit for approval, approve, reject, expiry. Events emitted.

### 2003 — Service: CompletionWorkflowService [M]

Manages: session completion → artifact creation → review assignment → quality gate. State machine: submitted → review → approved/revision_required/rejected.

**Acceptance**: Complete session, submit artifact, assign review, record findings, finalize verdict.

### 2004 — Service: CostTrackingService [M]

Aggregates costs from WorkSessions and Runs. Queries by objective, agent, pool, time period. Backs the cost reporting dashboard page.

**Acceptance**: Record run cost. Get cost report by objective. Budget check for objective.

### 2005 — Service: NotificationDispatchService [S]

Subscribes to EventBus. Dispatches to registered adapters (Slack, Discord, Teams — implemented in M6). Abstract NotificationAdapter protocol.

**Acceptance**: Register adapter, publish event, adapter receives it.

### 2006 — Router: Objectives (/api/v1/objectives) [M]

POST create, GET list (filter status/org), GET detail, PUT update, POST cancel, GET requests, GET cost.

**Acceptance**: All 7 endpoints return valid responses. Auth required. Rate limited.

### 2007 — Router: Requests (/api/v1/requests) [M]

POST submit, GET list (filter status/pool/agent), GET detail, POST cancel, GET sessions, GET artifacts.

**Acceptance**: All 6 endpoints. Governance verification on submit.

### 2008 — Router: Sessions (/api/v1/sessions) [S]

GET list, GET detail, GET events, POST pause, POST resume.

**Acceptance**: All 5 endpoints.

### 2009 — Router: Decisions (/api/v1/decisions) [M]

GET list (filter urgency/type), GET detail, POST approve, POST reject, GET stats.

**Acceptance**: All 5 endpoints. Approve/reject update AgenticDecision status.

### 2010 — Router: Pools (/api/v1/pools) [S]

POST create, GET list, GET detail, POST add member, DELETE remove member, GET capacity.

**Acceptance**: All 6 endpoints.

### 2011 — Router: Reviews (/api/v1/reviews) [S]

GET list, GET detail, POST add finding, POST finalize.

**Acceptance**: All 4 endpoints.

### 2012 — Router: Metrics (/api/v1/platform/metrics) [S]

GET cost, GET throughput, GET governance verdicts, GET budget utilization.

**Acceptance**: All 4 endpoints return aggregated data.

### 2013 — Mount all routers on existing FastAPI server [S]

Mount 7 new routers on the existing server alongside the 9 existing governance endpoints. Use existing `verify_token` and `limiter` middleware.

**Acceptance**: All 42+ new endpoints accessible. Existing 9 governance endpoints still work.

---

## M3: Admin CLI (Session 2, parallel with M1/M2)

### 3001 — CLI group structure + `pact quickstart` [M]

Click group with `--store` and `--db` options. Implement `pact quickstart --example university` — loads university org, creates GovernanceEngine, starts FastAPI server.

**Acceptance**: `pact quickstart --example university` starts server. Evaluator can POST to governance endpoints.

### 3002 — `pact org create <yaml>` + `pact org list` [S]

Load org from YAML, compile with GovernanceEngine. List compiled orgs.

**Acceptance**: Create org from university.yaml. List shows it.

### 3003 — `pact role assign <address> <user>` [S]

Assign a user/agent to a D/T/R role address.

**Acceptance**: Assign succeeds. GovernanceEngine reflects the mapping.

### 3004 — `pact clearance grant <address> <level>` [S]

Grant knowledge clearance to a role. Validates level is one of PUBLIC/RESTRICTED/CONFIDENTIAL/SECRET/TOP_SECRET.

**Acceptance**: Grant succeeds. Clearance stored in governance stores.

### 3005 — `pact bridge create <role_a> <role_b>` [S]

Create cross-functional bridge between two roles.

**Acceptance**: Bridge created. Access enforcement reflects it.

### 3006 — `pact envelope show <address>` [S]

Show effective envelope for a role address. Pretty-print with Rich.

**Acceptance**: Shows all 5 dimensions with current values.

### 3007 — `pact agent register <agent_id> <role_address>` [S]

Register an agent in the platform. Links agent to role.

**Acceptance**: Agent registered. Shows in agent registry.

### 3008 — `pact audit export [--format json|csv]` [S]

Export governance audit trail. JSON or CSV output.

**Acceptance**: Exports audit records. Both formats work.

---

## M4: PactEngine Wiring + Auto-Seeding (Session 3)

Depends on kailash-py #63 (primitives move) and #64 (PactEngine built). If those aren't ready, build the platform-side wiring with the current kailash-pact v0.3.0 API and adapt when v0.4.0 lands.

### 4001 — PlatformEnvelopeAdapter [M]

Converts GovernanceEngine effective envelopes to GovernedSupervisor parameters. Handles:

- `financial=None` → budget=0.0 (NOT $1 default) — RT-R01
- `confidentiality_clearance` → `data_clearance` string mapping
- `max_delegation_depth` + `expires_at` → documented limitation
- NaN/Inf validation on ALL numeric values during conversion

**Acceptance**: Unit tests for every edge case. Property test: adapted envelope never widens the original.

### 4002 — DelegateProtocol + GovernedDelegate [M]

DelegateProtocol: abstract interface for agent execution. GovernedDelegate: execute_node callback that:

1. Resolves D/T/R address from AgentSpec
2. Calls GovernanceEngine.verify_action() for clearance/bridge checks
3. BLOCKED → raise GovernanceBlockedError
4. HELD → create AgenticDecision, raise GovernanceHeldError
5. AUTO_APPROVED/FLAGGED → invoke LLM, return result + cost

**Acceptance**: Unit tests for BLOCKED (LLM never called), HELD (decision created), APPROVED (LLM called).

### 4003 — PlanEvent → WebSocket bridge [S]

Maps GovernedSupervisor PlanEvents to PlatformEvents. Publishes through existing EventBus for real-time dashboard.

**Acceptance**: PlanEvents appear on WebSocket. Dashboard receives them.

### 4004 — HELD verdict → AgenticDecision → Approval queue bridge [M]

When GovernedSupervisor's BudgetTracker triggers HELD, or when execute_node callback encounters GovernanceEngine HELD: create AgenticDecision in DataFlow, emit event, appear in approval queue UI.

After human approves: resume execution (retry node or mark failed).

**Acceptance**: Budget HELD creates decision. Governance HELD creates decision. Approve → resumes. Reject → fails.

### 4005 — Supervisor orchestrator: execute_request() [M]

The end-to-end function: receive request → adapt envelope → create GovernedSupervisor → create GovernedDelegate → run → record Run in DataFlow → bridge events → return results.

**Acceptance**: Submit objective → request created → session started → supervisor runs → artifacts recorded → cost tracked.

### 4006 — Auto-seeding module [M]

On first boot (no data exists): load university org, register 3 demo agents (researcher, administrator, librarian), submit 2 sample objectives, decompose into 5 requests, leave 1 action HELD for the evaluator, populate audit trail with 5 anchors, record sample costs.

**Acceptance**: `docker compose up` on fresh install → dashboard shows real data. Approval queue has 1 pending decision.

### 4007 — Governance integration tests [M]

Red team mandated. Tests that verify the Dual Plane bridge:

- BLOCKED verdict prevents LLM execution
- HELD verdict creates AgenticDecision
- Approve resumes execution
- Reject fails the request
- Cross-boundary access without bridge → BLOCKED
- NaN in envelope → adapter rejects
- Budget exhaustion → HELD

**Acceptance**: All 7 integration tests pass.

---

## M5: Frontend Updates (Session 4, parallel with M6)

### 5001 — Web: Objectives management page [M]

`apps/web/app/objectives/page.tsx` — Create, list, filter, detail view. Shows decomposed requests, cost summary, timeline.

**Acceptance**: Page renders with seeded data. Create objective works. Status transitions visible.

### 5002 — Web: Request queue page [M]

`apps/web/app/requests/page.tsx` — List requests, filter by status/pool/agent. Claim, review, submit actions. Shows governance verdict on each request.

**Acceptance**: Page renders. Request status updates in real-time via WebSocket.

### 5003 — Web: Pool management page [S]

`apps/web/app/pools/page.tsx` — Create pools, add/remove members, view capacity.

**Acceptance**: Page renders. CRUD operations work.

### 5004 — Web: Interactive org builder page [M]

`apps/web/app/org-builder/page.tsx` — Visual D/T/R tree creation. Drag-and-drop departments, teams, roles. YAML export. Compile and validate.

**Acceptance**: Build university org visually. Export YAML. YAML validates via `pact org create`.

### 5005 — Mobile: Objective tracking screen [S]

`apps/mobile/lib/features/objectives/` — List objectives, view detail, track progress.

**Acceptance**: Screen renders with seeded data.

### 5006 — Mobile: Request claiming/review screen [S]

`apps/mobile/lib/features/requests/` — View assigned requests, claim from pool, submit review.

**Acceptance**: Screen renders. Claim action works.

### 5007 — Mobile: Pool management screen [S]

`apps/mobile/lib/features/pools/` — View pools, manage membership.

**Acceptance**: Screen renders.

---

## M6: Integration Layer (Session 4, parallel with M5)

### 6001 — NotificationAdapter protocol + base class [S]

Abstract base for webhook adapters. Shared: signature verification, retry logic, payload formatting, rate limiting.

**Acceptance**: Protocol defined. Base class with retry and rate limiting.

### 6002 — Slack webhook adapter [M]

Sends governance events (HELD actions, BLOCKED actions, completion notifications) to Slack channels via incoming webhooks.

**Acceptance**: HELD action → Slack message. Configurable channel per event type.

### 6003 — Discord webhook adapter [S]

Same as Slack but for Discord webhook format.

**Acceptance**: Events delivered to Discord.

### 6004 — Teams webhook adapter [S]

Same pattern for Microsoft Teams.

**Acceptance**: Events delivered to Teams.

### 6005 — LLM provider management [M]

BYO API keys via `.env`. Provider selection per agent/role. Support OpenAI + Anthropic. Cost tracking per provider with 2026 pricing.

**Acceptance**: Configure provider in .env. Agent uses configured provider. Costs tracked accurately.

---

## M7: Red Team + Hardening (Session 5)

### 7001 — Security red team: full platform [L]

Red team all new code (DataFlow models, API routers, services, CLI, GovernedSupervisor wiring, webhooks). Focus on:

- DataFlow SQL injection surface
- GovernedSupervisor self-modification via execute_node
- Webhook SSRF
- Approval queue bypass (approve without authority)
- Pool flooding (create unlimited pools/members)
- CLI injection via YAML/arguments
- NaN/Inf on all numeric DataFlow fields

**Acceptance**: All findings fixed. Convergence round shows 0 actionable findings.

### 7002 — CLAUDE.md complete rewrite [M]

Rewrite for pact-platform identity. L1/L2/L3 stack. PactEngine architecture. Updated import patterns. Milestone index. Security knowledge locations.

**Acceptance**: CLAUDE.md accurately describes the platform as built.

### 7003 — README.md rewrite [M]

User-facing documentation. Quick start (`pact quickstart --example university`), architecture diagram, dependency installation, Docker deployment, CLI reference.

**Acceptance**: New user can follow README to a running platform.

### 7004 — Final test suite validation [M]

Run full test suite. Verify coverage. Document total test count and coverage percentage. Ensure governance tests validate kailash-pact, platform tests validate pact_platform.

**Acceptance**: All tests pass. Coverage documented.

### 7005 — Docker deployment validation [S]

`docker compose up` from clean state. Verify: API server starts, dashboard loads, auto-seeding runs, approval queue shows HELD action, WebSocket events stream.

**Acceptance**: 5-minute demo flow works in Docker.

---

## Summary

| Milestone                | Todos  | Session        | Depends On |
| ------------------------ | ------ | -------------- | ---------- |
| M0: Rename & Cleanup     | 15     | 1              | —          |
| M1: DataFlow Models      | 12     | 2              | M0         |
| M2: API + Services       | 13     | 2              | M0         |
| M3: Admin CLI            | 8      | 2              | M0         |
| M4: PactEngine Wiring    | 7      | 3              | M1, M2, M3 |
| M5: Frontend             | 7      | 4              | M4         |
| M6: Integration          | 5      | 4              | M4         |
| M7: Red Team + Hardening | 5      | 5              | All        |
| **Total**                | **72** | **5 sessions** |            |
