# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the `pact audit toctou` CLI command.

Tests the CLI subcommand that runs a post-execution TOCTOU comparison,
checking whether governance envelopes changed since verdicts were issued.
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
    import pact_platform.cli as mod

    return mod


@pytest.fixture()
def no_engine(cli_mod):
    old_engine = cli_mod._engine
    old_chain = cli_mod._audit_chain
    cli_mod._engine = None
    cli_mod._audit_chain = None
    yield
    cli_mod._engine = old_engine
    cli_mod._audit_chain = old_chain


@pytest.fixture()
def mock_engine_with_audit(cli_mod):
    """Provide a mock engine with audit chain that has anchors."""
    old_engine = cli_mod._engine
    old_chain = cli_mod._audit_chain

    mock_engine = MagicMock()
    mock_engine.org_name = "Test Org"
    mock_org = MagicMock()
    mock_org.nodes = {"D1-R1": MagicMock()}
    mock_engine.get_org.return_value = mock_org
    mock_engine.compute_envelope.return_value = None

    # Mock audit chain
    mock_chain = MagicMock()
    mock_chain.anchors = []
    cli_mod._audit_chain = mock_chain

    cli_mod._engine = mock_engine
    yield mock_engine
    cli_mod._engine = old_engine
    cli_mod._audit_chain = old_chain


# ---------------------------------------------------------------------------
# Tests: pact audit toctou
# ---------------------------------------------------------------------------


class TestAuditToctou:
    """Test `pact audit toctou` command."""

    def test_toctou_no_engine(self, runner, cli_mod, no_engine):
        result = runner.invoke(cli_mod.main, ["audit", "toctou"])
        assert result.exit_code != 0

    def test_toctou_with_engine_no_audit_records(self, runner, cli_mod, mock_engine_with_audit):
        result = runner.invoke(cli_mod.main, ["audit", "toctou"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "no" in output_lower or "0" in output_lower

    def test_toctou_help(self, runner, cli_mod):
        result = runner.invoke(cli_mod.main, ["audit", "toctou", "--help"])
        assert result.exit_code == 0
        assert "toctou" in result.output.lower() or "time-of-check" in result.output.lower()

    def test_toctou_command_registered_under_audit(self, runner, cli_mod):
        result = runner.invoke(cli_mod.main, ["audit", "--help"])
        assert result.exit_code == 0
        assert "toctou" in result.output.lower()
