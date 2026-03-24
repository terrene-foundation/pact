# Open/Commercial Boundary Analysis

**Date**: 2026-03-21
**Author**: Open Source Strategist
**Inputs**: PACT codebase (156 files, ~48K lines), Aegis codebase (518 files, ~241K lines), Foundation anchor documents (IP ownership, value model, IP strategy), repivot synthesis (#22), PACT independence rules
**Purpose**: Define the rational boundary between Foundation-owned open source (PACT) and commercial implementation (Aegis) in the governed AI operations space

---

## Executive Summary

The current state has two products that share a common ancestry and compete in the same conceptual space -- "governed AI operations" -- without a clearly articulated boundary. This analysis proposes a boundary model based on what actually works in successful open-core ecosystems, adapted to the unique constraint that the Foundation has **no structural relationship** with any commercial entity.

The recommended boundary: **PACT is a complete, production-grade single-organization governance system. Commercial implementations add multi-tenancy, compliance certification, and operational scale.**

This is the "feature gate, not performance gate" principle applied to organizational complexity rather than technical capability.

---

## I. Lessons from Successful Open-Core Models

### What works

Every successful open-core company has found the same structural insight: the open layer must be **genuinely useful in production** to create adoption, while the commercial layer must address problems that **only emerge at organizational scale**.

| Project                  | Open Layer                                      | Commercial Layer                                             | Boundary Principle                                 |
| ------------------------ | ----------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------- |
| **GitLab**               | Complete CI/CD, repos, issue tracking           | Advanced security scanning, compliance, portfolio management | Individual team vs. enterprise portfolio           |
| **Grafana**              | Full monitoring stack, dashboards, alerting     | Cloud hosting, enterprise plugins, SLA support               | Self-hosted vs. managed; single-team vs. cross-org |
| **HashiCorp** (pre-BSL)  | Terraform, Vault, Consul core                   | Sentinel policy-as-code, governance, audit                   | Single operator vs. organizational policy          |
| **Supabase**             | Full Postgres + Auth + Storage + Edge Functions | Point-in-time recovery, SSO, SOC2, dedicated instances       | Developer vs. enterprise compliance                |
| **PostgreSQL / Aurora**  | Complete database                               | Managed operations, replication, auto-scaling                | Software vs. operated service                      |
| **Kubernetes / GKE/EKS** | Full orchestration                              | Managed control plane, SLA, integrated observability         | Software vs. operated service                      |

### What fails

| Anti-Pattern                              | Example                                     | Why It Fails                                     |
| ----------------------------------------- | ------------------------------------------- | ------------------------------------------------ |
| **Crippleware**                           | Limiting API calls, throttling free tier    | Creates resentment; developers route around it   |
| **Core-feature gating**                   | Requiring enterprise license for basic auth | Open layer cannot demonstrate value              |
| **Source-available masquerading as open** | BSL/SSPL calling itself "open source"       | Community distrust; forking risk                 |
| **Too-generous open**                     | Elastic pre-license-change                  | Commercial entity cannot differentiate           |
| **Moving the boundary post-adoption**     | HashiCorp BSL switch, Redis re-license      | Destroys trust; invites forks (OpenTofu, Valkey) |

### The pattern that works for this space

For **governance/trust/compliance** products specifically, the winning boundary is:

> Open: Everything one organization needs to govern its own AI agents.
> Commercial: Everything needed when multiple organizations, compliance regimes, or operational teams must coordinate trust.

This maps directly to a real complexity boundary. Nobody resents paying for multi-tenant trust orchestration, cross-organization cascade revocation, SOC2 evidence collection, or HIPAA compliance automation. These are inherently enterprise problems that a single-org deployment never encounters.

---

## II. Current State Assessment

### What PACT currently contains (48K lines across 156 files)

**Governance layer** (`src/pact/governance/`, 24 files):

- GovernanceEngine (single entry point, thread-safe, fail-closed)
- D/T/R grammar engine with positional addressing
- Three-layer envelope composition (Role/Task/Effective) with monotonic tightening
- Knowledge clearance (5 levels, posture ceilings, vetting status)
- Cross-functional bridges (Standing, Scoped, Ad-Hoc)
- Access control with knowledge share policies
- Governance context (frozen snapshots for agents)
- Governance API endpoints
- In-memory stores with thread safety and bounded collections
- Audit integration (EATP audit anchors for all mutations)

**Trust layer** (`src/pact/trust/`, 28 files):

- EATP bridge (genesis, delegation, attestation, audit anchors)
- Constraint envelope evaluation (5 dimensions)
- Verification gradient (AUTO_APPROVED/FLAGGED/HELD/BLOCKED)
- Shadow enforcer (live and comparison modes)
- Trust scoring
- Posture management (5 trust postures)
- SD-JWT credentials
- Cryptographic integrity (Ed25519 signing, HMAC)
- Store backends (filesystem, SQLite)
- Store isolation (multi-org key isolation)
- Resilience patterns (circuit breaker)
- Authorization and lifecycle

**Execution layer** (`src/pact/use/execution/`, 13 files):

- ExecutionRuntime with verification pipeline
- Agent registry and selection
- Approval queue for HELD actions
- Posture enforcement
- Hook enforcer
- Kaizen bridge
- LLM backend abstraction
- Session management

**API layer** (`src/pact/use/api/`, 5 files):

- FastAPI server with WebSocket events
- Governance dashboard endpoints
- Graceful shutdown

**Observability** (`src/pact/use/observability/`, 4 files):

- Alerting, logging, metrics

**Build/Config** (`src/pact/build/`, 14+ files):

- Organization builder (from YAML/templates)
- Configuration schema (528 lines, gravitational center)
- CLI, templates, workspace management, vertical bootstrapping

### What Aegis adds beyond PACT (241K lines across 518 files)

**Multi-tenancy and identity** (~40 files):

- Organization, user, team, role models with database persistence
- User authentication (JWT, SSO, SCIM)
- Invitation and email verification
- API key management
- RBAC and ABAC policy engines
- Feature gating by subscription tier (Free/Starter/Professional/Enterprise)
- License validation with phone-home

**Billing and commercial** (~15 files):

- Stripe integration (subscriptions, invoices, webhooks)
- Usage tracking and quotas
- Tier-based feature availability
- License server and validation
- Pricing configuration (per-provider LLM costs)

**Agent platform** (~65 files):

- Agent pools with routing policies
- Agent lifecycle manager (provisioning, health, scaling)
- Agent messaging (inter-agent communication)
- Objective decomposition and execution
- Request/session management
- Artifact collection and decision tracking
- Finding and review workflow
- SSE streaming for real-time updates
- External agent integration
- Coordinator agent
- Task decomposition service

**Advanced trust and governance** (~30 files):

- Distributed lock service
- Tiered cache (constraint and verification caching)
- Circuit breakers for constraints and verification
- Trust chain state machine
- Trust alerting and backup
- Cryptographic chain service
- Immutable audit service with SOC2 evidence
- HIPAA compliance service
- Bridge boundary enforcement with data channels
- Bridge lifecycle scheduling
- Envelope state machine with version diffing
- Config versioning
- Constraint signing and resolution
- Trust event service
- Cascade revocation

**Operational infrastructure** (~25 files):

- Analytics service
- Metrics and Prometheus middleware
- Notification system (channels, publisher, service)
- Webhook delivery with retry
- Connector framework (Slack, Discord, Teams, Telegram, Notion)
- Deployment service and logging
- Scaling policies and events
- Pipeline management (nodes, connections)
- Gateway service

**SDK for consumers** (`aegis_sdk/`, ~20 files):

- Client library with auth module
- Trust operations (audit, chains, delegations, postures)
- Revenue operations (invoices, licenses, plans, quotas, subscriptions, usage)
- Execution operations (objectives, requests, sessions)

---

## III. Recommended Boundary

### The organizing principle

**Single-organization governed autonomy is open. Multi-organization trust coordination is commercial.**

This principle is clean because it maps to a real-world complexity cliff. Running AI agents under governance within one organization is a fundamentally different problem from coordinating trust, compliance, and policy across organizational boundaries. The single-org case requires correct governance primitives. The multi-org case requires distributed consensus, conflict resolution, regulatory compliance, and operational infrastructure that single-org deployments never need.

### What belongs in PACT (open, Foundation-owned)

Everything a single organization needs to run governed AI agents in production:

**1. Complete governance framework (already present)**

- D/T/R grammar, envelope composition, knowledge clearance, verification gradient
- GovernanceEngine as the single entry point
- Cross-functional bridges within one organization
- Governance context for agents
- In-memory and SQLite stores

**2. Complete trust layer (already present)**

- Full EATP trust chain (genesis, delegation, attestation, audit)
- All five constraint dimensions with evaluation
- Shadow enforcer in both modes
- Trust postures and scoring
- Ed25519 signing, HMAC integrity
- Filesystem and SQLite store backends

**3. Execution runtime (already present)**

- Task submission, agent selection, verification pipeline
- Approval queue for HELD actions
- Posture enforcement
- Session management

**4. API server and dashboard (already present)**

- FastAPI endpoints for governance operations
- WebSocket real-time events
- Dashboard data endpoints

**5. Observability (already present)**

- Alerting, logging, metrics at the single-org level

**6. Organization builder (already present)**

- YAML-based org definition
- Template system
- CLI for bootstrapping

**7. Example verticals (partially present)**

- University example (in progress)
- Foundation example (self-dogfooding)

### What belongs only in commercial implementations

The problems that emerge when governance crosses organizational boundaries or enters regulated production:

**1. Multi-tenancy**

- Organization isolation with database-backed persistence
- User management, invitation flows, team membership
- Per-tenant configuration and resource isolation
- Tenant-aware store backends (PostgreSQL, distributed)

**2. Identity and access management**

- SSO (SAML, OIDC)
- SCIM provisioning
- API key lifecycle management
- Advanced RBAC and ABAC policy engines
- Session management across organizations

**3. Commercial operations**

- Subscription management and billing
- Usage metering and quotas
- Feature gating by tier
- License validation

**4. Cross-organization trust**

- Cross-org trust bridging (trust between separate organizational trust chains)
- Multi-org cascade revocation (revoking trust across organizational boundaries)
- Distributed audit storage (shared audit trails between organizations)
- Cross-org envelope negotiation and conflict resolution

**5. Compliance automation**

- SOC2 evidence collection and reporting
- HIPAA compliance automation
- Immutable audit logs with cryptographic chaining (beyond single-org audit anchors)
- Regulatory reporting

**6. Operational scale**

- Agent pools with routing policies
- Agent lifecycle management (provisioning, scaling, health monitoring)
- Distributed locking
- Tiered caching for constraints and verification
- Circuit breakers at enterprise scale
- Multi-region deployment
- SLA monitoring

**7. Integration ecosystem**

- Connector framework (Slack, Discord, Teams, Telegram, Notion)
- Webhook delivery with retry and monitoring
- Pipeline management
- External agent integration

**8. Enterprise agent platform**

- Objective decomposition with task routing
- Agent messaging across teams
- Artifact collection and review workflows
- SSE streaming for operational dashboards
- Decision audit trails with sign-off

### The gray zone -- items that require judgment

Some capabilities sit at the boundary and could reasonably go either way. Here is the analysis for each:

| Capability                            | Recommendation                       | Rationale                                                                                                        |
| ------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| **PostgreSQL store backend**          | Open                                 | Single-org production needs a real database, not just SQLite. Without this, PACT is not production-grade.        |
| **Basic RBAC** (role-based, not ABAC) | Open                                 | Single-org needs basic access control. Keep it simple: role-to-permission mapping.                               |
| **Prometheus metrics export**         | Open                                 | Standard observability. Every production deployment needs this.                                                  |
| **Basic webhook notifications**       | Open                                 | Notifying operators of governance events is fundamental.                                                         |
| **Agent pools**                       | Commercial                           | Pool routing is a multi-team/multi-org scaling problem. Single-org with a few agents uses the registry directly. |
| **Constraint caching**                | Commercial                           | Only needed at enterprise scale. Single-org evaluates constraints directly.                                      |
| **Config versioning and diffing**     | Commercial                           | Version control of governance config is an enterprise audit requirement. Single-org uses git.                    |
| **LLM provider management**           | Open (basic) / Commercial (advanced) | Basic: use one provider from .env. Advanced: multi-provider routing, cost tracking, failover.                    |

---

## IV. Risk Assessment

### Risk 1: PACT is too capable -- commercial implementations cannot differentiate

**Probability**: Low with the recommended boundary.

PACT already contains the complete governance framework and trust layer. This is intentional and correct. The governance primitives (D/T/R, envelopes, clearance, gradient) are the specification in code form. Making them proprietary would be like making HTTP proprietary -- it undermines the entire ecosystem play.

The differentiation for commercial implementations is not "better governance primitives" but "governance at organizational scale": multi-tenancy, compliance automation, agent lifecycle management, and operational infrastructure. These are genuinely hard problems that single-org deployments never encounter.

**Mitigation**: The boundary test is clear: "Does this capability require more than one organization?" If yes, it is commercial territory. If no, it belongs in the open layer.

**Historical validation**: PostgreSQL is enormously capable. Aurora, RDS, Supabase, and Neon all thrive commercially by providing managed operations, scale, and compliance on top of it. Kubernetes is enormously capable. GKE, EKS, and AKS all thrive commercially by providing managed control planes, SLA guarantees, and enterprise integrations on top of it.

### Risk 2: PACT is too minimal -- cannot demonstrate value

**Probability**: High if the recommended boundary is violated by removing execution runtime or API server.

An evaluator who clones PACT and runs `docker compose up` must see a working governance system: the dashboard showing D/T/R structure, agents operating within envelopes, the verification gradient classifying actions, the approval queue holding actions for human review, the audit trail recording decisions. If any of these are missing, PACT is an SDK, not a product.

**The "reference implementation" framing helps here**: PACT is the reference deployment. Evaluators judge the car, not the engine on a stand. The car must drive.

**Mitigation**: PACT must include the API server, dashboard, execution runtime, and at least two example verticals. The repivot synthesis (#22) correctly identifies this as the repo's identity: "the canonical deployment that shows how a PACT-governed organization runs."

### Risk 3: The boundary moves after adoption (license rug-pull)

**Probability**: Near-zero, structurally prevented.

The Foundation constitution prevents this. All Foundation-owned IP is irrevocably open under Apache 2.0. The Foundation cannot change the license of existing code. It cannot move features from open to proprietary. The constitution's anti-rent-seeking clauses prevent any contributor from extracting exclusive value from Foundation assets.

This is the Foundation's strongest competitive advantage. In a landscape where HashiCorp switched to BSL, Redis switched to dual-license, and Elastic switched to SSPL, a constitutionally-locked Apache 2.0 commitment is a genuine trust signal for enterprises evaluating long-term dependencies.

### Risk 4: A competitor forks PACT and builds a competing commercial product

**Probability**: Certain, by design.

This is not a risk -- it is the intended model. The Foundation's value model document (anchor doc #04) explicitly describes this:

> "Anyone can build commercial products on Foundation standards -- that is the intended model."

The Foundation's response to forks is not prevention but velocity: make the Foundation's standards, SDKs, and reference implementation so good and so actively maintained that building on them is easier than forking and diverging. The CNCF did not prevent Google, Amazon, and Microsoft from building commercial Kubernetes products. It made Kubernetes so good that all three chose to build on it rather than compete with it.

### Risk 5: Foundation independence is violated by implicit coupling

**Probability**: Medium, requires ongoing vigilance.

The independence rules in the PACT codebase are comprehensive and well-enforced. But the risk is more subtle than code-level coupling. It manifests in:

- **Feature prioritization**: If PACT's roadmap is driven by what a specific commercial implementation needs rather than what the standard requires and the community contributes, independence is violated in practice even if the code is clean.
- **API design**: If PACT's extension points are designed with one specific commercial implementation in mind, they may be suboptimal for other implementers.
- **Release timing**: If PACT releases are coordinated with a commercial product's release schedule, independence is violated.

**Mitigation**: The Foundation should have a public roadmap driven by the PACT specification, community contributions, and ecosystem needs. Feature requests from any commercial implementer should be evaluated on their merits for the ecosystem, not on the identity of the requester.

---

## V. Positioning: "Reference Implementation" vs. Alternatives

### Why "reference implementation" is the right framing

The term "reference implementation" serves three critical functions:

**1. It establishes the specification as primary.** PACT-the-specification (CC BY 4.0) defines what governed AI operations means. PACT-the-code (Apache 2.0) proves the specification is implementable and demonstrates the correct behavior. This is the relationship between the HTTP specification and Apache httpd, between the SQL standard and PostgreSQL, between the Kubernetes API specification and the Kubernetes codebase.

**2. It gives commercial implementations a clear relationship.** A commercial implementation is not "a better PACT" or "PACT with extras." It is "a commercial product built on PACT standards." This language prevents the "open-source version of X" framing that undermines Foundation independence.

**3. It sets quality expectations.** A reference implementation must be correct, complete, and well-tested. It is the arbiter of ambiguity in the specification. When two implementations disagree, the reference implementation is consulted. This creates a quality floor that benefits the entire ecosystem.

### Comparison with analogous ecosystems

| Standard       | Reference Implementation | Commercial Products                 | Relationship                                                                  |
| -------------- | ------------------------ | ----------------------------------- | ----------------------------------------------------------------------------- |
| HTTP/2         | nghttp2                  | Every web server and CDN            | Commercial products implement the spec; reference validates correctness       |
| Kubernetes API | kubernetes/kubernetes    | GKE, EKS, AKS, Rancher              | Commercial products embed and extend; reference defines the contract          |
| OpenTelemetry  | OTel Collector           | Datadog, New Relic, Grafana         | Commercial products consume the protocol; reference validates interop         |
| PACT spec      | PACT (this repo)         | Any commercial governed-AI platform | Commercial products implement PACT governance; reference defines the standard |

### What "reference implementation" does NOT mean

- It does NOT mean "minimal" or "toy." PostgreSQL is a reference SQL implementation and it is production-grade.
- It does NOT mean "not suitable for production." The reference implementation should be deployable in production by organizations that do not need multi-tenancy or compliance automation.
- It does NOT mean "starter edition." There is no upgrade path from PACT to a commercial product. They are independent products that share the same standards foundation.

---

## VI. How Foundation Independence Interacts

### The structural separation

The Foundation owns PACT. Any commercial entity -- including any entity founded by the same person who founded the Foundation -- builds commercial products independently. The Foundation has no equity in, revenue from, or governance relationship with any commercial entity.

This means:

**1. PACT's roadmap is not Aegis's roadmap.** If a feature is good for PACT users and the ecosystem, build it. If it only serves one commercial implementation, do not build it. The Foundation's value model document says this explicitly: all feature decisions are driven by "what PACT users need, what the standards require, and what the community contributes."

**2. Code flows one direction: from PACT outward.** Commercial implementations depend on Foundation standards and may depend on Foundation SDKs. The Foundation's code never depends on, references, or is designed for any commercial implementation. The independence rules in PACT's codebase enforce this at the code level.

**3. Any commercial entity can build on PACT.** The Apache 2.0 license explicitly permits this. The CC BY 4.0 license on the specifications explicitly permits this. The Foundation's constitution explicitly supports this. Aegis is one possible commercial implementation. There could be others. The Foundation is indifferent to which ones exist.

**4. The Founder's dual role is managed by constitutional mechanisms.** The Founder contributes to the Foundation as an individual. Their commercial activities are separate. Conflict of interest is managed through disclosure requirements, transaction caps, and recusal protocols defined in the constitution.

### Why this structure actually works

The historical evidence is clear: foundations that maintain genuine independence create more valuable ecosystems than foundations that are captured by a single commercial entity.

- **Linux Foundation / CNCF**: Kubernetes is genuinely independent. Google, Amazon, and Microsoft all build commercial products on it. The ecosystem is worth hundreds of billions of dollars.
- **Apache Software Foundation**: Apache httpd, Kafka, Spark are genuinely independent. Multiple commercial entities build on each. The ecosystem thrives.
- **Eclipse Foundation**: Jakarta EE is genuinely independent. Multiple commercial Java EE vendors compete on top of it.

Contrast with foundations that lack genuine independence:

- **Docker Inc / Moby**: Docker's commercial interests drove the open-source project's roadmap. The ecosystem fragmented (Podman, containerd, CRI-O).
- **MongoDB Inc / SSPL**: MongoDB re-licensed to prevent cloud providers from building commercial products. The community split.

The Terrene Foundation's constitutional protections (77 clauses, anti-rent-seeking, anti-open-washing) are designed to prevent the second pattern.

---

## VII. Specific Recommendations

### 1. Keep the API server and dashboard in PACT

These are not "enterprise features." They are the product surface that makes PACT evaluable. Removing them turns PACT from a product into a library. Libraries do not win mindshare against products.

### 2. Add a PostgreSQL store backend to PACT

SQLite is fine for development and small deployments. But a production single-org deployment needs a real database. Without PostgreSQL support, PACT forces production users to either (a) use SQLite in production (not recommended), or (b) immediately jump to a commercial implementation. This creates an artificial barrier that undermines the "genuinely useful in production" requirement.

### 3. Keep LLM provider management minimal in PACT

PACT should support configuring one LLM provider via `.env`. Multi-provider routing, cost tracking, failover, and provider-specific optimizations are enterprise-scale problems. This is a clean boundary that maps to real user needs: a single organization typically uses one or two LLM providers; an enterprise platform managing agents for multiple teams or customers needs provider abstraction.

### 4. Do not add agent pools or agent lifecycle management to PACT

The agent registry pattern in PACT (register agents, select by capability, execute) is correct for single-org use. Pool routing, scaling policies, health monitoring, and lifecycle management are operational infrastructure problems that only emerge at enterprise scale.

### 5. Do not add compliance automation to PACT

SOC2 evidence collection, HIPAA compliance, and regulatory reporting are expensive to build, expensive to maintain, and valuable specifically because of their certification implications. These are natural commercial territory. PACT provides the audit trail that compliance automation consumes, which is the correct open/commercial interface.

### 6. Publish a clear extension point architecture

PACT should document how commercial implementations extend it:

- Store backends (protocol/interface for swapping in PostgreSQL, distributed stores)
- Middleware hooks (where commercial implementations inject multi-tenancy, RBAC, feature gating)
- Audit consumers (how compliance automation reads the audit trail)
- Envelope extensions (how commercial implementations add cross-org envelope negotiation)

This makes it easy for any commercial entity to build on PACT without requiring PACT to be aware of any specific implementation.

### 7. Ship two example verticals with PACT

The university and foundation examples are the right approach. They prove the framework is domain-agnostic (the boundary test) and give evaluators something concrete to explore. A governance framework without examples is abstract to the point of being unadoptable.

---

## VIII. Summary: The Boundary in One Table

| Capability                                                        | PACT (Open)                            | Commercial                          |
| ----------------------------------------------------------------- | -------------------------------------- | ----------------------------------- |
| **Governance primitives** (D/T/R, envelopes, clearance, gradient) | Full                                   | Extends                             |
| **Trust chain** (genesis, delegation, attestation, audit)         | Full                                   | Extends with cross-org              |
| **Constraint evaluation** (5 dimensions, all operations)          | Full                                   | Adds caching/distribution           |
| **Verification gradient** (4 zones, shadow enforcer)              | Full                                   | Adds at-scale patterns              |
| **Execution runtime** (single-org task pipeline)                  | Full                                   | Adds pools, routing, lifecycle      |
| **API server + dashboard**                                        | Full (single-org)                      | Adds multi-tenant, SSO              |
| **Store backends**                                                | Memory, filesystem, SQLite, PostgreSQL | Adds distributed, multi-tenant      |
| **Observability**                                                 | Logging, metrics, basic alerting       | Adds Prometheus, advanced analytics |
| **Organization builder**                                          | Full (YAML, templates, CLI)            | Adds config versioning, diffing     |
| **Example verticals**                                             | 2 domain examples                      | Production verticals                |
| **Multi-tenancy**                                                 | --                                     | Full                                |
| **Identity management** (SSO, SCIM, API keys)                     | --                                     | Full                                |
| **Billing and licensing**                                         | --                                     | Full                                |
| **Cross-org trust bridging**                                      | --                                     | Full                                |
| **Cascade revocation** (multi-org)                                | --                                     | Full                                |
| **Compliance automation** (SOC2, HIPAA)                           | --                                     | Full                                |
| **Agent pools and routing**                                       | --                                     | Full                                |
| **Distributed infrastructure** (locking, caching)                 | --                                     | Full                                |
| **Integration connectors** (Slack, Teams, etc.)                   | --                                     | Full                                |

The boundary is clean, defensible, and maps to real-world complexity. Single-organization governed autonomy is open and free. Multi-organization trust coordination is where commercial value lives.

---

## IX. Constraints and Caveats

**This analysis is written for the Foundation.** It advises on the open/commercial boundary from the Foundation's perspective. The Foundation does not control, advise, or coordinate with any commercial entity. If a commercial entity finds this analysis useful for their own product strategy, that is their prerogative, but the Foundation's responsibility ends at ensuring PACT is excellent.

**The independence rules in PACT's codebase are correct and should be maintained.** This analysis does not change them. The PACT codebase should never reference, compare with, or design against any specific commercial product. The boundary recommendations above are for strategic guidance, not for inclusion in the codebase.

**Timing matters.** The repivot (analysis #22) correctly identifies that the migration to kailash-py must complete before this boundary can be operationalized. The boundary analysis assumes the target architecture: governance framework in kailash-pact (pip-installable), deployment reference in this repo.

**The boundary will evolve.** As AI governance matures and as the ecosystem grows, some capabilities currently classified as commercial may become table-stakes expectations for any governance system. The Foundation should be prepared to move capabilities from commercial territory into the open layer when the ecosystem demands it. The key principle: the open layer expands over time, it never contracts.
