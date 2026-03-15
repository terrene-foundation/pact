# Todo 2204: Nonce Persistence to TrustStore

**Milestone**: M22 — API Hardening
**Priority**: High
**Effort**: Medium
**Source**: RT5-03
**Dependencies**: 2101, 2102

## What

The current nonce store for approver authentication is in-memory only. A process restart clears all nonces, reopening a replay window for up to `max_decision_age_seconds` (the validity window of a signed approval). This todo closes that window by persisting used nonces to the TrustStore.

Required changes:

1. When an approver nonce is consumed, write it to TrustStore with its expiry timestamp before accepting the decision.
2. On server startup, load all non-expired nonces from TrustStore into the in-memory set before accepting any approval decisions. This ensures a restarted process rejects replayed decisions from the previous session's validity window.
3. Add a periodic cleanup task (or cleanup on startup) that removes nonces older than `max_decision_age_seconds` from TrustStore to prevent unbounded storage growth. Cleanup should happen at startup and then on a configurable interval.

## Where

- `src/care_platform/execution/approver_auth.py` — nonce write-on-consume, startup load
- `src/care_platform/persistence/store.py` — nonce persistence interface (add nonce read/write/delete operations if not already present)

## Evidence

- [ ] Used nonces are written to TrustStore synchronously before the approval decision is accepted
- [ ] On startup, nonces from TrustStore are loaded into the in-memory set before the approval endpoint becomes active
- [ ] A replay attack using a valid signed decision that was used before a restart is rejected
- [ ] Nonces older than `max_decision_age_seconds` are removed from TrustStore at startup and periodically thereafter
- [ ] Unit tests cover: nonce persisted on use, nonce loaded on startup, replay blocked after restart, old nonces cleaned up
- [ ] Existing tests continue to pass
