# Contributing to the CARE Platform

Thank you for your interest in contributing to the CARE Platform. This guide covers everything you need to set up your development environment, understand the contribution process, and submit changes.

The CARE Platform is owned by the Terrene Foundation and licensed under Apache 2.0. All contributions are welcome from anyone -- the Foundation operates under a uniform contributor framework with no special access or advantage for any contributor.

---

## Development Setup

### Prerequisites

- **Python 3.11 or later** (3.12 and 3.13 are also supported)
- **Git**
- A virtual environment tool (`venv`, `virtualenv`, or similar)

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/terrene-foundation/care.git
cd care

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"
```

### Environment Configuration

Copy the environment template and configure your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your API keys. At minimum, configure one LLM provider. The root `conftest.py` auto-loads `.env` for all pytest sessions, so no manual setup is needed for tests.

**Important**: Never commit `.env` files. The `.gitignore` already excludes them.

### Verify Your Setup

```bash
# Run the test suite
pytest

# Run with coverage
pytest --cov=care_platform

# Lint
ruff check .

# Type check
mypy care_platform/
```

All 875+ tests should pass. If any fail, check that your dependencies installed correctly and your `.env` is configured.

---

## Project Structure

```
care_platform/          Main package
  trust/                EATP trust layer (genesis, delegation, posture, scoring)
  constraint/           Constraint envelopes and verification gradient
  execution/            Agent runtime (teams, sessions, approval queues)
  audit/                Tamper-evident audit chains
  workspace/            Workspace management and cross-functional bridges
  config/               Configuration schema and loader
  persistence/          Storage abstraction (MemoryStore, FilesystemStore)
tests/                  Test suite (unit, integration)
docs/                   Documentation
```

See [docs/architecture.md](docs/architecture.md) for the full architecture overview.

---

## Running Tests

The project uses pytest with a three-tier testing strategy:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_trust_posture.py

# Run tests matching a pattern
pytest -k "test_delegation"

# Run with coverage report
pytest --cov=care_platform --cov-report=term-missing
```

### Test Requirements

- **All changes must include tests.** If you add a feature, add tests that cover it. If you fix a bug, add a test that reproduces the bug.
- Tests should be self-contained and not depend on external services unless testing integration specifically.
- Use the fixtures defined in `conftest.py` for common setup.
- Async tests are supported via `pytest-asyncio` (configured with `asyncio_mode = "auto"`).

---

## Code Style

### Formatting and Linting

The project uses **ruff** for linting with the following rules enabled:

- `E` (pycodestyle errors)
- `F` (pyflakes)
- `I` (isort)
- `UP` (pyupgrade)
- `B` (bugbear)
- `SIM` (simplify)

Line length is 100 characters.

```bash
# Check for issues
ruff check .

# Auto-fix what can be fixed
ruff check --fix .
```

### Type Checking

The project uses **mypy** for type checking:

```bash
mypy care_platform/
```

### Conventions

- Use **Pydantic** models for data structures (the project uses Pydantic v2).
- Use `from __future__ import annotations` for deferred annotation evaluation.
- All public classes and methods should have docstrings.
- Use `logging` (not `print`) for diagnostic output.
- Follow existing patterns in the codebase -- look at similar modules for guidance.

### License Headers

All Python source files must include the Apache 2.0 license header:

```python
# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
```

---

## Commit Conventions

The project uses **Conventional Commits**:

```
type(scope): description

[optional body]

[optional footer]
```

**Types**:

- `feat` -- new feature
- `fix` -- bug fix
- `docs` -- documentation
- `style` -- formatting (no logic change)
- `refactor` -- code restructure
- `test` -- adding or updating tests
- `chore` -- maintenance

**Examples**:

```
feat(trust): add posture downgrade notification
fix(constraint): handle zero budget in financial evaluation
docs(readme): update quick start example
test(delegation): add monotonic tightening edge cases
```

Each commit should be self-contained: tests and implementation together, building and passing on its own.

---

## Pull Request Process

### 1. Create a Feature Branch

```bash
git checkout -b feat/your-feature-name
# or: fix/your-bug-fix, docs/your-doc-update, etc.
```

### 2. Make Your Changes

- Follow the code style guidelines above.
- Include tests for new functionality.
- Update documentation if your changes affect public APIs.

### 3. Run the Full Check Suite

```bash
# Tests
pytest

# Lint
ruff check .

# Type check
mypy care_platform/
```

### 4. Submit a Pull Request

Push your branch and open a PR against `main`. Include:

- **Summary**: What changed and why (1-3 bullet points)
- **Test plan**: How to verify the changes
- **Related issues**: Link any relevant GitHub issues

**PR template**:

```markdown
## Summary

- [what changed and why]

## Test plan

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Related issues

Fixes #123
```

### 5. Review

All PRs require review before merging. Reviewers will check:

- Code quality and style
- Test coverage
- Standards alignment (see below)
- Security considerations

---

## Standards Alignment

The CARE Platform is the reference implementation of the CARE, EATP, and CO specifications. Contributions must not violate these standards:

- **CARE**: Dual Plane Model (Trust Plane + Execution Plane), constraint envelopes with five dimensions, monotonic tightening
- **EATP**: Five-element trust lineage chains, verification gradient, trust postures
- **CO**: Seven principles, five layers of cognitive orchestration

If your change touches trust, governance, or constraint enforcement, consider consulting the specification documents at [terrene.dev](https://terrene.dev).

Key invariants that must be preserved:

- Constraint envelopes can only be tightened through delegation, never loosened
- Trust posture upgrades require evidence; downgrades are instant
- Every agent action must produce an audit anchor
- The five constraint dimensions (Financial, Operational, Temporal, Data Access, Communication) are the governance mechanism
- Certain actions (content strategy, crisis response, financial decisions, governance modifications) are never fully delegated regardless of posture level

---

## Code of Conduct

Contributors are expected to act professionally and respectfully. The Terrene Foundation is committed to providing a welcoming and inclusive environment for everyone.

---

## Questions?

- **Documentation**: [terrene.dev/care](https://terrene.dev/care)
- **Issues**: [github.com/terrene-foundation/care/issues](https://github.com/terrene-foundation/care/issues)
- **Foundation**: [terrene.foundation](https://terrene.foundation)
