# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for the emergency bypass API router.

Tier 1 (Unit): Tests in dev mode verify endpoint validation, 503 when
bypass engine not configured, and proper responses with a real
EmergencyBypass instance.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api import governance as gov_mod
from pact_platform.use.api.routers import emergency_bypass as bp_mod
from pact_platform.use.api.server import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dev_config() -> EnvConfig:
    return EnvConfig(pact_dev_mode=True, pact_api_token="")


@pytest.fixture()
def app(dev_config: EnvConfig):
    import pact_platform.use.api.server as server_module

    old_default = server_module._default_api
    server_module._default_api = None
    old_engine = gov_mod._engine
    old_dev = gov_mod._dev_mode
    old_dev_frozen = gov_mod._dev_mode_frozen
    old_bypass = bp_mod._bypass
    application = create_app(env_config=dev_config)
    yield application
    server_module._default_api = old_default
    gov_mod._engine = old_engine
    gov_mod._dev_mode = old_dev
    gov_mod._dev_mode_frozen = old_dev_frozen
    bp_mod._bypass = old_bypass


@pytest.fixture()
async def client(app) -> httpx.AsyncClient:  # type: ignore[misc]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.fixture()
def bypass_engine():
    """Create a real EmergencyBypass with in-memory rate limiter."""
    from pact_platform.engine.emergency_bypass import EmergencyBypass

    return EmergencyBypass()


@pytest.fixture()
def client_with_bypass(app, bypass_engine):
    """Wire the bypass engine into the router module."""
    bp_mod.set_bypass(bypass_engine)
    return bypass_engine


# ---------------------------------------------------------------------------
# Validation Tests (no engine)
# ---------------------------------------------------------------------------


class TestBypassRouterValidation:
    """Tests for input validation when bypass engine is NOT configured."""

    async def test_create_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        bp_mod._bypass = None
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={
                "role_address": "D1-R1",
                "tier": "tier_1",
                "reason": "test",
                "approved_by": "admin",
            },
        )
        assert resp.status_code == 503

    async def test_create_requires_role_address(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={"tier": "tier_1", "reason": "test", "approved_by": "admin"},
        )
        assert resp.status_code == 400
        assert "role_address" in resp.json()["detail"]

    async def test_create_requires_tier(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={"role_address": "D1-R1", "reason": "test", "approved_by": "admin"},
        )
        assert resp.status_code == 400
        assert "tier" in resp.json()["detail"]

    async def test_create_requires_reason(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={"role_address": "D1-R1", "tier": "tier_1", "approved_by": "admin"},
        )
        assert resp.status_code == 400
        assert "reason" in resp.json()["detail"]

    async def test_create_requires_approved_by(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={"role_address": "D1-R1", "tier": "tier_1", "reason": "test"},
        )
        assert resp.status_code == 400
        assert "approved_by" in resp.json()["detail"]

    async def test_create_rejects_invalid_address(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={
                "role_address": "D1-D2",
                "tier": "tier_1",
                "reason": "test",
                "approved_by": "admin",
            },
        )
        assert resp.status_code == 400
        assert "D/T/R" in resp.json()["detail"] or "address" in resp.json()["detail"].lower()

    async def test_create_rejects_invalid_tier(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={
                "role_address": "D1-R1",
                "tier": "tier_99",
                "reason": "test",
                "approved_by": "admin",
            },
        )
        assert resp.status_code == 400
        assert "tier" in resp.json()["detail"].lower()

    async def test_create_rejects_invalid_authority_level(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={
                "role_address": "D1-R1",
                "tier": "tier_1",
                "reason": "test",
                "approved_by": "admin",
                "authority_level": "god_mode",
            },
        )
        assert resp.status_code == 400
        assert "authority_level" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Functional Tests (with engine)
# ---------------------------------------------------------------------------


class TestBypassRouterFunctional:
    """Tests with a real EmergencyBypass engine wired in."""

    async def test_create_bypass_succeeds(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={
                "role_address": "D1-R1",
                "tier": "tier_1",
                "reason": "Production incident",
                "approved_by": "admin@example.com",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["data"]["role_address"] == "D1-R1"
        assert data["data"]["tier"] == "tier_1"
        assert data["data"]["bypass_id"]

    async def test_check_bypass_returns_active(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        # Create first
        await client.post(
            "/api/v1/emergency-bypass",
            json={
                "role_address": "D1-R1",
                "tier": "tier_1",
                "reason": "incident",
                "approved_by": "admin",
            },
        )
        # Check
        resp = await client.get("/api/v1/emergency-bypass/check/D1-R1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["data"] is not None
        assert data["data"]["role_address"] == "D1-R1"

    async def test_check_bypass_returns_null_when_none(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.get("/api/v1/emergency-bypass/check/D2-R1")
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    async def test_expire_bypass(self, client: httpx.AsyncClient, client_with_bypass) -> None:
        # Create
        create_resp = await client.post(
            "/api/v1/emergency-bypass",
            json={
                "role_address": "D1-R1",
                "tier": "tier_1",
                "reason": "incident",
                "approved_by": "admin",
            },
        )
        bypass_id = create_resp.json()["data"]["bypass_id"]

        # Expire
        resp = await client.post(f"/api/v1/emergency-bypass/expire/{bypass_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["expired_manually"] is True

        # Verify no longer active
        check_resp = await client.get("/api/v1/emergency-bypass/check/D1-R1")
        assert check_resp.json()["data"] is None

    async def test_expire_nonexistent_returns_404(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post("/api/v1/emergency-bypass/expire/nonexistent-id")
        assert resp.status_code == 404

    async def test_list_active_bypasses(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.get("/api/v1/emergency-bypass/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["data"], list)
        assert data["count"] == len(data["data"])

    async def test_reviews_due(self, client: httpx.AsyncClient, client_with_bypass) -> None:
        resp = await client.get("/api/v1/emergency-bypass/reviews/due")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["data"], list)

    async def test_reviews_overdue(self, client: httpx.AsyncClient, client_with_bypass) -> None:
        resp = await client.get("/api/v1/emergency-bypass/reviews/overdue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["data"], list)

    async def test_create_with_authority_level(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={
                "role_address": "D2-R1",
                "tier": "tier_1",
                "reason": "incident",
                "approved_by": "supervisor@example.com",
                "authority_level": "supervisor",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["tier"] == "tier_1"

    async def test_create_rejects_tier_4(
        self, client: httpx.AsyncClient, client_with_bypass
    ) -> None:
        resp = await client.post(
            "/api/v1/emergency-bypass",
            json={
                "role_address": "D1-R1",
                "tier": "tier_4",
                "reason": "test",
                "approved_by": "admin",
            },
        )
        assert resp.status_code == 400
        assert (
            "72 hours" in resp.json()["detail"] or "not permitted" in resp.json()["detail"].lower()
        )
