# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for readiness probe endpoint (M22-2202 / I2).

Validates that:
- GET /ready returns {"status": "ready"} with HTTP 200 when healthy
- GET /ready returns {"status": "not_ready", "reason": "..."} with HTTP 503 when not ready
- GET /ready checks trust store accessibility when configured
- GET /health still works independently
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api.server import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dev_config():
    """Dev mode config (no auth needed for testing endpoints)."""
    return EnvConfig(pact_api_token="", pact_dev_mode=True)


@pytest.fixture()
def app_no_store(dev_config):
    """App with no trust store configured."""
    return create_app(env_config=dev_config)


@pytest.fixture()
def healthy_store():
    """A mock trust store that reports healthy."""
    store = MagicMock()
    store.health_check.return_value = True
    return store


@pytest.fixture()
def unhealthy_store():
    """A mock trust store that reports unhealthy."""
    store = MagicMock()
    store.health_check.return_value = False
    return store


@pytest.fixture()
def failing_store():
    """A mock trust store that raises on health check."""
    store = MagicMock()
    store.health_check.side_effect = ConnectionError("Database connection lost")
    return store


# ---------------------------------------------------------------------------
# Tests: Readiness probe without store
# ---------------------------------------------------------------------------


class TestReadinessProbeNoStore:
    """Readiness when no trust store is configured."""

    def test_ready_returns_200_without_store(self, app_no_store):
        """Without a trust store, readiness should return ready."""
        client = TestClient(app_no_store)
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


# ---------------------------------------------------------------------------
# Tests: Readiness probe with healthy store
# ---------------------------------------------------------------------------


class TestReadinessProbeHealthyStore:
    """Readiness when trust store is healthy."""

    def test_ready_returns_200_with_healthy_store(self, dev_config, healthy_store):
        """With a healthy trust store, readiness should return ready."""
        app = create_app(env_config=dev_config, trust_store=healthy_store)
        client = TestClient(app)
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


# ---------------------------------------------------------------------------
# Tests: Readiness probe with unhealthy store
# ---------------------------------------------------------------------------


class TestReadinessProbeUnhealthyStore:
    """Readiness when trust store is unhealthy."""

    def test_ready_returns_503_with_unhealthy_store(self, dev_config, unhealthy_store):
        """With an unhealthy trust store, readiness should return 503."""
        app = create_app(env_config=dev_config, trust_store=unhealthy_store)
        client = TestClient(app)
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert "reason" in data
        assert len(data["reason"]) > 0

    def test_ready_returns_503_with_failing_store(self, dev_config, failing_store):
        """When trust store raises an exception, readiness should return 503."""
        app = create_app(env_config=dev_config, trust_store=failing_store)
        client = TestClient(app)
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert "reason" in data


# ---------------------------------------------------------------------------
# Tests: Health endpoint still works
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Health endpoint is independent of readiness."""

    def test_health_returns_200_always(self, app_no_store):
        """Health endpoint always returns 200 (liveness probe)."""
        client = TestClient(app_no_store)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
