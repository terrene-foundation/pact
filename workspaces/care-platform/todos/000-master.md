# CARE Platform — Master Roadmap

**Created**: 2026-03-11
**Last Updated**: 2026-03-14
**Status**: Phase 1 COMPLETE (M1-M12, 96 tasks). Phase 2 COMPLETE (M13-M20, 54 tasks). Phase 3 ACTIVE (M21-M30, 57 tasks). Phase 4 ACTIVE (M31-M36, 27 tasks). Total: 234 tasks.

---

## Overview

Build the CARE Platform (Apache 2.0) — a governed operational model for running organizations with AI agents under EATP trust governance. Phase 1 closed the 5 architecture gaps. Phase 2 aligns with updated standards (EATP v2.2, CARE formal specs, Constrained Organization thesis), restructures the project, adds a frontend dashboard, and validates the platform IS a Constrained Organization.

**Phase 1**: 96 tasks across 12 milestones — COMPLETE
**Phase 2**: 54 tasks across 8 milestones (M13-M20) — ACTIVE

### Phase 2 Dependency Graph

```
M13 (Restructure) ──────────────────────────────┐
  |                                               |
  +─── M14 (Lifecycle State Machines)             |
  |                                               |
  +─── M15 (EATP v2.2 Alignment)                 |
  |                                               |
  +─── M16 (Gap Closure: Runtime Enforcement)     |
  |       |                                       |
  |       +─── M17 (Gap Closure: Integrity)       |
  |               |                               |
  |               +─── M19 (Constrained Org       |
  |                     Validation)               |
  |                                               |
  +─── M18 (Frontend Scaffold & API) ────────────+
          |
          +─── M20 (Frontend Dashboard Views)

(M14, M15, M16 can run in parallel after M13)
```

---

## Milestones

### Milestone 1: Project Foundation and Core Models (Phase 1) — COMPLETE

Package the COC setup pattern as a reusable Python framework. Define data models for all EATP trust chain elements, constraint envelopes, verification gradient, trust postures, agent definitions, workspace structure, and audit anchors.

**Todos**: 101-113 (13 tasks)
**Status**: COMPLETE — all 13 todos in completed/
**Dependencies**: None (foundation layer)
**Delivers**: Installable `care-platform` package with all core data models, configuration schema, CLI entry point, and test suite

| #   | Task                                                        | Priority | Effort |
| --- | ----------------------------------------------------------- | -------- | ------ |
| 101 | CI/CD Pipeline Setup                                        | High     | Small  |
| 102 | Platform Configuration Schema                               | High     | Medium |
| 103 | Constraint Envelope Data Model                              | High     | Medium |
| 104 | Verification Gradient Engine                                | High     | Medium |
| 105 | Trust Posture Model (5 levels, incl. Pseudo-Agent)          | High     | Medium |
| 106 | Capability Attestation Model (EATP Element 4)               | High     | Medium |
| 107 | Trust Scoring Model (5-factor weighted)                     | Medium   | Small  |
| 108 | Agent Definition Model                                      | High     | Medium |
| 109 | Workspace-as-Knowledge-Base Model                           | High     | Medium |
| 110 | Audit Anchor Model (tamper-evident)                         | High     | Medium |
| 111 | Core Models Comprehensive Unit Tests                        | High     | Medium |
| 112 | Create Example Configuration (Foundation as First Deployer) | Medium   | Small  |
| 113 | Package as Installable Python Module with CLI               | High     | Small  |

---

### Milestone 2: EATP Trust Integration (Phase 2) — COMPLETE

Integrate EATP SDK for cryptographic trust — genesis records, delegation chains, signed constraint envelopes, audit pipeline, credential lifecycle, cascade revocation, ShadowEnforcer, and reasoning traces.

**Todos**: 201-212 (12 tasks)
**Status**: COMPLETE — all 12 todos in completed/
**Dependencies**: Milestone 1 (core models), EATP SDK
**Delivers**: Cryptographic trust enforcement — every agent action traceable to human authority
**CRITICAL PATH**: 201 (EATP SDK operations) blocks all trust features

| #   | Task                                                                         | Priority | Effort |
| --- | ---------------------------------------------------------------------------- | -------- | ------ |
| 201 | EATP SDK Phase 2 — Extract Core Operations (ESTABLISH/DELEGATE/VERIFY/AUDIT) | Critical | Large  |
| 202 | Genesis Record Integration (root of all trust)                               | High     | Medium |
| 203 | Delegation Chain with Monotonic Tightening                                   | High     | Medium |
| 204 | Constraint Envelope Signing and Verification                                 | High     | Medium |
| 205 | Audit Anchor Integration into Action Pipeline                                | High     | Medium |
| 206 | Credential Lifecycle Management (5-min TTL, rotation, renewal)               | High     | Medium |
| 207 | Cascade Revocation (surgical and team-wide)                                  | High     | Medium |
| 208 | ShadowEnforcer Implementation                                                | Medium   | Medium |
| 209 | Reasoning Traces — EATP v2.2                                                 | Medium   | Medium |
| 210 | Inter-Agent Messaging with Replay Protection                                 | Medium   | Medium |
| 211 | Milestone 2 Integration Tests — Full EATP Trust Flow                         | High     | Medium |
| 212 | Verification Middleware (QUICK/STANDARD/FULL levels at runtime)              | High     | Medium |

Note: If `201-eatp-sdk-integration-audit.md` or `203-delegation-chain-integration.md` exist in `active/`, they are supplementary research files, not canonical implementation todos.

---

### Milestone 3: Persistence Layer (Phase 2 continued) — COMPLETE

Connect trust models and platform state to DataFlow for structured, queryable, persistent storage. Audit anchor table is append-only. Posture history is append-only. Trust chains survive restarts.

**Todos**: 301-307 (7 tasks)
**Status**: COMPLETE — all 7 todos in completed/
**Dependencies**: Milestone 2 (trust objects to persist), DataFlow SDK
**Delivers**: Durable trust chains, queryable audit history, constraint envelope versioning, API cost tracking

