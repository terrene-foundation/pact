# M13-T01: Move care_platform/ to src/care_platform/

**Status**: ACTIVE
**Priority**: Critical
**Milestone**: M13 — Project Restructure
**Dependencies**: None (first task)
**Effort**: Small (high blast radius)

## What

Move the entire `care_platform/` directory to `src/care_platform/`. This is the Python `src/` layout best practice — prevents accidental imports from the working directory.

## Where

- `src/care_platform/` (new location for all 60 Python modules)
- Remove stale `care_platform.egg-info/`

## Evidence

- `ls src/care_platform/__init__.py` succeeds
- `ls care_platform/` fails (old location gone)
- `python -c "import care_platform"` works after `pip install -e .`

## Risk

HIGH blast radius — 136 internal cross-module imports, 369 test import references, eager loading in `__init__.py`. Must be atomic.
