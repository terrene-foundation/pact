# PACT Platform — Red-Teamed Analysis Synthesis

**Date**: 2026-03-24
**Round**: Final (red-teamed)
**Inputs**: #34 deep analysis, #35 requirements, #36 COC, #37 framework design, #38 value audit, #39 red team findings
**Status**: Ready for /todos

---

## What We're Building

PACT is the **human judgment surface** for governed AI operations. Operators define orgs, configure envelopes, assign clearances. Agents do work under governance. Humans approve held actions, review artifacts, manage costs. The platform sits on kailash-pact (governance primitives, L1) and kaizen-agents (autonomous core, L2).

All upstream packages are production-ready. The pyproject.toml is updated. The namespace is `pact_platform`. The build is 7 milestones, ~60 todos, 3-5 autonomous sessions.

---

## Red Team Findings That Change the Plan

The red team found 14 findings. Three are critical and reshape the architecture:

### RT-R01: Three-Way Envelope Mismatch (CRITICAL)

Not two envelope types — **three**:

1. `ConstraintEnvelopeConfig` (kailash-pact, Pydantic, `financial: Optional[FinancialConstraintConfig]`)
2. `ConstraintEnvelope` (kaizen-agents, frozen dataclass, `financial: dict = {"limit": 1.0}`)
3. `ConstraintEnvelope` (local trust layer, Pydantic, different field structure)

**Dangerous semantics**: kailash-pact's `financial=None` means "no financial capability." kaizen-agents' default `{"limit": 1.0}` means "$1 budget." Converting `None` → `{"limit": 1.0}` silently assigns a $1 budget to agents that should have none. Converting `None` → `{}` removes budget tracking entirely. Both are wrong.

**Impact on M4**: The PlatformEnvelopeAdapter must handle `None` semantics explicitly. Needs dedicated edge-case tests. Fields `max_delegation_depth` and `expires_at` exist in kailash-pact but not kaizen-agents — they are silently dropped. This must be documented as a known limitation or bridged.

### RT-R02: Dual Governance Systems (CRITICAL)

GovernedSupervisor has its **own complete governance stack** (BudgetTracker, ClearanceEnforcer, AccountabilityTracker, etc.) that operates **independently** from GovernanceEngine. They are parallel systems with no bridge.

**The HELD problem**: GovernedSupervisor handles HELD only for budget exhaustion. There is NO mechanism for external HELD verdicts (from GovernanceEngine) to pause execution and wait for human approval. The `execute_node` callback is a plain async function — it can raise (fail) or return (succeed), but cannot pause.

**Decision required**: Which governance system is authoritative?

- **Option A**: GovernanceEngine is authoritative. GovernedSupervisor's internal governance is disabled (pass `budget_usd=float('inf')`, `data_clearance="top_secret"`). All governance decisions go through GovernanceEngine via the execute_node callback. HELD verdicts raise an exception; the platform catches it, creates an AgenticDecision, and retries the node after approval.
- **Option B**: Both systems active. GovernedSupervisor handles budget/cascade internally; GovernanceEngine handles envelope/clearance/access externally. Reconciliation layer merges verdicts (strictest wins).
- **Option C**: GovernedSupervisor is authoritative for runtime execution. GovernanceEngine is authoritative for policy definition. The adapter converts GovernanceEngine policy into GovernedSupervisor parameters at session start — then GovernedSupervisor enforces autonomously.

**Recommendation**: Option C. GovernanceEngine defines the policy (envelopes, clearances, bridges). The adapter converts policy to GovernedSupervisor parameters at session creation. GovernedSupervisor enforces at runtime. HELD verdicts from GovernedSupervisor's BudgetTracker flow to the platform's approval queue. The execute_node callback adds a governance pre-check for actions not covered by GovernedSupervisor's internal subsystems (e.g., knowledge clearance, cross-boundary access).

### RT-R03: Auto-Seeding Missing From Requirements (HIGH)

The value audit says auto-seeding is essential. The requirements have zero todos for it. Empty dashboard on first boot is the #1 evaluator experience risk.

**Fix**: Add auto-seeding to M4. On first boot: load university org, register demo agents, submit sample objectives, create sample requests, leave one action HELD for the evaluator, populate audit trail with ~5 anchors.

### RT-R04: Docker/Scripts Reference Old Paths (HIGH)

`run_seeded_server.py`, `seed_demo.py`, Dockerfile CMD, docker-compose env vars (`CARE_*`), frontend class names (`CareApiClient`), network name (`care_net`) — all need updating in M0. The requirements partially cover this but miss several files.

### RT-R05: 153 Test Errors Never Diagnosed (HIGH)

Nobody ran `pytest --collect-only` to categorize the errors. M0 cannot be confident without root cause analysis first.

---

## Corrected Architecture Decision: Governance Integration (Option C)

```
GovernanceEngine (kailash-pact)          GovernedSupervisor (kaizen-agents)
  Defines policy:                          Enforces at runtime:
  - D/T/R envelopes                        - BudgetTracker (financial)
  - Knowledge clearance                    - ClearanceEnforcer (data access)
  - Access enforcement                     - AccountabilityTracker (operational)
  - Verification gradient                  - CascadeManager (delegation)
  - Bridges + KSPs                         - DerelictionDetector (liveness)
         |                                        ^
         |  PlatformEnvelopeAdapter               |
         |  (converts policy → parameters)        |
         v                                        |
  GovernedSupervisor.__init__(                    |
    budget_usd=envelope.financial.max_spend,      |
    tools=envelope.operational.allowed,           |
    data_clearance=clearance.level.value,         |
  )                                               |
         |                                        |
         |  execute_node callback                 |
         |  (adds pre-check for clearance,        |
         |   cross-boundary access, bridges)      |
         v                                        |
  LLM execution ←── GovernedSupervisor.run()  ──→ PlanEvents → WebSocket
                                                   Budget HELD → AgenticDecision → Approval UI
```

