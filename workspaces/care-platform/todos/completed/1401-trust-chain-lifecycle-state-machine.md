# M14-T01: Trust chain lifecycle state machine

**Status**: ACTIVE
**Priority**: High
**Milestone**: M14 — CARE Formal Specifications
**Dependencies**: 1301-1304 (src layout)

## What

Add `TrustChainState` enum (DRAFT, PENDING, ACTIVE, SUSPENDED, REVOKED, EXPIRED) and `TrustChainStateMachine` with valid transitions and enforcement. Integrate with `GenesisManager` and `DelegationManager`.

Valid transitions: DRAFT→PENDING, PENDING→ACTIVE, PENDING→REVOKED, ACTIVE→SUSPENDED, ACTIVE→REVOKED, ACTIVE→EXPIRED, SUSPENDED→ACTIVE, SUSPENDED→REVOKED.

## Where

- New: `src/care_platform/trust/lifecycle.py`
- Modify: `src/care_platform/trust/genesis.py`, `src/care_platform/trust/delegation.py`

## Evidence

- Unit tests covering all valid transitions and rejection of invalid transitions
