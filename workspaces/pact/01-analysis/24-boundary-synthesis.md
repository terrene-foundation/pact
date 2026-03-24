# Boundary Synthesis: PACT (Open) vs Commercial Implementations

**Date**: 2026-03-21
**Inputs**: Deep analysis (#18), Requirements (#19), COC analysis (#20), Value audit (#21), Repivot synthesis (#22), Open/commercial boundary (#23), Aegis capability mapping, commercial features deep dive
**Decision**: Unified analysis resolving both the repivot and the open/commercial boundary

---

## The Organizing Principle

**Single-organization governed autonomy is open. Multi-organization trust coordination is commercial.**

This maps to a real complexity cliff. Running AI agents under governance within one organization requires correct primitives. Coordinating trust across organizational boundaries requires distributed consensus, compliance certification, and operational infrastructure that single-org deployments never need. Nobody resents paying for multi-tenant trust orchestration.

---

## Where We Came From (Aegis Origin Story)

Aegis (518 files, 241K lines) was the original shadow enterprise — the first implementation of governed AI operations. The governance patterns that define PACT today **originated in Aegis**:

- Shadow Enforcer (what-if enforcement testing)
- Verification Gradient (4-zone classification)
- Trust Scoring (5-factor behavioral model)
- Constraint Envelope Composition (3-layer with monotonic tightening)
- Posture Adapter (5-level trust progression)

These patterns were extracted from Aegis and formalized as the PACT specification (CC BY 4.0) + reference implementation (Apache 2.0). The extraction was correct — these are domain-agnostic governance primitives, not commercial features.

**What Aegis kept** (commercial differentiators):

- Stripe billing with metered usage, subscription tiers, and webhook processing
- Self-hosted licensing with phone-home validation and offline grace periods
- Multi-tenancy with org isolation and runtime provisioning
- Enterprise auth (SSO via Azure AD/Google/Okta/Auth0, scoped API keys, SCIM)
- RBAC/ABAC policy engines (attribute-based, not envelope-based)
- Agent pools with routing policies and lifecycle management
- Compliance automation (SOC2 evidence, HIPAA, immutable audit with hash chaining)
- Integration connectors (Slack, Discord, Teams, Telegram, Notion)
- Distributed infrastructure (Redis pubsub, distributed locking, tiered caching)
- SDK for consumers (`aegis_sdk/` with trust, revenue, and execution operations)

---

## Capability-by-Capability Boundary

### Open (PACT — everything one org needs)

| Capability                        | Status                 | Notes                                                      |
| --------------------------------- | ---------------------- | ---------------------------------------------------------- |
| D/T/R Grammar Engine              | PACT more spec-aligned | Aegis uses implicit supervisor chains; should adopt PACT's |
| Operating Envelopes (3-layer)     | Both complete          | Functionally identical implementations                     |
| Knowledge Clearance (5-level)     | Both complete          | PACT lightweight; Aegis has embeddings/versioning          |
| Verification Gradient (4-zone)    | Both complete          | Aegis richer (posture adaptation); PACT sufficient         |
| Constraint Enforcement            | Both complete          | Different architectures, comparable completeness           |
| Shadow Enforcer                   | Both complete          | Aegis more features; PACT sufficient for framework         |
| EATP Integration                  | Both complete          | PACT delegates to trust-plane (better reuse)               |
| GovernanceEngine facade           | PACT                   | Single entry point, thread-safe, fail-closed               |
| API Server (governance endpoints) | PACT                   | 15 endpoints, sufficient for single-org                    |
| Dashboard                         | PACT                   | Next.js, 20+ pages, governance visualization               |
| Execution Runtime                 | PACT                   | Agent registry, approval queue, session management         |
| Observability                     | PACT                   | Alerting, logging, Prometheus metrics                      |
| Organization Builder              | PACT                   | YAML-based, templates, CLI                                 |
| Example Verticals                 | PACT                   | University, Foundation                                     |
| Docker Deployment                 | PACT                   | Reference deployment                                       |
| SQLite + In-memory Stores         | PACT                   | Sufficient for single-org                                  |

### Commercial (enterprise scale features)

| Capability                 | In Aegis?         | Notes                                                  |
| -------------------------- | ----------------- | ------------------------------------------------------ |
| Multi-tenancy              | Yes (production)  | Org isolation, user management, runtime provisioning   |
| SSO/SCIM                   | Yes (production)  | Azure AD, Google, Okta, Auth0                          |
| Billing/Licensing          | Yes (production)  | Stripe, phone-home, feature gating, subscription tiers |
| RBAC/ABAC Policy Engine    | Yes (production)  | Different model from PACT envelopes — attribute-based  |
| Agent Pools/Routing        | Yes (production)  | Task distribution, claiming, load balancing            |
| Agent Lifecycle Management | Yes (production)  | Provisioning, health, scaling                          |
| Compliance Automation      | Yes (production)  | SOC2 evidence, HIPAA, immutable audit                  |
| Cross-org Trust Bridging   | Partial           | Distributed audit, cascade revocation                  |
| Integration Connectors     | Yes (5 platforms) | Slack, Discord, Teams, Telegram, Notion                |
| Distributed Infrastructure | Yes               | Redis pubsub, distributed locking, tiered cache        |
| Consumer SDK               | Yes               | Client library for trust, revenue, execution ops       |
| Advanced LLM Management    | Yes               | Multi-provider routing, cost tracking, 2026 pricing    |

### Gray Zone (judgment calls)

| Capability                  | Recommendation | Rationale                                                                       |
| --------------------------- | -------------- | ------------------------------------------------------------------------------- |
| PostgreSQL store backend    | **Open**       | Single-org production needs a real DB. Without it, PACT isn't production-grade. |
| Basic webhook notifications | **Open**       | Notifying operators of governance events is fundamental.                        |
| Constraint caching          | Commercial     | Only needed at enterprise scale.                                                |
| Config versioning/diffing   | Commercial     | Enterprise audit requirement. Single-org uses git.                              |
| Trust Scoring (behavioral)  | Commercial     | Autonomous posture evolution is an enterprise feature.                          |

---

## How the Repos Relate After Repivot

```
PACT Specification (CC BY 4.0)
    defines the standard
         |
         v
kailash-pact (Apache 2.0, in kailash-py)
    governance primitives as a pip-installable library
    D/T/R, envelopes, clearance, gradient, stores, CLI
         |
         v
    +----+----+
    |         |
    v         v
PACT repo    Commercial implementations
(Apache 2.0) (proprietary)
    |         |
    |         +-- Aegis (enterprise platform)
    |         +-- Future: any vendor
    |
    +-- Reference deployment
    +-- API server + dashboard
    +-- Execution runtime
    +-- Example verticals (university, foundation)
    +-- Docker deployment
    +-- Trust layer (deprecated, pending EATP merge)
```

**PACT repo is not a library.** It is a deployable product — the canonical reference deployment that evaluators clone, run, and judge. The library is kailash-pact (in kailash-py). The product is this repo.

**Aegis should eventually import kailash-pact** instead of maintaining parallel governance code. Two areas where Aegis should adopt PACT's implementations: (1) D/T/R grammar (PACT's explicit addressing is more spec-aligned than Aegis's implicit supervisor chains), (2) constraint envelopes (functionally identical, no reason to maintain two).

---

## What This Means for the Repivot

The boundary analysis reinforces the repivot plan:

1. **Keep everything in PACT that a single org needs** — API server, dashboard, execution runtime, examples, deployment. Don't strip it down to a library wrapper.

2. **The trust layer stays** — It's battle-tested (10+ red team rounds). Even though EATP is merging into kailash core, the trust patterns here are production-proven. Mark as deprecated but don't rush removal.

3. **Add PostgreSQL store backend** — Without it, PACT forces production users to SQLite or immediately to a commercial product. This is the strategist's strongest recommendation.

4. **The "reference implementation" framing is correct** — It establishes the spec as primary, gives commercial implementations a clear relationship ("built on PACT standards"), and sets quality expectations. Reference implementation does NOT mean minimal — PostgreSQL is a reference SQL implementation and it is production-grade.

---

## Positioning Summary

|                          | PACT                                | Commercial (e.g., Aegis)                     |
| ------------------------ | ----------------------------------- | -------------------------------------------- |
| **License**              | Apache 2.0 (irrevocable)            | Proprietary                                  |
| **Owner**                | Terrene Foundation                  | Any commercial entity                        |
| **Scope**                | Single-org governed autonomy        | Multi-org trust coordination at scale        |
| **Relationship to spec** | IS the reference implementation     | Built ON the specification                   |
| **Target user**          | Developers, single-org operators    | Enterprise teams, multi-tenant platforms     |
| **Value prop**           | "Run governed AI agents correctly"  | "Run governed AI agents at enterprise scale" |
| **Boundary test**        | "Does this need more than one org?" | Everything that does                         |
