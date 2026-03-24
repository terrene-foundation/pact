# Avoid Stubs, TODOs, or Simulated Data in Production

## Scope

These rules apply to ALL production code (non-test files).

## SHOULD NOT Rules

### 1. Avoid Stubs or Placeholders in Production Code

Production code SHOULD NOT contain:

- `TODO`, `FIXME`, `HACK`, `STUB`, `XXX` markers in shipped code
- `raise NotImplementedError` (implement the method)
- `pass # placeholder` or `pass # stub`
- `return None # not implemented`
- Empty function/method bodies that should have logic

**Note**: During active development and iteration, TODOs may be used temporarily to track work in progress. Remove them before shipping.

### 2. Avoid Simulated or Fake Data

Production code SHOULD NOT contain:

- `simulated_data`, `fake_response`, `dummy_value`
- Hardcoded mock responses pretending to be real API calls
- `return {"status": "ok"}` as a placeholder for real logic
- Test fixtures masquerading as production defaults

### 3. Avoid Silent Fallbacks

Production code SHOULD NOT silently swallow errors:

- `except: pass` (bare except with pass)
- `catch(e) {}` (empty catch block)
- `except Exception: return None` without logging

**Acceptable**: `except: pass` in hooks/cleanup code where failure is expected.

### 4. Avoid Deferred Implementation

When implementing a feature:

- Implement ALL methods fully, not just the happy path
- If an endpoint exists, it should return real data
- If a service is referenced, it should be functional
- Prefer implementing over leaving "will implement later" comments

## Enforcement

- **PostToolUse hook**: `validate-workflow.js` warns on stub patterns in production Python code
- **UserPromptSubmit hook**: Injects reminder every turn
- **Red-team agents**: Scan for violations during validation rounds

## Why This Matters

Stubs and TODOs accumulate silently. Each one is a hidden failure point:

- Users encounter `NotImplementedError` in production
- Silent fallbacks mask real bugs
- Simulated data gives false confidence in demos
- TODOs never get done without active tracking

## Exceptions

Test files (`test_*`, `*_test.*`, `*.test.*`, `*.spec.*`, `__tests__/`) are excluded from stub detection.

During active development, TODOs are acceptable as temporary markers. Remove them before releasing or shipping production code.

See also: `rules/zero-tolerance.md` (Absolute Rule 2)
