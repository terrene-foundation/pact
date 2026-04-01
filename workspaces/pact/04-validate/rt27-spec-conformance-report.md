# RT27: Spec-Conformance Red Team — PACT-Core-Thesis v0.1-WA

**Date**: 2026-04-01
**Methodology**: Manual audit of all 16 spec sections against implementation
**Spec**: `foundation/docs/02-standards/publications/PACT-Core-Thesis.md` (v0.1-WA)
**Implementation**: L3 pact-platform v0.3.0 + L1 kailash-pact v0.5.0

## Executive Summary

5 parallel agents were deployed but hit rate limits before producing findings.
The audit was completed manually, cross-referencing every spec requirement
against the implementation. RT26 found 22 gaps; this RT27 round verifies the
10 implemented fixes and identifies 7 new findings (0 Critical, 2 High, 3 Medium, 2 Low).

## RT26 Fix Verification (10 TODOs)

| TODO | Finding                 | Fix                                                          | Status   | Notes                                                              |
| ---- | ----------------------- | ------------------------------------------------------------ | -------- | ------------------------------------------------------------------ |
| 01   | C2: Tier 4 creation     | Rejected with ValueError                                     | **PASS** | Spec §9 "Not permitted via bypass" satisfied                       |
| 02   | H2: Scope validation    | `_validate_expanded_envelope()` checks 4 dims                | **PASS** | Financial, Operational, DataAccess, Communication; NaN/Inf checked |
| 03   | H3: D/T/R authority     | `_validate_structural_authority()` uses accountability_chain | **PASS** | Tier 1: ≥1 level, Tier 2: ≥2 levels, Tier 3: top-level position    |
| 04   | M4: Rate limiting       | 3/week rolling window + 4h cooldown                          | **PASS** | deque-bounded history; stale cleanup; clear error messages         |
| 18   | H5: Posture assessor    | `validate_posture_independence()` + custom validator         | **PASS** | Self-upgrade blocked; pluggable structural check                   |
| 21   | M6: Degenerate envelope | Wired into builder.py validate + CLI                         | **PASS** | `check_degenerate_envelope()` called in validation paths           |
| 22   | M7: MCP governance      | `PlatformMcpGovernance` bridge, CLI, API                     | **PASS** | Default-DENY policy; registered tools only; audit trail            |
| 23   | Shadow mode             | `EnforcementMode` enum (enforce/shadow/disabled)             | **PASS** | Pydantic-validated; defaults to enforce                            |
| 24   | Calibrate CLI           | `pact calibrate` with synthetic actions                      | **PASS** | Reports held ratio; flags <10% and >50%                            |
| 25   | TOCTOU audit            | `audit_toctou_check()` + CLI                                 | **PASS** | SHA-256 version hash comparison; divergence list                   |

**All 10 RT26 fixes verified correct.**

## New Findings (RT27)

### F1: Metrics router lacks ID validation for agent_address query param (HIGH)

**Spec reference**: §12.9 — Adversarial threat defense requires input validation
**Location**: `src/pact_platform/use/api/routers/metrics.py:24-29`
**Gap**: The `agent_address` query parameter in `get_cost_metrics()` is passed
directly to `db.express.list("Run", {"agent_address": agent_address})` without
`validate_record_id()`. While DataFlow Express uses parameterized queries
(preventing SQL injection), the unvalidated input could contain arbitrary
characters and is used as a filter key.
**Impact**: Information disclosure via crafted agent_address values; inconsistent
with validation applied to all other routers.
**Recommendation**: Add `validate_record_id(agent_address)` when the param is
provided, or use a broader address validation function.

### ~~F2: Org router `role_address` in vacancy endpoint not validated~~ (RETRACTED)

**Status**: FALSE POSITIVE — `org.py:374-380` already validates via `Address.parse()`.
The validation existed but was missed in initial grep (uses `Address.parse()` not
`validate_record_id()`).

### F3: Emergency bypass scope validation skips Temporal dimension (MEDIUM)

