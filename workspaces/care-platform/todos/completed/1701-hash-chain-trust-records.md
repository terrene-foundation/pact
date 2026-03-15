# M17-T01: Cryptographic integrity — hash-chain trust records

**Status**: ACTIVE
**Priority**: High
**Milestone**: M17 — Gap Closure: Integrity & Resilience
**Dependencies**: 1601-1605 (M16 complete)

## What

Trust chain records (genesis, delegations) are plain DB rows with no chaining or tamper detection. Add hash chaining: each delegation includes hash of previous record, forming Merkle-like structure. Add tamper detection via periodic integrity verification.

## Where

- Modify: `src/care_platform/trust/delegation.py` (add `previous_record_hash`)
- Modify: `src/care_platform/persistence/sqlite_store.py` (store/verify hashes)
- New: `src/care_platform/trust/integrity.py` (TrustChainIntegrity verifier)

## Evidence

- Test: tamper with delegation record → integrity check catches it
- Test: append new delegation → hash chain valid
