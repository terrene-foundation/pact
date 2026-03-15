# Todo 2305: In-Flight Action Revocation Check

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: High
**Effort**: Medium
**Source**: RT10-A5
**Dependencies**: 2201 (M22 complete), 207 (cascade revocation — completed)

## What

Add post-execution validation that detects and flags actions that completed during a parent revocation window. When a revocation event fires, any action that was submitted before revocation but completed after it must be retroactively flagged in the audit trail. The implementation must hook into the existing revocation event system rather than polling. Flagged actions must have their audit anchor updated with a `completed_during_revocation: true` field and a FLAGGED status reason, so auditors can identify the window of concern.

## Where

- `src/care_platform/trust/revocation.py` — add a listener hook that, on revocation, identifies in-flight actions by agent ID and marks them
- `src/care_platform/constraint/middleware.py` — maintain a registry of in-flight action IDs (start time, agent ID) so revocation can query it; remove entries on completion

## Evidence

- [ ] Actions that start before revocation and complete after revocation are flagged in the audit trail
- [ ] Actions that complete before revocation fires are not retroactively flagged
- [ ] Actions that start after revocation are BLOCKED by the existing revocation check (no regression)
- [ ] Flagged audit anchors contain `completed_during_revocation: true` and a descriptive reason string
- [ ] The in-flight registry in middleware is thread-safe (guarded by lock)
- [ ] Unit tests cover: action completes before revocation (clean), action completes after revocation (flagged), action starts after revocation (blocked)
- [ ] Integration test validates the full sequence: establish trust, start action, revoke, complete action, inspect audit