| #   | Task                                                   | Priority | Effort | Status    |
| --- | ------------------------------------------------------ | -------- | ------ | --------- |
| 301 | DataFlow Schema Design for Trust Persistence           | Critical | Medium | COMPLETED |
| 302 | Trust Object Persistence Layer                         | High     | Medium | COMPLETED |
| 303 | Workspace and Agent Registry Persistence               | High     | Small  | COMPLETED |
| 304 | Audit History Query Interface                          | Medium   | Medium | COMPLETED |
| 305 | Persisted Posture History and Upgrade Workflow         | Medium   | Medium | COMPLETED |
| 306 | API Cost Tracking and Budget Controls (M-6 mitigation) | Medium   | Small  | COMPLETED |
| 307 | Milestone 3 Integration Tests — Full Persistence Stack | High     | Small  | COMPLETED |

---

### Milestone 4: Agent Execution Runtime (Phase 3) — COMPLETE

Bridge COC agent definitions to Kaizen multi-agent execution. Closes Gaps 1 (multi-user runtime), 3 (cryptographic enforcement at execution), and 4 (runtime independence). Includes human approval queue, session management, and Nexus API layer.

**Todos**: 401-409 (9 tasks)
**Status**: COMPLETE — all 9 todos in completed/
**Dependencies**: Milestones 1-3 (models, trust, persistence), Kaizen SDK, Nexus SDK
**Delivers**: Multi-agent runtime with trust enforcement at execution time; REST API and MCP interfaces

| #   | Task                                               | Priority | Effort | Status    |
| --- | -------------------------------------------------- | -------- | ------ | --------- |
| 401 | Kaizen Agent Bridge — COC to Kaizen Execution      | Critical | Large  | COMPLETED |
| 402 | Multi-LLM Backend Abstraction                      | High     | Medium | COMPLETED |
| 403 | Human-in-the-Loop Approval System                  | High     | Medium | COMPLETED |
| 404 | COC Hook System Integration                        | High     | Medium | COMPLETED |
| 405 | Session Management and Context Persistence         | Medium   | Medium | COMPLETED |
| 406 | Verification Performance Optimization              | Medium   | Medium | COMPLETED |
| 407 | Agent Registry and Discovery                       | Medium   | Small  | COMPLETED |
| 408 | Nexus API Layer — REST, CLI, MCP                   | Medium   | Medium | ACTIVE    |
| 409 | Milestone 4 Integration Tests — Full Runtime Stack | High     | Medium | ACTIVE    |

---

### Milestone 5: Cross-Functional Bridges (Phase 4) — COMPLETE

Implement workspace-to-workspace coordination via EATP cross-team delegation. Standing, Scoped, and Ad-Hoc bridge types. Closes Gap 5 (workspace coordination).

**Todos**: 501-506 (6 tasks)
**Status**: COMPLETE — all 6 todos in completed/
**Dependencies**: Milestone 4 (agent execution runtime)
**Delivers**: Agent teams can coordinate across workspace boundaries with full trust verification and provenance

| #   | Task                                                     | Priority | Effort | Status    |
| --- | -------------------------------------------------------- | -------- | ------ | --------- |
| 501 | Cross-Functional Bridge Data Model                       | High     | Medium | COMPLETED |
| 502 | Bridge Request and Approval Workflow                     | High     | Medium | COMPLETED |
| 503 | Bridge Messaging — Signed Inter-Team Communication       | High     | Medium | COMPLETED |
| 504 | Knowledge Bridge Integration                             | Medium   | Medium | ACTIVE    |
| 505 | Cross-Team Coordinator Agent Definition                  | Medium   | Small  | ACTIVE    |
| 506 | Milestone 5 Integration Tests — Cross-Functional Bridges | High     | Small  | ACTIVE    |

---

### Milestone 6: DM Team Vertical (First Full-Service Team)

Define, establish, calibrate, test, and launch the Digital Marketing team as the first operational vertical. 8 agents (6 specialist, 2 universal) under EATP trust governance, with complete constraint envelopes, gradient rules, posture evolution plan, and safety validation.

**Todos**: 601-610 (10 tasks)
**Status**: COMPLETE — all 10 todos in completed/
**Dependencies**: Milestones 1-2 required; Milestones 3-5 needed before live operation; can start agent definitions (601) in parallel with M1
**Delivers**: First fully-governed agent team; reference implementation demonstrating CARE in practice

| #   | Task                                                      | Priority | Effort | Status    |
| --- | --------------------------------------------------------- | -------- | ------ | --------- |
| 601 | DM Team Agent Definitions (5 agents)                      | High     | Medium | COMPLETED |
| 602 | DM Team Specialist Agents with Constraint Envelopes       | High     | Medium | COMPLETED |
| 603 | DM Team Verification Gradient Rules Configuration         | High     | Medium | COMPLETED |
| 604 | DM Team Trust Posture Evolution Plan                      | Medium   | Small  | ACTIVE    |
| 605 | DM Team Workspace Setup                                   | Medium   | Small  | ACTIVE    |
| 606 | Initial ShadowEnforcer Run and Calibration                | Medium   | Medium | ACTIVE    |
| 607 | Cascade Revocation Test and Crisis Protocol               | High     | Small  | ACTIVE    |
| 608 | Approval Load Analysis — H-4 Mitigation                   | High     | Small  | ACTIVE    |
| 609 | DM Team End-to-End Test — Content Creation to Publication | High     | Medium | ACTIVE    |
| 610 | DM Team Launch Readiness Review                           | High     | Small  | ACTIVE    |

---

### Milestone 7: Organization Builder (Phase 5)

Auto-generate agent teams, constraint envelopes, workspace structures, and delegation chains from organizational definitions. Template library for common team types. The Foundation's complete org definition generated and validated.

**Todos**: 701-706 (6 tasks)
**Status**: COMPLETE — all 6 todos in completed/
**Dependencies**: Milestones 1-5
**Delivers**: Any organization can define its structure in YAML and auto-generate a fully governed CARE Platform

| #   | Task                                               | Priority | Effort | Status    |
| --- | -------------------------------------------------- | -------- | ------ | --------- |
| 701 | Organization Definition Schema                     | Medium   | Medium | COMPLETED |
| 702 | Auto-Generate Agent Definitions from Org Structure | Medium   | Medium | COMPLETED |
| 703 | Organization Builder Integration Tests             | Medium   | Small  | COMPLETED |
| 704 | Constraint Envelope Template Library               | Medium   | Medium | ACTIVE    |
| 705 | Organization Builder CLI Commands                  | Medium   | Small  | ACTIVE    |
| 706 | Terrene Foundation Full Organization Validation    | Medium   | Medium | ACTIVE    |

