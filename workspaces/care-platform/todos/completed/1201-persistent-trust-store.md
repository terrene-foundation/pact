# 1201: Persistent TrustStore — Durable Trust State

**Priority**: Critical
**Effort**: Large
**Source**: RT3 Theme A (all 4 agents flagged)
**Dependencies**: M2 (trust objects exist), M3 (DataFlow schemas exist)

## Problem

All trust state (genesis records, delegations, constraint envelopes, attestations, audit chains) lives in Python dictionaries. A process restart loses the Foundation's entire trust history.

## Implementation

Create `care_platform/persistence/trust_store.py`:

- SQLite-backed persistent store for trust objects
- Store/load genesis records, delegation records, constraint envelopes
- Store/load capability attestations and their revocation status
- Append-only audit anchor persistence
- Integration point for EATPBridge to use persistent storage
- Migration support for schema evolution

## Acceptance Criteria

- [ ] Trust state survives process restart
- [ ] Audit anchors are append-only (cannot modify or delete)
- [ ] Constraint envelope history is preserved (versioned)
- [ ] Tests verify persistence and recovery
