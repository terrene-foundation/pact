# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for Task 5027: Expanded health check endpoint.

Tests that /health returns structured JSON with component-level health
status and a version number from pact.__version__.
"""

from __future__ import annotations

import httpx
import pytest

import pact
from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api.server import create_app


@pytest.fixture()
def dev_config() -> EnvConfig:
    """EnvConfig in dev mode (auth disabled)."""
    return EnvConfig(pact_dev_mode=True, pact_api_token="")


@pytest.fixture()
def app(dev_config: EnvConfig):
    """Create a FastAPI app with dev config for health check testing."""
    import pact_platform.use.api.server as server_module

    old_default = server_module._default_api
    server_module._default_api = None
    application = create_app(env_config=dev_config)
    yield application
    server_module._default_api = old_default


@pytest.fixture()
async def client(app) -> httpx.AsyncClient:
    """Async HTTP client targeting the test app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestHealthEndpoint:
    """Expanded /health endpoint returns structured component health."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: httpx.AsyncClient):
        """GET /health should return HTTP 200."""
        resp = await client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_has_status_field(self, client: httpx.AsyncClient):
        """Response should include a top-level 'status' field."""
        resp = await client.get("/health")
        data = resp.json()
        assert "status" in data
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_has_components(self, client: httpx.AsyncClient):
        """Response should include component-level health checks."""
        resp = await client.get("/health")
        data = resp.json()
        assert "components" in data
        components = data["components"]
        assert "api" in components
        assert components["api"] == "ok"

    @pytest.mark.asyncio
    async def test_health_has_version(self, client: httpx.AsyncClient):
        """Response should include the platform version."""
        resp = await client.get("/health")
        data = resp.json()
        assert "version" in data
        assert data["version"] == pact.__version__

    @pytest.mark.asyncio
    async def test_health_version_matches_package(self, client: httpx.AsyncClient):
        """Version in health response must match pact.__version__."""
        resp = await client.get("/health")
        data = resp.json()
        from pact import __version__

        assert data["version"] == __version__

    @pytest.mark.asyncio
    async def test_health_components_include_database(self, client: httpx.AsyncClient):
        """Components should include database status."""
        resp = await client.get("/health")
        data = resp.json()
        assert "database" in data["components"]

    @pytest.mark.asyncio
    async def test_health_components_include_trust_store(self, client: httpx.AsyncClient):
        """Components should include trust_store status."""
        resp = await client.get("/health")
        data = resp.json()
        assert "trust_store" in data["components"]

    @pytest.mark.asyncio
    async def test_health_response_is_json(self, client: httpx.AsyncClient):
        """Health check should return application/json content type."""
        resp = await client.get("/health")
        assert "application/json" in resp.headers.get("content-type", "")
