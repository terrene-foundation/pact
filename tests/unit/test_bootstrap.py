# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for PlatformBootstrap — trust hierarchy initialization.

Tests verify that bootstrap:
- Creates genesis records from PactConfig
- Discovers workspaces from disk
- Registers agents, teams, and constraint envelopes
- Creates delegation records
- Is idempotent (safe to re-run)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pact_platform.build.bootstrap import BootstrapResult, PlatformBootstrap
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
from pact_platform.trust.store.sqlite_store import SQLiteTrustStore

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
                    allowed_actions=["read", "write", "summarize"],
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
                capabilities=["write", "summarize"],
            ),
            AgentConfig(
                id="agent-reviewer",
                name="Reviewer Agent",
                role="Content reviewer",
                constraint_envelope="env-default",
                capabilities=["read", "review"],
            ),
        ],
        teams=[
            TeamConfig(
                id="team-content",
                name="Content Team",
                workspace="ws-docs",
                agents=["agent-writer", "agent-reviewer"],
            ),
        ],
        workspaces=workspaces or [],
    )


@pytest.fixture
def store() -> SQLiteTrustStore:
    return SQLiteTrustStore(":memory:")


@pytest.fixture
def config() -> PactConfig:
    return _make_config()


# ---------------------------------------------------------------------------
# Genesis
# ---------------------------------------------------------------------------


