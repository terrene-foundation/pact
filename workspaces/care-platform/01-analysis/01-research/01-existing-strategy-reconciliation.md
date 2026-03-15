# Existing Strategy Reconciliation

**Date**: 2026-03-11
**Source**: Open-source strategist analysis + existing strategy documents
**Status**: Critical finding — must be resolved before proceeding

---

## The Discovery

The CARE Platform brief proposes a new product layer without referencing existing strategy work that already covers this layer in detail. Two strategy documents in `workspaces/shadow-enterprise/` contain comprehensive, stress-tested analysis:

1. **`workspaces/shadow-enterprise/briefs/02-open-source-strategy.md`** — 657-line strategic memo defining a four-layer architecture (Specs → SDKs → Platform → Verticals) with detailed Community/Enterprise boundary analysis, pricing, competitive positioning, risk analysis, and implementation roadmap.

2. **`workspaces/shadow-enterprise/01-analysis/01-research/01-aegis-community-enterprise-boundary.md`** — 506-line boundary analysis covering: what Community must include, what justifies Enterprise pricing, the BSL 1.1 vs Apache 2.0 question, competitive moat, and self-governance credibility testing.

Both were produced by three independent specialist agents and refined through subsequent analysis.

---

## Where the CARE Platform Brief and Existing Strategy CONVERGE

| Aspect | CARE Platform Brief | Existing Strategy | Alignment |
|--------|-------------------|------------------|-----------|
| Four-layer architecture | Specs → SDKs → Agent Platform → Verticals | Specs → SDKs → Platform → Verticals | Same |
| Foundation self-governance | Core use case | "Shadow Enterprise" initiative | Same concept, different name |
| Single-org vs multi-org boundary | Implied (Foundation = single-org) | Explicitly analyzed and stress-tested | Compatible |
| Dog-fooding | "Foundation runs on its own platform" | "Self-governance credibility test" | Same |
| Open model | Foundation publishes open standards and platform | Same | Same |
| DM as first application | Explicit | Not specified (broader scope) | Extension |

**The CARE Platform brief and the Shadow Enterprise initiative are the same vision from different angles.** The existing strategy provides the architectural framework. The CARE Platform brief provides the operational specificity (starting with DM).

---

## Where They DIVERGE

| Aspect | CARE Platform Brief | Existing Strategy | Conflict |
|--------|-------------------|------------------|----------|
| **Platform name** | "CARE" (Apache 2.0) | Previously used "Community Edition" framing (BSL 1.1 → Apache 2.0) | Naming conflict — resolved: CARE |
| **License** | Apache 2.0 (stated without analysis) | BSL 1.1 recommended (3 options analyzed) | Needs resolution |
| **Publisher** | Foundation | Foundation | Aligned |
| **Scope** | Agent orchestration + governance + operations | Governance platform (EATP-specific) | Scope question |

---

## Resolution Recommendations

### 1. Name: CARE (Decision Made)

The open-source strategist recommended against naming the platform "CARE" due to legal ambiguity, SEO collision, and competitive confusion. However, the founder has decided to proceed with "CARE" as an intentional brand consolidation — the philosophy manifests as the platform.

**Disambiguation policy**: Use "CARE specification" or "CARE Framework" for the CC BY 4.0 governance spec. Use "CARE Platform" or just "CARE" for the open-source operational model. The platform README will state the dual meaning upfront.

**Implication**: All Foundation operational model content moves to the care-platform workspace.

### 2. License: Align with Existing Analysis

The existing boundary analysis recommends:
- **Foundation publishes**: Apache 2.0 (consistent with Foundation principles, maximum adoption)
- **Do NOT use BSL 1.1** (narrative tension for a non-profit standards body)

The CARE Platform is Foundation-owned. All Foundation open-source IP was fully and irrevocably transferred to the Foundation. Apache 2.0 is the correct licence — consistent with Foundation principles and maximum adoption.

### 3. Scope: Governed Orchestration, Not Generic Orchestration

The existing strategy positions the platform as an EATP-native governance platform, not a general-purpose agent orchestrator. The competitive landscape analysis confirms this is the only viable differentiation:

- LangChain has 80K+ GitHub stars and 4+ years of community
- CrewAI raised $18M
- Microsoft and Google have infinite resources
- A solo founder cannot compete on generic orchestration

**The viable position**: EATP-native governance middleware that works alongside or on top of existing frameworks. Think "EATP governance for LangChain" rather than "replacement for LangChain."

The DM team is the first *application* running on this governed orchestration layer — not a reason to build a competing orchestration framework.

---

## What This Means for the CARE Platform Workspace

The CARE Platform workspace should **reconcile with and build on** the existing shadow-enterprise strategy, not replace it. Specifically:

1. Adopt the existing four-layer architecture
2. Use the existing Community/Enterprise boundary (single-org vs multi-org)
3. Resolve the naming question (use CARE — Foundation's open platform)
4. Add the DM team design as the first operational application
5. Add the "workspace-as-knowledge-base" concept (not in existing strategy)
6. Add the Foundation-as-first-deployer operationalization plan

---

## Key Files

- `workspaces/shadow-enterprise/briefs/02-open-source-strategy.md`
- `workspaces/shadow-enterprise/01-analysis/01-research/01-aegis-community-enterprise-boundary.md`
- `workspaces/care-platform/briefs/01-care-platform-brief.md`
