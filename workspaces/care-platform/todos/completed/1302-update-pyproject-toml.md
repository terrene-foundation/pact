# M13-T02: Update pyproject.toml for src/ layout

**Status**: ACTIVE
**Priority**: Critical
**Milestone**: M13 — Project Restructure
**Dependencies**: 1301

## What

Change `[tool.setuptools.packages.find]` from `where = ["."]` to `where = ["src"]`. CLI entry point `care-platform = "care_platform.cli:main"` references the package name (not filesystem path) so should remain valid.

## Where

- `pyproject.toml` (lines 69-71)

## Evidence

- `pip install -e .` succeeds
- `python -c "import care_platform"` works
- `care-platform --help` works
