# RT27 Hardening Fixes

Based on `04-validate/rt27-spec-conformance-report.md`. 6 findings from RT27;
3 already fixed (F1, F3, F4) in the red team session. 3 remaining.

**Created**: 2026-04-01
**Source**: RT27 spec-conformance red team round 2

---

## TODO-01: MCP tool_name format validation (F5 — MEDIUM)

**Spec**: §10 — Tools scoped to each role's function
**Current**: `PlatformMcpGovernance.__init__()` registers tool names from
`tool_policies` without validating the tool*name string format.
**Fix**: Validate `tool_name` against `^[a-zA-Z0-9*.-]+$` before registration.
Reject names with path separators, null bytes, or other dangerous characters.

**Files**: `src/pact_platform/use/mcp/bridge.py`
**Tests**: Invalid tool names rejected; valid names accepted
**Status**: [x] Done

---

## TODO-02: YAML deploy endpoint size + safety (F6 — LOW)

**Spec**: §12.9 — Adversarial threat defense
**Current**: `POST /api/v1/org/deploy` accepts YAML body with no explicit
size limit or YAML safety verification.
**Fix**:

1. Verify `yaml.safe_load()` is used (not `yaml.load()`)
2. Add explicit body size check (reject > 1MB)
3. Add YAML nesting depth limit via custom constructor or post-parse check

**Files**: `src/pact_platform/use/api/routers/org.py`
**Tests**: Oversized YAML rejected; deeply nested YAML rejected; normal YAML accepted
**Status**: [x] Done

---

## TODO-03: Post-incident bypass review enforcement (F7 — LOW)

**Spec**: §9 — "Post-incident review is mandatory within 7 days"
**Current**: `BypassRecord.review_due_by` is set but never checked. No mechanism
to surface overdue reviews.
**Fix**:

1. Add `check_overdue_reviews()` method to `EmergencyBypass` that returns
   bypass records past their `review_due_by` date
2. Wire into CLI: `pact audit bypass-reviews` command
3. Include count in `pact status` output

**Files**: `src/pact_platform/engine/emergency_bypass.py`, `src/pact_platform/cli.py`
**Tests**: Overdue reviews returned; non-overdue excluded; CLI displays results
**Status**: [x] Done

---

## Summary

| TODO | Finding | Severity | Layer | Dependency |
| ---- | ------- | -------- | ----- | ---------- |
| 01   | F5      | MEDIUM   | L3    | None       |
| 02   | F6      | LOW      | L3    | None       |
| 03   | F7      | LOW      | L3    | None       |

All 3 items are L3 (this repo), no upstream dependency, implementable in 1 session.
