# Aegis Upstream — Standards Alignment Analysis

**Date**: 2026-03-14
**Source**: CARE/EATP/CO standards expert analysis of all 12 Aegis foundational strengths.

---

## Alignment Categories

### Already Required by Open Specs (6 strengths)

These features are defined or implied by the published CARE/EATP specifications (CC BY 4.0). Any CARE implementation MUST have them.

| ID  | Strength              | Spec Requirement                                                                                                                                                                                                                                             |
| --- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| S2  | Verification Gradient | EATP spec defines 4-level gradient (AUTO_APPROVED, FLAGGED, HELD, BLOCKED). Posture-aware rules are a spec requirement.                                                                                                                                      |
| S3  | Ed25519 Signing       | EATP spec requires cryptographic trust lineage. Ed25519 is the canonical signing algorithm. Dual-signature and multi-sig are protocol-level requirements for audit anchors and multi-authority envelopes.                                                    |
| S5  | Shadow Enforcer       | CARE spec defines ShadowEnforcer as a spec concept. Recording enforcement decisions without blocking is a defined trust posture operation.                                                                                                                   |
| S7  | Reasoning Traces      | EATP spec requires reasoning traces for delegations and posture transitions. The trace structure (decision, rationale, evidence, methodology, confidence) is spec-defined.                                                                                   |
| S8  | Fail-Closed           | CARE philosophy requires fail-closed behavior. The EATP verification gradient requires unknown states to resolve to most-restrictive. This is foundational to the trust model.                                                                               |
| S9  | EATP Decorators       | EATP spec defines VERIFY, AUDIT, and shadow operations. Decorators are the natural DX expression of these operations. The 3-decorator migration path (`@shadow` -> `@audited` -> `@verified`) maps directly to the EATP gradual trust establishment pattern. |

### Spec-Required, Implementation-Quality (3 strengths)

These features are implied by the specs but the specific implementation approach is a quality decision.

| ID  | Strength                  | Analysis                                                                                                                                                                                                                                         |
| --- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| S4  | Proximity Thresholds      | EATP defines constraint dimensions and verification gradient. The specific threshold values (0.70/0.90/1.00) are implementation decisions, but having configurable thresholds is spec-required for the gradient to function.                     |
| S6  | Per-Agent Circuit Breaker | CARE requires that agent failures don't cascade to other agents (isolation is a trust model requirement). Per-agent isolation is the correct implementation of this requirement. A global circuit breaker violates the CARE isolation principle. |
| S12 | Posture History           | EATP requires audit trails for posture transitions. The specific trigger taxonomy and append-only guarantee are implementation quality, but the capability is spec-required.                                                                     |

### Enhancements Beyond Spec (3 strengths)

These features are valuable but not strictly required by current specs. They extend the platform beyond minimum spec compliance.

| ID  | Strength           | Analysis                                                                                                                                                                                                                                                                                |
| --- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1  | Behavioral Scoring | EATP defines trust scoring for chain structural quality. Behavioral scoring (agent performance over time) is an enhancement. It complements structural scoring but is not spec-required. However, the CARE philosophy of "trust is earned through demonstrated behavior" supports this. |
| S10 | Posture Adapter    | The CARE and EATP specs use consistent terminology, so an adapter is not strictly required. However, as multiple implementations emerge, vocabulary drift is inevitable. An adapter prevents it.                                                                                        |
| S11 | Dimension Adapter  | Same rationale as S10 — prevents vocabulary drift across implementations of the five constraint dimensions.                                                                                                                                                                             |

---

## Key Standards Finding

**S9 (EATP Decorators) is the highest-priority gap.** The EATP spec defines VERIFY, AUDIT, and shadow as core operations. Every other spec operation has a programmatic interface in the CARE Platform — but these three lack the natural decorator expression. This is the difference between:

```python
# Without decorators (current)
def process_invoice(agent_id, invoice):
    trust_ops = get_trust_operations()
    result = trust_ops.verify(agent_id, "process_invoice")
    if result.level == VerificationLevel.BLOCKED:
        raise TrustViolationError(...)
    # ... actual logic
    trust_ops.create_audit_anchor(agent_id, "process_invoice", result)

# With decorators (S9)
@care_verified(action="process_invoice", agent_id_param="agent_id")
@care_audited(agent_id_param="agent_id")
def process_invoice(agent_id, invoice):
    # ... actual logic only
```

The decorator approach makes EATP enforcement a one-line concern rather than boilerplate in every trust-sensitive function.

---

## Recommendation

All 12 strengths align with CARE/EATP specifications and philosophy. None contradict the open standards. The 6 spec-required features should be treated as compliance gaps. The 3 implementation-quality features improve correctness. The 3 enhancements improve developer experience and prevent vocabulary drift.
