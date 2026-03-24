# PACT Platform

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-2198%20passed-green.svg)]()

**Human judgment surface for governed AI operations.**

PACT Platform is a Layer 3 application built on kailash-pact governance primitives and kaizen-agents autonomous execution. It provides the org definition, approval UX, work management, dashboard, and deployment that turn governance rules into an operational system.

> **Not a generic agent orchestrator.** Every agent action passes through a governance pipeline -- D/T/R accountability, operating envelopes, knowledge clearance, and verification gradient -- before execution.

---

## Quick Start

```bash
pip install pact-platform[all]
pact quickstart --example university
```

This loads the university demo org, registers 3 agents, seeds sample data, and starts the API server at `http://localhost:8000`.

### What you'll see:

- **Dashboard** at `http://localhost:3000` -- objectives, requests, approvals, cost tracking
- **1 HELD action** in the approval queue (researcher needs CONFIDENTIAL clearance)
- **$0.10 total cost** across 3 demo agent runs
- **API** at `http://localhost:8000/docs` -- 42+ endpoints

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  L3: pact-platform (this package)                   │
│  ┌────────┐ ┌────────┐ ┌─────┐ ┌──────────────┐    │
│  │ Models │ │ API    │ │ CLI │ │ Integrations │    │
│  │ (11)   │ │ (42+)  │ │     │ │ Slack/Teams  │    │
│  └────────┘ └────────┘ └─────┘ └──────────────┘    │
│  ┌─────────────────────────────────────────────┐    │
│  │ Engine: Envelope Adapter, Governed Delegate, │    │
│  │ Approval Bridge, Supervisor Orchestrator     │    │
│  └─────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────┤
│  L2: kaizen-agents (GovernedSupervisor)             │
├─────────────────────────────────────────────────────┤
│  L1: kailash-pact (GovernanceEngine, D/T/R grammar) │
│  L1: kailash[trust] (EATP SDK, trust chains)        │
│  L1: kailash-dataflow (auto-generated CRUD nodes)   │
├─────────────────────────────────────────────────────┤
│  L0: Kailash Core SDK (workflow runtime, 140+ nodes) │
└─────────────────────────────────────────────────────┘
```

## Key Concepts

| Concept                   | What it means                                                                             |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| **D/T/R Grammar**         | Department → Team → Role. Every address resolves to exactly one governance envelope.      |
| **Operating Envelope**    | Five constraint dimensions: Financial, Operational, Temporal, Data Access, Communication. |
| **Knowledge Clearance**   | Five levels: PUBLIC → RESTRICTED → CONFIDENTIAL → SECRET → TOP_SECRET.                    |
| **Verification Gradient** | Four zones: AUTO_APPROVED → FLAGGED → HELD → BLOCKED.                                     |
| **GovernedSupervisor**    | Autonomous agent execution within governance constraints.                                 |

## CLI Reference

```bash
pact quickstart --example university   # Demo with seeded data
pact org create my-org.yaml            # Load org from YAML
pact org list                          # List compiled orgs
pact role assign D1-T1-R1 agent-001    # Assign agent to role
pact clearance grant D1-T1-R1 CONFIDENTIAL  # Grant clearance
pact bridge create D1-R1 D2-R1         # Cross-functional bridge
pact envelope show D1-T1-R1            # Show effective envelope
pact agent register agent-001 D1-T1-R1 # Register agent
pact audit export --format json        # Export audit trail
```

## API Endpoints

| Group      | Prefix                     | Endpoints                                             |
| ---------- | -------------------------- | ----------------------------------------------------- |
| Objectives | `/api/v1/objectives`       | create, list, detail, update, cancel, requests, cost  |
| Requests   | `/api/v1/requests`         | submit, list, detail, cancel, sessions, artifacts     |
| Sessions   | `/api/v1/sessions`         | list, detail, pause, resume                           |
| Decisions  | `/api/v1/decisions`        | list, detail, approve, reject, stats                  |
| Pools      | `/api/v1/pools`            | create, list, detail, add/remove members, capacity    |
| Reviews    | `/api/v1/reviews`          | list, detail, add finding, finalize                   |
| Metrics    | `/api/v1/platform/metrics` | cost, throughput, governance, budget                  |
| Governance | `/api/v1/`                 | teams, agents, envelopes, trust-chains, bridges, etc. |

## Docker Deployment

```bash
docker compose up
```

Services:

- **api** — FastAPI server (port 8000)
- **web** — Next.js dashboard (port 3000)
- **mobile** — Flutter web (port 8080)

## Development

```bash
git clone https://github.com/terrene-foundation/pact.git
cd pact
pip install -e ".[all,dev]"
pytest  # 2198 tests
```

## License

Apache 2.0 — Terrene Foundation (Singapore CLG). Fully independent, irrevocably open.

## The Quartet

| Standard | Purpose                                              | License   |
| -------- | ---------------------------------------------------- | --------- |
| **CARE** | Governance philosophy (Dual Plane Model)             | CC BY 4.0 |
| **PACT** | Architecture (D/T/R, envelopes, clearance, gradient) | CC BY 4.0 |
| **EATP** | Protocol (trust chains, delegation, verification)    | CC BY 4.0 |
| **CO**   | Methodology (human-AI collaboration)                 | CC BY 4.0 |
