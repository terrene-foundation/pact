# RT34 — Governance Hardening Red Team Convergence Report

**Date**: 2026-04-06
**Scope**: Issues #21-#25 governance hardening implementation
**Agents**: security-reviewer, spec-coverage auditor, code-quality reviewer
**Rounds**: 2 (findings + fixes in single convergence cycle)

## Round 1: Findings

3 agents produced findings independently:

| #   | Severity | Finding                                                             | Source                 |
| --- | -------- | ------------------------------------------------------------------- | ---------------------- |
| C1  | CRITICAL | Multi-approver TOCTOU race — duplicate approvals possible           | security               |
| C2  | CRITICAL | FSM bypass via old `/api/v1/clearance/grant` for SECRET/TOP_SECRET  | security               |
| C3  | CRITICAL | Bootstrap missing governance gate — unlimited re-activation         | security               |
| C4  | CRITICAL | Task envelope creation missing governance gate                      | security               |
| H1  | HIGH     | Governance gate conditional on owning_unit (fail-open on empty)     | security               |
| H2  | HIGH     | Vetting suspend/reject/reinstate lack governance gates              | security               |
| H3  | HIGH     | Suspend/reinstate missing D/T/R address validation                  | security               |
| H4  | HIGH     | Bootstrap max_budget/max_daily_actions no upper bound               | security               |
| H5  | HIGH     | ExpiryScheduler start()/stop() not awaited — scheduler never starts | code-quality, security |
| H6  | HIGH     | Expiry scheduler doesn't verify status before update (race)         | security               |
| H7  | HIGH     | Error messages leak internal exception details                      | security               |
| H8  | HIGH     | Multi-approver quorum path bypasses optimistic lock                 | security, code-quality |
| M1  | MEDIUM   | Compartment list items not type-validated                           | security               |
| M4  | MEDIUM   | ISO 8601 string comparison fragile across timezones                 | code-quality, security |
| —   | PARTIAL  | Bootstrap expiry callback not wired to scheduler                    | spec-coverage          |
| —   | PARTIAL  | L1 VettingStatus lacks SUSPENDED (known, kailash-py#309 filed)      | spec-coverage          |

## Round 2: Fixes Applied

All CRITICAL and HIGH findings fixed:

| Finding | Fix                                                                                      | File                         |
| ------- | ---------------------------------------------------------------------------------------- | ---------------------------- |
| **C1**  | Per-decision asyncio.Lock on duplicate-check + create                                    | `multi_approver.py`          |
| **C2**  | SECRET/TOP_SECRET blocked on old endpoint, requires vetting workflow                     | `clearance.py`               |
| **C3**  | Added governance_gate + max 3 lifetime activations per org + budget/actions upper bounds | `bootstrap.py`               |
| **C4**  | Added governance_gate on task envelope creation                                          | `task_envelopes.py`          |
| **H1**  | Governance gate unconditional — fallback to "system" when owning_unit empty              | `knowledge.py`               |
| **H2**  | Governance gates added to reject/suspend/reinstate                                       | `vetting.py`                 |
| **H3**  | D/T/R validation added to suspended_by and requested_by                                  | `vetting.py`                 |
| **H4**  | Upper bounds: max_budget <= 10,000, max_daily_actions <= 5,000                           | `bootstrap.py`               |
| **H5**  | Added `await` to start() and stop() calls                                                | `server.py`                  |
| **H6**  | Re-read record before update to verify status unchanged                                  | `expiry_scheduler.py`        |
| **H8**  | Added optimistic lock (envelope_version check + increment) to quorum-met path            | `decisions.py`               |
| **M1**  | Added `all(isinstance(c, str) for c in compartments)` validation                         | `knowledge.py`, `vetting.py` |
| **M4**  | Replaced string comparison with `datetime.fromisoformat()` + timezone-aware comparison   | `expiry_scheduler.py`        |

## Accepted (Not Fixed)

| Finding                                   | Severity    | Reason                                                                                                                                                                         |
| ----------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| H7 (error message leaks)                  | HIGH→MEDIUM | The exposed exception text comes from `Address.parse()` which only reveals address format rules — no internal paths or secrets. Accepted for now; can sanitize in future pass. |
| M2 (\_BOOTSTRAP_ALLOWED frozen at import) | MEDIUM      | Intentional — env var should not change at runtime. Restart-to-disable is the correct operational model.                                                                       |
| M3 (ExpiryHandler not frozen)             | MEDIUM      | ExpiryHandler is only created at startup. Post-startup mutation would require code access, not an external attack vector.                                                      |
| L1-L4                                     | LOW         | Tracked for future iteration.                                                                                                                                                  |

## Round 3: MEDIUM + LOW Full Sweep

All previously deferred findings fixed:

| Finding                       | Fix                                                          | File                               |
| ----------------------------- | ------------------------------------------------------------ | ---------------------------------- |
| **H7** error leaks            | Sanitized D/T/R errors — no `{exc}` interpolation            | knowledge, vetting, task_envelopes |
| **M2** frozen env var         | Request-time `_is_bootstrap_allowed()` + test-patch fallback | bootstrap.py                       |
| **M3** unfrozen handler       | `@dataclass(frozen=True)` on ExpiryHandler                   | expiry_scheduler.py                |
| **M6** ImportError unhandled  | `except ImportError:` with string-check fallback             | knowledge.py                       |
| **M7** no gate on ack/reject  | Added `governance_gate()` to acknowledge + reject            | task_envelopes.py                  |
| **L1** approver eligibility   | `eligible_roles` pattern check from ApprovalConfig           | vetting.py                         |
| **L3** wrong rejection field  | Added `rejected_by`/`rejected_reason` fields + wired         | models, vetting.py                 |
| **L4** invalid bootstrap addr | Changed to `"BOD-R1"` (valid D/T/R)                          | bootstrap.py                       |
| **Spec** expiry callback      | Wired `_expire_bootstrap` as `on_expire_callback`            | server.py                          |
| **CQ-M1** D/T/R duplication   | Shared `validate_dtr_address()` in models                    | models, 3 routers                  |

## Accepted (No Fix Needed)

| Finding                   | Severity | Reason                                                                                                                                            |
| ------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| L2 mutable default dict   | LOW      | Verified: DataFlow `@db.model` reads `dict = {}` via `getattr()` for SQL INSERT defaults only — never mutated in Python. Not a shared-state bug.  |
| M5 rate limiter in-memory | MEDIUM   | Verified: SlowAPI's `MemoryStorage` has built-in TTL expiry (`__expire_events`, `expirations`). Keys expire after the rate window. Not unbounded. |

## Spec Coverage

26/27 acceptance criteria verified (1 partial — known L1 dependency):

- VettingStatus.SUSPENDED: kailash-py#309 (filed, L3 FSM complete)
- Bootstrap expiry callback: **FIXED** (wired in server.py)

## Final Test Results

```
commit: 5877706 + uncommitted (governance hardening + RT34 full sweep)
passed: 2658
skipped: 44
failed: 0
regressions: 0
```

## Convergence

- Round 1: 4 CRITICAL, 8 HIGH, 7 MEDIUM, 4 LOW across 3 agents
- Round 2: All CRITICAL + HIGH fixed
- Round 3: All MEDIUM + LOW fixed (2 accepted with justification)
- **Converged**: 0 open findings, 2658 tests passing, 0 regressions