---

### Milestone 8: Documentation and Developer Experience

README, architecture docs, trust model docs, constraint envelope guide, getting-started tutorial, contributor guide, API documentation, security policy, examples, and documentation validation.

**Todos**: 801-808 (8 tasks)
**Status**: COMPLETE — all 8 todos in completed/
**Dependencies**: M1 minimum; evolves with each milestone; 808 (validation) depends on all docs being written
**Delivers**: New developers can understand, install, configure, and contribute to the platform

| #   | Task                                          | Priority | Effort |
| --- | --------------------------------------------- | -------- | ------ |
| 801 | CARE Platform README                          | High     | Medium |
| 802 | Architecture Documentation                    | Medium   | Medium |
| 803 | Contributor Guide                             | Medium   | Small  |
| 804 | API Documentation                             | Medium   | Medium |
| 805 | Getting Started Guide (step-by-step tutorial) | Medium   | Medium |
| 806 | Security Policy and Vulnerability Disclosure  | Medium   | Small  |
| 807 | Examples and Cookbook                         | Low      | Medium |
| 808 | Documentation Validation                      | Medium   | Small  |

---

### Milestone 9: Cross-Reference Updates (Terrene Knowledge Base)

Update Foundation anchor documents and rules to reflect the CARE Platform layer. Address red team finding C-2 (make CARE technical blueprint implementation-neutral). Update naming rules with CARE Platform terminology.

**Todos**: 901-905 (5 tasks)
**Status**: COMPLETE — all 5 todos in completed/
**Dependencies**: M1 (platform exists to reference)
**Delivers**: Consistent, accurate cross-references across all Foundation documentation

| #   | Task                                                       | Priority | Effort |
| --- | ---------------------------------------------------------- | -------- | ------ |
| 901 | Update Core Entities anchor document                       | Medium   | Small  |
| 902 | Update IP Ownership anchor document                        | Medium   | Small  |
| 903 | Update Value Model anchor document                         | Medium   | Small  |
| 904 | Make CARE Technical Blueprint Implementation-Neutral (C-2) | High     | Medium |
| 905 | Update Terrene Naming Rules — CARE Platform Terminology    | Medium   | Small  |

---

### Milestone 10: Red Team Findings and Risk Mitigation

Address all findings from the analysis red team. Most findings are addressed within other milestones; this milestone documents the mitigation strategy, monitors implementation, and handles findings that are primarily research/documentation tasks.

**Todos**: 1001-1007 (7 tasks)
**Status**: COMPLETE — all 7 todos in completed/
**Dependencies**: Various (noted per todo)
**Delivers**: All identified risks mitigated or tracked with concrete plans

| #    | Task                                           | Priority | Finding |
| ---- | ---------------------------------------------- | -------- | ------- |
| 1001 | Qualify "Nascent CARE Platform" Claims         | Medium   | H-1     |
| 1002 | Competitive Window Assessment                  | Medium   | H-2     |
| 1003 | Define ShadowEnforcer in CARE Platform Context | Medium   | H-3     |
| 1004 | Model Solo Founder Approval Bottleneck         | Medium   | H-4     |
| 1005 | Third-Party Implementation Governance          | Medium   | H-5     |
| 1006 | API Cost Risk Modeling                         | Medium   | M-6     |
| 1007 | EATP Interoperability Token Exchange (Future)  | Low      | —       |

Note: Several red team findings are addressed within implementation milestones:

- H-4 (approval bottleneck): primarily addressed in 403, 608
- M-6 (API cost risk): primarily addressed in 306, 608
- H-3 (ShadowEnforcer undefined): primarily addressed in 208, 606
- C-2 (blueprint neutrality): addressed in 904

---

### Milestone 11: RT3 Red Team Hardening (Production Readiness) — COMPLETE

Fixes all code-level findings from Round 3 red teaming. Pipeline parity enforcement, test coverage gaps, type safety, traceability, and code cleanup.

**Todos**: 1101-1107 (7 tasks)
**Status**: COMPLETE — all 7 todos in completed/
**Dependencies**: Milestones 1-10
**Delivers**: HookEnforcer and ShadowEnforcer at full pipeline parity with middleware; 16 new tests; complete RT comment traceability; no deprecated patterns

| #    | Task                                                          | Priority | Effort | Source            |
| ---- | ------------------------------------------------------------- | -------- | ------ | ----------------- |
| 1101 | HookEnforcer Pipeline Parity (expiry + kwargs forwarding)     | Critical | Small  | R3-01/10          |
| 1102 | ShadowEnforcer Envelope Expiry Check                          | High     | Small  | R3-01             |
| 1103 | Missing RT2 Test Coverage (RT2-16, RT2-19, RT2-21)            | High     | Small  | R3-04             |
| 1104 | Log Swallowed Exception in get_trust_chain()                  | High     | Tiny   | R3-11             |
| 1105 | RT Comment Traceability (RT2-04, RT2-20, RT-30)               | Medium   | Tiny   | R3-05/12          |
| 1106 | Type Annotations and Docstring Accuracy                       | Medium   | Small  | R3-02/06/07       |
| 1107 | Code Cleanup (unused imports, asyncio, defense-in-depth docs) | Low      | Tiny   | R3-08/09/13/14/16 |

### Milestone 12: Production Architecture Modules (RT3 Gaps) — COMPLETE

Six new modules identified by RT3 red team as missing for production readiness. Persistent trust store, workspace discovery from disk, bootstrap initialization flow, cryptographic approver authentication, agent execution runtime, and asymmetric audit signing.

**Todos**: 1201-1206 (6 tasks)
**Status**: COMPLETE — all 6 todos in completed/
**Dependencies**: M11 (RT3 hardening)
**Delivers**: SQLiteTrustStore, WorkspaceDiscovery, PlatformBootstrap, ApproverAuth (Ed25519), ExecutionRuntime, Ed25519 audit anchor signing

