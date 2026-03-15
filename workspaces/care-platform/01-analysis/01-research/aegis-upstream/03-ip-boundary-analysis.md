# Aegis Upstream — IP Boundary Analysis

**Date**: 2026-03-14
**Source**: Open-source strategist analysis using Foundation anchor documents and constitution.

---

## Constitutional Framework

The Terrene Foundation constitution governs all IP decisions:

1. **All open-source IP is Foundation-owned** (fully transferred, irrevocable)
2. **The constitution prevents favoring any commercial entity** — including the Founder's commercial interests
3. **Apache 2.0 licensed code is irrevocably open** — anyone can build on it
4. **CLA required** before any code is accepted from external sources

---

## Per-Strength IP Assessment

### ZERO IP Risk (10 strengths)

These strengths are either spec-required, implementation-necessary, or standard software patterns with no proprietary content.

| ID  | Strength              | Risk | Rationale                                                               |
| --- | --------------------- | ---- | ----------------------------------------------------------------------- |
| S2  | Verification Gradient | ZERO | Spec-defined (EATP). Implementation is the canonical reference.         |
| S3  | Ed25519 Signing       | ZERO | Standard cryptographic patterns. Ed25519 is a public algorithm.         |
| S4  | Proximity Thresholds  | ZERO | Threshold values are implementation configuration, not IP.              |
| S5  | Shadow Enforcer       | ZERO | Spec concept (CARE). Shadow enforcement is a defined pattern.           |
| S6  | Circuit Breaker       | ZERO | Per-agent isolation is a standard resilience pattern.                   |
| S7  | Reasoning Traces      | ZERO | Spec-defined structure (EATP).                                          |
| S8  | Fail-Closed           | ZERO | Architectural discipline, not proprietary logic.                        |
| S9  | EATP Decorators       | ZERO | Python decorators wrapping spec-defined operations. No novel algorithm. |
| S11 | Dimension Adapter     | ZERO | Mapping between canonical names. Pure vocabulary alignment.             |
| S12 | Posture History       | ZERO | Append-only audit trail is a standard pattern.                          |

### MEDIUM IP Risk (2 strengths)

These strengths contain elements that need careful handling to avoid creating preferential treatment.

| ID  | Strength           | Risk   | Concern                                                                                                                                                                                                                | Mitigation                                                                                                                                                                                                                                                                                                                    |
| --- | ------------------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1  | Behavioral Scoring | MEDIUM | The 5-factor model with specific weights (25/25/20/15/15) and grade boundaries (A=90+, F=<60) could be seen as a proprietary algorithm. If upstreamed verbatim, it gives the Founder's commercial entity a head start. | **Define behavioral scoring in the CARE spec first** (CC BY 4.0) with independently-derived factor weights. The CARE Platform implementation then follows the spec, not the commercial implementation. Different weight distributions are acceptable as long as the factors and grade boundaries are independently justified. |
| S10 | Posture Adapter    | MEDIUM | Aegis uses display labels ("Pseudo/Supervised/Validated/Trusted/Autonomous") that may differ from CARE canonical names. Upstreaming Aegis-specific labels could enshrine one commercial vendor's vocabulary.           | **Use only CARE canonical posture names** (PSEUDO_AGENT, SUPERVISED, SHARED_PLANNING, CONTINUOUS_INSIGHT, DELEGATED). The adapter maps between these and EATP SDK identifiers. No vendor-specific display labels in the open platform.                                                                                        |

---

## Upstream Process Requirements

### CLA Requirement

Before ANY code flows from Aegis to the CARE Platform:

1. **Contributor License Agreement** must be signed — this transfers IP ownership to the Foundation
2. The CLA must cover all contributors who touched the relevant Aegis code
3. The Foundation's IP committee (when constituted) reviews the transfer

### Independent Implementation Requirement

For the two MEDIUM-risk items (S1, S10):

1. **S1 (Behavioral Scoring)**: Write the scoring algorithm section of the CARE spec first. Derive factor weights independently. The CARE Platform implementation follows the spec.
2. **S10 (Posture Adapter)**: Use only canonical CARE/EATP terminology. No Aegis-specific display labels.

### Anti-Favoritism Check

The Foundation constitution requires that no upstream creates structural advantage for any commercial entity. For each strength:

- **Does upstreaming this give any vendor a head start?** No — all 12 are foundational capabilities that any CARE implementation needs.
- **Does the implementation reveal proprietary business logic?** No — all 12 are infrastructure, not business logic.
- **Could withholding this create a competitive moat?** Yes — which is precisely why it should be open. The constitution's anti-rent-seeking provisions apply.

---

## Recommendation

**ALL 12 strengths: UPSTREAM to CARE Platform (Apache 2.0).**

- 10 with zero IP risk — proceed directly with CLA
- 2 with medium IP risk — define in spec first, implement independently in platform
- Zero strengths should be withheld — withholding would violate the Foundation's anti-rent-seeking mandate