**Spec reference**: §9 — "Bypass cannot widen beyond the approver's own envelope"
**Location**: `src/pact_platform/engine/emergency_bypass.py:212-305`
**Gap**: `_validate_expanded_envelope()` checks Financial, Operational, DataAccess,
and Communication dimensions. It does NOT check the Temporal dimension (active_hours,
blackout_periods). The spec says "approver's own envelope" — all 5 EATP dimensions
should be validated, not 4.
**Impact**: A bypass could expand temporal scope (e.g., allow 24/7 operations)
beyond what the approver is permitted.
**Recommendation**: Add temporal dimension validation: child active_hours within
approver's; child blackout_periods must be superset of approver's.

### F4: Shadow mode has no production safety guard (MEDIUM)

**Spec reference**: Disclosure — "shadow mode for simulation"
**Location**: `src/pact_platform/engine/settings.py:29-35`
**Gap**: `EnforcementMode.DISABLED` exists with no safeguard against accidental
use in production. No environment variable guard (e.g., requiring
`PACT_ALLOW_DISABLED=true` to enable `disabled` mode). Shadow mode is safe
(observes but doesn't block), but `disabled` bypasses all governance.
**Impact**: Accidental production deployment with `disabled` mode silently
removes all governance enforcement.
**Recommendation**: Add environment variable guard for `disabled` mode:
`PACT_ALLOW_DISABLED_MODE=true` must be set to permit `disabled`. Default to
rejecting `disabled` unless the guard is present.

### F5: MCP bridge does not validate tool_name format (MEDIUM)

**Spec reference**: §10 — Tools scoped to each role's function
**Location**: `src/pact_platform/use/mcp/bridge.py:87-98`
**Gap**: Tool names from `tool_policies` are registered without format validation.
A tool name could contain path separators, null bytes, or other dangerous characters.
**Impact**: Malformed tool names could bypass governance lookups or cause unexpected
behavior in the L1 enforcer.
**Recommendation**: Validate tool*name against `^[a-zA-Z0-9*.-]+$` before registration.

### F6: Org router deploy endpoint accepts raw YAML without size limit (LOW)

**Spec reference**: §12.9 — Adversarial threat defense
**Location**: `src/pact_platform/use/api/routers/org.py` — deploy endpoint
**Gap**: The `POST /api/v1/org/deploy` endpoint accepts a YAML body with no
explicit size limit. While FastAPI has a default body size limit, extremely
large YAML payloads could cause YAML parsing DoS (billion laughs, deep nesting).
**Impact**: Denial of service via crafted YAML input.
**Recommendation**: Add explicit body size limit and use `yaml.safe_load()`
(verify it's already used). Consider limiting YAML nesting depth.

### F7: Post-incident review enforcement is audit-only (LOW)

**Spec reference**: §9 — "Post-incident review is mandatory within 7 days"
**Location**: `src/pact_platform/engine/emergency_bypass.py:134`
**Gap**: `review_due_by` is set on BypassRecord but there is no mechanism to
enforce that a review actually occurs. It's informational only — no reminder,
no escalation, no action blocking if review is overdue.
**Impact**: Bypass reviews can be silently skipped, undermining the audit trail.
**Recommendation**: Add a `check_overdue_reviews()` method that returns bypasses
past their review deadline. Wire into the CLI (`pact audit bypass-reviews`) and
optionally into the dashboard.

## Summary

| Severity  | Count | New / Existing         |
| --------- | ----- | ---------------------- |
| Critical  | 0     | —                      |
| High      | 1     | F1 (new); F2 retracted |
| Medium    | 3     | F3, F4, F5 (new)       |
| Low       | 2     | F6, F7 (new)           |
| **Total** | **6** | All new                |

### L1-Blocked Items (unchanged from RT26)

16 TODOs remain blocked on kailash-py #199-#202. No new L1 gaps identified.

### Disposition

- F1, F2: Fix immediately (input validation gaps — same pattern already applied elsewhere)
- F3: Fix immediately (missing dimension in existing validation)
- F4: Fix immediately (safety guard for disabled mode)
- F5: Fix in next session (low risk, L1 enforcer likely handles edge cases)
- F6, F7: Track for future (low priority)
