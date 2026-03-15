# Architecture Gap Analysis: COC Setup → CARE Platform

**Date**: 2026-03-11
**Source**: Deep analyst
**Status**: Research complete

---

## What Already Exists

The current COC setup at `.claude/` is structurally a single-user CARE deployment:

| COC Component | CARE Architecture Equivalent |
|--------------|------------------------------|
| 14 agents with defined roles | Execution Plane agents |
| Agent descriptions with allowed-tools | Constraint Envelopes (operational dimension) |
| Skills (knowledge references) | Knowledge Ledger |
| Rules (8 files) | Trust Plane policies |
| Hooks (7 lifecycle hooks) | Trust Verification Bridge |
| Commands (9 workflow triggers) | Workspace lifecycle phases |
| Workspaces (media, constitution, etc.) | CARE Workspaces (objective containers) |

This is not metaphorical. The `.claude/rules/` directory functions as the Trust Plane. The `.claude/agents/` directory functions as the Execution Plane. The hooks function as the Trust Verification Bridge.

---

## Five Gaps Between COC Setup and CARE Platform

### Gap 1: Multi-User, Multi-Team Runtime

**Current**: Runs in a single Claude Code session. One person, one context window.
**Needed**: Multiple humans operating multiple agent teams concurrently, with shared state and inter-team coordination.
**Assessment**: Largest gap. Requires a runtime layer that does not exist in the COC setup.
**Path**: Kaizen (Kailash agent framework) already addresses multi-agent execution. Bridge COC-style agent definitions to Kaizen agent execution.

### Gap 2: Persistence and State Management

**Current**: Relies on filesystem (markdown, `.session-notes`, git).
**Needed**: Structured persistence — trust chains with cryptographic integrity, constraint envelopes versioned and auditable, execution history queryable.
**Assessment**: EATP SDK (Phase 1 complete, 238 tests) provides trust layer primitives, but storage is not connected to the agent runtime.
**Path**: Connect EATP SDK to DataFlow for persistent storage.

### Gap 3: Trust Plane Enforcement (Cryptographic)

**Current**: Trust enforced by convention (rules that Claude reads) and lightweight hooks (validate-bash-command.js).
**Needed**: Agents cannot modify their own constraints. Actions verified against signed constraint envelopes. Every action produces an audit anchor.
**Assessment**: EATP SDK has the cryptographic primitives (Ed25519, verification gradient). Not integrated into agent execution.
**Path**: Integrate EATP SDK into the hook system. Hooks become EATP VERIFY operations.

### Gap 4: Agent Runtime Independence

**Current**: All agents run as sub-conversations within Claude Code (Anthropic API).
**Needed**: Multiple LLM backends, local models, non-LLM agent types (workflow, data pipeline, integration).
**Assessment**: Kaizen framework already supports multiple backends. The platform needs to bridge COC agent definitions to Kaizen execution.
**Path**: Agent definition format (markdown) becomes the abstraction layer. Runtime (Claude, OpenAI, Gemini, local) is a deployment choice.

### Gap 5: Workspace-to-Workspace Coordination

**Current**: Workspaces are isolated directories.
**Needed**: Cross-Functional Bridges enabling agent teams to coordinate across workspace boundaries (e.g., DM team requesting content from Standards team).
**Assessment**: CARE specification describes Standing, Scoped, and Ad-Hoc bridges. Not implemented.
**Path**: Implement as EATP cross-team delegation (see EATP trust model research).

---

## Implementation Phases

| Phase | What | Builds On |
|-------|------|-----------|
| 1 | Package COC setup pattern as reusable framework (agent defs, rules, hooks as shareable structure) | Existing COC setup |
| 2 | Add persistence layer (EATP SDK for trust, DataFlow for state) | EATP SDK Phase 1 |
| 3 | Add multi-team runtime (Kaizen agents executing COC-defined agent roles) | Kaizen framework |
| 4 | Add Cross-Functional Bridges (workspace-to-workspace coordination) | EATP cross-team delegation |
| 5 | Add Organization Builder (auto-generate agent teams from org structure) | All previous phases |

---

## Full Agent Team Inventory (All Foundation Teams)

