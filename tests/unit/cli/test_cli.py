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
