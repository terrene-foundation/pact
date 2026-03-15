# EATP SDK Gaps — Flagged During Phase 3 Analysis

**Date**: 2026-03-14
**Updated**: 2026-03-14 (M24 EATP SDK Alignment — adapters implemented)
**Action**: These gaps should be addressed in the EATP SDK (`~/repos/kailash/kailash-py/packages/eatp/`), NOT reimplemented in the CARE Platform.

---

## Messaging Gaps (4)

| #   | Gap                                                                    | Current CARE Workaround                                    | Adapter Status | File & Location                                  |
| --- | ---------------------------------------------------------------------- | ---------------------------------------------------------- | -------------- | ------------------------------------------------ |
| M1  | No delegation_request / delegation_response message types              | CARE defines `MessageType` enum with domain-specific types | Adapter active | `src/care_platform/trust/messaging.py` ~L55-78   |
| M2  | No bounded nonce cache eviction strategy in `InMemoryReplayProtection` | CARE implements `BoundedNonceCache` with age+size eviction | Adapter active | `src/care_platform/trust/messaging.py` ~L81-115  |
| M3  | No thread-safe synchronous API (EATP is fully async)                   | CARE wraps in `threading.Lock`, sync `send()`/`receive()`  | Adapter active | `src/care_platform/trust/messaging.py` ~L241-270 |
| M4  | No agent revocation integration in SecureChannel                       | CARE's `MessageRouter.revoke_sender()` fills this gap      | Adapter active | `src/care_platform/trust/messaging.py` ~L432-510 |

## Revocation Gaps (6)

| #   | Gap                                                               | Current CARE Workaround                                                                   | Adapter Status | File & Location                                     |
| --- | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | -------------- | --------------------------------------------------- |
| R1  | No reparenting on surgical revocation (RT9-07)                    | CARE's `RevocationManager.surgical_revoke()` reparents children to grandparent            | Adapter active | `src/care_platform/trust/revocation.py` ~L309-370   |
| R2  | No cooling-off period / temporal re-delegation constraints        | CARE implements `can_redelegate()` with `min_cooling_off_hours`                           | Adapter active | `src/care_platform/trust/revocation.py` ~L591-610   |
| R3  | No CredentialManager integration (key/token revocation)           | CARE ties credential revocation to agent revocation via `CredentialManager`               | Adapter active | `src/care_platform/trust/revocation.py` ~L100, L325 |
| R4  | No persistent storage integration for revocation events           | CARE persists to `TrustStore` with hydration on startup                                   | Adapter active | `src/care_platform/trust/revocation.py` ~L173-223   |
| R5  | No delegation tree fallback when EATP bridge unavailable (RT7-04) | CARE maintains local delegation tree as fallback, hydrated from `TrustStore`              | Adapter active | `src/care_platform/trust/revocation.py` ~L225-268   |
| R6  | No dead-letter persistence for failed broadcasts                  | CARE logs broadcast failures; EATP SDK tracks dead letters in memory but does not persist | Adapter active | `src/care_platform/trust/revocation.py` ~L134-170   |

## Posture Gaps (4)

| #   | Gap                                                                | Current CARE Workaround                                                     | Adapter Status | File & Location                                                |
| --- | ------------------------------------------------------------------ | --------------------------------------------------------------------------- | -------------- | -------------------------------------------------------------- |
| P1  | No evidence-based upgrade model (TransitionGuard is callback-only) | CARE defines `PostureEvidence` with success rate, operations, incidents     | Adapter active | `src/care_platform/trust/posture.py` ~L94-130                  |
| P2  | No canonical NEVER_DELEGATED_ACTIONS set                           | CARE defines `NEVER_DELEGATED_ACTIONS` as a CARE-specific enforcement layer | Adapter active | `src/care_platform/trust/posture.py` ~L69-84                   |
| P3  | No ShadowEnforcer integration in posture transitions               | CARE requires `shadow_enforcer_pass_rate` in `PostureEvidence` for upgrades | Adapter active | `src/care_platform/trust/posture.py` ~L118, L163-178, L282-292 |
| P4  | No time-based upgrade prerequisites (days_at_current_posture)      | CARE enforces minimum time at each posture level via `UPGRADE_REQUIREMENTS` | Adapter active | `src/care_platform/trust/posture.py` ~L117, L154-174, L257-263 |

---

## M24 Integration Summary

All 14 gaps have been wrapped in thin adapters marked with `# EATP-GAP: <gap-id>`. Each adapter can be removed when the corresponding EATP SDK feature is implemented.

### What was migrated to EATP SDK

