# M13-T03: Verify conftest.py for src/ layout

**Status**: ACTIVE
**Priority**: High
**Milestone**: M13 — Project Restructure
**Dependencies**: 1301, 1302

## What

Verify root `conftest.py` still works. `.env` path resolution uses `Path(__file__).parent / ".env"` which remains valid if conftest stays at root. With `pip install -e .` the package is installed in the venv.

## Where

- `conftest.py` (root)

## Evidence

- `pytest tests/ --co` (collection) succeeds with no import errors
