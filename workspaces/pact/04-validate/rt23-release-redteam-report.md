---
type: RED-TEAM
date: 2026-03-26
project: pact
topic: v0.3.0 release red team — spec compliance, delegates, security
phase: redteam
tags: [release, compliance, delegates, security, eatp, governance]
---

# RT23: v0.3.0 Release Red Team Report

**Branch**: `feat/coc-sync-engine-migration`
**Commit**: `ec5617d`
**Agents**: pact-expert, security-reviewer, eatp-expert

## Executive Summary

The PACT Platform v0.3.0 is **architecturally complete** with the governance engine fully wired into all execution paths. The D/T/R grammar, operating envelopes, knowledge clearance, and verification gradient are all functional. **Delegates are structurally in place** — the university example demonstrates President -> Provost -> Dean -> CS Chair delegation with monotonic financial tightening ($100K -> $50K -> $25K -> $10K).

Three gaps require attention:

| # | Finding | Severity | Agent |
|---|---------|----------|-------|
| **F1** | Monotonic tightening not enforced at write time (L1 engine) | CRITICAL | pact-expert |
| **F2** | `str(exc)` leaked in 10+ API error responses | CRITICAL | security |
| **F3** | Trust records use unsigned dicts instead of signed L1 types | HIGH | eatp-expert |
| **F4** | `RequestRouterService` fails-open without governance engine | HIGH | pact-expert, security |
| **F5** | `==` used for hash comparison in `verify_against_checkpoint()` | HIGH | security |
| **F6** | Decision approve/reject has TOCTOU race | HIGH | security |
| **F7** | `ExecutionRuntime` silently auto-approves without governance engine | MEDIUM | pact-expert |
| **F8** | No multi-level delegation chains (genesis->agent only) | MEDIUM | eatp-expert |
| **F9** | Missing input validation in requests/reviews/sessions routers | MEDIUM | security |

## Detailed Findings

### F1: CRITICAL — Monotonic Tightening Not Enforced at Write Time

**Location**: `kailash-py/src/kailash/trust/pact/engine.py:738-756` (L1)

`GovernanceEngine.set_role_envelope()` saves envelopes directly to the store without calling `RoleEnvelope.validate_tightening()`. A caller can store a child envelope with a HIGHER `max_spend_usd` than the parent.

**Mitigant**: `_multi_level_verify()` at runtime takes the most restrictive verdict across all ancestors. So widened envelopes are still constrained at verification time. But they appear valid in the store, API, and dashboard.

**Scope**: This is an L1 (kailash-pact) fix, not an L3 (pact-platform) fix. The platform correctly delegates to the engine.

### F2: CRITICAL — Exception Messages Leaked to API Clients

**Location**: `src/pact_platform/use/api/endpoints.py` (10+ locations), `server.py:882`

`str(exc)` returned in `ApiResponse(status="error", error=str(exc))`. Internal exception details (file paths, SQL errors, class names) can leak to untrusted clients.

### F3: HIGH — Trust Records Are Unsigned Dicts

**Location**: `src/pact_platform/build/bootstrap.py` (genesis, delegation, attestation creation)

Bootstrap creates plain dicts instead of using signed L1 types (`TrustOperations.establish()`, `.delegate()`, `.verify()`). The audit anchor implementation IS properly signed (Ed25519 + HMAC), but genesis, delegation, and attestation records lack cryptographic integrity.

**Root cause**: During L1 migration, the platform replaced its own implementations with plain dict storage rather than wiring in the L1 signed types from `kailash.trust`.

### F4: HIGH — RequestRouterService Fails-Open

**Location**: `src/pact_platform/use/services/request_router.py:93`

When `governance_engine` is `None`, requests are approved unconditionally. The `HookEnforcer` correctly blocks in this scenario — inconsistent fail-safe behavior.

### F5: HIGH — Timing-Vulnerable Hash Comparison

**Location**: `src/pact_platform/trust/audit/anchor.py:324`

Uses `==` for hash comparison in `verify_against_checkpoint()`. Same file correctly uses `hmac.compare_digest()` elsewhere.

### F6: HIGH — Decision TOCTOU Race

**Location**: `src/pact_platform/use/api/routers/decisions.py:84-144`

Read-then-update pattern for approve/reject is not atomic. Concurrent requests can both approve the same decision.

### F7: MEDIUM — Runtime Silent Auto-Approve

**Location**: `src/pact_platform/use/execution/runtime.py:654-657`

When no governance engine is configured, all tasks default to `AUTO_APPROVED`. Inconsistent with HookEnforcer's fail-closed behavior.

### F8: MEDIUM — Single-Level Delegation Only

**Location**: `src/pact_platform/build/bootstrap.py:406-470`

All delegations are genesis -> agent (one level). L1 `DelegationRecord` supports `parent_delegation_id` and `delegation_depth` for multi-level chains, but the platform never creates sub-delegations.

### F9: MEDIUM — Missing Input Validation in API Routers

**Location**: `src/pact_platform/use/api/routers/requests.py:22-51`, `reviews.py:59-78`, `sessions.py:61-88`

Missing `validate_string_length()` calls on title, description fields. Sessions allow invalid state transitions (completed -> active).

## What PASSED

| Check | Status | Evidence |
|-------|--------|----------|
| D/T/R Grammar | PASS | Address validation, university example with 12 roles |
| verify_action() single path | PASS | All 4 L3 callers route through engine |
| No split-brain governance | PASS | Exclusive paths with `_governance_verified` flag |
| Multi-level ancestor verification | PASS | `_multi_level_verify()` walks full chain |
| Audit anchors for all mutations | PASS | 7 mutation types + verify_action anchored |
| Self-modification prevention | PASS | `_VerifierWrapper` with `__slots__` |
| Fail-closed error handling | PASS | All 6 decision points return BLOCKED on error |
| NaN/Inf financial guards | PASS | Full stack coverage (13 locations) |
| Emergency halt check order | PASS | First check in process_next() and enforce() |
| Cumulative budget injection | PASS | cumulative_spend_usd + action_count_today |
| Rate limit enforcement | PASS | Enforced (not just logged) |
| Thread safety | PASS | Locks on runtime, enforcer, audit, stores |
| Secrets handling | PASS | All from env vars, keys redacted in to_dict() |
| SQL injection prevention | PASS | Parameterized queries throughout |
| Security headers | PASS | CSP, HSTS, DENY framing, rate limiting |
| Trust posture enforcement | PASS | All 5 postures with anti-bypass (homoglyph) |
| University example | PASS | Covers all PACT concepts comprehensively |

## Scope Boundary

| Finding | Fix Location | Why |
|---------|-------------|-----|
| F1 (tightening) | L1 kailash-pact | Engine method, not platform code |
| F2-F9 | L3 pact-platform | Platform code |
| F3 (signed types) | L3 bootstrap | Platform should use L1 `TrustOperations` |

## Recommendation

**For v0.3.0 release**: F2 (leaked exceptions) and F5 (hash comparison) are the only findings that directly affect users of the released package. F1 is mitigated by runtime enforcement. F4/F7 only matter if the platform is instantiated without a governance engine (unusual in production).

**For v0.4.0**: F1 (L1 fix), F3 (signed trust records), F4/F7 (fail-closed consistency), F6 (atomic decisions), F8 (multi-level delegation), F9 (input validation).
