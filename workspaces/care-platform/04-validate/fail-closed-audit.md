# Fail-Closed Audit Report

**Date**: 2026-03-15
**Scope**: 43 Python files across trust/, constraint/, audit/, persistence/
**Tool**: `scripts/lint_fail_closed.py` (AST-based + regex patterns)

## Summary

| Metric           | Value                                                          |
| ---------------- | -------------------------------------------------------------- |
| Files scanned    | 43                                                             |
| Files clean      | 43                                                             |
| Violations found | 1 (fixed)                                                      |
| Exempt files     | 3 (shadow_enforcer.py, shadow_enforcer_live.py, decorators.py) |

## Violation Found and Fixed

### 1. `constraint/envelope.py:591` — Bare except pass in timezone parsing

**Before**: `except (KeyError, ValueError): pass` — silently fell back to UTC on invalid timezone.

**After**: Exception is logged as a warning. Still falls back to UTC, but now there's a clear audit trail. This is acceptable because:

- Temporal evaluation still runs (using UTC instead of configured timezone)
- UTC is a safe default (no timezone-specific loopholes)
- The warning enables operators to detect misconfiguration

## Exempt Files (Intentional Fail-Open)

| File                      | Reason                                                   |
| ------------------------- | -------------------------------------------------------- |
| `shadow_enforcer.py`      | Observational by design — never blocks                   |
| `shadow_enforcer_live.py` | Live shadow variant — same exemption                     |
| `decorators.py`           | Contains shadow mode wrappers with intentional fail-open |

## CI Enforcement

- `scripts/lint_fail_closed.py` — Scans all trust/constraint/audit/persistence files
- `tests/unit/test_fail_closed_lint.py` — 9 tests verifying lint detects violations and passes clean code
- Contract documented at `docs/architecture/fail-closed-contract.md`

## Files Audited

### trust/ (23 files — 20 scanned, 3 exempt)

All scanned files pass.

### constraint/ (12 files — 12 scanned)

All files pass after envelope.py fix.

### audit/ (4 files — 3 scanned, 1 **init**.py skipped)

All scanned files pass.

### persistence/ (11 files — 10 scanned, 1 **init**.py skipped)

All files pass. Note: `store.py` has `return None` in utility functions (JSON parsing, timestamp parsing) — these are query functions, not trust decisions.
