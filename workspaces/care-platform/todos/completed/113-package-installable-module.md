# 113: Package care-platform as Installable Python Module

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (completes Phase 1 deliverable)
**Estimated effort**: Small
**Status**: COMPLETED — 2026-03-12

## Completion Summary

Package is fully installable with complete public API exports and CLI entry point.

- `care_platform/__init__.py` — all public types exported with `__all__`
- `care_platform/cli/__init__.py` — Click CLI with `--version`, `status`, `validate` commands
- `pyproject.toml` — `[project.scripts]` entry: `care-platform = "care_platform.cli:main"`
- `examples/minimal-config.yaml` — smallest valid CARE configuration
- `examples/quickstart.py` — 20-line script demonstrating core API
- `tests/unit/test_package_exports.py` — verifies all top-level exports
- `tests/unit/cli/test_cli.py` — CLI command tests

## Description

Ensure the `care-platform` package installs correctly, exports its public API cleanly, and produces a working `care-platform --help` CLI entry point.

## Tasks

- [x] `care_platform/__init__.py` exports all public types from each submodule
- [x] `care_platform/config/__init__.py` exports `PlatformConfig`, `TeamDefinition`, `AgentDefinition`
- [x] `care_platform/constraint/__init__.py` exports `ConstraintEnvelope`, `VerificationLevel`, `GradientEngine`
- [x] `care_platform/trust/__init__.py` exports `TrustPosture`, `CapabilityAttestation`, `TrustScore`
- [x] `care_platform/audit/__init__.py` exports `AuditAnchor`, `AuditChain`
- [x] `care_platform/workspace/__init__.py` exports `Workspace`, `WorkspaceRegistry`
- [x] `care_platform/cli/__init__.py` — Click CLI entry point with `--version`, `status`, `validate`
- [x] `[project.scripts]` entry in `pyproject.toml`
- [x] `examples/minimal-config.yaml` — smallest valid CARE configuration
- [x] `examples/quickstart.py` — 20-line script demonstrating core API
- [x] Smoke test passes: `from care_platform import ConstraintEnvelope`

## Acceptance Criteria

- [x] `pip install -e ".[dev]"` succeeds with no errors
- [x] All public types importable from top-level `care_platform` namespace
- [x] CLI entry point works: `care-platform --version` outputs version string
- [x] `examples/quickstart.py` runs without errors
- [x] Package passes `ruff`, `mypy`, and `black` checks

## Dependencies

- 102-110: All core models (all completed)

## References

- `pyproject.toml` — Package definition with `[project.scripts]`
- `care_platform/__init__.py` — Top-level exports
