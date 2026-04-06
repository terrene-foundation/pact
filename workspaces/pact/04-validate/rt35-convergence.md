# RT35 Convergence Report — SUSPENDED L1 Wiring + SDK Upgrade

**Date**: 2026-04-06
**Scope**: L1 transition_clearance integration, kailash stack upgrade, FSM spec compliance
**Agents**: Security reviewer (background), manual code audit

## Findings

### Round 1 — Code Audit

| ID  | Sev | Finding                                                                                                              | Status               |
| --- | --- | -------------------------------------------------------------------------------------------------------------------- | -------------------- |
| F1  | H   | Reinstate endpoint does not call L1 transition_clearance(REVOKED) — L1 clearance stays SUSPENDED after reinstatement | FIXED                |
| F2  | H   | No standalone /revoke endpoint — active→revoked FSM transition unreachable via API                                   | FIXED                |
| F3  | M   | Suspend endpoint used grant_clearance() workaround instead of transition_clearance()                                 | FIXED (prior commit) |
| F4  | M   | .spec-coverage AC-1 (#22) marked PARTIAL despite SUSPENDED now in L1                                                 | FIXED                |
| F5  | L   | .spec-coverage AC-3 (#23) marked PARTIAL but callback IS wired (server.py:1045+1054)                                 | FIXED                |
| F6  | L   | .test-results stale — references kailash 2.5.1 / kailash-pact 0.7.2                                                  | FIXED                |

### Round 1 — FSM Comparison (L1 vs L3)

L3 is intentionally stricter than L1:

| L1 Transition      | L3 Equivalent      | Design Decision                                                  |
| ------------------ | ------------------ | ---------------------------------------------------------------- |
| PENDING → REVOKED  | Not allowed        | L3 uses "rejected" for denied vettings                           |
| SUSPENDED → ACTIVE | Not allowed        | L3 requires new pending vetting (reinstatement with re-approval) |
| EXPIRED → ACTIVE   | Not allowed        | L3 requires new submission (expired is terminal)                 |
| (none)             | pending → rejected | L3-only state for human denial                                   |

All differences are deliberate governance strictness at the platform layer.

### Tests Added (17 new, 2675 total)

| Test                                              | What it verifies                                 |
| ------------------------------------------------- | ------------------------------------------------ |
| test_approve_vetting_reaches_active               | Approval with quorum → active status + read-back |
| test_suspend_active_vetting                       | Active → suspended FSM transition                |
| test_suspend_non_active_fails                     | Pending → suspended blocked (409)                |
| test_revoke_active_vetting                        | Active → revoked via new /revoke endpoint        |
| test_revoke_suspended_vetting                     | Suspended → revoked via /revoke                  |
| test_revoke_pending_fails                         | Pending → revoked blocked (409)                  |
| test_revoke_terminal_fails                        | Revoked → revoked blocked (409)                  |
| test_reinstate_creates_new_pending                | Suspended → revoked + new pending created        |
| test_reinstate_non_suspended_fails                | Pending → reinstate blocked (409)                |
| test_full_lifecycle_submit_approve_suspend_revoke | Complete lifecycle through all states            |
| test_secret_requires_dual_approval                | 2-approver quorum for secret clearance           |
| test_revoke_input_validation                      | Missing fields return 400                        |
| test_filter_vettings_by_status                    | List endpoint status filter works                |
| test_suspended_enum_exists                        | L1 VettingStatus.SUSPENDED present               |
| test_l1_fsm_transition_table                      | L1 FSM allows expected transitions               |
| test_validate_transition_rejects_invalid          | L1 FSM rejects REVOKED→ACTIVE                    |
| test_validate_transition_accepts_valid            | L1 FSM accepts ACTIVE→SUSPENDED                  |

## Convergence

- 0 CRITICAL findings
- 0 HIGH findings remaining (2 found, 2 fixed)
- 0 MEDIUM findings remaining (2 found, 2 fixed)
- Spec coverage: 25/25 VERIFIED (0 PARTIAL, 0 MISSING)
- Tests: 2675 passed, 44 skipped, 0 failed
- Security review: pending (background agent)
