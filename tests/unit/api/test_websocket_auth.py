# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for WebSocket authentication (M22-2201 / RT10-A4).

Validates that:
- WebSocket requires bearer token when PACT_API_TOKEN is set
- Token can be provided via query parameter (?token=...)
- Invalid/missing token causes close with code 4001
- Dev mode with no token allows unauthenticated connections
- Max subscriber limit is still enforced after auth
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api.server import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def env_config_with_token():
    """EnvConfig with a known API token (production mode)."""
    return EnvConfig(
        pact_api_token="test-secret-token-42",
        pact_dev_mode=False,
        pact_max_ws_subscribers=5,
    )


@pytest.fixture()
def env_config_dev_mode_no_token():
    """EnvConfig in dev mode with no API token."""
    return EnvConfig(
        pact_api_token="",
        pact_dev_mode=True,
        pact_max_ws_subscribers=5,
    )


@pytest.fixture()
def env_config_dev_mode_with_token():
    """EnvConfig in dev mode with an API token."""
    return EnvConfig(
        pact_api_token="dev-token-99",
        pact_dev_mode=True,
        pact_max_ws_subscribers=5,
    )


@pytest.fixture()
def app_with_token(env_config_with_token):
    """FastAPI app with token auth enabled."""
    return create_app(env_config=env_config_with_token)


@pytest.fixture()
def app_dev_no_token(env_config_dev_mode_no_token):
    """FastAPI app in dev mode, no token configured."""
    return create_app(env_config=env_config_dev_mode_no_token)


@pytest.fixture()
def app_dev_with_token(env_config_dev_mode_with_token):
    """FastAPI app in dev mode with a token configured."""
    return create_app(env_config=env_config_dev_mode_with_token)


# ---------------------------------------------------------------------------
# Tests: WebSocket auth with token required
# ---------------------------------------------------------------------------


class TestWebSocketAuthRequired:
    """When PACT_API_TOKEN is set, WebSocket requires authentication."""

    def test_websocket_rejects_no_token(self, app_with_token):
        """WebSocket connection without token should be rejected with 4001."""
        client = TestClient(app_with_token)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws"):
                pass
        # The connection should have been closed with code 4001
        assert exc_info.value.code == 4001

    def test_websocket_rejects_wrong_token(self, app_with_token):
        """WebSocket connection with wrong token should be rejected with 4001."""
        client = TestClient(app_with_token)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws?token=wrong-token"):
                pass
        assert exc_info.value.code == 4001

    def test_websocket_accepts_valid_token_query_param(self, app_with_token):
        """WebSocket connection with correct token in query param should succeed."""
        client = TestClient(app_with_token)
        with client.websocket_connect("/ws?token=test-secret-token-42") as ws:
            # Connection accepted, ws is open
            assert ws is not None

    def test_websocket_rejects_empty_token(self, app_with_token):
        """WebSocket connection with empty token query param should be rejected."""
        client = TestClient(app_with_token)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws?token="):
                pass
        assert exc_info.value.code == 4001


# ---------------------------------------------------------------------------
# Tests: WebSocket auth in dev mode
# ---------------------------------------------------------------------------


class TestWebSocketDevMode:
    """In dev mode with no token, WebSocket allows unauthenticated access."""

    def test_websocket_allows_no_token_in_dev_mode(self, app_dev_no_token):
        """Dev mode with no token configured allows WebSocket without auth."""
        client = TestClient(app_dev_no_token)
        with client.websocket_connect("/ws") as ws:
            assert ws is not None

    def test_websocket_requires_token_in_dev_mode_when_configured(self, app_dev_with_token):
        """Dev mode with a token configured still requires that token."""
        client = TestClient(app_dev_with_token)
        with pytest.raises(Exception), client.websocket_connect("/ws"):
            pass

    def test_websocket_accepts_token_in_dev_mode_when_configured(self, app_dev_with_token):
        """Dev mode with a token configured accepts correct token."""
        client = TestClient(app_dev_with_token)
        with client.websocket_connect("/ws?token=dev-token-99") as ws:
            assert ws is not None


# ---------------------------------------------------------------------------
# Tests: Max subscriber limit still works with auth
# ---------------------------------------------------------------------------


class TestWebSocketAuthWithSubscriberLimit:
    """Auth does not interfere with the max subscriber limit."""

    def test_subscriber_limit_still_enforced(self, env_config_with_token):
        """Max subscriber limit still works with authenticated connections."""
        config = EnvConfig(
            pact_api_token="test-secret-token-42",
            pact_dev_mode=False,
            pact_max_ws_subscribers=1,
        )
        app = create_app(env_config=config)
        client = TestClient(app)

        # First connection should succeed
        with client.websocket_connect("/ws?token=test-secret-token-42"):
            # Second connection should be rejected due to subscriber limit
            with pytest.raises(Exception):
                with client.websocket_connect("/ws?token=test-secret-token-42"):
                    pass
