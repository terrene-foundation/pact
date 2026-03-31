# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for PACT CLI entry point (Task 113).

Tests the Click CLI with --version, validate, and status commands.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def valid_config_file(tmp_path):
    config = tmp_path / "test-config.yaml"
    config.write_text(
        """
name: "Test Org"
genesis:
  authority: "test.org"
  authority_name: "Test Organization"
"""
    )
    return config


@pytest.fixture()
def invalid_config_file(tmp_path):
    config = tmp_path / "bad-config.yaml"
    config.write_text(
        """
# Missing required 'name' and 'genesis' fields
version: "1.0"
"""
    )
    return config


class TestCLIVersion:
    def test_version_flag(self, runner):
        from pact_platform import __version__
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_shows_pact(self, runner):
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["--version"])
        assert "pact" in result.output.lower()


class TestCLIHelp:
    def test_help_flag(self, runner):
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "validate" in result.output
        assert "status" in result.output

    def test_validate_help(self, runner):
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["validate", "--help"])
        assert result.exit_code == 0


class TestCLIValidate:
    def test_validate_valid_config(self, runner, valid_config_file):
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["validate", str(valid_config_file)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "ok" in result.output.lower()

    def test_validate_invalid_config(self, runner, invalid_config_file):
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["validate", str(invalid_config_file)])
        assert result.exit_code != 0

    def test_validate_nonexistent_file(self, runner):
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["validate", "/nonexistent/path/config.yaml"])
        assert result.exit_code != 0

    def test_validate_example_config(self, runner):
        from pact_platform.build.cli import main

        example_path = Path(__file__).parents[3] / "examples" / "care-config.yaml"
        if example_path.exists():
            result = runner.invoke(main, ["validate", str(example_path)])
            assert result.exit_code == 0

    def test_validate_minimal_config(self, runner):
        from pact_platform.build.cli import main

        example_path = Path(__file__).parents[3] / "examples" / "minimal-config.yaml"
        if example_path.exists():
            result = runner.invoke(main, ["validate", str(example_path)])
            assert result.exit_code == 0

    def test_validate_shows_details_on_success(self, runner, valid_config_file):
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["validate", str(valid_config_file)])
        assert result.exit_code == 0
        # Should show at least something about the validated config
        assert "Test Org" in result.output or "valid" in result.output.lower()


class TestCLIStatus:
    def test_status_command_exists(self, runner):
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0

    def test_status_shows_no_active_workspaces(self, runner):
        from pact_platform.build.cli import main

        result = runner.invoke(main, ["status"])
        assert "no active workspaces" in result.output.lower()


class TestCLIModuleExecutable:
    def test_cli_module_importable(self):
        """Verify pact.build.cli is importable and has main."""
        from pact_platform.build.cli import main

        assert callable(main)


class TestBridgeApproveCLI:
    """Tests for `pact bridge approve` command (TODO-10 L3 wiring)."""

    def test_bridge_approve_no_engine(self, runner):
        import pact_platform.cli as cli_mod

        old_engine = cli_mod._engine
        cli_mod._engine = None
        try:
            result = runner.invoke(
                cli_mod.main, ["bridge", "approve", "D1-R1", "D1-R1-T1-R1", "D1-R1"]
            )
            assert result.exit_code != 0
            assert "no org loaded" in result.output.lower()
        finally:
            cli_mod._engine = old_engine

    def test_bridge_approve_invalid_address(self, runner):
        import pact_platform.cli as cli_mod

        result = runner.invoke(
            cli_mod.main, ["bridge", "approve", "INVALID", "D1-R1-T1-R1", "D1-R1"]
        )
        assert result.exit_code != 0

    def test_bridge_approve_success(self, runner):
        from unittest.mock import MagicMock

        import pact_platform.cli as cli_mod

        mock_engine = MagicMock()
        mock_approval = MagicMock()
        mock_approval.expires_at = "2026-04-01T00:00:00"
        mock_engine.approve_bridge.return_value = mock_approval
        old_engine = cli_mod._engine
        cli_mod._engine = mock_engine
        try:
            result = runner.invoke(
                cli_mod.main, ["bridge", "approve", "D1-R1", "D1-R1-T1-R1", "D1-R1"]
            )
            assert result.exit_code == 0
            assert "approved" in result.output.lower()
            mock_engine.approve_bridge.assert_called_once()
        finally:
            cli_mod._engine = old_engine


class TestRoleDesignateActingCLI:
    """Tests for `pact role designate-acting` command (TODO-11 L3 wiring)."""

    def test_designate_acting_no_engine(self, runner):
        import pact_platform.cli as cli_mod

        old_engine = cli_mod._engine
        cli_mod._engine = None
        try:
            result = runner.invoke(
                cli_mod.main, ["role", "designate-acting", "D1-R1", "D1-R1-T1-R1", "D1-R1"]
            )
            assert result.exit_code != 0
            assert "no org loaded" in result.output.lower()
        finally:
            cli_mod._engine = old_engine

    def test_designate_acting_invalid_address(self, runner):
        import pact_platform.cli as cli_mod

        result = runner.invoke(
            cli_mod.main, ["role", "designate-acting", "INVALID", "D1-R1-T1-R1", "D1-R1"]
        )
        assert result.exit_code != 0

    def test_designate_acting_success(self, runner):
        from unittest.mock import MagicMock

        import pact_platform.cli as cli_mod

        mock_engine = MagicMock()
        mock_designation = MagicMock()
        mock_designation.expires_at = "2026-04-01T00:00:00"
        mock_engine.designate_acting_occupant.return_value = mock_designation
        old_engine = cli_mod._engine
        cli_mod._engine = mock_engine
        try:
            result = runner.invoke(
                cli_mod.main, ["role", "designate-acting", "D1-R1", "D1-R1-T1-R1", "D1-R1"]
            )
            assert result.exit_code == 0
            assert "designated" in result.output.lower()
            mock_engine.designate_acting_occupant.assert_called_once()
        finally:
            cli_mod._engine = old_engine


class TestRoleVacancyStatusCLI:
    """Tests for `pact role vacancy-status` command (TODO-11 L3 wiring)."""

    def test_vacancy_status_no_engine(self, runner):
        import pact_platform.cli as cli_mod

        old_engine = cli_mod._engine
        cli_mod._engine = None
        try:
            result = runner.invoke(cli_mod.main, ["role", "vacancy-status", "D1-R1"])
            assert result.exit_code != 0
            assert "no org loaded" in result.output.lower()
        finally:
            cli_mod._engine = old_engine


class TestGovernanceCLIAuditChain:
    """Verify _make_audit_chain() produces a valid AuditChain."""

    def test_make_audit_chain_returns_valid_chain(self):
        from pact_platform.cli import _make_audit_chain

        chain = _make_audit_chain()
        assert chain.chain_id.startswith("cli-")
        assert chain.length == 0

    def test_make_audit_chain_accepts_appends(self):
        """Audit chain must accept the append() signature GovernanceEngine uses."""
        from pact_platform.build.config.schema import VerificationLevel
        from pact_platform.cli import _make_audit_chain

        chain = _make_audit_chain()
        anchor = chain.append(
            agent_id="governance-engine:test-org",
            action="envelope_created",
            verification_level=VerificationLevel.AUTO_APPROVED,
            metadata={"role_address": "D1-R1", "envelope_id": "env-001"},
        )
        assert chain.length == 1
        assert anchor.action == "envelope_created"
