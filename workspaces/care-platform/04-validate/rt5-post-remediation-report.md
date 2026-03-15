# CARE Platform Red Team Report — Round 5 (Post-RT4 Remediation)

**Date**: 2026-03-12
**Agents deployed**: deep-analyst, security-reviewer, care-expert, gold-standards-validator
**Scope**: Post-RT4 remediation review — find gaps the RT4 fixes missed or introduced
**Test suite**: 1,691 tests passing
**RT4 status**: 34/34 findings fixed (including RT4-L1 enum casing)

---

## Executive Summary

RT5 targeted the integration points between the modules that RT4 fixed individually. Four agents converged on a clear pattern: **the `ExecutionRuntime.process_next()` path has significant enforcement gaps compared to the `VerificationMiddleware` path.** The middleware correctly implements envelope evaluation, NEVER_DELEGATED actions, SUPERVISED posture escalation, and TOCTOU protection — but the runtime does none of these. The most critical finding is that envelope evaluation in the runtime is dead code (a `pass` statement where evaluation should occur), meaning the central CARE governance mechanism is bypassed when tasks go through the primary runtime path.

**Totals (deduplicated)**: 5 CRITICAL, 8 HIGH, 10 MEDIUM, 8 LOW

---

## CRITICAL Findings (5)

### RT5-01: Runtime envelope evaluation is dead code — constraints never enforced in primary execution path

**Sources**: RT5-DA-11 (deep-analyst), RT5-CARE-01 (care-expert)
**File**: `care_platform/execution/runtime.py:446-455`

The `process_next()` method sets `envelope_evaluation = None`, looks up envelopes from the store, then hits a `pass` statement — the evaluation is never computed. The gradient engine always receives `envelope_evaluation=None`, so the 5 constraint dimensions (Financial, Operational, Temporal, Data Access, Communication) are unenforced in the primary runtime path. The middleware path correctly evaluates envelopes, but the runtime path does not.

**Impact**: An agent can exceed its constraint envelope boundaries if tasks flow through `process_next()` rather than through `VerificationMiddleware`. This is a fundamental breach of the Dual Plane Model — the Trust Plane's constraint definitions have no effect on the Execution Plane for the primary runtime path.

**Fix**: Actually call `ConstraintEnvelope.evaluate_action()` in `process_next()` and pass the result to the gradient engine. Alternatively, make the middleware non-optional when envelopes are configured.

---

### RT5-02: `resume_held()` bypasses all authentication, revocation, and posture checks

**Sources**: RT5-DA-05 (deep-analyst), RT5-SEC-03 (security-reviewer)
**File**: `care_platform/execution/runtime.py:575-634`

`resume_held(task_id, "approved")` executes a HELD task with zero authentication. It requires no approver identity, no signed decision, no revocation re-check, and no posture re-check. Any code path that can call `runtime.resume_held()` can approve any HELD task, completely bypassing the `AuthenticatedApprovalQueue`.

Additionally, between the time a task is HELD and the time `resume_held` is called, the assigned agent may have been revoked or its posture downgraded — but these are not re-checked.

**Fix**: Require `approver_id` and `SignedDecision` parameters. Re-check revocation and posture before executing.

---

### RT5-03: Nonce replay protection lost on process restart

**Sources**: RT5-DA-01 (deep-analyst), RT5-SEC-01 (security-reviewer)
**File**: `care_platform/execution/approver_auth.py:306`

`_used_nonces: set[str]` is in-memory only. After a process restart, all nonce history is lost. An attacker who captured a valid `SignedDecision` can replay it within the `max_decision_age_seconds` window (default 300s) after a restart.

**Fix**: Persist used nonces to the TrustStore. On startup, load recent nonces. Add periodic cleanup of nonces older than `max_decision_age_seconds`.

---

### RT5-04: Execution Plane can mutate Trust Plane state — no immutability enforcement

**Source**: RT5-CARE-02 (care-expert)
**File**: `care_platform/constraint/envelope.py`, `care_platform/config/schema.py`

`ConstraintEnvelope` and `ConstraintEnvelopeConfig` are standard Pydantic models with mutable fields. Nothing prevents execution-plane code from doing `envelope.config.financial.max_spend_usd = 999999.0`. The CARE specification states this is "a hard architectural rule" — agents cannot modify their own constraints.

**Fix**: Use `model_config = {"frozen": True}` to make constraint models immutable. Additionally, verify `content_hash()` at the start of every `evaluate_action()` call.

---

### RT5-05: Future-dated `signed_at` bypasses freshness check

**Source**: RT5-SEC-04 (security-reviewer)
**File**: `care_platform/execution/approver_auth.py:484-488`

