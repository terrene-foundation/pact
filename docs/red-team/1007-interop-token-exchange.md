# Red Team Finding 1007: EATP Interoperability Token Exchange

**Finding ID**: Future Extension
**Severity**: Low (Phase 1), Medium (Phase 2+)
**Status**: DOCUMENTED -- future extension, not needed for Phase 1
**Date**: 2026-03-12

---

## Finding

EATP v2.2 defines interoperability token exchange formats for integration with existing identity and authorization systems. While not needed for the Foundation's single-organization deployment, this capability is important for enterprise adoption and multi-organization trust scenarios.

## Risk/Impact

**Low for Phase 1**. The CARE Platform's initial scope is single-organization governance. Token exchange is only needed when:

- Enterprises want to integrate CARE-governed agents with their existing IAM systems
- Multiple organizations need to establish cross-boundary trust for agent delegation
- Regulatory bodies require interoperable audit formats

**Medium for Phase 2+**. Without token exchange, enterprise adoption faces integration friction. Organizations already using OAuth2/JWT for authorization would need to run parallel systems.

## Analysis

### Supported Token Formats (Priority Order)

| Format                                            | Priority | Use Case                                     | Rationale                                                                                                                                                  |
| ------------------------------------------------- | -------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **JWT** (JSON Web Tokens)                         | High     | API authentication, service-to-service trust | Most widely adopted. Every enterprise IAM system supports JWT. Needed for CARE Platform API integration.                                                   |
| **W3C Verifiable Credentials**                    | High     | Regulatory compliance, government interop    | Growing adoption in government and regulated industries. Regulatory alignment. Supports selective disclosure.                                              |
| **SD-JWT** (Selective Disclosure JWT)             | Medium   | Privacy-preserving credential exchange       | Allows sharing only the claims needed for a specific verification. Important for multi-org scenarios where full constraint envelopes should not be shared. |
| **UCAN** (User Controlled Authorization Networks) | Medium   | Decentralized delegation chains              | Natural fit for EATP delegation chains. Content-addressed, no central authority needed. Aligns with EATP's design philosophy.                              |
| **DID** (Decentralized Identifiers)               | Low      | Agent identity across organizations          | Useful for persistent agent identity in multi-org scenarios. Not needed for single-org deployment.                                                         |
| **Biscuit**                                       | Low      | Capability-based authorization tokens        | Interesting for fine-grained capability delegation. Less mature ecosystem than JWT/VC.                                                                     |

### Token Exchange Interfaces

When implemented, the following mappings would enable EATP trust artifacts to interoperate with standard authorization systems:

#### EATP Trust Chain to JWT

```
EATP Genesis Record
    --> JWT claim: "iss" (issuer = genesis record holder)
    --> JWT claim: "sub" (subject = agent ID)
    --> JWT claim: custom "eatp:trust_chain" (array of delegation hops)

EATP Delegation Chain
    --> JWT claim: custom "eatp:delegations" (array)
    --> Each delegation includes: delegator, delegate, constraints, signature

EATP Constraint Envelope
    --> JWT claim: custom "eatp:constraints" (object)
    --> Maps to: {financial: {...}, operational: {...}, temporal: {...}, data_access: {...}, communication: {...}}
```

#### EATP Constraint Envelope to OAuth2 Scopes

```
Financial dimension (budget: $100/day)
    --> OAuth2 scope: "eatp:financial:100usd_daily"

Operational dimension (allowed: [draft, edit])
    --> OAuth2 scope: "eatp:ops:draft eatp:ops:edit"

Communication dimension (external: held)
    --> OAuth2 scope: "eatp:comm:internal_only"
```

This mapping is lossy -- OAuth2 scopes are string-based and lack the formal structure of constraint envelopes. The mapping works for basic authorization but cannot express monotonic tightening or verification gradient semantics.

#### EATP Audit Anchor to W3C Verifiable Credential

```
EATP Audit Anchor
    --> W3C VC type: "EATPAuditCredential"
    --> VC claim: action, agent, result, timestamp
    --> VC proof: Ed25519 signature (same key material as EATP)
    --> VC issuer: Genesis record holder DID
```

This is the highest-fidelity mapping. W3C Verifiable Credentials support the same cryptographic proof structure that EATP uses, and the credential model naturally maps to audit anchors.

### Cross-Organizational Trust

When EATP delegation chains cross organizational boundaries, token exchange becomes the mechanism for establishing inter-org trust:

1. **Organization A** has an EATP-governed agent team
2. **Organization B** needs to delegate a task to Organization A's agents
3. Organization B issues a **cross-org delegation** with constraints
4. The delegation is expressed as a **W3C Verifiable Credential** or **JWT** that Organization A's EATP runtime can verify
5. Organization A's agents operate under the **intersection** of their own constraints and Organization B's delegation constraints (monotonic tightening across organizational boundaries)

This pattern extends EATP's single-org delegation model to multi-org scenarios without changing the core trust semantics. The constraint envelope evaluation remains the same; only the source of constraints changes.

### Implementation Roadmap

| Phase                     | What                             | Why                                                                                                                                      |
| ------------------------- | -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Phase 1** (current)     | No token exchange needed         | Single-organization deployment. EATP trust chain is self-contained.                                                                      |
| **Phase 2** (10 Members)  | JWT exchange for API integration | Enables CARE Platform API to accept JWT-authenticated requests. Enables CARE-governed agents to call external APIs with JWT credentials. |
| **Phase 2+**              | W3C VC for audit export          | Enables exporting audit anchors as Verifiable Credentials for regulatory compliance and external verification.                           |
| **Phase 3** (30+ Members) | Full token exchange suite        | SD-JWT for privacy-preserving multi-org delegation. UCAN for decentralized delegation chains. DID for persistent agent identity.         |

## Conclusion

EATP interoperability token exchange is a well-understood extension that builds naturally on the existing trust model. It is not needed for Phase 1 (single-organization governance) but becomes important for enterprise adoption and multi-organization trust in Phase 2+. The highest-priority formats are JWT (ubiquitous enterprise adoption) and W3C Verifiable Credentials (regulatory interoperability). The exchange interfaces are designed but implementation is deferred to the phase where they become necessary.
