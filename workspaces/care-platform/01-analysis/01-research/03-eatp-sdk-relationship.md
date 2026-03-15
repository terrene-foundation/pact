# Phase 3 Research: EATP SDK Relationship

**Date**: 2026-03-14
**Source**: Codebase exploration of care_platform/trust/ (4.8K LOC) and eatp/ (15.3K LOC)

---

## Current Architecture

**Correct and intentional**: EATP SDK provides cryptographic trust primitives; CARE Platform layers governance on top.

```
CARE Platform (care_platform/trust/)      EATP SDK (eatp/)
├── eatp_bridge.py ─────────────────────→ operations/, chain.py, crypto.py
├── genesis.py ─────────────────────────→ GenesisRecord, generate_keypair
├── delegation.py ──────────────────────→ DelegationRecord
├── revocation.py                         revocation/broadcaster.py (unused)
├── shadow_enforcer.py                    (no equivalent)
├── posture.py                            postures.py (overlapping)
├── messaging.py                          messaging/ (duplicated)
├── credentials.py                        (no equivalent)
├── reasoning.py                          reasoning.py
├── uncertainty.py                        (CARE-specific)
├── integrity.py                          (extends chain concepts)
├── authorization.py                      (CARE-specific)
├── attestation.py                        (uses structures)
├── scoring.py                            (CARE-specific)
├── sd_jwt.py                             (independent)
├── lifecycle.py                          (CARE-specific)
├── jcs.py                                (independent)
└── dual_binding.py                       (independent)
```

## Overlaps (3 areas)

### 1. Messaging (HIGH overlap)

- CARE: Basic authenticated channels + replay protection (271 LOC)
- EATP: Comprehensive SecureChannel + signing/verification (6 files)
- **Recommendation**: Migrate to eatp.messaging. CARE's version is simpler and redundant.

### 2. Posture State Machine (MODERATE overlap)

- CARE: PSEUDO_AGENT → DELEGATED with upgrade requirements (236 LOC)
- EATP: PostureStateMachine with transition guards (734 LOC)
- **Recommendation**: Align. CARE's upgrade logic becomes guards in EATP's state machine.

### 3. Revocation (MODERATE overlap)

- CARE: Surgical & cascade via delegation tree (500 LOC)
- EATP: Pub/sub RevocationBroadcaster with TrustRevocationList
- **Recommendation**: Keep CARE's RevocationManager (credential integration is CARE-specific). Integrate with EATP's RevocationBroadcaster for event publishing.

## CARE-Specific (No Extraction Needed)

- GenesisManager lifecycle (DRAFT → PENDING → ACTIVE)
- DelegationManager with monotonic tightening
- ShadowEnforcer
- VerificationGradient & middleware
- Credentials, authorization, attestation integration
- All config schema integration

## Phase 3 Action Items (~1 week)

1. Migrate care_platform.trust.messaging → eatp.messaging.SecureChannel (2-3 days)
2. Integrate RevocationManager with eatp.revocation.RevocationBroadcaster (2-3 days)
3. Align posture upgrade logic with eatp.postures.PostureStateMachine (1-2 days)
