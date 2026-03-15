# M13-T04: Verify all test imports

**Status**: ACTIVE
**Priority**: Critical
**Milestone**: M13 — Project Restructure
**Dependencies**: 1301, 1302, 1303

## What

Run the full test suite; fix any import failures. With `pip install -e .` and `where = ["src"]`, imports should resolve as `care_platform.*` without change. This is validation, not bulk rewriting.

## Where

- `tests/**/*.py` (88 test files, 369 import references)

## Evidence

- `pytest tests/ -x --tb=short` passes (1610 tests, 0 failures)