**Policy flows down** (GovernanceEngine → GovernedSupervisor parameters).
**Enforcement happens inside** GovernedSupervisor at runtime.
**The execute_node callback** adds governance checks that GovernedSupervisor doesn't cover (knowledge clearance, cross-boundary bridges).
**HELD verdicts** from GovernedSupervisor's own budget tracking flow to the approval queue.

This avoids the reconciliation nightmare of two active governance systems.

---

## Corrected Milestones

### M0: Platform Rename & Cleanup (1 session)

- Rename src/pact/ → src/pact_platform/
- Delete governance/ (30 files, now from kailash-pact)
- Triage trust/ (delete ~22 superseded, keep ~36)
- Delete build/verticals/ (5 dead shims)
- Bulk rewrite ~1,500 imports
- Fix scripts (run_seeded_server.py, seed_demo.py, shadow_calibrate.py)
- Fix Docker (Dockerfile CMD, docker-compose env vars CARE*→PACT*, network name)
- Fix frontend class names (CareApiClient → PactApiClient)
- **NEW**: Diagnose all 153 test collection errors FIRST (before rename)
- **NEW**: Catalog 3 at-risk security patterns before deleting trust files
- Fix all test collection errors
- Quality gate: `pytest --collect-only` = 0 errors

### M1: Work Management Models (1 session, parallel with M2/M3)

- 11 DataFlow models with NaN/Inf guards on ALL numeric fields
- Alembic migration infrastructure
- Quality gate: all 11 models CRUD-testable

### M2: Work Management API + Services (1 session, parallel with M1/M3)

- 7 FastAPI routers (40+ endpoints)
- 5 services (request routing, approval queue, completion workflow, cost tracking, notification)
- Quality gate: all endpoints return valid responses

### M3: Admin CLI (1 session, parallel with M1/M2)

- 8 Click commands
- `pact quickstart --example university` (loads org, starts API)
- Quality gate: all commands execute successfully

### M4: GovernedSupervisor Wiring (1 session)

- PlatformEnvelopeAdapter with three-way type handling
  - `financial=None` → explicit "no budget" semantics (not $1 default)
  - `confidentiality_clearance` → `data_access.ceiling` mapping
  - `max_delegation_depth` + `expires_at` → documented limitation
  - NaN/Inf validation on ALL dict field numeric values
- DelegateProtocol interface
- GovernedDelegate (execute_node callback with governance pre-check)
- PlanEvent → WebSocket bridge
- HELD verdict → AgenticDecision → Approval queue bridge
- **NEW**: Auto-seeding module (university org, demo agents, sample objectives, one HELD action)
- **NEW**: Governance integration tests (BLOCKED prevents LLM, HELD creates decision)
- Quality gate: 5-minute demo flow works end-to-end

### M5: Frontend Updates (parallel with M6)

- 4 new web pages (objectives, requests, pools, org builder)
- 3 new mobile screens
- Quality gate: all pages render with seeded data

### M6: Integration Layer (parallel with M5)

- 3 webhook adapters (Slack, Discord, Teams)
- Notification service
- LLM provider management
- Quality gate: webhook delivery verified

---

## Execution Plan (Autonomous Sessions)

```
Session 1: M0 (rename + cleanup + test diagnosis)
Session 2: M1 + M2 + M3 (parallel streams)
Session 3: M4 (GovernedSupervisor wiring + auto-seeding)
Session 4: M5 + M6 (frontend + integration, parallel)
Session 5: Red team + hardening + CLAUDE.md rewrite
```

5 autonomous sessions. No human-time estimates. No scoping down.

---

## Remaining Risks After Red Team

| Risk                                 | Severity | Mitigation                                                      |
| ------------------------------------ | -------- | --------------------------------------------------------------- |
| Three-way envelope mismatch          | CRITICAL | Adapter with explicit None semantics + edge case tests          |
| Dual governance reconciliation       | CRITICAL | Option C: policy down, enforcement inside, callback adds checks |
| Auto-seeding missing                 | HIGH     | Added to M4                                                     |
| Docker/scripts old paths             | HIGH     | Expanded M0 scope                                               |
| 153 test errors undiagnosed          | HIGH     | Root cause analysis first in M0                                 |
| 3 security patterns at risk          | HIGH     | Catalog before deleting trust files                             |
| kaizen-agents v0.1.0 API instability | MEDIUM   | DelegateProtocol as anti-corruption layer                       |
| Frontend CARE→PACT naming            | MEDIUM   | Added to M0                                                     |

---

## Analysis Documents Produced

| #      | Title                             | Focus                                        |
| ------ | --------------------------------- | -------------------------------------------- |
| 18-24  | Repivot + Boundary Analysis       | First round (superseded by corrections)      |
| 25-29  | Delegate Integration (first pass) | Initial analysis with incorrect Aegis data   |
| 30-33  | Final Analysis (corrected data)   | Updated with Aegis RT2 corrections           |
| 34     | RT Deep Analysis                  | Full failure analysis, M0-M6                 |
| 35     | RT Requirements                   | 55 todos, acceptance criteria                |
| 36     | RT COC Analysis                   | Anti-amnesia, convention drift, security     |
| 37     | RT Framework Design               | DataFlow models, services, API, adapter code |
| 38     | RT Value Audit                    | Full platform evaluation, user journeys      |
| 39     | RT Red Team Findings              | 14 findings (2 CRITICAL, 3 HIGH)             |
| **40** | **This synthesis**                | **Final, red-teamed, ready for /todos**      |
