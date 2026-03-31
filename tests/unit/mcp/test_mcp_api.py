# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the MCP governance API endpoint.

Tests POST /api/v1/mcp/evaluate — evaluates an MCP tool call against governance.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Create a FastAPI test app with the MCP router mounted."""
    from fastapi import FastAPI

    from pact_platform.use.mcp.router import create_mcp_router

    app = FastAPI()
    router = create_mcp_router()
    app.include_router(router, prefix="/api/v1/mcp")
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/mcp/evaluate
# ---------------------------------------------------------------------------


class TestMcpEvaluateEndpoint:
    """Test POST /api/v1/mcp/evaluate."""

    def test_evaluate_returns_verdict(self, client):
        """Evaluating a tool call should return a verdict dict."""
        response = client.post(
            "/api/v1/mcp/evaluate",
            json={
                "tool_name": "web_search",
                "args": {"query": "test"},
                "agent_address": "D1-R1",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "level" in data
        assert "tool_name" in data
        assert "reason" in data
        assert data["tool_name"] == "web_search"

    def test_evaluate_unregistered_tool_blocked(self, client):
        """An unregistered tool should return a blocked verdict."""
        response = client.post(
            "/api/v1/mcp/evaluate",
            json={
                "tool_name": "not_a_real_tool",
                "args": {},
                "agent_address": "D1-R1",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Default-deny means unregistered tools are blocked
        assert data["level"] == "blocked"

    def test_evaluate_missing_tool_name(self, client):
        """Missing tool_name should return 422."""
        response = client.post(
            "/api/v1/mcp/evaluate",
            json={
                "args": {},
                "agent_address": "D1-R1",
            },
        )
        assert response.status_code == 422

    def test_evaluate_missing_agent_address(self, client):
        """Missing agent_address should return 422."""
        response = client.post(
            "/api/v1/mcp/evaluate",
            json={
                "tool_name": "web_search",
                "args": {},
            },
        )
        assert response.status_code == 422

    def test_evaluate_empty_args_accepted(self, client):
        """Empty args dict should be accepted."""
        response = client.post(
            "/api/v1/mcp/evaluate",
            json={
                "tool_name": "web_search",
                "args": {},
                "agent_address": "D1-R1",
            },
        )
        assert response.status_code == 200

    def test_evaluate_returns_timestamp(self, client):
        """Response should include a timestamp."""
        response = client.post(
            "/api/v1/mcp/evaluate",
            json={
                "tool_name": "web_search",
                "args": {},
                "agent_address": "D1-R1",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