| #    | Task                               | Priority | Effort | Source |
| ---- | ---------------------------------- | -------- | ------ | ------ |
| 1201 | SQLite-backed TrustStore           | Critical | Medium | RT3-D  |
| 1202 | Workspace Discovery (disk scan)    | High     | Small  | RT3-D  |
| 1203 | Bootstrap and Initialization Flow  | Critical | Medium | RT3-D  |
| 1204 | Approver Authentication (Ed25519)  | High     | Medium | RT3-E  |
| 1205 | Agent Execution Runtime            | Critical | Large  | RT3-B  |
| 1206 | Asymmetric Audit Signing (Ed25519) | Medium   | Small  | RT3-G  |

---

## Execution Order

```
Sprint 1 — Foundation (Milestones 1 + DM definitions + initial docs):
  M1: Core Models (101-112) ─────────────────────────────────→
  M6a: DM Agent Definitions (601) — parallel with M1         →
  M8a: README + Architecture Docs (801, 802) — start early   →
  M9: Cross-reference updates (901-905) — start with M1      →

Sprint 2 — Trust Layer (Milestone 2):
  M2: EATP Trust Integration (201-210) ──────────────────────→
  M10: Red Team Research (1001-1007) — ongoing alongside     →

Sprint 3 — Persistence (Milestone 3):
  M3: DataFlow Persistence (301-307) ────────────────────────→

Sprint 4 — Runtime (Milestone 4):
  M4: Kaizen Agent Execution (401-408 + 409 tests) ──────────→
  M6b: DM Team Trust Establishment (602-607) — M1+M2 ready  →

Sprint 5 — Bridges (Milestone 5):
  M5: Cross-Functional Bridges (501-506) ────────────────────→
  M6c: DM Team Final Validation (608-610) — all M's ready   →

Sprint 6 — Organization Builder (Milestone 7):
  M7: Organization Builder (701-706) ────────────────────────→

Ongoing throughout all sprints:
  M8: Documentation evolves with each milestone
  M10: Red team findings resolved as implementation progresses
```

---

## Red Team Coverage Map

| Finding                              | Severity | Primary Resolution      | Supporting Resolution                  |
| ------------------------------------ | -------- | ----------------------- | -------------------------------------- |
| C-2: Blueprint commercial references | Critical | 904 (rewrite blueprint) | 801 (README establishes CARE Platform) |
| H-1: "Nascent platform" overclaim    | High     | 1001 (qualify claims)   | —                                      |
| H-2: Competitive window              | High     | 1002 (assessment)       | 801, 802 (clear positioning)           |
| H-3: ShadowEnforcer undefined        | High     | 208 (implement)         | 606 (DM calibration), 1003 (docs)      |
| H-4: Approval bottleneck             | High     | 403 (approval system)   | 608 (load analysis), 1004 (model)      |
| H-5: Third-party governance          | High     | 1005 (research + plan)  | — (Phase 2 topic)                      |
| M-6: API cost risk                   | Medium   | 306 (cost tracking)     | 608 (DM budget), 1006 (model)          |

---

## Architecture Gaps Closure Map

| Gap                              | Closed By                                     | Milestone |
| -------------------------------- | --------------------------------------------- | --------- |
| Gap 1: Multi-user runtime        | 401 (Kaizen bridge) + 408 (Nexus API)         | M4        |
| Gap 2: Persistence               | 301-307 (DataFlow persistence)                | M3        |
| Gap 3: Cryptographic enforcement | 202-207 (EATP trust) + 404 (hook integration) | M2 + M4   |
| Gap 4: Runtime independence      | 402 (multi-LLM backends)                      | M4        |
| Gap 5: Workspace coordination    | 501-506 (Cross-Functional Bridges)            | M5        |

---

## EATP Trust Chain Elements Coverage

| EATP Element                      | Implementation Todo          | Milestone |
| --------------------------------- | ---------------------------- | --------- |
| Element 1: Genesis Record         | 202                          | M2        |
| Element 2: Delegation Record      | 203                          | M2        |
| Element 3: Constraint Envelope    | 103 (model) + 204 (signing)  | M1 + M2   |
| Element 4: Capability Attestation | 106 (model) + 202 (creation) | M1 + M2   |
| Element 5: Audit Anchor           | 110 (model) + 205 (pipeline) | M1 + M2   |

All five EATP Trust Lineage Chain elements are covered.

---

## Phase 2 Milestones (M13-M20)

### Milestone 13: Project Restructure (Work Stream A)

Move to `src/` layout, scaffold frontend directories, fix naming.

**Todos**: 1301-1307 (7 tasks)
**Status**: ACTIVE
**Dependencies**: None
**Delivers**: Modern Python project structure, frontend scaffolds, terminology fix

| #    | Task                                  | Priority | Effort |
| ---- | ------------------------------------- | -------- | ------ |
| 1301 | Move care_platform/ to src/           | Critical | Small  |
| 1302 | Update pyproject.toml for src/ layout | Critical | Small  |
| 1303 | Verify conftest.py                    | High     | Tiny   |
| 1304 | Verify all test imports               | Critical | Small  |
| 1305 | Scaffold apps/web/ (Next.js)          | Medium   | Small  |
| 1306 | Scaffold apps/mobile/ (Flutter)       | Low      | Tiny   |
| 1307 | Fix eatp-expert.md casing             | Medium   | Tiny   |

---

### Milestone 14: CARE Formal Specifications — Lifecycle State Machines

Implement three lifecycle state machines, constraint resolution, uncertainty classifier, and failure modes from CARE formal specs.

**Todos**: 1401-1407 (7 tasks)
**Status**: ACTIVE
**Dependencies**: M13
**Delivers**: Formal state machines for trust chains, bridges, workspaces; constraint resolution algorithm; uncertainty classification; failure mode detection

| #    | Task                                | Priority | Effort |
| ---- | ----------------------------------- | -------- | ------ |
| 1401 | Trust chain lifecycle state machine | High     | Medium |
| 1402 | Bridge lifecycle state machine      | High     | Medium |
| 1403 | Workspace lifecycle state machine   | High     | Small  |
| 1404 | Constraint resolution algorithm     | High     | Medium |
| 1405 | Uncertainty classifier (5 levels)   | Medium   | Medium |
| 1406 | Five failure modes                  | Medium   | Medium |
| 1407 | M14 tests                           | High     | Medium |

