# 207: Implement Cascade Revocation

**Milestone**: 2 — EATP Trust Integration
**Priority**: High (critical safety mechanism)
**Estimated effort**: Medium
**Status**: COMPLETED — 2026-03-12

## Completion Summary

`RevocationManager` implemented in `care_platform/trust/revocation.py` with surgical and cascade revocation.

- `care_platform/trust/revocation.py` — `RevocationManager`, `RevocationRecord`, `RevocationRegistry`
- `surgical_revoke(agent_id)` — only the target agent revoked
- `cascade_revoke(root_agent_id)` — BFS to revoke all downstream agents
- Forward-looking semantics enforced (revocation prevents future actions, not past)
- `tests/unit/trust/test_revocation.py` — surgical, cascade, cross-team, re-delegation scenarios

## Description

Implement cascade revocation — surgical (one agent) and team-wide (team lead → all downstream) revocation.

## Tasks

- [x] `surgical_revoke(agent_id, reason, revoker)` → RevocationRecord
- [x] `cascade_revoke(root_id, reason, revoker)` → [RevocationRecord]
- [x] Push-based revocation notification (via CredentialManager bulk revocation)
- [x] VERIFY checks revocation status (revoked chains → BLOCKED)
- [x] Forward-looking semantics (revocation prevents future actions, audit trail preserved)
- [x] Integration tests (surgical, cascade, re-delegation)

## Acceptance Criteria

- [x] Surgical and team-wide revocation both work correctly
- [x] No orphaned agents after team-wide revocation
- [x] Cross-team delegations properly invalidated
- [x] Forward-looking semantics enforced
- [x] Integration tests cover all revocation scenarios

## References

- `care_platform/trust/revocation.py`
- `tests/unit/trust/test_revocation.py`
