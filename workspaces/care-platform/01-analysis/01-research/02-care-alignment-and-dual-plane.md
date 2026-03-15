# CARE Alignment and Dual Plane Mapping

**Date**: 2026-03-11
**Source**: CARE expert analysis
**Status**: Research complete

---

## Key Finding

The Foundation's existing COC setup (rules, agents, skills, hooks, commands) is already a nascent CARE implementation. The rules files (`terrene-naming.md`, `constitution.md`, `security.md`, `communication.md`, `no-stubs.md`) are constraint envelopes in everything but name. The "CARE Platform" concept is less about building something new and more about recognizing and formalizing what already exists, then extending it with the full rigor of EATP's verification gradient, constraint envelope architecture, and evolutionary trust lifecycle.

---

## 1. Dual Plane Mapping for Foundation Operations

### Trust Plane (Always Human)

These decisions require ethical judgment, relationship capital, and contextual wisdom that agents cannot provide:

| Domain | Examples | Why Human |
|--------|----------|-----------|
| Constitutional governance | Modify 77 clauses, interpret Entrenched Provisions, board composition | Values-encoded boundaries |
| Standards approval | Whether a CARE/EATP/CO version is ready for publication | Purpose alignment |
| Partnership commitments | Engaging IMDA, MAS, ASME, SBF | Relationship capital, shared vulnerability |
| Licensing decisions | Apache 2.0 for code, CC BY 4.0 for specs | Values judgment |
| Public positioning | What the Foundation says externally about AI governance | Cultural navigation |
| Membership admission | Who qualifies as Committer Member | Merit evaluation |
| Financial strategy | How surplus is reinvested in mission | Values judgment |

### Execution Plane (Agent-Handled)

| Domain | Examples | Constraint Envelope |
|--------|----------|-------------------|
| Document drafting | Standards docs, research briefs, strategy papers | Write to workspaces/ only; published docs require approval |
| Cross-reference validation | Clause X references, EP consistency | Read-only access to all docs/ |
| Content pipeline | Markdown → decks, distributable formats | Internal operations only |
| Community content | Newsletter drafts, podcast notes, social summaries | External publication always HELD |
| Workspace coordination | Progress tracking, session notes, stalled work flagging | Internal channels only |
| Quality validation | Gold-standards checks, intermediate review, security review | Already implemented as agents |
| Competitive intelligence | Monitor other AI governance frameworks, summarize developments | Read external, write internal only |

### Verification Gradient

| Level | Foundation Example |
|-------|-------------------|
| **Auto-approved** | Internal workspace notes, cross-reference checks, document formatting |
| **Flagged** | Draft references a concept not yet in anchor documents |
| **Held** | External-facing content, partnership briefs, government communications |
| **Blocked** | Modify constitutional text, change licensing terms, publish binding commitments |

---

## 2. Mirror Thesis: The Foundation as First Empirical Test

If the Foundation runs on CARE, it becomes the first testable instance of the Mirror Thesis. The thesis predicts that when AI executes all measurable tasks of a role, what becomes visible is the uniquely human contribution.

**What the mirror should reveal about the founder's contribution:**

1. **Ethical Judgment** — Deciding non-profit structure, irrevocable licensing, contributor protection
2. **Relationship Capital** — ASME/SBF council positions, IMDA relationships, university partnerships
3. **Contextual Wisdom** — Knowing CARE will resonate with Singapore government because of Smart Nation alignment
4. **Creative Synthesis** — The SDN control/data plane → organizational governance insight
5. **Emotional Intelligence** — Reading how government, enterprise, and community each need different framing
6. **Cultural Navigation** — Singapore CLG structure, ACRA requirements, unwritten rules of government partnerships

**Organizational maturity mirrors agent system maturity:**

| Foundation Phase | Agent System | Constraints |
|-----------------|-------------|-------------|
| Phase 1 (incorporation, 0-2 years) | Conservative templates | Every external communication held; financial constraints near zero |
| Phase 2 (10 Members) | Relaxed based on performance | Proven agent teams earn broader envelopes |
| Phase 3 (30 Members + 3 years) | High-trust templates | Agents operate with significant autonomy; human intervention based on Observation Advantage |

This alignment between constitutional governance phases and CARE trust evolution is structurally elegant — the constitution's phased governance is itself an expression of CARE Principle 7 (Evolutionary Trust).

---

## 3. Solo Founder: What Works and What's Dangerous

### What Works

- **Faster refinement loop** — Single human adjusts constraint envelopes immediately, no committee deliberation
- **No automation misuse** — Founder sets constraints and reviews patterns, not rubber-stamping 200 approvals/day
- **Concentrated contextual wisdom** — One person holds all institutional knowledge; envelopes can be precisely tuned

### What's Dangerous

- **Single point of failure** — Bus factor of one in the Trust Plane. If founder is unavailable, agents must halt or narrow to most conservative template. No external-facing output until the human returns.
- **No mirror on the mirror-holder** — The Mirror Thesis says "management deploys the mirror onto workers, not the reverse." Who mirrors the only manager? Genuine governance gap until Phase 2 (10 Members).
- **Observation fatigue** — Solo founder under time pressure may set constraints once and never revisit. The staleness problem.

### Mitigation

**Phase 1 → Phase 2 transition**: Publish agent configurations, constraint envelopes, and operational logs openly. External observers function as an informal Trust Plane check even before formal membership exists.

---

## 4. Dog-Fooding Credibility by Stakeholder

### Government (IMDA, MAS)
- **Risk**: "Is a Foundation run by agents accountable enough for policy collaboration?"
- **Framing**: "We demonstrate that human governance of AI agents is practical and transparent. Every consequential decision traces to a named human."

### Enterprise
- **Risk**: "Is CARE an academic exercise?"
- **Framing**: "Proof of concept at smallest viable scale. Our constraint envelope templates are battle-tested, not theoretical."

### Open-Source Community
- **Risk**: Minimal. Communities value transparency and operational honesty.
- **Opportunity**: Community can contribute to agent configurations, creating feedback loop.

### The Framing That Works Across All

"We are not replacing human governance with AI. We are demonstrating that human governance of AI agents produces better outcomes than either pure human operation or pure AI operation. The Trust Plane — accountability, values, boundaries — remains permanently human. The Execution Plane — drafting, research, validation, formatting — is shared with agents operating within human-defined constraints."

---

## 5. Constraint Dimensions Already Partially Implemented

| CARE Dimension | Existing COC Implementation | Gap |
|---------------|---------------------------|-----|
| Financial | Not implemented | Need explicit $0 / API cost caps |
| Operational | `rules/no-stubs.md`, `rules/constitution.md` (blocked actions) | Need formalization as CARE envelopes |
| Temporal | Not implemented | Need operating hours, blackout periods, review windows |
| Data Access | `rules/security.md` (PII, secrets, sensitive info) | Need explicit read/write scope per agent team |
| Communication | `rules/communication.md` (tone), hooks (validation) | Need explicit internal/external channel boundaries |

The existing rules are constraint envelopes in everything but name. Formalizing them requires:
1. Restructuring from prose rules to structured constraint envelope definitions
2. Adding the dimensions not currently covered (financial, temporal)
3. Implementing verification gradient evaluation at runtime