If `signed_at` is set to a future timestamp, the age calculation yields a negative value, which always passes the `age > max_decision_age_seconds` check. An attacker can pre-sign decisions that remain valid indefinitely until the future timestamp is reached.

**Fix**: Reject decisions with negative age (future `signed_at`).

---

## HIGH Findings (8)

| ID     | Finding                                                                                    | Sources        | File(s)                                           |
| ------ | ------------------------------------------------------------------------------------------ | -------------- | ------------------------------------------------- |
| RT5-06 | Runtime doesn't enforce NEVER_DELEGATED_ACTIONS — high-stakes actions can be auto-approved | CARE-04        | `execution/runtime.py`                            |
| RT5-07 | SUPERVISED posture not enforced in runtime — only PSEUDO_AGENT is blocked                  | CARE-05        | `execution/runtime.py:435-444`                    |
| RT5-08 | `_sync_revocations()` and `_persist_posture_change()` are dead code — never called         | DA-06, CARE-08 | `execution/runtime.py:715-754`                    |
| RT5-09 | Hydration TOCTOU gap — store can change between `from_store()` and task execution          | DA-03          | `execution/runtime.py:197-299`                    |
| RT5-10 | Unlocked task mutation after dequeue in `process_next()` — race condition                  | DA-04, SEC-10  | `execution/runtime.py:410-416`                    |
| RT5-11 | Cascade revocation state is in-memory only — lost on restart                               | DA-07          | `trust/revocation.py:76`                          |
| RT5-12 | Audit chain not crash-safe — in-memory append and store persist are separate operations    | DA-08          | `audit/anchor.py`, `execution/runtime.py:703-713` |
| RT5-13 | Bridge state machine missing NEGOTIATING and SUSPENDED states from CARE spec               | CARE-06        | `workspace/bridge.py:36-43`                       |

---

## MEDIUM Findings (10)

| ID     | Finding                                                                                                 | Sources       | File(s)                            |
| ------ | ------------------------------------------------------------------------------------------------------- | ------------- | ---------------------------------- |
| RT5-14 | MemoryStore and FilesystemStore genesis is overwritable — inconsistent with SQLiteTrustStore write-once | DA-09         | `persistence/store.py:243-245`     |
| RT5-15 | Bootstrap isolation_level restoration incomplete under BaseException                                    | DA-10         | `bootstrap.py:227-240`             |
| RT5-16 | Nonce set grows without bound — no eviction of expired nonces                                           | DA-13, SEC-02 | `execution/approver_auth.py:306`   |
| RT5-17 | Financial constraint model missing daily_limit, monthly_limit, vendor_limits from spec                  | CARE-07       | `config/schema.py:51-60`           |
| RT5-18 | Monotonic tightening check bypassed when child has None rate limit but parent has a value               | CARE-11       | `constraint/envelope.py:195-200`   |
| RT5-19 | Financial constraint default of 0.0 creates ambiguity (block everything vs not configured)              | CARE-10       | `config/schema.py:54`              |
| RT5-20 | Communication constraint missing recipient_limits and escalation_triggers from spec                     | CARE-12       | `config/schema.py:122-131`         |
| RT5-21 | Bridge doesn't enforce "most restrictive wins" against agent's constraint envelope                      | CARE-14       | `workspace/bridge.py`              |
| RT5-22 | "cross-team bridges" naming in coordinator.py — should be "Cross-Functional Bridges"                    | GS-01, GS-02  | `workspace/coordinator.py:103,124` |
| RT5-23 | Middleware "most restrictive wins" logic has redundant re-classification call                           | CARE-15       | `execution/runtime.py:466-493`     |

---

## LOW Findings (8)

| ID     | Finding                                                                                   | Sources       | File(s)                               |
| ------ | ----------------------------------------------------------------------------------------- | ------------- | ------------------------------------- |
| RT5-24 | Delegation expiry (`expires_at`) never enforced at runtime                                | DA-12         | `execution/runtime.py`                |
| RT5-25 | store_genesis read-then-write could use INSERT OR IGNORE for atomicity                    | DA-14, SEC-11 | `persistence/sqlite_store.py:500-513` |
| RT5-26 | Audit anchor lacks delegation_id and genesis_authority for full EATP accountability chain | CARE-09       | `audit/anchor.py`                     |
| RT5-27 | EATP element ordering in code (attestation as element 4) differs from spec (element 2)    | CARE-03       | `trust/attestation.py`, CLAUDE.md     |
| RT5-28 | Temporal constraint missing max_duration and deadline_behavior from spec                  | CARE-13       | `config/schema.py:77-104`             |
| RT5-29 | Data access blocked type check uses substring matching — can false-positive               | CARE-19       | `constraint/envelope.py:365-372`      |
| RT5-30 | Unused `import copy` in templates/registry.py                                             | GS-03         | `templates/registry.py:20`            |
| RT5-31 | `_redact_metadata` doesn't traverse nested lists                                          | SEC-15        | `audit/anchor.py:409-428`             |

