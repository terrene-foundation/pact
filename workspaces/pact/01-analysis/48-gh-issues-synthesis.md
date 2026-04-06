# GitHub Issues #21-#25: Analysis Synthesis

**Date**: 2026-04-06
**Phase**: 01-analysis (synthesis)
**Inputs**: 45-gap-analysis.md, 46-requirements.md, 47-pact-alignment.md

---

## Executive Summary

Five governance hardening issues from Aegis. Three agents analyzed independently and converge on the same core findings:

1. **#21 (Compartments) is already done** — L1 `can_access()` Step 3 enforces compartment checks. L3 already passes compartments. Close or re-scope to test coverage + optional KnowledgeRecord model.

2. **#22 (Vetting FSM) requires an L1 release** — SUSPENDED enum value needed. FSM transition validation at L1. Multi-approver for clearance grants at L3 (uses #25 infrastructure).

3. **#23 (Bootstrap mode) is highest risk** — Directly tensions with PACT's fail-closed and monotonic tightening invariants. All three analysts agree: implement at L3 ONLY, never L1. Time-limited, bounded, audited.

4. **#24 (Task envelopes) is L3 lifecycle only** — L1 has full TaskEnvelope support. Gaps are persistence, auto-expiry, and acknowledgment at L3.

5. **#25 (Multi-approver) is foundational** — Pure L3, no L1 changes. #22 depends on it. Build first.

## Cross-Analyst Agreement Matrix

| Finding                                            |        Gap Analyst        |  Requirements Analyst   |  PACT Specialist   |
| -------------------------------------------------- | :-----------------------: | :---------------------: | :----------------: |
| #21 already implemented at L1                      |            YES            |           YES           |        YES         |
| #22 needs SUSPENDED enum in L1                     |            YES            |           YES           |        YES         |
| #22 FSM enforcement: L1 validates, L3 orchestrates |            YES            | YES (Option A+B hybrid) |        YES         |
| #23 must be L3-only (not L1)                       | Recommended L1 (Option B) |         L3-only         | L3-only (strongly) |
| #24 L1 complete, L3 lifecycle gaps                 |            YES            |           YES           |        YES         |
| #25 pure L3, foundational for #22                  |            YES            |           YES           |        YES         |
| Build order: #25 → #22, #21/#24 parallel           |            YES            |           YES           |        YES         |
| Shared infra: scheduler + multi-approver           |            YES            |           YES           |         —          |

### One Disagreement: #23 L1 vs L3

The gap analyst recommended L1 engine support (Option B) for bootstrap mode. The requirements analyst and PACT specialist both argue L3-only.

**Resolution: L3-only.** The PACT specialist's argument is definitive:

- L1's `compute_effective_envelope()` returning `None` (maximally restrictive) IS the correct fail-closed behavior
- Bootstrap mode is an operational concern, not a governance primitive
- Putting bootstrap in L1 would embed a permissive-default path in the governance specification layer, violating PACT's core invariant
- L3 already has `_dev_mode` as precedent for operational overrides

## Issue Disposition

| Issue | Action                                            | Scope   |   Blocking on L1?    |
| ----- | ------------------------------------------------- | ------- | :------------------: |
| #21   | Re-scope to test coverage + KnowledgeRecord model | L3 only |          No          |
| #22   | Implement (L1 enum + L3 service)                  | L1 + L3 | Yes (SUSPENDED enum) |
| #23   | Implement (L3 only)                               | L3 only |          No          |
| #24   | Implement (L3 lifecycle)                          | L3 only |          No          |
| #25   | Implement (L3, foundational)                      | L3 only |          No          |

## L1 Changes (Batch into kailash-pact release)

Only #22 requires L1 changes:

1. Add `SUSPENDED = "suspended"` to `VettingStatus` enum (~1 line)
2. Add `_VALID_TRANSITIONS` map to `clearance.py` (~15 lines)
3. Add `transition_clearance(role_address, new_status)` to `GovernanceEngine` (~30 lines)
4. `grant_clearance()` checks transition validity when existing clearance exists (~10 lines)
5. Change `revoke_clearance()` to set status=REVOKED instead of deleting (~5 lines)

Total: ~60 lines of L1 changes. Backward-compatible. File as kailash-py issue.

## New Models (4)

