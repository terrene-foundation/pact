# Todo 2401: Migrate Messaging to eatp.messaging

**Milestone**: M24 — EATP SDK Alignment
**Priority**: High
**Effort**: Medium
**Source**: EATP SDK alignment — messaging gap
**Dependencies**: 2101 (M21 complete)

## What

Replace the custom `care_platform.trust.messaging` implementation — which includes `MessageChannel`, `MessageRouter`, and `AgentMessage` cryptographic primitives — with `eatp.messaging.SecureChannel`. The CARE Platform must not re-implement EATP cryptographic primitives; it must delegate to the SDK.

Four EATP SDK gaps (M1-M4) identified during Phase 2 analysis require adapters because the SDK does not yet support them. These gaps must be bridged with thin adapter classes and marked with `# EATP-GAP: <gap-id>` comments so they are easy to find when the SDK adds the missing capability.

Keep the CARE-specific `MessageType` enum (it encodes CARE governance semantics that are outside EATP's scope). Keep the gap adapters. Remove all custom crypto.

## Where

- `src/care_platform/trust/messaging.py` — migrate to `eatp.messaging.SecureChannel`; retain `MessageType` enum; add gap adapters with `# EATP-GAP` markers

## Evidence

- [ ] No custom cryptographic operations (signing, verification, key exchange) remain in `messaging.py`
- [ ] `eatp.messaging.SecureChannel` is used for all message encryption and integrity
- [ ] `MessageType` enum is preserved with all CARE-specific values
- [ ] Exactly 4 gap adapter blocks present, each marked `# EATP-GAP: M1` through `# EATP-GAP: M4`
- [ ] All existing messaging unit tests pass against the migrated implementation
- [ ] Integration test: two agents exchange a signed message via the migrated channel; message integrity verified
