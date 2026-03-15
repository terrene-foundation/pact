# CARE Platform

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-active%20development-orange.svg)]()

**Governed operational model for running organizations with AI agents under EATP trust governance, CO methodology, and CARE philosophy.**

The CARE Platform is the Terrene Foundation's reference implementation of the CARE specification -- an open-source framework for organizations that want to deploy AI agents with cryptographic trust enforcement, constraint governance, and tamper-evident audit trails.

> **What it is NOT**: A generic agent orchestrator competing with LangChain or CrewAI. The CARE Platform is _governed orchestration_ -- an opinionated framework where every agent action passes through a trust verification pipeline before execution.

---

## The Trinity

The CARE Platform implements three open specifications published by the Terrene Foundation:

| Standard | Full Name                                      | Type        | License   |
| -------- | ---------------------------------------------- | ----------- | --------- |
| **CARE** | Collaborative Autonomous Reflective Enterprise | Philosophy  | CC BY 4.0 |
| **EATP** | Enterprise Agent Trust Protocol                | Protocol    | CC BY 4.0 |
| **CO**   | Cognitive Orchestration                        | Methodology | CC BY 4.0 |

- **CARE** defines the governance philosophy -- the Dual Plane Model (Trust Plane + Execution Plane) and the Mirror Thesis (organizational trust structures mirror human trust patterns).
- **EATP** defines the trust protocol -- how trust is established, delegated, verified, and audited through cryptographic chains.
- **CO** defines the methodology -- how agents are orchestrated within constraint boundaries using seven principles across five layers.

---

## Key Concepts

### Constraint Envelopes

Every agent operates within a **constraint envelope** that governs five dimensions:

| Dimension         | What It Controls                        | Example                             |
| ----------------- | --------------------------------------- | ----------------------------------- |
| **Financial**     | Spending limits, approval thresholds    | Max $500/day, approval above $100   |
| **Operational**   | Allowed/blocked actions, rate limits    | May read and draft; may not publish |
| **Temporal**      | Active hours, blackout periods          | 09:00-18:00 UTC, no weekends        |
| **Data Access**   | Read/write paths, blocked data types    | Read briefs/; no PII access         |
| **Communication** | Internal/external, channel restrictions | Internal only; Slack and email      |

Constraint envelopes enforce **monotonic tightening** -- a child agent's constraints can only be equal to or stricter than its parent's. Constraints can never be loosened through delegation.

### Verification Gradient

Every agent action is classified through the verification gradient before execution:

- **AUTO_APPROVED** -- execute and log (low-risk routine actions)
- **FLAGGED** -- execute but highlight for human review (near constraint boundaries)
- **HELD** -- queue for human approval before execution (high-impact actions)
- **BLOCKED** -- reject outright (constraint violations or forbidden actions)

### Trust Postures

Agents evolve through trust posture levels based on demonstrated performance:

1. **Pseudo-Agent** -- no autonomous action
2. **Supervised** -- every action requires human approval (default starting level)
3. **Shared Planning** -- agent proposes, human approves plans (requires 90 days, 95% success rate)
4. **Continuous Insight** -- agent executes with human oversight (requires 180 days, 98% success rate)
5. **Delegated** -- agent operates autonomously within constraints (requires 365 days, 99% success rate)

Upgrades are gradual and evidence-based. Downgrades are instant on any negative incident.

### Trust Lineage Chain (EATP Five Elements)

Every agent's authority traces back to a cryptographically signed root of trust:

1. **Genesis Record** -- the root authority record (Ed25519 signed)
2. **Delegation Record** -- signed transfer of capabilities with constraints
3. **Constraint Envelope** -- the five-dimension governance boundary
4. **Capability Attestation** -- signed declaration of what an agent may do
5. **Audit Anchor** -- tamper-evident record of every action taken

---

## Architecture

The CARE Platform operates on two planes, following the CARE Dual Plane Model:

```
 Trust Plane (care_platform.trust, care_platform.constraint)
 +---------------------------------------------------------+
 | Genesis -> Delegation -> Envelope -> Attestation -> Audit|
 | Verification Gradient | Trust Postures | Trust Scoring   |
 +---------------------------------------------------------+
                          |
                    verify/enforce
                          |
 Execution Plane (care_platform.execution)
 +---------------------------------------------------------+
 | Agent Teams | Workspaces | Session Management            |
 | Cross-Functional Bridges | Approval Queues               |
 +---------------------------------------------------------+
```

### Package Structure

```
care_platform/
  trust/          EATP trust layer (genesis, delegation, posture, attestation, scoring)
  constraint/     Constraint envelope evaluation and verification gradient engine
  execution/      Agent execution runtime (teams, sessions, approval queues)
  audit/          Tamper-evident audit anchor chains
  workspace/      Workspace-as-knowledge-base management, cross-functional bridges
  config/         Platform configuration schema (Pydantic models) and YAML loader
  persistence/    Storage abstraction (MemoryStore, FilesystemStore)
  org/            Organization builder
  verticals/      Domain-specific team templates
  cli/            Command-line interface
```

