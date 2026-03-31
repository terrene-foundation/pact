# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the `pact mcp` CLI command group.

Tests:
- `pact mcp status` — reports MCP governance configuration status
- `pact mcp evaluate` — evaluates a tool call against governance
"""

from __future__ import annotations

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
    """Ensure _engine is None during the test."""
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
    """Provide a MagicMock engine as module-level singleton."""
    old_engine = cli_mod._engine
    old_mapping = cli_mod._agent_mapping
    old_chain = cli_mod._audit_chain

    mock_engine = MagicMock()
    mock_engine.org_name = "Test Org"
    mock_org = MagicMock()
    mock_org.nodes = {"D1-R1": MagicMock(), "D1-R1-T1-R1": MagicMock()}
    mock_org.root_roles = ["D1-R1"]
    mock_engine.get_org.return_value = mock_org
    mock_engine.compute_envelope.return_value = None

    cli_mod._engine = mock_engine
    yield mock_engine
    cli_mod._engine = old_engine
    cli_mod._agent_mapping = old_mapping
    cli_mod._audit_chain = old_chain


# ---------------------------------------------------------------------------
# Tests: pact mcp status
# ---------------------------------------------------------------------------


class TestMcpStatus:
    """Test `pact mcp status` command."""

    def test_status_no_engine(self, runner, cli_mod, no_engine):
        result = runner.invoke(cli_mod.main, ["mcp", "status"])
        assert result.exit_code == 0
        assert "not configured" in result.output.lower() or "no org" in result.output.lower()

    def test_status_with_engine(self, runner, cli_mod, mock_engine_fixture):
        result = runner.invoke(cli_mod.main, ["mcp", "status"])
        assert result.exit_code == 0
        # Should show that MCP governance is available
        assert "mcp" in result.output.lower()

    def test_status_help(self, runner, cli_mod):
        result = runner.invoke(cli_mod.main, ["mcp", "status", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output.lower()


# ---------------------------------------------------------------------------
# Tests: pact mcp evaluate
# ---------------------------------------------------------------------------


class TestMcpEvaluate:
    """Test `pact mcp evaluate` command."""

    def test_evaluate_no_engine(self, runner, cli_mod, no_engine):
        result = runner.invoke(
            cli_mod.main, ["mcp", "evaluate", "--tool", "web_search", "--agent", "D1-R1"]
        )
        assert result.exit_code != 0

    def test_evaluate_with_engine(self, runner, cli_mod, mock_engine_fixture):
        result = runner.invoke(
            cli_mod.main, ["mcp", "evaluate", "--tool", "web_search", "--agent", "D1-R1"]
        )
        assert result.exit_code == 0
        # Should show a verdict
        output_lower = result.output.lower()
        assert any(
            level in output_lower for level in ["auto_approved", "blocked", "flagged", "held"]
        )

    def test_evaluate_missing_tool_flag(self, runner, cli_mod, mock_engine_fixture):
        result = runner.invoke(cli_mod.main, ["mcp", "evaluate", "--agent", "D1-R1"])
        assert result.exit_code != 0

    def test_evaluate_missing_agent_flag(self, runner, cli_mod, mock_engine_fixture):
        result = runner.invoke(cli_mod.main, ["mcp", "evaluate", "--tool", "web_search"])
        assert result.exit_code != 0

    def test_evaluate_help(self, runner, cli_mod):
        result = runner.invoke(cli_mod.main, ["mcp", "evaluate", "--help"])
        assert result.exit_code == 0
        assert "tool" in result.output.lower()
        assert "agent" in result.output.lower()


# ---------------------------------------------------------------------------
# Tests: pact mcp group
# ---------------------------------------------------------------------------


class TestMcpGroup:
    """Test the `pact mcp` command group registration."""

    def test_mcp_group_exists(self, runner, cli_mod):
        result = runner.invoke(cli_mod.main, ["mcp", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output.lower()
        assert "evaluate" in result.output.lower()

    def test_mcp_group_in_main_help(self, runner, cli_mod):
        result = runner.invoke(cli_mod.main, ["--help"])
        assert result.exit_code == 0
        assert "mcp" in result.output.lower()
