# CARE Platform Brief

**Date**: 2026-03-11
**Author**: Dr. Jack Hong
**Status**: Analysis complete — ready for planning

---

## Vision

Build an open-source AI agent platform called **CARE** that operationalizes the entire Terrene Foundation as an agent-orchestrated organization. CARE is the Foundation's open-source governed operational model for running organizations with AI agents under EATP trust governance. Since the standards, SDKs, and reference model are all open, anyone — including commercial vendors — can build their own proprietary implementations.

## Key Insight

The Foundation's existing workspace structure IS the CARE platform's knowledge layer:
- `workspaces/media/` = Digital Marketing team's knowledge base
- `workspaces/constitution/` = Management/Governance team's knowledge base
- Other workspaces = other operational teams' knowledge bases

Each workspace becomes the institutional memory for a team of AI agents, governed by CARE principles, secured by EATP, orchestrated by CO.

## Scope

- **Not just DM**: The CARE platform covers the entire Foundation — governance, standards development, community management, partnerships, digital marketing, operations
- **DM as first vertical**: The digital marketing value chain is the first fully-serviced agent team to build and showcase
- **Full-service teams**: Each team includes outreach, engagement, content creation, scheduling, analytics — not just automation but autonomous operation within trust boundaries

## Product Stack (Updated)

| Layer | Foundation (Open) |
|-------|------------------|
| Specs | CARE, EATP, CO, CDI (CC BY 4.0) |
| SDKs | Kailash Python, EATP SDK (Apache 2.0) |
| Agent Platform | **CARE Platform** (Apache 2.0) |

All Foundation IP is irrevocably open. The open standards, SDKs, and reference model enable anyone to build commercial implementations — the Foundation has no structural relationship with any commercial entity.

## Naming Decision

The open-source agent platform shares the name "CARE" with the governance philosophy. This is intentional — the philosophy manifests as the platform. Disambiguate with context when needed: "CARE specification" vs "CARE platform."

## Scope Boundary

The CARE Platform workspace owns the Foundation's open-source operational model. The Foundation's scope is single-organization governance — running one organization with AI agents under EATP trust governance. Multi-organization trust federation (cross-org trust bridging, distributed audit, etc.) is naturally more complex and is beyond the Foundation's scope. Commercial vendors can build multi-org products on top of the open standards.

## Critical Insight from Analysis

The Foundation's existing COC setup (14 agents, 8 rules, 5 skills, 9 commands, 8 hooks) is already a nascent CARE Platform. The rules files (`terrene-naming.md`, `constitution.md`, `security.md`, `communication.md`) are constraint envelopes in everything but name. Building the CARE Platform is less "new construction" and more "recognizing and formalizing what already exists."

## Constraints

- Solo founder — agent teams must be sustainable to operate and maintain
- Foundation hasn't incorporated yet — platform design should be ready for post-incorporation launch
- Must demonstrate CARE/EATP/CO principles in its own operation (dog-fooding)
- Open-source (Apache 2.0) — Foundation-owned, irrevocably open
- Platform is configuration + methodology, not complex compiled software
- Must not compete on generic orchestration (LangChain, CrewAI territory)