---

### Milestone 15: EATP v2.2 Alignment

Implement five new EATP v2.2 features: confidentiality levels, SD-JWT, REASONING_REQUIRED, JCS, dual-binding signing.

**Todos**: 1501-1506 (6 tasks)
**Status**: ACTIVE
**Dependencies**: M13 (1504 JCS needed before 1505 dual-binding)
**Delivers**: Full EATP v2.2 compliance — confidentiality-aware trust chains, selective disclosure, canonical serialization
**Risk**: HIGH — cryptographic changes (JCS, SD-JWT) may be 3-5x estimated effort

| #    | Task                                 | Priority | Effort |
| ---- | ------------------------------------ | -------- | ------ |
| 1501 | Confidentiality levels (first-class) | High     | Small  |
| 1502 | SD-JWT selective disclosure          | Medium   | Large  |
| 1503 | REASONING_REQUIRED constraint type   | High     | Medium |
| 1504 | JCS canonical serialization          | High     | Medium |
| 1505 | Dual-binding signing                 | Medium   | Medium |
| 1506 | M15 tests                            | High     | Medium |

---

### Milestone 16: Gap Closure — Runtime Enforcement (CRITICAL + HIGH)

Address CRITICAL codebase gaps: runtime constraint enforcement, capability attestation model, fail-closed behavior, deployment state persistence.

**Todos**: 1601-1605 (5 tasks)
**Status**: ACTIVE
**Dependencies**: M13
**Delivers**: Constraints enforced at runtime (not advisory), clean authorization model, fail-closed on store failure, persistent org state
**CRITICAL PATH**: 1601 (ConstraintEnforcer) blocks M17 and M19

| #    | Task                            | Priority | Effort |
| ---- | ------------------------------- | -------- | ------ |
| 1601 | ConstraintEnforcer in runtime   | Critical | Medium |
| 1602 | Capability attestation refactor | Critical | Medium |
| 1603 | Fail-closed behavior            | High     | Medium |
| 1604 | Deployment state persistence    | High     | Small  |
| 1605 | M16 tests                       | High     | Medium |

---

### Milestone 17: Gap Closure — Integrity & Resilience (HIGH + MEDIUM)

Hash-chain trust records, knowledge policy enforcement, verification caching, management/data plane isolation.

**Todos**: 1701-1705 (5 tasks)
**Status**: ACTIVE
**Dependencies**: M16
**Delivers**: Tamper-evident trust chains, enforced knowledge policies, <35ms cached verification, logical plane separation

| #    | Task                             | Priority | Effort |
| ---- | -------------------------------- | -------- | ------ |
| 1701 | Hash-chain trust records         | High     | Medium |
| 1702 | Knowledge policy enforcement     | Medium   | Medium |
| 1703 | Verification caching enhancement | Medium   | Small  |
| 1704 | Management/data plane isolation  | Medium   | Medium |
| 1705 | M17 tests                        | High     | Medium |

---

### Milestone 18: Frontend Scaffold & API Layer

API backend endpoints and initial frontend infrastructure for the dashboard.

**Todos**: 1801-1806 (6 tasks)
**Status**: ACTIVE
**Dependencies**: M13
**Delivers**: REST API + WebSocket for dashboard, shared React components, TypeScript API client

| #    | Task                           | Priority | Effort |
| ---- | ------------------------------ | -------- | ------ |
| 1801 | Dashboard API endpoints        | High     | Medium |
| 1802 | FastAPI/Nexus server wiring    | High     | Medium |
| 1803 | WebSocket real-time updates    | Medium   | Medium |
| 1804 | Frontend layout and components | Medium   | Medium |
| 1805 | TypeScript API client          | Medium   | Small  |
| 1806 | M18 tests                      | High     | Small  |

---

### Milestone 19: Constrained Organization Validation

Prove the CARE Platform IS a Constrained Organization: five constitutive properties, three behavioral tests, E2E proof.

**Todos**: 1901-1910 (10 tasks)
**Status**: ACTIVE
**Dependencies**: M16, M17 (enforcement and integrity)
**Delivers**: Formal proof that the CARE Platform satisfies all Constrained Organization criteria

| #    | Task                                     | Priority | Effort |
| ---- | ---------------------------------------- | -------- | ------ |
| 1901 | Test harness for constitutive properties | High     | Small  |
| 1902 | Property 1: Constraint Completeness      | High     | Small  |
| 1903 | Property 2: Trust Verifiability          | High     | Small  |
| 1904 | Property 3: Audit Continuity             | High     | Small  |
| 1905 | Property 4: Knowledge Structurality      | High     | Small  |
| 1906 | Property 5: Governance Coherence         | High     | Small  |
| 1907 | Behavioral: Constraints enforced         | High     | Small  |
| 1908 | Behavioral: Trust verifiable             | High     | Small  |
| 1909 | Behavioral: Knowledge compounds          | High     | Small  |
| 1910 | E2E: CARE Platform IS Constrained Org    | High     | Medium |

---

### Milestone 20: Frontend Dashboard Views

Build the seven dashboard views that make the platform's trust state visible.

**Todos**: 2001-2008 (8 tasks)
**Status**: ACTIVE
**Dependencies**: M18
**Delivers**: Full governance dashboard — trust chains, constraints, audit, agents, verification, workspaces, approvals

| #    | Task                             | Priority | Effort |
| ---- | -------------------------------- | -------- | ------ |
| 2001 | Trust chain visualization        | Medium   | Medium |
| 2002 | Constraint envelope dashboard    | Medium   | Medium |
| 2003 | Audit trail viewer               | Medium   | Medium |
| 2004 | Agent status & posture dashboard | Medium   | Medium |
| 2005 | Verification gradient monitoring | Medium   | Medium |
| 2006 | Workspace status views           | Medium   | Small  |
| 2007 | Approval queue (HELD items)      | High     | Medium |
| 2008 | Frontend tests                   | Medium   | Medium |

---

## Phase 2 Decision Points (All Resolved)

