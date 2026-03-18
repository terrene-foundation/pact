# Task 6003: Create py.typed Marker

**Milestone**: M0b
**Priority**: Medium
**Effort**: Tiny
**Status**: Active

## Description

PEP 561 requires a `py.typed` marker file in the package root for type checkers (mypy, pyright) to recognize that the package ships type information. Without this file, downstream users get no type checking benefits even though the codebase has type annotations.

## Acceptance Criteria

- [ ] Empty file created at `src/care_platform/py.typed`
- [ ] `py.typed` is included in the package manifest so it ships in the wheel (add to `MANIFEST.in` if applicable, or verify `pyproject.toml` includes it via `[tool.setuptools.package-data]`)
- [ ] `mypy --strict` run on a trivial import of `care_platform` does not complain about missing type stubs

## Dependencies

- None.
