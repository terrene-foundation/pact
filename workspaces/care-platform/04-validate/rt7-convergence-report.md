# CARE Platform Red Team Report — Round 7 (Convergence Check)

**Date**: 2026-03-12
**Agents deployed**: deep-analyst, security-reviewer
**Scope**: Post-RT6 convergence — verify fixes, find remaining gaps
**Test suite**: 1,711 tests passing
**RT6 status**: 8/8 findings fixed (RT6-01 through RT6-07, RT6-11)

---

## Convergence Assessment

**The platform continues converging.** Each round produces fewer and lower-severity findings:

| Round | CRITICAL | HIGH | MEDIUM | LOW | Total |
| ----- | -------- | ---- | ------ | --- | ----- |
| RT4   | 4        | 12   | 12     | 6   | 34    |
| RT5   | 5        | 8    | 10     | 8   | 31    |
| RT6   | 2        | 5    | 7      | 4   | 18    |
| RT7   | 0        | 2    | 8      | 5   | 15    |

**No CRITICAL findings.** Both agents agree.

**Security reviewer verdict**: "The codebase is converging toward a solid security posture. No CRITICAL findings remain."
**Deep analyst verdict**: "The codebase is approaching production readiness for single-threaded deployment (Phase 1-2)."

---

## RT6 Fix Verification (All PASSED)

| Fix                                                                  | Verified By | Status |
| -------------------------------------------------------------------- | ----------- | ------ |
| RT6-01: resume_held() TOCTOU — lock covers status check + transition | Both        | PASS   |
| RT6-02: Envelope re-evaluation in resume_held()                      | Both        | PASS   |
| RT6-03: Thread-safe nonces via \_nonce_lock                          | Both        | PASS   |
| RT6-04: Delegation tree persistence via TrustStore                   | Both        | PASS   |
| RT6-05: Bridge terminal state guards + SUSPENDED expiry              | Both        | PASS   |
| RT6-06: Action context from task.metadata in process_next()          | Both        | PASS   |
| RT6-07: O(1) is_revoked() via \_revoked_ids set                      | Both        | PASS   |
| RT6-11: revoke_team_bridges() skips terminal states                  | Both        | PASS   |

---

## HIGH Findings (2) — Deduplicated

### RT7-01: RevocationManager missing thread safety (\_revoked_ids, \_revocation_log, \_delegation_tree)

**Sources**: RT7-DA-03, RT7-SEC-01
**File**: `trust/revocation.py`

`_revoked_ids` set, `_revocation_log` list, and `_delegation_tree` dict are mutated without synchronization. Same pattern as the RT6-03 nonce fix, but applied to RevocationManager. The `is_revoked()` read-then-write fallback path (check set, then add from store) is not atomic.

**Fix**: Add `threading.Lock` to RevocationManager protecting all mutations.

### RT7-02: resume_held() re-evaluation omits current_action_count and access_type

**Sources**: RT7-SEC-02, RT7-DA-05 (partial — stale cumulative_spend)
**File**: `execution/runtime.py:812-826`

The RT6-02 re-evaluation block passes `spend_amount`, `cumulative_spend`, `data_paths`, and `is_external` but omits `current_action_count` and `access_type` (which ARE passed in `process_next()`). This means rate limits and write-vs-read path checks are bypassed during re-evaluation.

Additionally, `cumulative_spend` is read from original task metadata — potentially stale after hours/days of other tasks consuming budget.

**Fix**: Add `current_action_count` and `access_type` to the resume_held() re-evaluation. Document the stale cumulative_spend limitation.

---

## MEDIUM Findings (8)

| ID     | Finding                                                              | Sources       |
| ------ | -------------------------------------------------------------------- | ------------- |
| RT7-03 | Lock held during TrustStore I/O in resume_held() — throughput impact | DA-01         |
| RT7-04 | EATP bridge failure silently reduces cascade revocation scope        | DA-02         |
| RT7-05 | ApproverRegistry not thread-safe (TOCTOU between check and lookup)   | DA-04, SEC-03 |
| RT7-06 | Envelope selection uses first match without recency/expiry check     | DA-06         |
| RT7-07 | Bidirectional access through directional bridges                     | DA-07         |
| RT7-08 | AuditChain concurrent append could corrupt hash chain                | DA-09         |
| RT7-09 | is_tighter_than() ignores temporal and data_access dimensions        | DA-10         |
| RT7-10 | resume_held() silently continues on envelope re-evaluation exception | SEC-04        |

---

## LOW Findings (5)

| ID     | Finding                                                         | Sources       |
| ------ | --------------------------------------------------------------- | ------------- |
| RT7-11 | get_revocation_log() filter misses cascade-affected agents      | DA-11         |
| RT7-12 | resume_bridge() doesn't check valid_until before reactivation   | DA-12, SEC-06 |
| RT7-13 | task.metadata values (data_paths) not type-validated before use | SEC-05        |
| RT7-14 | \_redact_metadata misses "api_key" pattern                      | SEC-07        |
| RT7-15 | Delegation tree not cleared after cascade revoke                | SEC-08        |

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
| All RT6 fixes correctly implemented                      | Both      | PASS   |

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
- RT5-29: Data access substring matching

---

## Recommended Fix Priority

### Immediate (before next commit)

1. **RT7-01**: Add `threading.Lock` to RevocationManager
2. **RT7-02**: Add missing `current_action_count` + `access_type` to resume_held() re-evaluation

### Before multi-threaded deployment

3. RT7-03: Restructure lock scope or accept throughput trade-off
4. RT7-05: Add lock to ApproverRegistry
5. RT7-08: Add lock to AuditChain.append()
6. RT7-10: Fail-closed on envelope re-evaluation exception

### Next iteration

7. RT7-04: EATP bridge failure fallback
8. RT7-06: Envelope selection by recency/expiry
9. RT7-07: Bridge directionality enforcement
10. RT7-09: Monotonic tightening for temporal + data_access dimensions
    11-15: LOW findings

---

## Decision Points

1. **RT7-03**: Is correctness (preventing TOCTOU) worth the throughput cost of lock-during-I/O?
2. **RT7-07**: Should bridges be bidirectional by design or enforce directionality?
3. **RT7-09**: Should temporal and data_access dimensions be enforced in `is_tighter_than()`?
4. **Stale cumulative_spend**: Is there a plan for a live spend tracker, or should re-evaluation skip the financial dimension when live data is unavailable?