| Model                | Issue | Fields (key)                                                                         |
| -------------------- | ----- | ------------------------------------------------------------------------------------ |
| `KnowledgeRecord`    | #21   | item_id, classification, owning_unit_address, compartments, created_by               |
| `ClearanceVetting`   | #22   | role_address, requested_level, current_status (FSM), required_approvals, approved_by |
| `BootstrapRecord`    | #23   | org_id, status, expires_at, bootstrap_config, envelope_ids                           |
| `TaskEnvelopeRecord` | #24   | task_id, role_address, envelope_config, status, expires_at, acknowledged_at          |

Plus modifications to `AgenticDecision` (add `required_approvals`, `current_approvals`, `approval_record_ids`) and a new `ApprovalRecord` model for #25.

## New/Modified Endpoints (summary)

- **Knowledge** (#21): CRUD at `/api/v1/knowledge`
- **Clearance vetting** (#22): `/api/v1/clearance/vetting/{id}/approve|reject|suspend|reinstate`
- **Bootstrap** (#23): `/api/v1/org/bootstrap/status|end`
- **Task envelope lifecycle** (#24): `/api/v1/governance/envelopes/{addr}/task/{id}/acknowledge|reject`
- **Multi-approver** (#25): Modified approve/reject, new `/api/v1/approval-config`, `/api/v1/decisions/{id}/approvals`

## Shared Infrastructure (build first)

1. **ExpiryScheduler** — Background polling for time-limited records (#23 bootstrap, #24 task envelopes, #25 decision timeout)
2. **MultiApproverService** — Generic approval collection with configurable thresholds (#22 clearance vetting, #25 general decisions)

## Implementation Plan

### Session 1: Shared Infrastructure + #25 Multi-Approver

- Build ExpiryScheduler service
- Build MultiApproverService
- Implement #25: ApprovalConfig model, ApprovalRecord model, AgenticDecision enhancement, modified approve/reject endpoints, governance_gate enhancement
- Tests for multi-approver

### Session 2: #21 + #24 (parallel, both L3-only)

- #21: KnowledgeRecord model, knowledge CRUD router, access check enhancement (lookup by item_id), integration tests
- #24: TaskEnvelopeRecord model, auto-expiry via scheduler, acknowledge/reject endpoints, integration tests

### Session 3: #23 Bootstrap + L1 Issue Filing

- #23: BootstrapConfig, BootstrapManager service, BootstrapRecord model, org deploy modification, auto-expiry registration, integration tests
- File kailash-py issue for #22 L1 changes (SUSPENDED enum + FSM)

### Session 4: #22 Vetting FSM (after L1 release)

- L3: ClearanceVetting model, ClearanceVettingService, transition endpoints, multi-approver integration for SECRET/TOP_SECRET
- Integration tests: full vetting lifecycle
- Cross-issue integration: bootstrap + task envelopes + vetting + multi-approver

## Risk Register

| Risk                                                    | Severity | Issue | Mitigation                                                      |
| ------------------------------------------------------- | -------- | ----- | --------------------------------------------------------------- |
| Bootstrap as permanent escape hatch                     | CRITICAL | #23   | Max TTL (72h), single-use per org, explicit env var opt-in      |
| FSM bypass via direct `grant_clearance()`               | CRITICAL | #22   | Enforce at L1 (not L3 only)                                     |
| Race condition on multi-approver final approval         | HIGH     | #25   | Optimistic locking (envelope_version)                           |
| Bootstrap envelope too permissive                       | HIGH     | #23   | Cap at CONFIDENTIAL, bounded financial/operational limits       |
| Duplicate approver counted twice                        | HIGH     | #25   | Unique constraint on (decision_id, approver_address)            |
| L1 release blocks #22 indefinitely                      | MEDIUM   | #22   | All other issues proceed independently                          |
| AgenticDecision model migration breaks existing records | MEDIUM   | #25   | Default values (required_approvals=1) preserve current behavior |

## Questions for User

1. **#21**: The compartment enforcement is already fully working at L1 and L3. Should we close this issue and open a smaller one for the KnowledgeRecord model + test coverage? Or proceed with the full scope?

2. **#23**: All three analysts flag bootstrap mode as highest-risk. The PACT specialist recommends explicit opt-in via `PACT_ALLOW_BOOTSTRAP_MODE=true` env var. Do you want this, or should bootstrap be available by default?

3. **#22**: The L1 changes (SUSPENDED enum, FSM validation) need a kailash-pact release. Should we file this as a kailash-py issue and proceed with L3-only work in parallel? Or wait for the L1 release first?

4. **#25**: The issue mentions emergency bypass multi-approver (dual approval for different time windows). Should the existing emergency bypass router also adopt the new multi-approver infrastructure, or keep its current simpler model?
