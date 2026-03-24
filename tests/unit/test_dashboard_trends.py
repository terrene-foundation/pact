# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for L9: Dashboard trends endpoint.

Validates that GET /api/v1/dashboard/trends computes 7-day daily counts
from audit anchor timestamps, grouped by date and verification level.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

import pact_platform.use.api.server as server_module
from pact_platform.build.config.env import EnvConfig
from pact_platform.build.config.schema import VerificationLevel
from pact_platform.trust.audit.anchor import AuditChain
from pact_platform.trust.store.cost_tracking import CostTracker
from pact_platform.use.api.endpoints import PactAPI
from pact_platform.use.api.server import create_app
from pact_platform.use.execution.approval import ApprovalQueue
from pact_platform.use.execution.registry import AgentRegistry


@pytest.fixture(autouse=True)
def _reset_default_api():
    """Reset module-level _default_api between tests."""
    old = server_module._default_api
    server_module._default_api = None
    yield
    server_module._default_api = old


def _make_chain_with_anchors() -> AuditChain:
    """Create an audit chain with anchors spread over the last 7 days."""
    chain = AuditChain(chain_id="test-chain")
    now = datetime.now(UTC)

    # Day 0 (today): 2 AUTO_APPROVED, 1 FLAGGED
    for _ in range(2):
        anchor = chain.append(
            agent_id="agent-1",
            action="test-action",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        # Override timestamp to today
        anchor.timestamp = now
    anchor = chain.append(
        agent_id="agent-1",
        action="test-action",
        verification_level=VerificationLevel.FLAGGED,
    )
    anchor.timestamp = now

    # Day -1 (yesterday): 1 HELD
    anchor = chain.append(
        agent_id="agent-1",
        action="test-action",
        verification_level=VerificationLevel.HELD,
    )
    anchor.timestamp = now - timedelta(days=1)

    # Day -3: 1 BLOCKED
    anchor = chain.append(
        agent_id="agent-1",
        action="test-action",
        verification_level=VerificationLevel.BLOCKED,
    )
    anchor.timestamp = now - timedelta(days=3)

    # Day -6: 2 AUTO_APPROVED
    for _ in range(2):
        anchor = chain.append(
            agent_id="agent-1",
            action="test-action",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.timestamp = now - timedelta(days=6)

    return chain


@pytest.fixture()
def audit_chain() -> AuditChain:
    """An audit chain with anchors spread across 7 days."""
    return _make_chain_with_anchors()


@pytest.fixture()
def platform_api(audit_chain: AuditChain) -> PactAPI:
    """PactAPI wired with an audit chain for trends."""
    return PactAPI(
        registry=AgentRegistry(),
        approval_queue=ApprovalQueue(),
        cost_tracker=CostTracker(),
        audit_chain=audit_chain,
        verification_stats={},
    )


@pytest.fixture()
def app(platform_api: PactAPI) -> object:
    """FastAPI app with dev config and wired PactAPI."""
    cfg = EnvConfig(pact_dev_mode=True, pact_api_token="")
    return create_app(platform_api=platform_api, env_config=cfg)


@pytest.fixture()
async def client(app) -> httpx.AsyncClient:
    """Async HTTP client targeting the test app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestDashboardTrendsEndpoint:
    """L9: GET /api/v1/dashboard/trends returns 7-day daily counts."""

    @pytest.mark.asyncio
    async def test_trends_endpoint_returns_200(self, client: httpx.AsyncClient):
        """The trends endpoint should return HTTP 200."""
        resp = await client.get("/api/v1/dashboard/trends")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_trends_response_has_required_fields(self, client: httpx.AsyncClient):
        """Response must contain dates and per-level count arrays."""
        resp = await client.get("/api/v1/dashboard/trends")
        data = resp.json()
        assert data["status"] == "ok"
        trend_data = data["data"]
        assert "dates" in trend_data
        assert "auto_approved" in trend_data
        assert "flagged" in trend_data
        assert "held" in trend_data
        assert "blocked" in trend_data

    @pytest.mark.asyncio
    async def test_trends_has_7_days(self, client: httpx.AsyncClient):
        """Each array should have exactly 7 entries (one per day)."""
        resp = await client.get("/api/v1/dashboard/trends")
        trend_data = resp.json()["data"]
        assert len(trend_data["dates"]) == 7
        assert len(trend_data["auto_approved"]) == 7
        assert len(trend_data["flagged"]) == 7
        assert len(trend_data["held"]) == 7
        assert len(trend_data["blocked"]) == 7

    @pytest.mark.asyncio
    async def test_trends_dates_are_iso_format(self, client: httpx.AsyncClient):
        """Dates should be in ISO format (YYYY-MM-DD)."""
        resp = await client.get("/api/v1/dashboard/trends")
        dates = resp.json()["data"]["dates"]
        for d in dates:
            # Should parse without error
            datetime.strptime(d, "%Y-%m-%d")

    @pytest.mark.asyncio
    async def test_trends_counts_are_integers(self, client: httpx.AsyncClient):
        """All count values should be non-negative integers."""
        resp = await client.get("/api/v1/dashboard/trends")
        trend_data = resp.json()["data"]
        for key in ("auto_approved", "flagged", "held", "blocked"):
            for val in trend_data[key]:
                assert isinstance(val, int)
                assert val >= 0

    @pytest.mark.asyncio
    async def test_trends_reflect_actual_data(self, client: httpx.AsyncClient):
        """Counts should reflect the actual anchors in the audit chain."""
        resp = await client.get("/api/v1/dashboard/trends")
        trend_data = resp.json()["data"]
        # Sum of auto_approved across 7 days should be 4 (2 today + 2 at day -6)
        assert sum(trend_data["auto_approved"]) == 4
        # Sum of flagged should be 1
        assert sum(trend_data["flagged"]) == 1
        # Sum of held should be 1
        assert sum(trend_data["held"]) == 1
        # Sum of blocked should be 1
        assert sum(trend_data["blocked"]) == 1


class TestDashboardTrendsNoAuditChain:
    """L9: Trends endpoint when no audit chain is configured."""

    @pytest.mark.asyncio
    async def test_trends_without_audit_chain_returns_zeros(self):
        """When no audit chain is wired, return 7 days of zeros."""
        api = PactAPI(
            registry=AgentRegistry(),
            approval_queue=ApprovalQueue(),
            cost_tracker=CostTracker(),
            verification_stats={},
        )
        cfg = EnvConfig(pact_dev_mode=True, pact_api_token="")
        application = create_app(platform_api=api, env_config=cfg)

        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/dashboard/trends")
            assert resp.status_code == 200
            trend_data = resp.json()["data"]
            assert len(trend_data["dates"]) == 7
            assert all(v == 0 for v in trend_data["auto_approved"])
            assert all(v == 0 for v in trend_data["flagged"])
            assert all(v == 0 for v in trend_data["held"])
            assert all(v == 0 for v in trend_data["blocked"])