class TestGenesis:
    """Bootstrap creates a genesis record (root of trust)."""

    def test_creates_genesis(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        result = bootstrap.initialize(config)
        assert result.is_successful
        assert result.genesis_authority == "test.foundation"
        genesis = store.get_genesis("test.foundation")
        assert genesis is not None
        assert genesis["authority_name"] == "Test Foundation"

    def test_idempotent_genesis(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        result1 = bootstrap.initialize(config)
        result2 = bootstrap.initialize(config)
        assert result1.is_successful
        assert result2.is_successful
        # Genesis should still exist, not duplicated
        genesis = store.get_genesis("test.foundation")
        assert genesis is not None


# ---------------------------------------------------------------------------
# Agents and Delegations
# ---------------------------------------------------------------------------


class TestAgentsAndDelegations:
    """Bootstrap registers agents and creates delegation records."""

    def test_registers_agents(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        result = bootstrap.initialize(config)
        assert result.agents_registered == 2
        assert result.delegations_created == 2

    def test_delegation_links_to_authority(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        bootstrap.initialize(config)
        # Check agent-writer has a delegation from authority
        delegations = store.get_delegations_for("agent-writer")
        assert len(delegations) == 1
        assert delegations[0]["delegator_id"] == "test.foundation"
        assert delegations[0]["delegatee_id"] == "agent-writer"

    def test_delegation_includes_envelope_id(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        bootstrap.initialize(config)
        delegations = store.get_delegations_for("agent-writer")
        assert delegations[0]["envelope_id"] == "env-default"

    def test_attestation_stored_for_capable_agents(
        self, store: SQLiteTrustStore, config: PactConfig
    ):
        bootstrap = PlatformBootstrap(store=store)
        bootstrap.initialize(config)
        attestations = store.get_attestations_for("agent-writer")
        assert len(attestations) == 1
        assert attestations[0]["capabilities"] == ["write", "summarize"]


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


class TestTeams:
    """Bootstrap registers teams."""

    def test_registers_teams(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        result = bootstrap.initialize(config)
        assert result.teams_registered == 1


# ---------------------------------------------------------------------------
# Constraint Envelopes
# ---------------------------------------------------------------------------


class TestEnvelopes:
    """Bootstrap creates constraint envelopes."""

    def test_creates_envelopes(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        result = bootstrap.initialize(config)
        assert result.envelopes_created == 1
        envelope = store.get_envelope("env-default")
        assert envelope is not None
        assert envelope["financial"]["max_spend_usd"] == 100.0


# ---------------------------------------------------------------------------
# Workspace Discovery
# ---------------------------------------------------------------------------


class TestWorkspaceDiscovery:
    """Bootstrap discovers workspaces from disk."""

    def test_discovers_workspaces(self, store: SQLiteTrustStore, tmp_path: Path):
        # Create a COC workspace on disk
        ws = tmp_path / "my-project"
        ws.mkdir()
        (ws / "briefs").mkdir()
        (ws / "todos").mkdir()

        config = _make_config()
        bootstrap = PlatformBootstrap(store=store)
        result = bootstrap.initialize(config, workspace_root=tmp_path)
        assert result.workspaces_discovered == 1

    def test_configured_workspaces_not_rediscovered(self, store: SQLiteTrustStore, tmp_path: Path):
        """Workspaces already in config are not duplicated by discovery."""
        ws = tmp_path / "docs-ws"
        ws.mkdir()
        (ws / "briefs").mkdir()
        (ws / "todos").mkdir()

        config = _make_config(
            workspaces=[WorkspaceConfig(id="docs-ws", path=str(ws))],
        )
        bootstrap = PlatformBootstrap(store=store)
        result = bootstrap.initialize(config, workspace_root=tmp_path)
        # Already in config, so not counted as discovered
        assert result.workspaces_discovered == 0
        assert result.workspaces_registered == 1  # The configured one

    def test_skip_discovery(self, store: SQLiteTrustStore, tmp_path: Path):
        ws = tmp_path / "project"
        ws.mkdir()
        (ws / "briefs").mkdir()
        (ws / "todos").mkdir()

        config = _make_config()
        bootstrap = PlatformBootstrap(store=store)
        result = bootstrap.initialize(config, workspace_root=tmp_path, discover_workspaces=False)
        assert result.workspaces_discovered == 0


# ---------------------------------------------------------------------------
# RT4 Findings: Completion Marker, Attestation Fields, Delegation Expiry
# ---------------------------------------------------------------------------


class TestBootstrapCompletionMarker:
    """RT4-H7: Bootstrap stores a completion marker after successful run."""

    def test_completion_marker_stored(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        result = bootstrap.initialize(config)
        assert result.is_successful

        marker = store.get_envelope("bootstrap:complete:test.foundation")
        assert marker is not None
        assert marker["status"] == "complete"
        assert marker["authority"] == "test.foundation"
        assert "timestamp" in marker
        assert marker["agents_registered"] == 2
        assert marker["delegations_created"] == 2

    def test_rerun_logs_previous_bootstrap(self, store: SQLiteTrustStore, config: PactConfig):
        """Re-running bootstrap succeeds and updates the marker."""
        bootstrap = PlatformBootstrap(store=store)
        bootstrap.initialize(config)
        # Second run should succeed (idempotent) and update the marker
        result2 = bootstrap.initialize(config)
        assert result2.is_successful
        marker = store.get_envelope("bootstrap:complete:test.foundation")
        assert marker is not None
        assert marker["status"] == "complete"


class TestAttestationFormat:
    """RT4-M3: Attestations include required capability attestation fields."""

    def test_attestation_has_required_fields(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        bootstrap.initialize(config)

        attestations = store.get_attestations_for("agent-writer")
        assert len(attestations) == 1
        att = attestations[0]
        assert att["attestation_type"] == "capability"
        assert att["delegator_id"] == "test.foundation"
        assert "delegation_id" in att
        assert att["delegation_id"].startswith("del-")

    def test_attestation_has_all_fields_for_reviewer(
        self, store: SQLiteTrustStore, config: PactConfig
    ):
        bootstrap = PlatformBootstrap(store=store)
        bootstrap.initialize(config)

        attestations = store.get_attestations_for("agent-reviewer")
        assert len(attestations) == 1
        att = attestations[0]
        assert att["attestation_type"] == "capability"
        assert att["delegator_id"] == "test.foundation"
        assert att["delegation_id"].startswith("del-")
        assert att["capabilities"] == ["read", "review"]


class TestDelegationExpiry:
    """RT4-M6: Delegations include an expires_at timestamp."""

    def test_delegation_has_expires_at(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        bootstrap.initialize(config)

        delegations = store.get_delegations_for("agent-writer")
        assert len(delegations) == 1
        deleg = delegations[0]
        assert "expires_at" in deleg
        # Verify expires_at is approximately 365 days from created_at
        created = datetime.fromisoformat(deleg["created_at"])
        expires = datetime.fromisoformat(deleg["expires_at"])
        delta = expires - created
        assert delta == timedelta(days=365)

    def test_all_delegations_have_expires_at(self, store: SQLiteTrustStore, config: PactConfig):
        bootstrap = PlatformBootstrap(store=store)
        bootstrap.initialize(config)

        for agent_id in ("agent-writer", "agent-reviewer"):
            delegations = store.get_delegations_for(agent_id)
            assert len(delegations) == 1, f"Expected 1 delegation for {agent_id}"
            assert "expires_at" in delegations[0], f"Delegation for {agent_id} missing expires_at"


# ---------------------------------------------------------------------------
# Config Loading
# ---------------------------------------------------------------------------


class TestConfigLoading:
    """PlatformBootstrap.load_config loads YAML files."""

    def test_load_valid_yaml(self, tmp_path: Path):
        config_yaml = tmp_path / "platform.yaml"
        config_yaml.write_text(
            "name: Test\ngenesis:\n  authority: test.org\n  authority_name: Test Org\n"
        )
        config = PlatformBootstrap.load_config(config_yaml)
        assert config.name == "Test"
        assert config.genesis.authority == "test.org"

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            PlatformBootstrap.load_config(tmp_path / "nonexistent.yaml")

    def test_load_invalid_yaml_raises(self, tmp_path: Path):
        config_yaml = tmp_path / "bad.yaml"
        config_yaml.write_text("just a string")
        with pytest.raises(ValueError, match="YAML mapping"):
            PlatformBootstrap.load_config(config_yaml)


# ---------------------------------------------------------------------------
# BootstrapResult
# ---------------------------------------------------------------------------


class TestBootstrapResult:
    """Tests for the BootstrapResult model."""

    def test_successful_when_no_errors(self):
        result = BootstrapResult(genesis_authority="test")
        assert result.is_successful

    def test_not_successful_with_errors(self):
        result = BootstrapResult(genesis_authority="test", errors=["something broke"])
        assert not result.is_successful
