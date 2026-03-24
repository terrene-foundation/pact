# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for bootstrap exception handling (M22-2205 / RT5-15).

Validates that:
- Individual bootstrap step failures are caught and recorded in result.errors
- Individual step failures do not prevent subsequent steps from running
- Unhandled exceptions in steps are caught gracefully
- Bootstrap result reflects partial success accurately
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pact_platform.build.bootstrap import PlatformBootstrap
from pact_platform.build.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    OperationalConstraintConfig,
    PactConfig,
    TeamConfig,
    TrustPostureLevel,
    WorkspaceConfig,
)
from pact_platform.trust.store.store import MemoryStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(
    *,
    workspaces: list[WorkspaceConfig] | None = None,
) -> PactConfig:
    """Create a minimal PactConfig for testing."""
    return PactConfig(
        name="Test Foundation",
        genesis=GenesisConfig(
            authority="test.foundation",
            authority_name="Test Foundation",
            policy_reference="https://test.foundation/policy",
        ),
        constraint_envelopes=[
            ConstraintEnvelopeConfig(
                id="env-default",
                description="Default envelope",
                financial=FinancialConstraintConfig(max_spend_usd=100.0),
                operational=OperationalConstraintConfig(
                    allowed_actions=["read", "write"],
                ),
            ),
        ],
        agents=[
            AgentConfig(
                id="agent-writer",
                name="Writer Agent",
                role="Content writer",
                constraint_envelope="env-default",
                initial_posture=TrustPostureLevel.SUPERVISED,
                capabilities=["write"],
            ),
        ],
        teams=[
            TeamConfig(
                id="team-content",
                name="Content Team",
                workspace="ws-main",
                agents=["agent-writer"],
            ),
        ],
        workspaces=workspaces or [],
    )


@pytest.fixture()
def config():
    """Minimal platform config."""
    return _make_config()


@pytest.fixture()
def store():
    """In-memory trust store."""
    return MemoryStore()


# ---------------------------------------------------------------------------
# Tests: Step failure isolation
# ---------------------------------------------------------------------------


class TestBootstrapStepIsolation:
    """Individual step failures should not prevent other steps from running."""

    def test_envelope_creation_failure_recorded_in_errors(self, store, config):
        """If envelope creation fails, the error is recorded, not propagated."""
        bootstrap = PlatformBootstrap(store=store)

        # Patch store.store_envelope to fail only for constraint envelopes
        original_store_envelope = store.store_envelope
        call_count = {"count": 0}

        def failing_store_envelope(envelope_id: str, data: dict) -> None:
            call_count["count"] += 1
            # Fail only on actual constraint envelope IDs (not workspace or team)
            if envelope_id == "env-default":
                raise RuntimeError("Simulated envelope storage failure")
            original_store_envelope(envelope_id, data)

        store.store_envelope = failing_store_envelope

        result = bootstrap.initialize(config)

        # The error should be recorded
        assert len(result.errors) > 0
        assert any("envelope" in e.lower() or "env-default" in e for e in result.errors)

        # Other steps should still have run (genesis was created, delegations attempted)
        genesis = store.get_genesis("test.foundation")
        assert genesis is not None

    def test_delegation_failure_recorded_in_errors(self, store, config):
        """If delegation creation fails, the error is recorded."""
        bootstrap = PlatformBootstrap(store=store)

        original_store_delegation = store.store_delegation

        def failing_store_delegation(delegation_id: str, data: dict) -> None:
            raise RuntimeError("Simulated delegation storage failure")

        store.store_delegation = failing_store_delegation

        result = bootstrap.initialize(config)

        # Error should be recorded
        assert len(result.errors) > 0
        assert any("delegation" in e.lower() or "agent" in e.lower() for e in result.errors)

        # Genesis should still have been created
        genesis = store.get_genesis("test.foundation")
        assert genesis is not None

    def test_genesis_failure_recorded_in_errors(self, store, config):
        """If genesis creation fails, the error is recorded."""
        bootstrap = PlatformBootstrap(store=store)

        original_store_genesis = store.store_genesis

        def failing_store_genesis(authority_id: str, data: dict) -> None:
            raise RuntimeError("Simulated genesis storage failure")

        store.store_genesis = failing_store_genesis

        result = bootstrap.initialize(config)

        # Error should be recorded
        assert len(result.errors) > 0
        assert any("genesis" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Tests: Partial success reporting
# ---------------------------------------------------------------------------


class TestBootstrapPartialSuccess:
    """Bootstrap result accurately reflects partial success."""

    def test_is_successful_false_when_errors(self, store, config):
        """Bootstrap result is not successful when errors occurred."""
        bootstrap = PlatformBootstrap(store=store)

        # Force a failure
        store.store_delegation = MagicMock(side_effect=RuntimeError("fail"))

        result = bootstrap.initialize(config)
        assert result.is_successful is False

    def test_successful_bootstrap_has_no_errors(self, store, config):
        """A clean bootstrap run has no errors."""
        bootstrap = PlatformBootstrap(store=store)
        result = bootstrap.initialize(config)
        assert result.is_successful is True
        assert result.errors == []

    def test_errors_contain_context(self, store, config):
        """Error messages should contain enough context for debugging."""
        bootstrap = PlatformBootstrap(store=store)

        def failing_genesis(authority_id: str, data: dict) -> None:
            raise ValueError(f"Cannot store genesis for '{authority_id}': disk full")

        store.store_genesis = failing_genesis

        result = bootstrap.initialize(config)
        assert len(result.errors) > 0
        # Error message should contain the step and the original error message
        error_text = " ".join(result.errors)
        assert "genesis" in error_text.lower() or "disk full" in error_text.lower()
