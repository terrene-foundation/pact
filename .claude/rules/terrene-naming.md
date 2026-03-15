# Terrene Foundation Naming

## Scope

These rules apply to ALL new content and edits in this repository.

## Rules

### Foundation Name

The Foundation is **Terrene Foundation** (Singapore CLG).

- Domain: `terrene.foundation`
- Developer portal: `terrene.dev`
- GitHub org: `terrene-foundation`

### Foundation Independence

The Foundation is a fully independent entity. There is NO structural relationship between the Foundation and any commercial entity.

1. **All open-source IP was fully and irrevocably transferred to the Foundation**
2. **Kailash Python SDK is Foundation-owned** (Apache 2.0) — not "contributed by" or "licensed from" any entity
3. **The constitution prevents open-washing, rent-seeking, and self-interest** by ANY contributor
4. **Anyone can build commercial products on Foundation standards** — that is the intended model
5. **No contributor has exclusive rights, special access, or structural advantage**
6. **Never describe any commercial entity as having a "partnership" or "relationship" with the Foundation** — contributors operate under a uniform contributor framework
7. **The Founder contributes as an individual** — their commercial activities are separate from their Foundation role
8. **The Founder's conflict of interest is managed by constitutional mechanisms** — disclosure requirements, transaction caps, recusal protocols

See `rules/independence.md` for the full no-commercial-coupling policy.

### License Accuracy

- Specifications (CARE, EATP, CO, CDI): **CC BY 4.0** (NOT CC-BY-SA — ShareAlike would prevent proprietary implementations)
- Open source code (Kailash Python, EATP SDK, CO Toolkit, CARE Platform): **Apache 2.0**
- BSL 1.1 is **NOT** open source — use "source-available" or "open-core"

### Canonical Terminology

- CARE planes: **Trust Plane** + **Execution Plane** (NOT operational/governance plane)
- Constraint dimensions: **Financial, Operational, Temporal, Data Access, Communication** (these exact five names — no synonyms, no reordering)
- CO = Cognitive Orchestration (domain-agnostic base methodology)
- COC = Cognitive Orchestration for Codegen (CO applied to software development — the "C" already means "for Codegen")
- CO sits in the trinity: CARE (philosophy) + EATP (protocol) + CO (methodology)

### CARE Platform Terminology

**Platform identity:**

- **CARE Platform** = governed operational model (configuration + methodology + constraint templates), NOT a generic agent orchestrator
- "CARE specification" = the CARE standard itself (CC BY 4.0) — the philosophy and requirements
- "CARE Platform" = the Foundation's reference implementation of that specification (Apache 2.0) — code, configuration, constraint templates
- Never conflate the two: the specification defines what; the platform implements how

**Verification gradient levels** (exact names, uppercase):

- **AUTO_APPROVED** — action falls within all constraint dimensions
- **FLAGGED** — action is near a boundary
- **HELD** — action exceeds a soft limit, queued for human approval
- **BLOCKED** — action violates a hard constraint

**Trust postures** (exact names, uppercase):

- **PSEUDO_AGENT** — minimal autonomy, maximum oversight
- **SUPERVISED** — agent executes under close human supervision
- **SHARED_PLANNING** — human and agent plan together, agent executes
- **CONTINUOUS_INSIGHT** — agent operates autonomously, human monitors
- **DELEGATED** — full delegation within constraint envelope

**Cross-Functional Bridges** (exact names):

- Bridge types: **Standing**, **Scoped**, **Ad-Hoc** (these exact names)
- Use "Cross-Functional Bridge" — NOT "cross-team bridge" or "inter-team connector"

**Workspace terminology:**

- Use "workspace-as-knowledge-base" — NOT "knowledge workspace" or "knowledge base workspace"

### EATP Operations Terminology

**Four operations** (uppercase, used as verbs or nouns):

- **ESTABLISH** — create a trust root (Genesis Record)
- **DELEGATE** — extend trust to another entity (Delegation Record)
- **VERIFY** — check trust chain validity
- **AUDIT** — review trust lineage for compliance

**Five Trust Lineage Chain elements** (exact names):

- **Genesis Record** — trust origin, signed by the establishing authority
- **Delegation Record** — trust extension from one entity to another
- **Constraint Envelope** — five-dimensional boundary for agent actions
- **Capability Attestation** — declaration of what an agent can do
- **Audit Anchor** — cryptographic proof of trust state at a point in time

**ShadowEnforcer** — one word, PascalCase (NOT "shadow enforcer", "Shadow Enforcer", or "shadow mode")

### CO as Methodology

The Foundation publishes CO as an open methodology under CC BY 4.0. The Foundation does NOT sell methodology consulting. Publishing open methodologies is consistent with the Foundation mandate.
