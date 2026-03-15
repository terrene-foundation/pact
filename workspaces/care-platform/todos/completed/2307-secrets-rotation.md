# Todo 2307: Secrets Rotation (Token + Ed25519 Keys)

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: High
**Effort**: Medium-Large
**Source**: I4
**Dependencies**: 2101 (.env loading wired), 1204 (approver Ed25519 auth — completed), 1206 (asymmetric audit signing — completed)

## What

Implement rotation for both API tokens and Ed25519 signing keys without service downtime.

**API token rotation**:

- New `POST /auth/rotate-token` endpoint that generates a replacement API token and sets a configurable grace period (default 24 hours) during which both old and new tokens are accepted
- After the grace period expires, the old token is rejected

**Ed25519 key rotation**:

- Key versioning: each key pair has a version identifier stored alongside the public key
- A `POST /admin/rotate-signing-key` endpoint (admin only) that generates a new key pair and records the old public key in a `retired_keys` store
- Signatures made with the old key continue to verify against the retired key during the grace period
- After grace period, retired keys are removed and old signatures are considered invalid

**CLI commands**:

- `care rotate-token` — triggers token rotation, prints new token, states when old token expires
- `care rotate-signing-key` — triggers key rotation, states grace period deadline

## Where

- `src/care_platform/trust/` — key versioning data model, retired keys store, grace period logic
- `src/care_platform/api/endpoints.py` — token rotation and key rotation endpoints
- `src/care_platform/cli/` — `rotate-token` and `rotate-signing-key` commands

## Evidence

- [ ] Old API token accepted during grace period after rotation
- [ ] Old API token rejected after grace period expires
- [ ] New API token accepted immediately after rotation
- [ ] Old Ed25519 signatures verify against retired key during grace period
- [ ] New signatures use new key from rotation point forward
- [ ] Old key rejected after grace period
- [ ] `care rotate-token` CLI command functional and prints expiry information
- [ ] `care rotate-signing-key` CLI command functional and prints grace period deadline
- [ ] Token rotation endpoint requires current valid token for authentication
- [ ] Key rotation endpoint requires admin role
- [ ] Unit tests cover: within grace period (both accepted), after grace period (only new accepted), signature verification across key versions
