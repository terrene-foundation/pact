# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for L6: Request body size limit middleware.

Validates that requests with bodies larger than the configured limit
(default 1MB, configurable via PACT_MAX_BODY_SIZE) are rejected with
413 Payload Too Large.
"""

from __future__ import annotations

import httpx
import pytest

import pact_platform.use.api.server as server_module
from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api.server import create_app


@pytest.fixture(autouse=True)
def _reset_default_api():
    """Reset module-level _default_api between tests."""
    old = server_module._default_api
    server_module._default_api = None
    yield
    server_module._default_api = old


@pytest.fixture()
def dev_config() -> EnvConfig:
    """EnvConfig in dev mode (auth disabled)."""
    return EnvConfig(pact_dev_mode=True, pact_api_token="")


@pytest.fixture()
def app(dev_config: EnvConfig):
    """Create a FastAPI app with dev config."""
    return create_app(env_config=dev_config)


@pytest.fixture()
async def client(app) -> httpx.AsyncClient:
    """Async HTTP client targeting the test app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestBodySizeLimit:
    """L6: Requests exceeding max body size are rejected with 413."""

    @pytest.mark.asyncio
    async def test_small_body_accepted(self, client: httpx.AsyncClient):
        """A request with a small body should be accepted (not 413)."""
        resp = await client.post(
            "/api/v1/bridges",
            json={"bridge_type": "standing", "source_team_id": "a", "target_team_id": "b"},
            headers={"Content-Length": "100"},
        )
        # Should NOT be 413 — the request may fail for other reasons (auth, validation)
        # but not due to body size.
        assert resp.status_code != 413

    @pytest.mark.asyncio
    async def test_oversized_body_rejected(self, client: httpx.AsyncClient):
        """A request with Content-Length exceeding the limit should return 413."""
        # Default limit is 1MB = 1048576 bytes
        # Send a Content-Length header claiming a body larger than 1MB
        resp = await client.post(
            "/api/v1/bridges",
            content=b"x" * 100,  # actual body is small but header claims large
            headers={"Content-Length": "2000000", "Content-Type": "application/json"},
        )
        assert resp.status_code == 413

    @pytest.mark.asyncio
    async def test_exactly_at_limit_accepted(self, client: httpx.AsyncClient):
        """A request exactly at the limit should not be rejected for size."""
        # Use GET /health which doesn't parse the body -- just verify the
        # Content-Length check passes and doesn't produce 413.
        resp = await client.get(
            "/health",
            headers={"Content-Length": "1048576"},
        )
        # Exactly at limit should NOT be 413
        assert resp.status_code != 413

    @pytest.mark.asyncio
    async def test_get_request_without_body_accepted(self, client: httpx.AsyncClient):
        """GET requests without a body should not be affected by size limits."""
        resp = await client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_413_response_body(self, client: httpx.AsyncClient):
        """413 response should include an informative JSON body."""
        resp = await client.post(
            "/api/v1/bridges",
            content=b"x",
            headers={"Content-Length": "2000000", "Content-Type": "application/json"},
        )
        assert resp.status_code == 413
        body = resp.json()
        assert "error" in body


class TestBodySizeLimitConfigurable:
    """L6: Body size limit is configurable via PACT_MAX_BODY_SIZE env var."""

    @pytest.mark.asyncio
    async def test_custom_limit_via_env(self, monkeypatch):
        """When PACT_MAX_BODY_SIZE is set, the limit should change."""
        monkeypatch.setenv("PACT_MAX_BODY_SIZE", "500")
        cfg = EnvConfig(pact_dev_mode=True, pact_api_token="")
        application = create_app(env_config=cfg)

        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            # 600 bytes exceeds 500 limit
            resp = await ac.post(
                "/api/v1/bridges",
                content=b"x",
                headers={"Content-Length": "600", "Content-Type": "application/json"},
            )
            assert resp.status_code == 413
