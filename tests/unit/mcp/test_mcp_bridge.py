# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the L3 MCP governance bridge.

Tests PlatformMcpGovernance — the bridge that connects the L1 McpGovernanceEnforcer
to the platform's governance config, audit logging, and GovernanceEngine.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_engine():
    """Create a mock GovernanceEngine with basic behaviour."""
    engine = MagicMock()
    engine.org_name = "Test Org"
    mock_org = MagicMock()
    mock_org.nodes = {"D1-R1": MagicMock(), "D1-R1-T1-R1": MagicMock()}
    engine.get_org.return_value = mock_org
    return engine


@pytest.fixture()
def tool_policies():
    """A list of tool policy dicts as they would appear in org config."""
    return [
        {
            "tool_name": "web_search",
            "clearance_required": "public",
            "max_cost": 1.0,
            "description": "Search the web",
        },
        {
            "tool_name": "database_write",
            "clearance_required": "confidential",
            "max_cost": 10.0,
            "description": "Write to database",
        },
    ]


# ---------------------------------------------------------------------------
# Tests: PlatformMcpGovernance construction
# ---------------------------------------------------------------------------


class TestPlatformMcpGovernanceConstruction:
    """Test construction and configuration of PlatformMcpGovernance."""

    def test_creates_with_engine_and_policies(self, mock_engine, tool_policies):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        assert gov.engine is mock_engine
        assert gov.is_configured()

    def test_creates_with_empty_policies(self, mock_engine):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=[])

        assert gov.is_configured()

    def test_raises_on_none_engine(self):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        with pytest.raises(ValueError, match="engine"):
            PlatformMcpGovernance(engine=None, tool_policies=[])

    def test_registers_tool_policies_from_config(self, mock_engine, tool_policies):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        # The bridge should have registered both tools with the L1 enforcer
        registered = gov.registered_tools()
        assert "web_search" in registered
        assert "database_write" in registered


# ---------------------------------------------------------------------------
# Tests: evaluate_tool_call
# ---------------------------------------------------------------------------


class TestEvaluateToolCall:
    """Test the evaluate_tool_call method."""

    def test_auto_approved_for_registered_tool(self, mock_engine, tool_policies):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        result = gov.evaluate_tool_call(
            tool_name="web_search",
            args={"query": "test"},
            agent_address="D1-R1",
        )

        assert result["level"] == "auto_approved"
        assert result["tool_name"] == "web_search"
        assert "agent_address" in result

    def test_blocked_for_unregistered_tool(self, mock_engine, tool_policies):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        result = gov.evaluate_tool_call(
            tool_name="unknown_tool",
            args={},
            agent_address="D1-R1",
        )

        assert result["level"] == "blocked"

    def test_result_contains_reason(self, mock_engine, tool_policies):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        result = gov.evaluate_tool_call(
            tool_name="web_search",
            args={},
            agent_address="D1-R1",
        )

        assert "reason" in result
        assert isinstance(result["reason"], str)
        assert len(result["reason"]) > 0

    def test_result_contains_timestamp(self, mock_engine, tool_policies):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        result = gov.evaluate_tool_call(
            tool_name="web_search",
            args={},
            agent_address="D1-R1",
        )

        assert "timestamp" in result

    def test_audit_trail_records_evaluation(self, mock_engine, tool_policies):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        gov.evaluate_tool_call(
            tool_name="web_search",
            args={"query": "test"},
            agent_address="D1-R1",
        )

        trail = gov.get_audit_trail()
        assert len(trail) == 1
        assert trail[0]["tool_name"] == "web_search"
        assert trail[0]["agent_id"] == "D1-R1"

    def test_multiple_evaluations_accumulate_audit(self, mock_engine, tool_policies):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        gov.evaluate_tool_call("web_search", {}, "D1-R1")
        gov.evaluate_tool_call("database_write", {}, "D1-R1-T1-R1")
        gov.evaluate_tool_call("unknown_tool", {}, "D1-R1")

        trail = gov.get_audit_trail()
        assert len(trail) == 3


# ---------------------------------------------------------------------------
# Tests: audit logging
# ---------------------------------------------------------------------------


class TestAuditLogging:
    """Test that evaluations emit platform-level audit logs."""

    def test_approved_tool_logs_info(self, mock_engine, tool_policies, caplog):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        with caplog.at_level(logging.INFO, logger="pact_platform.use.mcp.bridge"):
            gov.evaluate_tool_call("web_search", {}, "D1-R1")

        assert any("auto_approved" in r.message for r in caplog.records)

    def test_blocked_tool_logs_warning(self, mock_engine, tool_policies, caplog):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        with caplog.at_level(logging.WARNING, logger="pact_platform.use.mcp.bridge"):
            gov.evaluate_tool_call("unknown_tool", {}, "D1-R1")

        assert any("blocked" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Tests: status
# ---------------------------------------------------------------------------


class TestStatus:
    """Test governance status reporting."""

    def test_status_shows_configured(self, mock_engine, tool_policies):
        from pact_platform.use.mcp.bridge import PlatformMcpGovernance

        gov = PlatformMcpGovernance(engine=mock_engine, tool_policies=tool_policies)

        status = gov.status()

        assert status["configured"] is True
        assert status["tool_count"] == 2
        assert "org_name" in status
        assert status["org_name"] == "Test Org"
