# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for untested PACT CLI commands.

Tests cover the following previously untested commands:
1. `pact clearance grant` — address validation, level argument, options
2. `pact envelope show` — address validation, no-engine handling
3. `pact agent register` — address validation, agent ID handling
4. `pact audit export` — format options, output handling, no-engine handling
5. `pact quickstart` — command registration, help text, --example option

All tests use Click's CliRunner for isolated invocation.
Engine state is carefully managed via module-level singleton save/restore.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cli_mod():
    """Import pact_platform.cli and return the module."""
    import pact_platform.cli as mod

    return mod


@pytest.fixture()
def no_engine(cli_mod):
    """Context manager fixture that ensures _engine is None during the test."""
    old_engine = cli_mod._engine
    old_mapping = cli_mod._agent_mapping
    old_chain = cli_mod._audit_chain
    cli_mod._engine = None
    cli_mod._agent_mapping = None
    cli_mod._audit_chain = None
    yield
    cli_mod._engine = old_engine
    cli_mod._agent_mapping = old_mapping
    cli_mod._audit_chain = old_chain


@pytest.fixture()
def mock_engine_fixture(cli_mod):
    """Fixture that provides a MagicMock engine set as the module-level singleton.

    Restores previous state after the test.
    """
    old_engine = cli_mod._engine
    old_mapping = cli_mod._agent_mapping
    old_chain = cli_mod._audit_chain

    mock_engine = MagicMock()
    mock_engine.org_name = "Test Org"
    mock_org = MagicMock()
    mock_org.nodes = {"D1-R1": MagicMock(), "D1-R1-T1-R1": MagicMock()}
    mock_org.root_roles = ["D1-R1"]
    mock_engine.get_org.return_value = mock_org
    mock_engine.get_node.return_value = None
    mock_engine.compute_envelope.return_value = None

    cli_mod._engine = mock_engine
    yield mock_engine
    cli_mod._engine = old_engine
    cli_mod._agent_mapping = old_mapping
    cli_mod._audit_chain = old_chain


# ===========================================================================
# 1. pact clearance grant
# ===========================================================================