| #   | Decision                | Status   | Resolution                                    |
| --- | ----------------------- | -------- | --------------------------------------------- |
| 1   | JCS library             | RESOLVED | Used `jcs` PyPI package                       |
| 2   | SD-JWT scope            | RESOLVED | CARE-sufficient subset                        |
| 3   | Frontend framework      | RESOLVED | React/Next.js for web, Flutter for mobile     |
| 4   | Plane isolation urgency | RESOLVED | MEDIUM — deferred to Phase 4                  |
| 5   | EATP SDK coordination   | RESOLVED | 14 gaps flagged for EATP SDK improvement      |
| 6   | Backward compatibility  | RESOLVED | Clean-slate; Phase 3 adds migration framework |

---

## Phase 3 Milestones (M21-M30) — Production Readiness

**Phase 3 takes the platform from "working governance framework" to "deployable platform that actually runs agents."**

All 5 original architecture phases from the brief are complete. Phase 3 is production readiness: security hardening, real LLM backends, connected frontend, deployment infrastructure, and all execution modes.

### Phase 3 Dependency Graph

```
M21 (Environment) ──────────────────────────────────────┐
  |                                                      |
  +─── M22 (Security Tier 1)                             |
  |       |                                              |
  |       +─── M23 (Security Tier 2)                     |
  |       |       |                                      |
  |       |       +─── M30 (Red Team RT11)               |
  |                                                      |
  +─── M24 (EATP Alignment)                              |
  |                                                      |
  +─── M25 (LLM Backends) ──────────────────────────────+
  |       |                                              |
  |       +─── M27 (Agent Execution)                     |
  |               |                                      |
  |               +─── M30 (Red Team RT11)               |
  |                                                      |
  +─── M26 (Persistence Upgrade)                         |
  |                                                      |
  +─── M28 (Frontend Dashboard) ────────────────────────+
  |       |                                              |
  |       +─── M30 (Red Team RT11)                       |
  |                                                      |
  +─── M29 (Deployment) ───────────────────────────────+
```

### Phase 3 Decision Points (All Resolved)

| #   | Decision             | Resolution                                          |
| --- | -------------------- | --------------------------------------------------- |
| 1   | Primary LLM backend  | Both (Anthropic Claude + OpenAI)                    |
| 2   | Deployment target    | Docker Compose                                      |
| 3   | Frontend scope       | All 7 dashboard views                               |
| 4   | Database             | SQLite AND PostgreSQL                               |
| 5   | Agent execution mode | Live execution — all modes including ShadowEnforcer |

---

### Milestone 21: Environment & Infrastructure Foundation

Wire .env loading across all entry points, validate configuration at startup, enforce auth guard.

**Todos**: 2101-2103 (3 tasks)
**Status**: ACTIVE
**Dependencies**: None
**Delivers**: Properly wired environment configuration; fail-fast on missing config; auth protection by default

| #    | Task                                              | Priority | Effort |
| ---- | ------------------------------------------------- | -------- | ------ |
| 2101 | Wire .env loading across server/CLI/bootstrap     | Critical | Small  |
| 2102 | Startup configuration validation                  | High     | Small  |
| 2103 | CARE_DEV_MODE guard for empty API token (RT10-A6) | Critical | Small  |

---

### Milestone 22: Security Hardening — Deployment Prerequisites

Fix the 6 most urgent security items that must be resolved before any deployment.

**Todos**: 2201-2206 (6 tasks)
**Status**: ACTIVE
**Dependencies**: M21
**Delivers**: WebSocket auth, health probes, graceful shutdown, nonce persistence, bootstrap fix, genesis enforcement

| #    | Task                                      | Priority | Effort       | Source  |
| ---- | ----------------------------------------- | -------- | ------------ | ------- |
| 2201 | WebSocket authentication                  | Critical | Small-Medium | RT10-A4 |
| 2202 | Health and readiness probes               | High     | Small        | I2      |
| 2203 | Graceful shutdown with signal handling    | High     | Small-Medium | I8      |
| 2204 | Nonce persistence to TrustStore           | High     | Small-Medium | RT5-03  |
| 2205 | Bootstrap exception handling fix          | Medium   | Trivial      | RT5-15  |
| 2206 | Non-SQLite genesis write-once enforcement | Medium   | Small        | RT5-14  |

---

### Milestone 23: Security Hardening — Production Readiness

Fix all remaining security and operational gaps for production use.

**Todos**: 2301-2310 (10 tasks)
**Status**: ACTIVE
**Dependencies**: M22
**Delivers**: Complete constraint model, delegation expiry, thread safety, secrets rotation, structured logging, alerting, audit completeness

| #    | Task                                     | Priority | Effort       | Source       |
| ---- | ---------------------------------------- | -------- | ------------ | ------------ |
| 2301 | Financial constraint Optional pattern    | High     | Small        | RT5-19       |
| 2302 | Missing constraint model parameters      | High     | Medium       | RT5-17/20/28 |
| 2303 | Delegation expiry enforcement at runtime | High     | Small        | RT5-24       |
| 2304 | Cumulative spend thread lock             | Medium   | Small        | RT10-A2      |
| 2305 | In-flight action revocation check        | High     | Medium       | RT10-A5      |
| 2306 | Per-agent rate limiting in middleware    | Medium   | Small-Medium | I7           |
| 2307 | Secrets rotation (token + Ed25519 keys)  | High     | Medium-Large | I4           |
| 2308 | Structured logging with correlation IDs  | High     | Medium       | I1           |
| 2309 | Error reporting and alerting (webhooks)  | Medium   | Small-Medium | I10          |
| 2310 | Audit chain EATP completeness            | Medium   | Small-Medium | RT5-26/27    |

---

### Milestone 24: EATP SDK Alignment

Migrate custom trust implementations to EATP SDK. Flag 14 gaps with adapters.

**Todos**: 2401-2404 (4 tasks)
**Status**: ACTIVE
**Dependencies**: M21
**Delivers**: No custom EATP reimplementations; clean adapter layer for 14 SDK gaps; EATP-GAP markers

| #    | Task                                      | Priority | Effort |
| ---- | ----------------------------------------- | -------- | ------ |
| 2401 | Migrate messaging to eatp.messaging       | High     | Medium |
| 2402 | Integrate revocation with eatp.revocation | High     | Medium |
| 2403 | Align posture with eatp.postures          | High     | Small  |
| 2404 | EATP gap adapter documentation + markers  | Medium   | Small  |