---

## Defenses That Held

| Defense                                                                                                             | Tested By                | Result |
| ------------------------------------------------------------------------------------------------------------------- | ------------------------ | ------ |
| Ed25519 signing implementation correct                                                                              | Security                 | PASS   |
| HMAC uses `hmac.compare_digest()` (constant-time)                                                                   | Security                 | PASS   |
| All SQL queries use parameterized values (no injection)                                                             | Security, Gold Standards | PASS   |
| `.env` in `.gitignore`, no secrets in source                                                                        | Security, Gold Standards | PASS   |
| No `eval()`/`exec()`, no `raise NotImplementedError`, no stubs                                                      | Gold Standards           | PASS   |
| All 60+ files have correct Apache 2.0 headers                                                                       | Gold Standards           | PASS   |
| CARE plane names correct ("Trust Plane" / "Execution Plane")                                                        | Gold Standards           | PASS   |
| All 5 constraint dimensions correctly named                                                                         | Gold Standards           | PASS   |
| All 5 trust postures correctly defined                                                                              | Gold Standards           | PASS   |
| Verification levels now uppercase (RT4-L1 fixed)                                                                    | Gold Standards           | PASS   |
| Cross-Functional Bridge types (Standing, Scoped, Ad-Hoc) correct                                                    | Gold Standards           | PASS   |
| ShadowEnforcer naming correct (PascalCase)                                                                          | Gold Standards           | PASS   |
| `VerificationMiddleware` correctly implements envelope eval, NEVER_DELEGATED, posture escalation, TOCTOU protection | CARE Expert              | PASS   |
| BFS with visited set prevents infinite loops in delegation tree                                                     | Security                 | PASS   |
| Approval queue enforces max_queue_depth                                                                             | Security                 | PASS   |
| Self-approval prevention in ApprovalQueue                                                                           | Security                 | PASS   |

---

## Systemic Pattern: "Dual Path Divergence"

RT5's systemic finding is that the platform has two execution paths with very different enforcement levels:

| Feature                       | `VerificationMiddleware`        | `ExecutionRuntime.process_next()`           |
| ----------------------------- | ------------------------------- | ------------------------------------------- |
| Envelope evaluation           | Yes (full 5 dimensions)         | **Dead code** (pass statement)              |
| NEVER_DELEGATED actions       | Yes (forced to HELD)            | **Not checked**                             |
| SUPERVISED posture escalation | Yes (HELD for all actions)      | **Not checked** (only PSEUDO_AGENT blocked) |
| TOCTOU protection on approval | Yes (re-verify before decision) | **Not checked**                             |
| Cumulative spend tracking     | Yes                             | **Not tracked**                             |
| Emergency halt                | Yes                             | **Not implemented**                         |

The middleware is strong. The runtime is weak. The fix is either: (a) make the middleware non-optional when constraint envelopes exist, or (b) mirror the middleware's enforcement in the runtime's `process_next()`, or (c) have the runtime delegate to the middleware for all verification.

---

## Recommended Fix Priority

### Immediate (before commit)

1. **RT5-01**: Wire envelope evaluation in `process_next()` — replace the `pass` statement
2. **RT5-02**: Add auth + revocation + posture re-checks to `resume_held()`
3. **RT5-05**: Reject future-dated `signed_at` in freshness check
4. **RT5-06**: Add NEVER_DELEGATED check in `process_next()`
5. **RT5-07**: Add SUPERVISED posture escalation in `process_next()`

### Before merge

6. **RT5-03**: Persist nonces to TrustStore
7. **RT5-04**: Make constraint models frozen (immutable)
8. **RT5-08**: Wire `_sync_revocations()` and `_persist_posture_change()` into lifecycle
9. **RT5-10**: Expand lock scope in `process_next()` or add per-task locks
10. **RT5-11**: Persist revocation records to TrustStore

### Next iteration

11. RT5-09, RT5-12: Hydration refresh and crash-safe audit
12. RT5-13: Bridge state machine alignment with CARE spec
13. RT5-17, RT5-20, RT5-28: Constraint model alignment with spec parameters
14. RT5-14-RT5-31: Remaining MEDIUM and LOW findings
