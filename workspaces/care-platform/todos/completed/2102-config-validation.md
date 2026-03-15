# Todo 2102: Startup Configuration Validation

**Milestone**: M21 — Hardening and Operational Readiness
**Priority**: High
**Effort**: Small
**Source**: RT10 general
**Dependencies**: 2101

## What

Create a configuration module that reads and validates all environment variables at startup. Required variables must be present; missing ones cause an immediate, descriptive error before any network listener or database connection is opened (fail-fast). Optional variables must have documented defaults. The module should provide a single `load_config()` function that returns a typed config object (dataclass or similar), and a companion table in the module docstring enumerating every recognized variable, its type, whether it is required, its default, and what it controls.

## Where

- `src/care_platform/config/env.py` (new file; `config/` package may need `__init__.py`)

## Evidence

- [ ] Server refuses to start and prints a clear error message when a required environment variable is absent
- [ ] All recognized environment variables are listed with descriptions in the module docstring or an adjacent `ENV_VARS` constant
- [ ] `load_config()` returns a typed object (not raw strings) with validated, coerced values
- [ ] Unit tests cover: all required vars present (happy path), each required var missing individually (error path), optional vars absent (uses default), optional vars overridden
- [ ] Existing tests continue to pass