---

### Milestone 25: LLM Backend Integration

Implement real LLM backends for Anthropic and OpenAI. Wire to .env. Cost tracking.

**Todos**: 2501-2505 (5 tasks)
**Status**: ACTIVE
**Dependencies**: M21
**Delivers**: Real agent content generation via Claude or OpenAI; cost tracking; failover routing

| #    | Task                                          | Priority | Effort |
| ---- | --------------------------------------------- | -------- | ------ |
| 2501 | Anthropic Claude backend implementation       | Critical | Medium |
| 2502 | OpenAI backend implementation                 | Critical | Medium |
| 2503 | Backend router wiring with .env configuration | High     | Small  |
| 2504 | Cost tracking integration with real API data  | Medium   | Small  |
| 2505 | LLM backend integration tests (real APIs)     | High     | Medium |

---

### Milestone 26: Persistence Upgrade

PostgreSQL support alongside SQLite. Schema migrations. Backup/restore.

**Todos**: 2601-2604 (4 tasks)
**Status**: ACTIVE
**Dependencies**: M21
**Delivers**: PostgreSQL for production, SQLite for dev; schema versioning; automated backup/restore

| #    | Task                                      | Priority | Effort       |
| ---- | ----------------------------------------- | -------- | ------------ |
| 2601 | PostgreSQL TrustStore implementation      | High     | Medium       |
| 2602 | SQLite WAL mode concurrency (Kailash SDK) | Medium   | Small        |
| 2603 | Schema migration framework                | High     | Medium       |
| 2604 | Trust store backup and restore            | High     | Small-Medium |

---

### Milestone 27: Agent Execution Runtime

Kaizen agent bridge. All trust posture modes. ShadowEnforcer live. Full task lifecycle.

**Todos**: 2701-2705 (5 tasks)
**Status**: ACTIVE
**Dependencies**: M25 (LLM backends)
**Delivers**: Agents execute real work under EATP governance; all 5 posture modes; ShadowEnforcer observes and compares

| #    | Task                                                     | Priority | Effort |
| ---- | -------------------------------------------------------- | -------- | ------ |
| 2701 | Kaizen agent bridge — real execution under governance    | Critical | Large  |
| 2702 | All trust posture execution modes                        | High     | Medium |
| 2703 | ShadowEnforcer live mode                                 | High     | Medium |
| 2704 | Agent task lifecycle (submit → verify → execute → audit) | High     | Medium |
| 2705 | Agent execution integration tests                        | High     | Medium |

---

### Milestone 28: Frontend Dashboard

Connect React dashboard to FastAPI backend. All 7 governance views.

**Todos**: 2801-2810 (10 tasks)
**Status**: ACTIVE
**Dependencies**: M21 (auth), M25 (agent data)
**Delivers**: Full governance dashboard — trust chains, constraints, audit, agents, verification, workspaces, approvals

| #    | Task                                         | Priority | Effort |
| ---- | -------------------------------------------- | -------- | ------ |
| 2801 | TypeScript API client (from Pydantic models) | High     | Medium |
| 2802 | Dashboard layout and navigation              | High     | Medium |
| 2803 | Trust chain visualization view               | Medium   | Medium |
| 2804 | Constraint envelope dashboard view           | Medium   | Medium |
| 2805 | Audit trail viewer                           | Medium   | Medium |
| 2806 | Agent status & posture dashboard view        | Medium   | Medium |
| 2807 | Verification gradient monitoring view        | Medium   | Medium |
| 2808 | Workspace status view                        | Medium   | Small  |
| 2809 | Approval queue (HELD items) view             | High     | Medium |
| 2810 | Frontend tests                               | High     | Medium |

---

### Milestone 29: Deployment & Operations

Dockerfile, Docker Compose, operator documentation, environment configuration guide.

**Todos**: 2901-2904 (4 tasks)
**Status**: ACTIVE
**Dependencies**: M22, M25
**Delivers**: Deployable platform with Docker Compose; operator guide for setup, config, monitoring, backup

| #    | Task                                       | Priority | Effort |
| ---- | ------------------------------------------ | -------- | ------ |
| 2901 | Dockerfile (FastAPI + Python dependencies) | High     | Small  |
| 2902 | Docker Compose (API + frontend + database) | High     | Medium |
| 2903 | Operator documentation                     | High     | Medium |
| 2904 | Environment configuration documentation    | Medium   | Small  |

---

### Milestone 30: Red Team RT11

Full Phase 3 security, standards, and integration validation.

**Todos**: 3001-3002 (2 tasks)
**Status**: ACTIVE
**Dependencies**: All Phase 3 milestones
**Delivers**: Security validation of production-ready platform; convergence report

| #    | Task                                           | Priority | Effort |
| ---- | ---------------------------------------------- | -------- | ------ |
| 3001 | Full Phase 3 security and standards validation | Critical | Large  |
| 3002 | Convergence report                             | High     | Small  |

---

## Phase 4 Milestones (M31-M36) — Bridge Trust Enforcement

**Phase 4 implements the cryptographic trust and constraint enforcement layer for Cross-Functional Bridges.** Phase 3 built the bridge data model and lifecycle (M5). Phase 4 makes bridges trust-governed: every cross-team action traces to a signed delegation, operates under the intersection of both teams' constraints, and produces dual audit anchors.

### Phase 4 Dependency Graph

```
M31 (Bridge Trust Foundation) ──────────────────────────────┐
  |                                                          |
  +─── M32 (Constraint Intersection) ──────────────────────+
  |                                                          |
  +─── M33 (Cross-Team Execution) ─────────────────────────+
  |       depends on M31, M32                               |
  |                                                          |
  +─── M34 (Bridge Lifecycle Operations) ──────────────────+
  |       depends on M31, M32, M33 (for revocation cascade) |
  |                                                          |
  +─── M35 (Security Hardening) ───────────────────────────+
  |       depends on M31 (bridge trust surface)             |
  |                                                          |
  +─── M36 (Bridge API + Dashboard) ───────────────────────+
          depends on M31-M34
```

(M31 and M32 can run in parallel — M32 has no dependency on M31. M33 requires both M31 and M32. M34 requires M33. M35 can run after M31. M36 requires M31-M34.)

---

