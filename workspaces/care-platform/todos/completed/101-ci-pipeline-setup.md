# 101: Set Up CI/CD Pipeline

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (blocks all subsequent work)
**Estimated effort**: Small

## Description

Configure the CI pipeline for the `care-platform` repository. The project uses pytest, and the existing `scripts/ci/run-all.js` needs adaptation for the CARE Platform.

## Tasks

- [ ] Configure GitHub Actions workflow (`.github/workflows/ci.yml`)
- [ ] pytest with coverage reporting (target: 90%+)
- [ ] Linting (ruff or flake8)
- [ ] Type checking (mypy)
- [ ] Pre-commit hooks for formatting (black/ruff-format)
- [ ] Verify `pyproject.toml` dependencies install correctly
- [ ] Create test fixtures directory structure matching `care_platform/` modules
- [ ] Verify EATP SDK (`eatp>=0.1.0`) installs as dependency

## Acceptance Criteria

- `pytest` runs with 0 failures (empty test suite passes)
- CI pipeline triggers on push and PR
- Coverage reporting configured
- Linting and type checking pass on existing code

## References

- `pyproject.toml` — package definition
- `scripts/ci/run-all.js` — existing CI script to adapt
- `conftest.py` — existing test configuration
