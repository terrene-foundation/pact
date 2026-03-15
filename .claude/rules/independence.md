# Foundation Independence Rules

## Scope

These rules apply to ALL files in this repository — code, documentation, configuration, comments, commit messages, and agent conversations.

## MUST Rules

### 1. CARE Platform Is a Standalone Foundation Product

CARE Platform is owned by the Terrene Foundation (Singapore CLG). It is an independent open-source product. All design decisions must be made on CARE Platform's own merits — what is best for its users and the open-source community.

### 2. No Commercial References

MUST NOT reference, discuss, compare with, or design against any commercial or proprietary product in any file in this repository. This includes:

- Proprietary product names (do not name them, do not compare against them)
- Proprietary SDKs or runtimes (do not reference Rust SDKs or proprietary frameworks)
- Commercial entities (no company names, no commercial partnerships)
- Market positioning or competitive differentiation (not a concern of this project)
- Commercial deployment models (managed hosting, enterprise pricing, SaaS)

**Why**: CARE Platform is Foundation-owned and irrevocably open. It has no structural relationship with any commercial entity. Introducing commercial references — even for comparison — creates implicit coupling and suggests a relationship that does not exist.

**How to apply**: If you find yourself writing "unlike X" or "the open-source version of Y" or "differentiates from Z" — stop. Describe what CARE Platform does on its own terms. If a feature is good for CARE Platform users, build it. If it isn't, don't. The existence or non-existence of any other product is irrelevant.

### 3. Foundation-Only Dependencies

CARE Platform MUST depend only on:

- **Terrene Foundation open-source packages**: Kailash Python SDK (Core, DataFlow, Nexus, Kaizen), EATP SDK, trust-plane
- **Standard open-source libraries**: From PyPI, with OSI-approved licenses
- **Open standards**: CARE, EATP, CO (CC BY 4.0)

MUST NOT depend on, import from, or interface with any proprietary SDK, runtime, or API.

### 4. No "Open-Source Version Of" Language

MUST NOT describe CARE Platform as:

- "The open-source version of [anything]"
- "The open-source counterpart to [anything]"
- "The community edition of [anything]"

CARE Platform IS the product. It is not a derivative, counterpart, or edition of something else.

**Correct**: "CARE Platform is the Terrene Foundation's open-source governed operational model."
**Incorrect**: "CARE Platform is the open-source version of [product name]."

### 5. Design for CARE Platform Users

All feature decisions, architectural choices, and roadmap priorities must be driven by:

- What CARE Platform users need
- What the CARE, EATP, and CO standards require
- What the open-source community contributes

Never by what any other product does, doesn't do, or plans to do.

## MUST NOT Rules

### 1. No Proprietary Codebase Awareness

Code, comments, and documentation MUST NOT demonstrate awareness of any proprietary codebase. Do not:

- Reference proprietary file paths, module names, or architecture patterns
- Suggest "compatibility" or "interop" with proprietary systems
- Design APIs "so that [proprietary product] can also use them"

### 2. No Commercial Strategy Discussion

MUST NOT discuss in any file:

- Revenue models, pricing, or monetization
- Enterprise vs community feature splits
- Commercial licensing considerations
- Market competition or positioning

### 3. No Cross-Codebase Coupling

MUST NOT:

- Share code, interfaces, or protocols designed for a specific proprietary product
- Create abstractions whose primary purpose is proprietary product compatibility
- Design extension points that assume a specific proprietary implementation

## Clarification

Third parties — anyone, anywhere — may build commercial products on top of CARE Platform and Foundation standards. That is the intended open-source model. But CARE Platform itself has zero knowledge of, zero dependency on, and zero design consideration for any such product. If someone builds on CARE Platform, they adapt to CARE Platform — not the other way around.