### Milestone 31: Bridge Trust Foundation (Phase 4)

Cryptographic trust foundation for cross-functional bridges. Every bridge activation creates signed bilateral delegation records. Cross-team actions operate under the intersection of both teams' postures and produce dual audit anchors with cross-references.

**Todos**: 3101-3105 (5 tasks)
**Status**: ACTIVE
**Dependencies**: M5 (bridge data model), M2 (EATP delegation), M12 (persistent trust store)
**Delivers**: BridgeDelegation primitive, bilateral trust roots on activation, effective posture resolution, cross-team dual audit anchors

| #    | Task                          | Priority | Effort |
| ---- | ----------------------------- | -------- | ------ |
| 3101 | Bridge Delegation Record      | High     | Medium |
| 3102 | Bridge Trust Root (bilateral) | High     | Medium |
| 3103 | Cross-Team Posture Resolution | High     | Small  |
| 3104 | Cross-Team Audit Anchoring    | High     | Medium |
| 3105 | Bridge Trust Tests            | High     | Medium |

---

### Milestone 32: Constraint Intersection (Phase 4)

Compute the tightest constraint envelope for cross-bridge actions by intersecting source team, bridge, and target team constraints across all five CARE dimensions. Field-level information sharing modes. Validation that bridges cannot grant wider access than either party holds.

**Todos**: 3201-3204 (4 tasks)
**Status**: ACTIVE
**Dependencies**: M5 (bridge model), M1 (ConstraintEnvelopeConfig)
**Delivers**: compute_bridge_envelope() across 5 dimensions, SharingMode field-level policy, validate_bridge_tightening() safety check

| #    | Task                          | Priority | Effort |
| ---- | ----------------------------- | -------- | ------ |
| 3201 | Envelope Intersection         | High     | Medium |
| 3202 | Information Sharing Modes     | High     | Medium |
| 3203 | Bridge Tightening Validation  | High     | Small  |
| 3204 | Constraint Intersection Tests | High     | Medium |

---

### Milestone 33: Cross-Team Execution (Phase 4)

Wire the bridge trust and constraint layers into the execution runtime. Cross-team tasks route through bridge verification, apply the effective envelope and posture, and return dual audit anchors. Ad-hoc bridge pattern detection suggests Standing bridge promotion.

**Todos**: 3301-3305 (5 tasks)
**Status**: ACTIVE
**Dependencies**: M31 (bridge trust), M32 (constraint intersection), 3103 (posture resolution)
**Delivers**: Bridge-verified cross-team task execution; BLOCKED path for bridgeless cross-team requests; ad-hoc bridge automation with promotion detection

| #    | Task                            | Priority | Effort |
| ---- | ------------------------------- | -------- | ------ |
| 3301 | Bridge Verification Pipeline    | High     | Large  |
| 3302 | Bridge-Level Revocation         | High     | Medium |
| 3303 | Ad-Hoc Bridge Management        | High     | Medium |
| 3304 | KaizenBridge Cross-Team Routing | High     | Large  |
| 3305 | Cross-Team Execution Tests      | High     | Large  |

---

### Milestone 34: Bridge Lifecycle Operations (Phase 4)

Complete the bridge lifecycle with trust-integrated approval, suspension, closure, and modification flows. Bridge terms are immutable once ACTIVE; modification creates a replacement bridge with a full audit chain. Standing bridges require periodic review.

**Todos**: 3401-3404 (4 tasks)
**Status**: ACTIVE
**Dependencies**: M31 (bridge trust), M32 (constraint intersection), M33 (revocation cascade)
**Delivers**: Trust records wired to approval/suspension/closure; bridge modification via replacement preserving audit chain; review cadence with overdue detection

| #    | Task                                | Priority | Effort |
| ---- | ----------------------------------- | -------- | ------ |
| 3401 | Bridge Approval Trust Flow          | High     | Large  |
| 3402 | Bridge Modification via Replacement | High     | Medium |
| 3403 | Bridge Review Cadence               | High     | Small  |
| 3404 | Bridge Lifecycle Trust Tests        | High     | Medium |

---

### Milestone 35: Security Hardening (Phase 4)

Harden the bridge trust surface against prompt injection, keyword smuggling, API abuse, and information leakage through response headers.

**Todos**: 3501-3504 (4 tasks)
**Status**: ACTIVE
**Dependencies**: M31 (bridge trust surface)
**Delivers**: Prompt injection protections, keyword normalization, per-agent API rate limiting, secure response headers

| #    | Task                       | Priority | Effort |
| ---- | -------------------------- | -------- | ------ |
| 3501 | Prompt Injection Hardening | High     | Medium |
| 3502 | Keyword Normalization      | High     | Small  |
| 3503 | API Rate Limiting          | High     | Medium |
| 3504 | Security Response Headers  | High     | Small  |

---

### Milestone 36: Bridge API + Dashboard (Phase 4)

REST endpoints for bridge CRUD, audit retrieval, and lifecycle operations. React dashboard views for bridge management, creation wizard, and audit trail.

**Todos**: 3601-3605 (5 tasks)
**Status**: ACTIVE
**Dependencies**: M31-M34 (full bridge trust layer)
**Delivers**: Full operator interface for Cross-Functional Bridges — create, manage, audit, and govern bridges through both API and UI

| #    | Task                        | Priority | Effort |
| ---- | --------------------------- | -------- | ------ |
| 3601 | Bridge CRUD Endpoints       | High     | Large  |
| 3602 | Bridge Audit Endpoint       | High     | Medium |
| 3603 | Bridge Management Dashboard | High     | Large  |
| 3604 | Bridge Creation Wizard      | High     | Large  |
| 3605 | Bridge Dashboard Tests      | High     | Medium |

---

## Phase 4 (Future) — Deferred Items

Items originally listed as out-of-scope for Phase 3. May become Phase 5 depending on adoption needs.

| Item                                        | When Needed                |
| ------------------------------------------- | -------------------------- |
| Physical store isolation (separate process) | Enterprise adopters        |
| HSM key management                          | Regulatory requirements    |
| External hash chain anchoring               | External audit credibility |
| Multi-tenant isolation                      | Commercial vendors         |
| Multi-instance horizontal scaling           | Exceeds single-instance    |
