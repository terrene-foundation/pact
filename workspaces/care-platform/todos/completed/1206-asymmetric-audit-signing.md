# 1206: Asymmetric Audit Anchor Signing (Ed25519)

**Priority**: Medium
**Effort**: Small
**Source**: RT3 Theme G
**Dependencies**: None

## Problem

Audit anchors use HMAC-SHA256 (symmetric key). Anyone with the signing key can forge anchors. Constraint envelopes use Ed25519 (asymmetric) — anchors should match.

## Implementation

Enhance `care_platform/audit/anchor.py`:

- Add Ed25519 signing option alongside existing HMAC
- Use private key to sign, public key to verify
- Backward compatible: HMAC still works, Ed25519 is opt-in
- Update AuditChain.append() to accept either key type
- Auto-detect key type (32 bytes = Ed25519 seed, other = HMAC)

## Acceptance Criteria

- [ ] Audit anchors can be signed with Ed25519
- [ ] Verification uses public key only (no private key needed)
- [ ] Backward compatible with existing HMAC signing
- [ ] Tests verify Ed25519 signing and verification
