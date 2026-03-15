# 301: Connect Trust Models to DataFlow for Persistent Storage

**Milestone**: 3 — Persistence Layer
**Priority**: High (trust without persistence is ephemeral)
**Estimated effort**: Large
**Depends on**: Milestone 2
**Completed**: 2026-03-12
**Verified by**: TrustStore protocol + MemoryStore + FilesystemStore in `care_platform/persistence/store.py`; 45 unit tests pass in `tests/unit/persistence/test_store.py`

## Description

Connect EATP trust models and platform state to DataFlow for structured, queryable, persistent storage. This replaces the MemoryStore (development-only) with durable storage.

## Tasks

- [ ] Design DataFlow schema for trust records:
  - Genesis Records table
  - Delegation Records table (with chain references)
  - Constraint Envelopes table (with version history)
  - Capability Attestations table
  - Audit Anchors table (with chain linking)
  - Revocation Records table
  - Verification Tokens table (short-lived cache)
  - Trust Scores table (computed, cacheable)
- [ ] Implement `FilesystemStore` (EATP SDK Phase 3):
  - JSON file-based storage for single-user/development
  - Same interface as MemoryStore and DataFlowStore
  - Suitable for Foundation's initial deployment
- [ ] Implement `DataFlowStore`:
  - DataFlow model definitions for all trust records
  - CRUD operations via DataFlow API
  - Query support (find by agent, by team, by date range)
- [ ] Implement storage abstraction:
  - `TrustStore` interface (abstract)
  - MemoryStore, FilesystemStore, DataFlowStore all implement it
  - Configurable via platform config (which store to use)
- [ ] Implement audit chain persistence:
  - Audit anchors stored with integrity proofs
  - Chain walk queries efficient (index on agent_id + timestamp)
- [ ] Implement migration support:
  - MemoryStore → FilesystemStore → DataFlowStore migration path
  - Data preserved across upgrades
- [ ] Write integration tests with FilesystemStore and MemoryStore

## Acceptance Criteria

- Trust records persist across platform restarts
- Query operations work (find delegation chain, audit history)
- Storage backend configurable
- Migration path tested
- Integration tests with FilesystemStore passing
