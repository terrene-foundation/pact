# 204: Implement Constraint Envelope Signing and Verification

**Milestone**: 2 — EATP Trust Integration
**Priority**: High (cryptographic enforcement)
**Estimated effort**: Medium
**Status**: COMPLETED — 2026-03-12

## Completion Summary

`SignedEnvelope` and `EnvelopeVersionHistory` implemented in `care_platform/constraint/signing.py`.

- `care_platform/constraint/signing.py` — Ed25519 signing, tamper detection, version history, 90-day expiry
- `SignedEnvelope.sign()` and `SignedEnvelope.verify()` using `cryptography` library
- `EnvelopeVersionHistory` tracks versions with append-only semantics
- `tests/unit/constraint/test_signing.py` — signing lifecycle, tamper detection, expiry

## Description

Integrate EATP SDK cryptographic signing into constraint envelopes.

## Tasks

- [x] Constraint envelope signing with Ed25519 key
- [x] Signature covers all five dimensions + metadata
- [x] Signed envelope verification (rejects tampered envelopes)
- [x] Envelope versioning (previous versions preserved for audit)
- [x] 90-day expiry with renewal and warnings
- [x] Schema compatibility (`to_schema_dict()` / `from_schema_dict()`)
- [x] Integration tests for signing lifecycle

## Acceptance Criteria

- [x] Envelopes signed with Ed25519
- [x] Signature verification rejects tampered envelopes
- [x] Version history maintained
- [x] 90-day expiry enforced with warnings
- [x] Integration tests passing

## References

- `care_platform/constraint/signing.py`
- `tests/unit/constraint/test_signing.py`