### Tier 1 — Needed Now (Solo Founder)

| Team | Workspace | Agents |
|------|-----------|--------|
| **Media/Content** | `workspaces/media/` | Content Researcher, Content Writer, Clip Extractor, Social Scheduler, Analytics Tracker, Engagement Monitor, Calendar Coordinator |
| **Standards** | `workspaces/standards/` | Spec Drafter, Cross-Reference Validator, RFC Monitor, Compatibility Checker, Publication Coordinator |
| **Governance** | `workspaces/constitution/` | Constitution Expert (exists), Compliance Monitor, Meeting Coordinator, Membership Tracker |
| **Partnerships** | `workspaces/partnerships/` | Government Researcher, Partnership Analyst, Engagement Tracker, Grant Writer, Reporting Agent |
| **Website** | `workspaces/website/` | (Already has planning) |

### Tier 2 — Needed at Phase 2 (10 Members)

| Team | Workspace | Agents |
|------|-----------|--------|
| **Community** | `workspaces/community/` | Onboarding Coordinator, Contribution Tracker, Community Health Monitor |
| **Developer Relations** | `workspaces/devrel/` | SDK Doc Writer, Tutorial Generator, Developer Experience Monitor |
| **Finance** | `workspaces/finance/` | Budget Tracker, Grant Reporter, Sponsorship Manager, Audit Preparer |

### Tier 3 — Needed at Scale (30+ Members)

| Team | Workspace | Agents |
|------|-----------|--------|
| **Certification** | `workspaces/certification/` | CDI Assessor, Certification Program Manager |
| **Training** | `workspaces/training/` | Curriculum Developer (content only, NTUC delivers) |
| **Legal** | `workspaces/legal/` | CLA Manager, Patent Covenant Admin, Compliance Monitor |

### Universal Agents (Every Team)

- **Knowledge Curator** — Maintains workspace knowledge base, ensures documentation currency
- **Cross-Team Coordinator** — Manages bridge interactions with other workspaces

---

## Cross-Reference Impact

Documents that would need updating if the CARE Platform layer is formalized:

| Document | Change Needed |
|----------|--------------|
| `docs/00-anchor/01-core-entities.md` | Add "agent platform" to what Foundation creates |
| `docs/00-anchor/02-the-gap.md` | Add "Open Agent Platform" to the gap analysis |
| `docs/00-anchor/03-ip-ownership.md` | Clarify IP ownership for CARE Platform |
| `docs/00-anchor/04-value-model.md` | Add Agent Platform layer to product stack |
| `docs/02-standards/care/05-implementation/03-technical-blueprint.md` | Currently references a specific commercial implementation; needs to be implementation-neutral |
| `.claude/rules/terrene-naming.md` | Add CARE Platform terminology |

### Inconsistency Found

The CARE technical blueprint (`docs/02-standards/care/05-implementation/03-technical-blueprint.md`) describes a specific implementation (FastAPI Management Plane, Nexus Data Plane, DataFlow models) using the term "Agentic OS." The blueprint must be updated to be implementation-neutral — describing the architectural requirements that any conforming implementation (including the CARE Platform) must satisfy, without privileging any specific commercial product.

---

## Open Decision Points

| # | Decision | Options | Impact |
|---|----------|---------|--------|
| 1 | IP ownership | Foundation-owned directly (all open-source IP was fully and irrevocably transferred) | Resolved — Foundation controls the platform |
| 2 | Build vs compose | From scratch vs compose from Kailash Python (Kaizen, DataFlow, Nexus) | Speed vs dependency |
| 3 | Technical blueprint | Rewrite to be implementation-neutral vs separate doc for open platform | Spec integrity |
| 4 | Internal tool first vs product | Build for Foundation first, publish later vs publish from start | Quality vs momentum |
| 5 | Transparency level | Full operational transparency vs selective disclosure | Credibility vs exposure |
| 6 | Runtime coupling | Target Claude Code initially vs runtime-agnostic from start | Pragmatism vs portability |
| 7 | Cascading risk mitigation | How to prevent "AI-run Foundation" → "open-washing" → mission failure | Critical path |
