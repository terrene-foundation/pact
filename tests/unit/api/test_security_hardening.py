# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for API security hardening — rate limiting and security headers (M35-3503/3504).

Tests cover:
- Security response headers present on all endpoints
- Rate limiting middleware is attached
- Rate limit exceeded returns 429
- Rate limit values configurable via EnvConfig
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api.server import SecurityHeadersMiddleware, create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dev_config():
    """EnvConfig in dev mode (no API token required)."""
    return EnvConfig(pact_dev_mode=True, pact_api_token="")


@pytest.fixture()
def strict_rate_config():
    """EnvConfig with very low rate limits for testing."""
    return EnvConfig(
        pact_dev_mode=True,
        pact_api_token="",
        pact_rate_limit_get="2/minute",
        pact_rate_limit_post="1/minute",
    )


@pytest.fixture()
def client(dev_config):
    """TestClient with dev-mode config (no auth required)."""
    app = create_app(env_config=dev_config)
    return TestClient(app)


@pytest.fixture()
def strict_client(strict_rate_config):
    """TestClient with strict rate limits for rate limit testing."""
    app = create_app(env_config=strict_rate_config)
    return TestClient(app)


# ---------------------------------------------------------------------------
# 3504: Security Response Headers
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    """Test that security response headers are present on all responses."""

    EXPECTED_HEADERS = {
        "content-security-policy": "default-src 'self'",
        "x-frame-options": "DENY",
        "x-content-type-options": "nosniff",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "camera=(), microphone=(), geolocation=()",
    }

    def test_health_endpoint_has_security_headers(self, client):
        """GET /health should return all security headers."""
        response = client.get("/health")
        assert response.status_code == 200
        for header, value in self.EXPECTED_HEADERS.items():
            assert response.headers.get(header) == value, (
                f"Missing or wrong header '{header}': "
                f"got '{response.headers.get(header)}', expected '{value}'"
            )

    def test_ready_endpoint_has_security_headers(self, client):
        """GET /ready should return all security headers."""
        response = client.get("/ready")
        assert response.status_code == 200
        for header, value in self.EXPECTED_HEADERS.items():
            assert response.headers.get(header) == value

    def test_api_endpoint_has_security_headers(self, client):
        """GET /api/v1/teams should return all security headers."""
        response = client.get("/api/v1/teams")
        assert response.status_code == 200
        for header, value in self.EXPECTED_HEADERS.items():
            assert response.headers.get(header) == value

    def test_csp_prevents_external_resources(self, client):
        """Content-Security-Policy should be set to self only."""
        response = client.get("/health")
        assert response.headers["content-security-policy"] == "default-src 'self'"

    def test_x_frame_options_deny(self, client):
        """X-Frame-Options should be DENY to prevent clickjacking."""
        response = client.get("/health")
        assert response.headers["x-frame-options"] == "DENY"

    def test_nosniff_header(self, client):
        """X-Content-Type-Options should prevent MIME sniffing."""
        response = client.get("/health")
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_referrer_policy(self, client):
        """Referrer-Policy should limit referrer leakage."""
        response = client.get("/health")
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_disables_sensors(self, client):
        """Permissions-Policy should disable camera, mic, geolocation."""
        response = client.get("/health")
        policy = response.headers["permissions-policy"]
        assert "camera=()" in policy
        assert "microphone=()" in policy
        assert "geolocation=()" in policy


# ---------------------------------------------------------------------------
# 3503: Rate Limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Test rate limiting middleware configuration."""

    def test_rate_limiter_attached_to_app(self, client):
        """The app should have a limiter in its state."""
        assert hasattr(client.app.state, "limiter")
        assert client.app.state.limiter is not None

    def test_normal_requests_succeed(self, client):
        """Normal requests within rate limits should succeed."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_rate_limit_exceeded_returns_429(self, strict_client):
        """Exceeding the rate limit should return HTTP 429."""
        # Rate limit is 2/minute for GET — send 3 requests
        for _ in range(2):
            resp = strict_client.get("/health")
            assert resp.status_code == 200

        # Third request should be rate limited
        resp = strict_client.get("/health")
        assert resp.status_code == 429

    def test_rate_limit_429_body_is_json(self, strict_client):
        """429 response should contain a JSON body with error details."""
        # Exhaust the rate limit
        for _ in range(2):
            strict_client.get("/health")

        resp = strict_client.get("/health")
        assert resp.status_code == 429
        body = resp.json()
        assert "error" in body
        assert body["error"] == "Rate limit exceeded"

    def test_default_rate_limit_values(self, dev_config):
        """Default rate limits should be 60/minute GET, 10/minute POST."""
        assert dev_config.pact_rate_limit_get == "60/minute"
        assert dev_config.pact_rate_limit_post == "10/minute"

    def test_custom_rate_limit_values(self):
        """Custom rate limit values should be respected."""
        cfg = EnvConfig(
            pact_dev_mode=True,
            pact_rate_limit_get="100/minute",
            pact_rate_limit_post="20/minute",
        )
        assert cfg.pact_rate_limit_get == "100/minute"
        assert cfg.pact_rate_limit_post == "20/minute"

    def test_post_endpoint_rate_limited(self, strict_rate_config):
        """POST endpoints should have the POST rate limit applied."""
        app = create_app(env_config=strict_rate_config)
        client = TestClient(app)

        # POST rate limit is 1/minute — first should succeed
        resp = client.post("/api/v1/agents/a1/approve/act1?approver_id=human1&reason=test")
        # May return 200 or 404 depending on agent state, but NOT 429
        assert resp.status_code != 429

        # Second POST should be rate limited
        resp = client.post("/api/v1/agents/a1/approve/act1?approver_id=human1&reason=test")
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware unit test
# ---------------------------------------------------------------------------


class TestSecurityHeadersMiddleware:
    """Test the SecurityHeadersMiddleware class directly."""

    def test_middleware_has_all_required_headers(self):
        """Middleware should define all seven security headers (RT12-005: added HSTS, X-XSS)."""
        expected_keys = {
            "Content-Security-Policy",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Strict-Transport-Security",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Permissions-Policy",
        }
        assert set(SecurityHeadersMiddleware._SECURITY_HEADERS.keys()) == expected_keys
