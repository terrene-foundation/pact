# 106: Create Capability Attestation Model

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (EATP Element 4 — missing from original plan)
**Estimated effort**: Medium

## Description

Implement Capability Attestation — the signed declaration of what an agent is authorized to do. This is Element 4 of EATP's five-element Trust Lineage Chain, created alongside the Genesis Record during the ESTABLISH operation. Without Capability Attestation, there is no verifiable record of each agent's authorized scope.

## Tasks

- [ ] Define `care_platform/trust/attestation.py`:
  - `CapabilityAttestation` model:
    - Attestation ID
    - Agent ID (who this attests)
    - Capabilities list (specific actions the agent is authorized to perform)
    - Constraint envelope reference (the boundaries within which capabilities apply)
    - Issuer (who created this attestation — typically the delegator)
    - Valid from / Valid until (time-bounded)
    - Signature (cryptographic, from issuer)
  - `AttestationRegistry` — Stores and queries active attestations
- [ ] Implement attestation creation (part of ESTABLISH operation):
  - Created by delegator when establishing an agent
  - Must be consistent with the agent's constraint envelope (capabilities cannot exceed envelope)
  - Signed by the delegator
- [ ] Implement attestation validation:
  - Verify signature integrity
  - Check expiry
  - Verify capabilities are subset of constraint envelope
- [ ] Implement capability drift detection:
  - Compare agent's actual actions against attested capabilities
  - Flag actions that fall outside attestation scope
- [ ] Write unit tests for:
  - Attestation creation and signing
  - Validity checking (valid, expired, tampered)
  - Capability-envelope consistency validation
  - Drift detection

## Acceptance Criteria

- Capability Attestation model complete with all fields
- Attestation signing and verification working
- Capability-envelope consistency enforced
- Drift detection identifies out-of-scope actions
- Unit tests passing

## Why This Was Missing

The EATP expert review identified that Capability Attestation (Element 4) was entirely absent from the original plan. The five EATP Trust Lineage Chain elements are:
1. Genesis Record
2. Delegation Record
3. Constraint Envelope
4. **Capability Attestation** (this todo)
5. Audit Anchor

## References

- EATP Core Thesis: Trust Lineage Chain elements
- EATP Trust Lineage spec: Capability Attestation (lines 177-212)
