# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Organization Builder CLI commands (Task 705).

Tests the `pact org` subcommand group with:
- org create --template <name> --name <name>
- org validate --config <file>
- org list-templates
"""

import pytest
from click.testing import CliRunner

from pact_platform.build.cli import main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def valid_org_config(tmp_path):
    """A valid org YAML config file."""
    config = tmp_path / "org.yaml"
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
def invalid_org_config(tmp_path):
    """An invalid org YAML config missing required fields."""
    config = tmp_path / "bad-org.yaml"
    config.write_text(
        """
# Missing 'name' and 'genesis'
version: "1.0"
"""
    )
    return config


# ---------------------------------------------------------------------------
# Test: org group exists
# ---------------------------------------------------------------------------


class TestOrgGroupExists:
    def test_org_group_registered(self, runner):
        """The 'org' subcommand group is registered on the main CLI."""
        result = runner.invoke(main, ["org", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "validate" in result.output
        assert "list-templates" in result.output


# ---------------------------------------------------------------------------
# Test: org list-templates
# ---------------------------------------------------------------------------


class TestOrgListTemplates:
    def test_list_templates_succeeds(self, runner):
        """'org list-templates' exits with code 0."""
        result = runner.invoke(main, ["org", "list-templates"])
        assert result.exit_code == 0

    def test_list_templates_shows_builtin_templates(self, runner):
        """list-templates output includes the four built-in templates."""
        result = runner.invoke(main, ["org", "list-templates"])
        assert "media" in result.output.lower()
        assert "governance" in result.output.lower()
        assert "standards" in result.output.lower()
        assert "partnerships" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: org create
# ---------------------------------------------------------------------------


class TestOrgCreate:
    def test_create_with_minimal_template(self, runner, tmp_path):
        """'org create --template minimal --name <name>' creates a valid org."""
        result = runner.invoke(
            main,
            ["org", "create", "--template", "minimal", "--name", "My Test Org"],
        )
        assert result.exit_code == 0
        assert "my test org" in result.output.lower() or "created" in result.output.lower()

    def test_create_with_unknown_template_fails(self, runner):
        """'org create --template nonexistent' fails with an error."""
        result = runner.invoke(
            main,
            ["org", "create", "--template", "nonexistent-template", "--name", "Bad Org"],
        )
        assert result.exit_code != 0

    def test_create_requires_name(self, runner):
        """'org create --template minimal' without --name fails."""
        result = runner.invoke(
            main,
            ["org", "create", "--template", "minimal"],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Test: org validate
# ---------------------------------------------------------------------------


class TestOrgValidate:
    def test_validate_valid_config(self, runner, valid_org_config):
        """'org validate --config <file>' succeeds for a valid config."""
        result = runner.invoke(
            main,
            ["org", "validate", "--config", str(valid_org_config)],
        )
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_invalid_config(self, runner, invalid_org_config):
        """'org validate --config <file>' fails for an invalid config."""
        result = runner.invoke(
            main,
            ["org", "validate", "--config", str(invalid_org_config)],
        )
        assert result.exit_code != 0

    def test_validate_nonexistent_file(self, runner):
        """'org validate --config nonexistent.yaml' fails."""
        result = runner.invoke(
            main,
            ["org", "validate", "--config", "/nonexistent/path/org.yaml"],
        )
        assert result.exit_code != 0