class TestClearanceGrantCLI:
    """Tests for `pact clearance grant <address> <level>` command."""

    def test_clearance_grant_help(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["clearance", "grant", "--help"])
        assert result.exit_code == 0
        assert "grant" in result.output.lower()
        assert "address" in result.output.lower()
        assert "level" in result.output.lower()

    def test_clearance_grant_missing_address(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["clearance", "grant"])
        assert result.exit_code != 0
        assert "missing" in result.output.lower() or "error" in result.output.lower()

    def test_clearance_grant_missing_level(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["clearance", "grant", "D1-R1"])
        assert result.exit_code != 0

    def test_clearance_grant_invalid_level(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["clearance", "grant", "D1-R1", "invalid_level"])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "choice" in result.output.lower()

    def test_clearance_grant_invalid_address(self, runner: CliRunner, cli_mod, no_engine) -> None:
        result = runner.invoke(cli_mod.main, ["clearance", "grant", "INVALID", "public"])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_clearance_grant_valid_no_engine(self, runner: CliRunner, cli_mod, no_engine) -> None:
        """When no engine is loaded, clearance grant still succeeds (displays info)."""
        result = runner.invoke(cli_mod.main, ["clearance", "grant", "D1-R1", "public"])
        assert result.exit_code == 0
        assert "granted" in result.output.lower()
        assert "PUBLIC" in result.output
        assert "no engine loaded" in result.output.lower()

    def test_clearance_grant_with_engine(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        result = runner.invoke(cli_mod.main, ["clearance", "grant", "D1-R1", "confidential"])
        assert result.exit_code == 0
        assert "granted" in result.output.lower()
        assert "CONFIDENTIAL" in result.output
        mock_engine_fixture.grant_clearance.assert_called_once()

    def test_clearance_grant_all_levels(self, runner: CliRunner, cli_mod, no_engine) -> None:
        """All five clearance levels should be accepted."""
        levels = ["public", "restricted", "confidential", "secret", "top_secret"]
        for level in levels:
            result = runner.invoke(cli_mod.main, ["clearance", "grant", "D1-R1", level])
            assert result.exit_code == 0, f"Level {level} failed: {result.output}"
            assert "granted" in result.output.lower()

    def test_clearance_grant_with_compartments(self, runner: CliRunner, cli_mod, no_engine) -> None:
        result = runner.invoke(
            cli_mod.main,
            [
                "clearance",
                "grant",
                "D1-R1",
                "confidential",
                "-c",
                "finance",
                "-c",
                "legal",
            ],
        )
        assert result.exit_code == 0
        assert "finance" in result.output
        assert "legal" in result.output

    def test_clearance_grant_with_nda_flag(self, runner: CliRunner, cli_mod, no_engine) -> None:
        result = runner.invoke(cli_mod.main, ["clearance", "grant", "D1-R1", "secret", "--nda"])
        assert result.exit_code == 0
        assert "yes" in result.output.lower()

    def test_clearance_grant_shows_address_in_output(
        self, runner: CliRunner, cli_mod, no_engine
    ) -> None:
        result = runner.invoke(cli_mod.main, ["clearance", "grant", "D1-R1-T1-R1", "restricted"])
        assert result.exit_code == 0
        assert "D1-R1-T1-R1" in result.output

    def test_clearance_grant_engine_failure(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        mock_engine_fixture.grant_clearance.side_effect = RuntimeError("Engine error")
        result = runner.invoke(cli_mod.main, ["clearance", "grant", "D1-R1", "public"])
        assert result.exit_code != 0
        assert "failed" in result.output.lower()


# ===========================================================================
# 2. pact envelope show
# ===========================================================================


class TestEnvelopeShowCLI:
    """Tests for `pact envelope show <address>` command."""

    def test_envelope_show_help(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["envelope", "show", "--help"])
        assert result.exit_code == 0
        assert "address" in result.output.lower()

    def test_envelope_show_missing_address(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["envelope", "show"])
        assert result.exit_code != 0
        assert "missing" in result.output.lower() or "error" in result.output.lower()

    def test_envelope_show_invalid_address(self, runner: CliRunner, cli_mod, no_engine) -> None:
        result = runner.invoke(cli_mod.main, ["envelope", "show", "INVALID"])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_envelope_show_no_engine(self, runner: CliRunner, cli_mod, no_engine) -> None:
        """When no engine is loaded, envelope show reports the error."""
        result = runner.invoke(cli_mod.main, ["envelope", "show", "D1-R1"])
        assert result.exit_code != 0
        assert "no org loaded" in result.output.lower()

    def test_envelope_show_no_envelope_configured(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        """When the engine returns None for a role, show a 'no envelope' message."""
        mock_engine_fixture.compute_envelope.return_value = None
        result = runner.invoke(cli_mod.main, ["envelope", "show", "D1-R1"])
        assert result.exit_code == 0
        assert "no envelope" in result.output.lower()

    def test_envelope_show_with_envelope(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        """When the engine returns a real envelope config, display all five dimensions."""
        from types import SimpleNamespace

        mock_envelope = SimpleNamespace(
            financial=SimpleNamespace(
                max_spend_usd=5000.0,
                requires_approval_above_usd=1000.0,
                api_cost_budget_usd=500.0,
            ),
            operational=SimpleNamespace(
                allowed_actions=["read", "write"],
                blocked_actions=[],
                max_actions_per_day=100,
                max_actions_per_hour=20,
            ),
            temporal=SimpleNamespace(
                active_hours_start="08:00",
                active_hours_end="18:00",
                timezone="UTC",
                blackout_periods=[],
            ),
            data_access=SimpleNamespace(
                read_paths=["/data/*"],
                write_paths=["/data/output/*"],
                blocked_data_types=[],
            ),
            communication=SimpleNamespace(
                internal_only=True,
                allowed_channels=["slack"],
                external_requires_approval=True,
            ),
            dimension_scope=None,
        )

        mock_engine_fixture.compute_envelope.return_value = mock_envelope

        result = runner.invoke(cli_mod.main, ["envelope", "show", "D1-R1"])
        assert result.exit_code == 0
        assert "financial" in result.output.lower()
        assert "operational" in result.output.lower()
        assert "temporal" in result.output.lower()
        assert "data access" in result.output.lower()
        assert "communication" in result.output.lower()

    def test_envelope_show_displays_address(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        mock_engine_fixture.compute_envelope.return_value = None
        result = runner.invoke(cli_mod.main, ["envelope", "show", "D1-R1-T1-R1"])
        assert result.exit_code == 0
        assert "D1-R1-T1-R1" in result.output


# ===========================================================================
# 3. pact agent register
# ===========================================================================


class TestAgentRegisterCLI:
    """Tests for `pact agent register <agent_id> <role_address>` command."""

    def test_agent_register_help(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["agent", "register", "--help"])
        assert result.exit_code == 0
        assert "agent_id" in result.output.lower()
        assert "role_address" in result.output.lower()

    def test_agent_register_missing_args(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["agent", "register"])
        assert result.exit_code != 0

    def test_agent_register_missing_role_address(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["agent", "register", "agent-001"])
        assert result.exit_code != 0

    def test_agent_register_invalid_address(self, runner: CliRunner, cli_mod, no_engine) -> None:
        result = runner.invoke(cli_mod.main, ["agent", "register", "agent-001", "INVALID"])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_agent_register_valid_no_engine(self, runner: CliRunner, cli_mod, no_engine) -> None:
        """When no engine is loaded, agent register still creates the mapping."""
        result = runner.invoke(cli_mod.main, ["agent", "register", "agent-cs-001", "D1-R1"])
        assert result.exit_code == 0
        assert "registered" in result.output.lower()
        assert "agent-cs-001" in result.output
        assert "D1-R1" in result.output

    def test_agent_register_with_engine(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        result = runner.invoke(cli_mod.main, ["agent", "register", "agent-001", "D1-R1"])
        assert result.exit_code == 0
        assert "registered" in result.output.lower()
        assert "agent-001" in result.output

    def test_agent_register_shows_role_name_when_engine_provides_it(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        mock_node = MagicMock()
        mock_node.name = "Test Role Name"
        mock_engine_fixture.get_node.return_value = mock_node
        result = runner.invoke(cli_mod.main, ["agent", "register", "agent-002", "D1-R1"])
        assert result.exit_code == 0
        assert "Test Role Name" in result.output

    def test_agent_register_creates_mapping_if_none(
        self, runner: CliRunner, cli_mod, no_engine
    ) -> None:
        """If _agent_mapping is None, register should create one."""
        assert cli_mod._agent_mapping is None
        result = runner.invoke(cli_mod.main, ["agent", "register", "agent-new", "D1-R1"])
        assert result.exit_code == 0
        # After invocation, mapping should have been created
        assert cli_mod._agent_mapping is not None


# ===========================================================================
# 4. pact audit export
# ===========================================================================


class TestAuditExportCLI:
    """Tests for `pact audit export [--format json|csv] [--output FILE]` command."""

    def test_audit_export_help(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["audit", "export", "--help"])
        assert result.exit_code == 0
        assert "format" in result.output.lower()
        assert "json" in result.output.lower()
        assert "csv" in result.output.lower()

    def test_audit_export_no_engine_json(self, runner: CliRunner, cli_mod, no_engine) -> None:
        """With no engine, audit export outputs an empty JSON array."""
        result = runner.invoke(cli_mod.main, ["audit", "export", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip().split("\n")[0])
        assert isinstance(data, list)
        assert len(data) == 0

    def test_audit_export_no_engine_csv(self, runner: CliRunner, cli_mod, no_engine) -> None:
        """With no engine, audit export outputs a minimal CSV header."""
        result = runner.invoke(cli_mod.main, ["audit", "export", "--format", "csv"])
        assert result.exit_code == 0
        assert "type" in result.output.lower()

    def test_audit_export_default_format_is_json(
        self, runner: CliRunner, cli_mod, no_engine
    ) -> None:
        """Default format should be json."""
        result = runner.invoke(cli_mod.main, ["audit", "export"])
        assert result.exit_code == 0
        # The output contains the JSON followed by a stderr message from Rich
        # console. Extract just the JSON portion (starts with '[').
        output = result.output.strip()
        json_end = output.index("]") + 1
        data = json.loads(output[:json_end])
        assert isinstance(data, list)

    def test_audit_export_with_engine_json(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        """With engine loaded but no audit anchors, export a governance snapshot."""
        mock_engine_fixture.audit_chain = MagicMock()
        mock_engine_fixture.audit_chain.anchors = []

        result = runner.invoke(cli_mod.main, ["audit", "export", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert isinstance(data, list)
        # Should have at least the governance snapshot record
        assert len(data) >= 1
        assert data[0]["type"] == "governance_snapshot"
        assert data[0]["org_name"] == "Test Org"

    def test_audit_export_with_engine_csv(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        mock_engine_fixture.audit_chain = MagicMock()
        mock_engine_fixture.audit_chain.anchors = []

        result = runner.invoke(cli_mod.main, ["audit", "export", "--format", "csv"])
        assert result.exit_code == 0
        assert "governance_snapshot" in result.output

    def test_audit_export_to_file(self, runner: CliRunner, cli_mod, no_engine, tmp_path) -> None:
        output_file = tmp_path / "audit.json"
        result = runner.invoke(
            cli_mod.main, ["audit", "export", "--format", "json", "--output", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert isinstance(data, list)

    def test_audit_export_csv_to_file(
        self, runner: CliRunner, cli_mod, no_engine, tmp_path
    ) -> None:
        output_file = tmp_path / "audit.csv"
        result = runner.invoke(
            cli_mod.main, ["audit", "export", "--format", "csv", "--output", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "type" in content.lower()

    def test_audit_export_invalid_format(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["audit", "export", "--format", "xml"])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "choice" in result.output.lower()

    def test_audit_export_with_real_anchors(
        self, runner: CliRunner, cli_mod, mock_engine_fixture: MagicMock
    ) -> None:
        """When audit chain has actual anchors, they should appear in the output."""
        mock_anchor = MagicMock()
        mock_anchor.to_dict.return_value = {
            "agent_id": "governance-engine:test",
            "action": "clearance_granted",
            "verification_level": "AUTO_APPROVED",
        }

        mock_chain = MagicMock()
        mock_chain.anchors = [mock_anchor]
        mock_engine_fixture.audit_chain = mock_chain

        result = runner.invoke(cli_mod.main, ["audit", "export", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert len(data) == 1
        assert data[0]["action"] == "clearance_granted"


# ===========================================================================
# 5. pact quickstart
# ===========================================================================


class TestQuickstartCLI:
    """Tests for `pact quickstart` command."""

    def test_quickstart_is_registered(self, runner: CliRunner, cli_mod) -> None:
        """Verify quickstart is a registered command in the main group."""
        result = runner.invoke(cli_mod.main, ["--help"])
        assert result.exit_code == 0
        assert "quickstart" in result.output

    def test_quickstart_help(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["quickstart", "--help"])
        assert result.exit_code == 0
        assert "example" in result.output.lower()
        assert "university" in result.output.lower()

    def test_quickstart_requires_example(self, runner: CliRunner, cli_mod) -> None:
        """quickstart without --example should fail because --example is required."""
        result = runner.invoke(cli_mod.main, ["quickstart"])
        assert result.exit_code != 0
        assert "missing" in result.output.lower() or "required" in result.output.lower()

    def test_quickstart_invalid_example(self, runner: CliRunner, cli_mod) -> None:
        """quickstart with an unknown example name should fail."""
        result = runner.invoke(cli_mod.main, ["quickstart", "--example", "nonexistent"])
        assert result.exit_code != 0
        assert (
            "invalid" in result.output.lower()
            or "choice" in result.output.lower()
            or "nonexistent" in result.output.lower()
        )

    def test_quickstart_university_no_serve(self, runner: CliRunner, cli_mod) -> None:
        """quickstart --example university --no-serve should compile and display the org."""
        result = runner.invoke(
            cli_mod.main, ["quickstart", "--example", "university", "--no-serve"]
        )
        assert result.exit_code == 0
        assert "compiled" in result.output.lower() or "university" in result.output.lower()
        assert "ready" in result.output.lower()

    def test_quickstart_shows_serve_options(self, runner: CliRunner, cli_mod) -> None:
        """Help should show --serve/--no-serve, --host, and --port options."""
        result = runner.invoke(cli_mod.main, ["quickstart", "--help"])
        assert result.exit_code == 0
        assert "serve" in result.output.lower()
        assert "host" in result.output.lower()
        assert "port" in result.output.lower()


# ===========================================================================
# 6. Command group registration — verify all groups exist
# ===========================================================================


class TestCommandGroupRegistration:
    """Verify that all top-level command groups are registered on main."""

    def test_clearance_group_exists(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["clearance", "--help"])
        assert result.exit_code == 0
        assert "grant" in result.output

    def test_envelope_group_exists(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["envelope", "--help"])
        assert result.exit_code == 0
        assert "show" in result.output

    def test_agent_group_exists(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["agent", "--help"])
        assert result.exit_code == 0
        assert "register" in result.output

    def test_audit_group_exists(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["audit", "--help"])
        assert result.exit_code == 0
        assert "export" in result.output

    def test_all_commands_in_main_help(self, runner: CliRunner, cli_mod) -> None:
        result = runner.invoke(cli_mod.main, ["--help"])
        assert result.exit_code == 0
        for cmd in ["clearance", "envelope", "agent", "audit", "quickstart", "org"]:
            assert cmd in result.output, f"Expected '{cmd}' in main help output"
