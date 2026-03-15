# CARE Platform Red Team Report — Round 8

**Date**: 2026-03-12
**Agents deployed**: deep-analyst, security-reviewer
**Scope**: Post-RT7 convergence — verify all RT7 fixes, find remaining gaps
**Test suite**: 1,915 tests passing
**RT7 status**: 15/15 findings fixed (RT7-01 through RT7-15)

---

## Convergence Assessment

**Strong convergence.** Zero CRITICAL or HIGH findings for the first time:

| Round | CRITICAL | HIGH | MEDIUM | LOW | Total |
| ----- | -------- | ---- | ------ | --- | ----- |
| RT4   | 4        | 12   | 12     | 6   | 34    |
| RT5   | 5        | 8    | 10     | 8   | 31    |
| RT6   | 2        | 5    | 7      | 4   | 18    |
| RT7   | 0        | 2    | 8      | 5   | 15    |
| RT8   | 0        | 0    | 5      | 5   | 10    |

**No CRITICAL or HIGH findings.** Both agents agree the codebase has reached a strong security posture.

---

## RT7 Fix Verification (All PASSED)

| Fix                                                                        | Verified By | Status |
| -------------------------------------------------------------------------- | ----------- | ------ |
| RT7-01: RevocationManager thread safety (\_lock on all mutations)          | Both        | PASS   |
| RT7-02: resume_held() re-eval includes current_action_count + access_type  | Both        | PASS   |
| RT7-03: Pre-fetch TrustStore I/O outside lock scope in resume_held()       | Both        | PASS   |
| RT7-04: EATP bridge failure falls back to local delegation tree            | Both        | PASS   |
| RT7-05: ApproverRegistry thread safety (\_lock on dict operations)         | Both        | PASS   |
| RT7-06: select_active_envelope() filters expired, picks most recent        | Both        | PASS   |
| RT7-07: Bridge directionality enforced (source→target only)                | Both        | PASS   |
| RT7-08: AuditChain.\_chain_lock protects concurrent appends                | Both        | PASS   |
| RT7-09: is_tighter_than() checks all 5 dimensions (temporal + data_access) | Both        | PASS   |
| RT7-10: Fail-closed on envelope re-evaluation exception                    | Both        | PASS   |
| RT7-11: get_revocation_log() filter includes affected_agents               | Both        | PASS   |
| RT7-12: resume_bridge() checks valid_until before reactivation             | Both        | PASS   |
| RT7-13: Type-validates data_paths and access_type before use               | Both        | PASS   |
| RT7-14: \_redact_metadata covers api_key + encryption_key patterns         | Both        | PASS   |
| RT7-15: Delegation tree cleared after cascade revoke                       | Both        | PASS   |

---

## RT8 Findings (All Fixed)

### MEDIUM Findings (5)

| ID     | Finding                                                             | Fix Applied                                                     |
| ------ | ------------------------------------------------------------------- | --------------------------------------------------------------- |
| RT8-01 | can_redelegate() reads delegation tree without lock                 | Wrapped in self.\_lock                                          |
| RT8-02 | get_downstream_agents() BFS iterates mutable tree without snapshot  | Snapshot tree under lock before BFS traversal                   |
| RT8-03 | Expired envelope fallback: `or envelopes[0]` bypasses select_active | Removed fallback — returns None when select_active returns None |
| RT8-04 | \_persist_delegation_tree() I/O held under lock                     | Moved persist call outside lock scope                           |
| RT8-05 | Bridge access with agent_team_id=None bypasses directionality check | Fail-closed: None team denied instead of bypassing              |

### LOW Findings (5)

| ID     | Finding                                                              | Fix Applied                                                       |
| ------ | -------------------------------------------------------------------- | ----------------------------------------------------------------- |
| RT8-06 | \_envelope_sort_key() mixed datetime/string comparison in edge cases | Normalize all sort keys to datetime with fallback                 |
| RT8-07 | surgical_revoke() doesn't clean delegation tree parent references    | Remove agent from delegation tree as parent after revocation      |
| RT8-08 | Data path subset check uses literal string matching (not glob)       | Added \_paths_covered_by() with glob-prefix matching              |
| RT8-09 | DM analytics envelope violates monotonic tightening (24/7 vs lead)   | Added active hours + board_minutes to analytics/SEO blocked types |
| RT8-10 | Pyright: `tree` possibly unbound in get_downstream_agents()          | Initialize `tree: dict = {}` before conditional assignment        |

---

## Defenses That Held

| Defense                                                  | Tested By | Status |
| -------------------------------------------------------- | --------- | ------ |
| No hardcoded secrets in source                           | Security  | PASS   |
| All SQL queries parameterized (dict-based storage)       | Security  | PASS   |
| Path traversal prevention in FilesystemStore             | Security  | PASS   |
| Ed25519 signing implementation correct                   | Security  | PASS   |
| HMAC uses constant-time comparison                       | Security  | PASS   |
| Signature includes algorithm type (downgrade prevention) | Security  | PASS   |
| Canonical JSON serialization for deterministic signing   | Security  | PASS   |
| No eval()/exec()/shell=True                              | Security  | PASS   |
| Bridge dual-side approval + permission freezing          | Security  | PASS   |
| Seal-then-sign order enforced in audit anchors           | Security  | PASS   |
| .env in .gitignore, no secrets in code                   | Security  | PASS   |
| All RT6 + RT7 fixes correctly implemented                | Both      | PASS   |
| Thread safety: RevocationManager, ApproverRegistry,      |           |        |
| AuditChain, AuthenticatedApprovalQueue                   | Both      | PASS   |
| Pre-fetch pattern: I/O outside locks, re-validate inside | Both      | PASS   |
| Fail-closed: exceptions → FAILED, not silent continue    | Both      | PASS   |
| Bridge directionality enforcement                        | Both      | PASS   |
| Monotonic tightening across all 5 dimensions             | Both      | PASS   |

---

## Known Deferred Items (from RT5/RT6)

Not re-reported:

- RT5-03: Nonce persistence (in-memory only, mitigated by freshness check)
- RT5-14: MemoryStore/FilesystemStore genesis overwritable
- RT5-15: Bootstrap BaseException handling
- RT5-17/20/28: Constraint model spec parameter gaps
- RT5-19: Financial default 0.0 ambiguity
- RT5-24: Delegation expiry enforcement
- RT5-26/27: EATP element ordering and audit chain completeness
- RT5-29: Data access substring matching (now addressed by RT8-08 glob prefix matching)

---

## Convergence Verdict

The platform has reached **convergence** for single-threaded Phase 1-2 deployment:

- **0 CRITICAL** findings across 2 consecutive rounds (RT7, RT8)
- **0 HIGH** findings in RT8
- All thread safety patterns applied consistently
- Monotonic tightening enforced across all 5 constraint dimensions
- Fail-closed semantics throughout the execution path
- 1,915 tests passing with no regressions

**Recommended next steps**:

1. The remaining deferred items (RT5-series) are acceptable risks for Phase 1-2
2. Multi-threaded deployment (Phase 3+) should revisit lock contention under load testing
3. Consider fuzz testing for constraint evaluation edge cases