| CARE Component                             | EATP SDK Component Used                                     | Integration Type                                            |
| ------------------------------------------ | ----------------------------------------------------------- | ----------------------------------------------------------- |
| `messaging.py` — signing payload pattern   | `eatp.messaging.envelope.SecureMessageEnvelope`             | Import + `to_eatp_envelope()` method                        |
| `messaging.py` — replay protection concept | `eatp.messaging.replay_protection.InMemoryReplayProtection` | Import (referenced in docs; sync adapter wraps concept)     |
| `revocation.py` — event broadcasting       | `eatp.revocation.broadcaster.InMemoryRevocationBroadcaster` | Direct integration via `_broadcast_revocation_event()`      |
| `revocation.py` — event types              | `eatp.revocation.broadcaster.RevocationType`                | Direct use of EATP enum values                              |
| `revocation.py` — event model              | `eatp.revocation.broadcaster.RevocationEvent`               | Direct construction from CARE `RevocationRecord`            |
| `posture.py` — state machine               | `eatp.postures.PostureStateMachine`                         | Used for `upgrade()` and `downgrade()` transitions          |
| `posture.py` — transition requests         | `eatp.postures.PostureTransitionRequest`                    | Constructed from CARE evidence model                        |
| `posture.py` — posture enum                | `eatp.postures.TrustPosture`                                | Bidirectional mapping via `_CARE_TO_EATP` / `_EATP_TO_CARE` |
| `posture.py` — transition guards           | `eatp.postures.TransitionGuard`                             | Available for custom guard registration                     |
| `posture.py` — emergency downgrade         | `eatp.postures.PostureStateMachine.emergency_downgrade()`   | Used for PSEUDO_AGENT downgrades                            |

### What remains CARE-specific (by design)

These are CARE governance semantics that will remain even after the EATP SDK is extended:

1. **`MessageType` enum** (M1) — CARE governance vocabulary (DELEGATION_REQUEST, DELEGATION_RESPONSE, etc.)
2. **`NEVER_DELEGATED_ACTIONS`** (P2) — CARE-specific set of actions that must never be fully delegated
3. **Reparenting on surgical revocation** (R1) — CARE's RT9-07 governance requirement
4. **Cooling-off period** (R2) — CARE's temporal re-delegation constraint

---

## Gap Closure Requirements

For each gap, what the EATP SDK needs to add for the adapter to be removed:

### Messaging

| Gap    | EATP SDK Change Needed                                                                                                                                                                                                             |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **M1** | Add a `message_type` field to `SecureMessageEnvelope` or a `MessageType` registry that allows domain-specific type vocabularies. Even with this, CARE's specific type values (DELEGATION_REQUEST, etc.) will remain CARE-specific. |
| **M2** | Add proactive age-based eviction to `InMemoryReplayProtection.check_nonce()` (currently only evicts on explicit `cleanup_expired_nonces()` call) and expose a synchronous API.                                                     |
| **M3** | Add a synchronous wrapper or `SyncSecureChannel` class that wraps the async API with `threading.Lock` for use in non-async contexts.                                                                                               |
| **M4** | Add an `is_revoked(agent_id)` check in `SecureChannel.send()` and `SecureChannel.receive()`, consulting a `TrustRevocationList` or similar revocation-aware component.                                                             |

### Revocation

| Gap    | EATP SDK Change Needed                                                                                                                                                                                                     |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R1** | Add reparenting support to `CascadeRevocationManager` for surgical (non-cascade) revocations: when a node is removed, its children should be reparented to its parent.                                                     |
| **R2** | Add a `cooling_off_period` parameter to `CascadeRevocationManager` or `TrustRevocationList` that prevents re-delegation within a configurable time window after revocation.                                                |
| **R3** | Add a `CredentialProvider` protocol and integration point in `RevocationBroadcaster` or `CascadeRevocationManager` so that credential lifecycle events (token revocation) are triggered automatically on agent revocation. |
| **R4** | Add a persistent backend option for `RevocationBroadcaster` (e.g., `PersistentRevocationBroadcaster`) that stores events to the EATP `TrustStore` and hydrates on startup.                                                 |
| **R5** | Add a fallback delegation tree mechanism in `CascadeRevocationManager` that maintains a local cache of the delegation tree and uses it when the primary `DelegationRegistry` is unavailable.                               |
| **R6** | Add durable dead-letter persistence to `InMemoryRevocationBroadcaster` (currently in-memory only, lost on restart). Should integrate with `TrustStore` for persistence.                                                    |

### Posture

| Gap    | EATP SDK Change Needed                                                                                                                                                                                                                       |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P1** | Add a structured `TransitionEvidence` dataclass to the posture module that `TransitionGuard` callbacks can inspect, replacing the current untyped `metadata` dict approach. Should include: `success_rate`, `total_operations`, `incidents`. |
| **P2** | Add a `NeverDelegatedActions` registry to `PostureStateMachine` that blocks transitions to DELEGATED for configured action types, regardless of guard results.                                                                               |
| **P3** | Add a `ShadowEnforcerGuard` as a built-in `TransitionGuard` that checks `shadow_enforcer_pass_rate` in the transition evidence before allowing upgrades.                                                                                     |
| **P4** | Add a `MinimumTimeGuard` as a built-in `TransitionGuard` that enforces a minimum time at each posture level before upgrade is permitted. Should track `posture_since` per agent.                                                             |

---

## Phase 3 Approach

Until these gaps are addressed in the EATP SDK:

- CARE Platform uses EATP SDK where EATP has equivalent functionality (state machine, broadcasting, envelope model)
- CARE Platform keeps its own implementations ONLY for the 14 gaps above
- Each gap is wrapped in a clearly documented adapter with `# EATP-GAP: <gap-id>` markers
- When the EATP SDK adds a feature, the corresponding adapter can be removed by searching for its marker
