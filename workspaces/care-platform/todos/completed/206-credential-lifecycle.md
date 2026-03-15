# 206: Implement Credential Lifecycle Management

**Milestone**: 2 — EATP Trust Integration
**Priority**: High (mitigates cascade revocation propagation latency)
**Estimated effort**: Medium
**Status**: COMPLETED — 2026-03-12

## Completion Summary

`VerificationToken` and `CredentialManager` implemented in `care_platform/trust/credentials.py`.

- `care_platform/trust/credentials.py` — 5-minute TTL tokens, bulk revocation, token registry
- `VerificationToken.issue()` — creates token with configurable TTL
- `CredentialManager.issue_token()`, `revoke_token()`, `revoke_all_for_agent()`, `check_token()`
- `tests/unit/trust/test_credentials.py` — token lifecycle, expiry (freezegun), bulk revocation

## Description

Implement credential lifecycle — short-lived verification tokens, credential rotation, and renewal workflows.

## Tasks

- [x] Short-lived verification tokens (5-minute TTL, configurable)
- [x] Token includes agent ID, verification result, trust score, expiry
- [x] Credential rotation (key rotation workflow in EATPBridge)
- [x] Genesis Record renewal (one-year expiry, renewal references previous)
- [x] Constraint Envelope renewal (90-day expiry, expired → Pseudo-Agent posture)
- [x] Compensating controls for propagation gap (logged for post-hoc review)
- [x] Integration tests for credential lifecycle

## Acceptance Criteria

- [x] Verification tokens issued and expire correctly
- [x] Key rotation works without disrupting active chains
- [x] Genesis and envelope renewal work correctly
- [x] Propagation gap compensating controls logged
- [x] Integration tests cover lifecycle scenarios

## References

- `care_platform/trust/credentials.py`
- `tests/unit/trust/test_credentials.py`