---

## Quick Start

### Installation

```bash
pip install care-platform
```

Or for development:

```bash
git clone https://github.com/terrene-foundation/care.git
cd care
pip install -e ".[dev]"
```

### Configure

Copy the environment template and add your API keys:

```bash
cp .env.example .env
```

### Define Your Organization

Create a platform configuration (YAML or Python):

```python
from care_platform.config.schema import (
    PlatformConfig,
    GenesisConfig,
    AgentConfig,
    TeamConfig,
    WorkspaceConfig,
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    CommunicationConstraintConfig,
)

config = PlatformConfig(
    name="My Organization",
    genesis=GenesisConfig(
        authority="my-org.example",
        authority_name="My Organization",
        policy_reference="https://my-org.example/policy",
    ),
    constraint_envelopes=[
        ConstraintEnvelopeConfig(
            id="analyst-envelope",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "analyze", "draft"],
                blocked_actions=["publish", "delete"],
            ),
            communication=CommunicationConstraintConfig(internal_only=True),
        ),
    ],
    agents=[
        AgentConfig(
            id="analyst-01",
            name="Research Analyst",
            role="Analyze data and produce reports",
            constraint_envelope="analyst-envelope",
            capabilities=["read", "analyze", "draft"],
        ),
    ],
    teams=[
        TeamConfig(
            id="research-team",
            name="Research Team",
            workspace="research-ws",
            agents=["analyst-01"],
        ),
    ],
    workspaces=[
        WorkspaceConfig(
            id="research-ws",
            path="workspaces/research",
            description="Research team knowledge base",
        ),
    ],
)
```

### Establish Trust and Run

```python
import asyncio
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.trust.genesis import GenesisManager
from care_platform.trust.delegation import DelegationManager

async def main():
    # 1. Initialize the EATP bridge
    bridge = EATPBridge()
    await bridge.initialize()

    # 2. Establish genesis (root of trust)
    genesis_mgr = GenesisManager(bridge)
    genesis = await genesis_mgr.create_genesis(config.genesis)

    # 3. Delegate to agents with constraint envelopes
    delegation_mgr = DelegationManager(bridge)
    agent_config = config.get_agent("analyst-01")
    envelope_config = config.get_envelope("analyst-envelope")
    delegation = await delegation_mgr.create_delegation(
        delegator_id=f"authority:{config.genesis.authority}",
        delegate_config=agent_config,
        envelope_config=envelope_config,
    )

    # 4. Verify an action before execution
    result = await bridge.verify_action(
        agent_id="analyst-01",
        action="read",
        resource="briefs/quarterly-report.md",
    )
    print(f"Verification: valid={result.valid}")

    # 5. Record an audit anchor
    anchor = await bridge.record_audit(
        agent_id="analyst-01",
        action="read",
        resource="briefs/quarterly-report.md",
        result="SUCCESS",
    )
    print(f"Audit anchor recorded: {anchor.id}")

asyncio.run(main())
```

---

## Built On

The CARE Platform is built on the **Kailash Python SDK**, the Foundation's open-source toolkit:

| Framework    | Purpose                                    | Install                        |
| ------------ | ------------------------------------------ | ------------------------------ |
| **Core SDK** | Workflow orchestration, 140+ nodes         | `pip install kailash`          |
| **DataFlow** | Zero-config database operations            | `pip install kailash-dataflow` |
| **Nexus**    | Multi-channel deployment (API + CLI + MCP) | `pip install kailash-nexus`    |
| **Kaizen**   | AI agent framework                         | `pip install kailash-kaizen`   |

The EATP SDK provides the cryptographic trust chain implementation:

| Package      | Purpose                                             | Install            |
| ------------ | --------------------------------------------------- | ------------------ |
| **EATP SDK** | Trust lineage chains, Ed25519 signing, verification | `pip install eatp` |

---

## Requirements

- Python 3.11 or later
- See `pyproject.toml` for the full dependency list

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy care_platform/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor guide.

---

## Documentation

- [Architecture](docs/architecture.md) -- module structure, data flow, extension points
- [API Reference](docs/api.md) -- public interfaces and usage examples
- [Specifications](https://terrene.dev) -- CARE, EATP, and CO standards
- [Foundation](https://terrene.foundation) -- Terrene Foundation

---

## License

Copyright 2026 Terrene Foundation

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

The CARE Platform is Foundation-owned, Apache 2.0 licensed, and irrevocably open. The Foundation has no structural relationship with any commercial entity. Anyone can build commercial implementations on top of the Foundation's open standards and SDKs.

**Specifications** (CARE, EATP, CO): CC BY 4.0
**Code** (CARE Platform, Kailash SDK, EATP SDK): Apache 2.0
