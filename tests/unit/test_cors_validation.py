# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for L5: CORS origin validation in production mode.

Validates that when is_production is True, CORS origins are checked for
HTTPS and wildcard '*' is rejected. Invalid origins log a warning and
fall back to an empty list.
"""

from __future__ import annotations

import logging

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


class TestCorsValidationProduction:
    """L5: CORS origins must use HTTPS and reject wildcard in production."""

    def test_production_rejects_wildcard_origin(self):
        """In production mode, wildcard '*' must be rejected."""
        cfg = EnvConfig(
            pact_dev_mode=False,
            pact_api_token="test-token-12345",
            pact_cors_origins=["*"],
        )
        app = create_app(env_config=cfg)
        # The app should have been created with empty CORS origins
        # Verify by checking that CORS middleware was configured without '*'
        cors_middleware = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_middleware = mw
                break
        assert cors_middleware is not None
        assert cors_middleware.kwargs.get("allow_origins") == []

    def test_production_rejects_http_origins(self):
        """In production mode, HTTP (non-HTTPS) origins must be rejected."""
        cfg = EnvConfig(
            pact_dev_mode=False,
            pact_api_token="test-token-12345",
            pact_cors_origins=["http://example.com"],
        )
        app = create_app(env_config=cfg)
        cors_middleware = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_middleware = mw
                break
        assert cors_middleware is not None
        assert cors_middleware.kwargs.get("allow_origins") == []

    def test_production_allows_https_origins(self):
        """In production mode, HTTPS origins should be allowed."""
        cfg = EnvConfig(
            pact_dev_mode=False,
            pact_api_token="test-token-12345",
            pact_cors_origins=["https://app.example.com"],
        )
        app = create_app(env_config=cfg)
        cors_middleware = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_middleware = mw
                break
        assert cors_middleware is not None
        assert cors_middleware.kwargs.get("allow_origins") == ["https://app.example.com"]

    def test_production_filters_mixed_origins(self):
        """In production, only HTTPS origins survive; HTTP ones are dropped."""
        cfg = EnvConfig(
            pact_dev_mode=False,
            pact_api_token="test-token-12345",
            pact_cors_origins=[
                "https://good.example.com",
                "http://bad.example.com",
                "https://also-good.example.com",
            ],
        )
        app = create_app(env_config=cfg)
        cors_middleware = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_middleware = mw
                break
        assert cors_middleware is not None
        allowed = cors_middleware.kwargs.get("allow_origins")
        assert "https://good.example.com" in allowed
        assert "https://also-good.example.com" in allowed
        assert "http://bad.example.com" not in allowed

    def test_production_logs_warning_for_invalid_origins(self, caplog):
        """Production mode should log a warning when invalid origins are found."""
        cfg = EnvConfig(
            pact_dev_mode=False,
            pact_api_token="test-token-12345",
            pact_cors_origins=["http://insecure.com", "*"],
        )
        with caplog.at_level(logging.WARNING, logger="pact_platform.use.api.server"):
            create_app(env_config=cfg)
        assert any("CORS" in r.message for r in caplog.records)

    def test_dev_mode_allows_http_origins(self):
        """In dev mode (is_production=False), HTTP origins should be accepted."""
        cfg = EnvConfig(
            pact_dev_mode=True,
            pact_api_token="",
            pact_cors_origins=["http://localhost:3000"],
        )
        app = create_app(env_config=cfg)
        cors_middleware = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_middleware = mw
                break
        assert cors_middleware is not None
        assert "http://localhost:3000" in cors_middleware.kwargs.get("allow_origins")

    def test_dev_mode_allows_wildcard(self):
        """In dev mode, wildcard should be accepted without modification."""
        cfg = EnvConfig(
            pact_dev_mode=True,
            pact_api_token="",
            pact_cors_origins=["*"],
        )
        app = create_app(env_config=cfg)
        cors_middleware = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "CORSMiddleware":
                cors_middleware = mw
                break
        assert cors_middleware is not None
        assert "*" in cors_middleware.kwargs.get("allow_origins")
