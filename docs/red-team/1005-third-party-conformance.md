# Red Team Finding 1005: Third-Party Implementation Governance

**Finding ID**: H-5
**Severity**: Medium (not urgent now, critical before Phase 2)
**Status**: RESOLVED -- conformance framework designed
**Date**: 2026-03-12

---

## Finding

Since the CARE, EATP, and CO standards are published under CC BY 4.0 and the CARE Platform is Apache 2.0, anyone can build commercial implementations. The question: how does the Foundation govern third-party conformance? What does "CARE-compatible" mean? Who decides? How is it tested?

## Risk/Impact

**Medium now, High at scale**. Without a conformance framework:

- Implementations claiming "CARE compliance" may implement only superficial features, diluting the brand
- Enterprises cannot distinguish genuine CARE governance from marketing claims
- The Foundation has no mechanism to protect the integrity of its standards

## Analysis

### Research: Existing Conformance Models

| Standard           | Conformance Approach                                                                                                  | Lessons                                                                             |
| ------------------ | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **OpenID Connect** | Certification program with automated test suite. Implementations must pass all tests. Foundation-verified.            | Gold standard for protocol conformance. Requires investment in test infrastructure. |
| **Kubernetes**     | Conformance testing via Sonobuoy. Self-certification with public results. CNCF-verified for commercial distributions. | Self-certification scales well; Foundation verification adds credibility.           |
| **FIDO Alliance**  | Formal certification with accredited labs. Multiple conformance levels.                                               | Too heavyweight for early-stage standards. Better for mature standards.             |
| **W3C**            | Test suites published alongside specifications. Browser vendors self-report results.                                  | Low barrier to entry; works for wide adoption.                                      |

### Proposed CARE Conformance Levels

Aligned with EATP's verification gradient and trust posture model:

| Level       | Name                        | Requirements                                                                                                                                               | What It Means                                                                                |
| ----------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **CARE-L1** | Basic Constraint Evaluation | Implements constraint envelope evaluation with at least 3 of 5 dimensions. Actions classified as allowed/denied.                                           | "This system evaluates agent actions against constraints before execution."                  |
| **CARE-L2** | Full Verification Gradient  | All 5 constraint dimensions. Four-level verification gradient (AUTO_APPROVED, FLAGGED, HELD, BLOCKED). Trust postures with evidence-based upgrades.        | "This system provides full EATP-grade governance with trust lifecycle management."           |
| **CARE-L3** | Full EATP Integration       | Complete 5-element trust chain (genesis record, delegation, constraint envelope, verification, audit anchor). Cascade revocation. Cryptographic integrity. | "This system provides cryptographically verifiable trust governance with full audit trails." |

### "CARE" Name Usage Policy

| Term                             | Meaning                        | Requirements                                                                              |
| -------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------- |
| **"Built with CARE principles"** | Inspired by CARE philosophy    | No formal requirements. Acknowledgment encouraged.                                        |
| **"CARE-L1 conformant"**         | Passes L1 conformance tests    | Must pass automated L1 test suite. Self-certification acceptable.                         |
| **"CARE-L2 conformant"**         | Passes L2 conformance tests    | Must pass automated L2 test suite. Self-certification with published results.             |
| **"CARE-L3 certified"**          | Full EATP integration verified | Must pass L3 test suite. Foundation-verified (when certification program is established). |

The Foundation should register "CARE" as a trademark in the agent governance context to protect against misuse, while keeping the specifications themselves under CC BY 4.0.

### Conformance Test Suite Requirements

Each conformance level requires an automated test suite that third-party implementations can run against their systems:

**L1 Test Suite**:

- Constraint envelope creation with at least 3 dimensions
- Action evaluation returning allow/deny decisions
- Constraint violation detection (action exceeding a dimension limit)
- Basic audit logging of evaluation decisions

**L2 Test Suite**:

- All L1 tests, plus:
- Five-dimension constraint envelopes (Financial, Operational, Temporal, Data Access, Communication)
- Verification gradient classification (AUTO_APPROVED, FLAGGED, HELD, BLOCKED)
- Trust posture lifecycle (upgrade with evidence, instant downgrade)
- ShadowEnforcer-equivalent observation mode
- Human approval queue for HELD actions

**L3 Test Suite**:

- All L2 tests, plus:
- Genesis record with cryptographic signing
- Delegation chain with monotonic constraint tightening
- Signed constraint envelopes (Ed25519 or equivalent)
- Audit anchor generation with integrity verification
- Cascade revocation (surgical and team-wide)
- Cross-reference verification (delegation chain integrity)

### Test Vectors

The CARE Platform repository should publish reference test vectors:

- Known constraint envelopes with expected evaluation results
- Known delegation chains with expected constraint tightening outcomes
- Known verification gradient inputs with expected classification levels
- Known trust posture evidence with expected upgrade/deny decisions

These serve as the canonical "correct answers" that any conforming implementation must produce.

### Self-Certification vs Foundation-Verified

| Phase                     | Approach                                          | Rationale                                                                                                |
| ------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **Now - Phase 2**         | Self-certification only                           | Foundation lacks capacity for formal verification. Publish test suites, let implementations self-report. |
| **Phase 2 (10 Members)**  | Self-certification + Foundation review on request | Members with domain expertise can review submissions.                                                    |
| **Phase 3 (30+ Members)** | Formal certification program                      | Certification committee, accredited test labs, periodic re-certification.                                |

## Conclusion

The conformance framework is designed with three levels (L1-L3) aligned to the EATP verification gradient. The approach scales from self-certification (appropriate for current Foundation capacity) to formal certification (appropriate at scale). The immediate action is to publish the conformance level definitions and begin building the L1 test suite alongside the CARE Platform implementation. L2 and L3 test suites naturally emerge from the CARE Platform's own test suite.
