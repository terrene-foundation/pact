# CARE Platform Red Team Report — Round 6 (Convergence Check)

**Date**: 2026-03-12
**Agents deployed**: deep-analyst, security-reviewer
**Scope**: Post-RT5 convergence — verify fixes, find remaining gaps
**Test suite**: 1,770 tests passing
**RT5 status**: 17/31 findings fixed

---

## Convergence Assessment

**The platform is converging.** Each round produces fewer and lower-severity findings:

| Round | CRITICAL | HIGH | MEDIUM | LOW | Total |
| ----- | -------- | ---- | ------ | --- | ----- |
| RT4   | 4        | 12   | 12     | 6   | 34    |
| RT5   | 5        | 8    | 10     | 8   | 31    |
| RT6   | 2        | 5    | 7      | 4   | 18    |

The RT5 "Dual Path Divergence" is **partially resolved** — `process_next()` now evaluates envelopes, enforces NEVER_DELEGATED, escalates SUPERVISED, and checks revocation. The remaining divergence is in `resume_held()` (missing envelope re-evaluation and context-aware constraint checking).

**Security reviewer verdict**: "No new CRITICAL findings. The platform is now secure at the CRITICAL level."
**Deep analyst verdict**: "2 CRITICALs in resume_held() thread safety and envelope re-evaluation."

The disagreement reflects different threat models — the deep analyst considers TOCTOU in multi-threaded resume as CRITICAL, while the security reviewer considers it exploitable only by authenticated internal actors.

---

## CRITICAL Findings (2) — Deep Analyst Only

### RT6-01: TOCTOU race in resume_held() — task status read outside lock

**Source**: RT6-DA-01
**File**: `execution/runtime.py:702-707`

Task is retrieved under the lock, but status is checked after lock release. Two concurrent `resume_held()` calls could both pass the HELD check and execute the task twice.

**Fix**: Hold lock for status check and initial transition to EXECUTING/FAILED.

### RT6-02: resume_held() does not re-evaluate constraint envelope

**Source**: RT6-DA-02
**File**: `execution/runtime.py:710-784`

Between HELD and approval (hours/days), the envelope may have expired, constraints may have tightened, or budgets may have been exhausted. The middleware path has `_re_verify_before_decision()` but the runtime path does not.

**Fix**: Add envelope re-evaluation before executing approved HELD tasks.

---

## HIGH Findings (5) — Deduplicated

| ID     | Finding                                                                                               | Sources          | File(s)                                       |
| ------ | ----------------------------------------------------------------------------------------------------- | ---------------- | --------------------------------------------- |
| RT6-03 | `_used_nonces` dict not thread-safe — concurrent nonce check/write race                               | DA-03, SEC-03    | `execution/approver_auth.py:306`              |
| RT6-04 | Delegation tree not persisted — cascade revocation broken after restart                               | DA-04            | `trust/revocation.py:82`                      |
| RT6-05 | Bridge close()/revoke() accept transitions from any state — no guard + SUSPENDED bridge expiry bypass | SEC-01, SEC-02   | `workspace/bridge.py`                         |
| RT6-06 | Envelope evaluation in process_next() ignores action context (spend, data paths, external flag)       | DA-06            | `execution/runtime.py:502-505`                |
| RT6-07 | is_revoked() full-table-scan on every process_next() — O(agents \* revocations)                       | DA-07/10, SEC-04 | `trust/revocation.py`, `execution/runtime.py` |

---

## MEDIUM Findings (7)

| ID     | Finding                                                                | Sources |
| ------ | ---------------------------------------------------------------------- | ------- |
| RT6-08 | Bridge state is purely in-memory — lost on restart                     | DA-08   |
| RT6-09 | resume_held() doesn't re-check NEVER_DELEGATED_ACTIONS                 | DA-09   |
| RT6-10 | Middleware cumulative spend tracking is in-memory only                 | DA-11   |
| RT6-11 | revoke_team_bridges revokes bridges in ALL states including terminal   | SEC-05  |
| RT6-12 | ApprovalQueue is not thread-safe despite multi-threaded runtime        | SEC-06  |
| RT6-13 | ConstraintEnvelope.model_post_init mutates self — latent freeze hazard | SEC-07  |
| RT6-14 | RevocationManager has no thread protection                             | SEC-09  |

---

## LOW Findings (4)

| ID     | Finding                                                      | Sources |
| ------ | ------------------------------------------------------------ | ------- |
| RT6-15 | refresh_from_store() only adds, never removes revoked agents | DA-12   |
| RT6-16 | No expiry sweep for SUSPENDED bridges                        | DA-13   |
| RT6-17 | Approval queue action_id not linked to runtime task_id       | DA-14   |
| RT6-18 | Bridge access_log is unbounded                               | SEC-11  |

---

## Defenses That Held (RT5 Fixes Verified)

| Fix                                                                        | Verified By | Status |
| -------------------------------------------------------------------------- | ----------- | ------ |
| Frozen constraint models (no mutation possible)                            | Security    | PASS   |
| Nonce eviction timing correct (evict before check, freshness before nonce) | Security    | PASS   |
| Expanded lock scope in process_next() — no deadlocks                       | Security    | PASS   |
| Revocation persistence (store + hydrate)                                   | Security    | PASS   |
| Bridge NEGOTIATING/SUSPENDED state transitions guarded                     | Security    | PASS   |
| Future-dated signed_at rejection                                           | Security    | PASS   |
| No secrets in expanded audit metadata                                      | Security    | PASS   |
| Envelope evaluation in process_next() works                                | Both        | PASS   |
| NEVER_DELEGATED checked in process_next()                                  | Both        | PASS   |
| SUPERVISED escalated in process_next()                                     | Both        | PASS   |

---

## Known Deferred Items (from RT5)

These were documented as deferred and are not re-reported:

- RT5-03: Nonce persistence (in-memory only, mitigated by freshness check)
- RT5-14: MemoryStore/FilesystemStore genesis overwritable
- RT5-15: Bootstrap BaseException handling
- RT5-17/20/28: Constraint model spec parameter gaps
- RT5-19: Financial default 0.0 ambiguity
- RT5-24: Delegation expiry enforcement
- RT5-26/27: EATP element ordering and audit chain completeness
- RT5-29: Data access substring matching
