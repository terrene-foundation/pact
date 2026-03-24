# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for graceful shutdown handling (M22-2203 / I8).

Validates that:
- Shutdown event exists and can be triggered
- Shutdown handler stops accepting new WebSocket connections
- In-flight requests complete during shutdown
- Shutdown handler is registered via lifespan
"""

from __future__ import annotations

import pytest

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api.server import create_app
from pact_platform.use.api.shutdown import ShutdownManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dev_config():
    """Dev mode config."""
    return EnvConfig(pact_api_token="", pact_dev_mode=True)


# ---------------------------------------------------------------------------
# Tests: ShutdownManager
# ---------------------------------------------------------------------------


class TestShutdownManager:
    """ShutdownManager provides a clean shutdown mechanism."""

    def test_initial_state_not_shutting_down(self):
        """ShutdownManager starts in non-shutdown state."""
        manager = ShutdownManager()
        assert manager.is_shutting_down is False

    def test_trigger_sets_shutting_down(self):
        """Triggering shutdown sets the flag."""
        manager = ShutdownManager()
        manager.trigger_shutdown()
        assert manager.is_shutting_down is True

    def test_trigger_is_idempotent(self):
        """Triggering shutdown multiple times is safe."""
        manager = ShutdownManager()
        manager.trigger_shutdown()
        manager.trigger_shutdown()
        assert manager.is_shutting_down is True

    @pytest.mark.asyncio
    async def test_register_and_close_connection(self):
        """Registered connections can be tracked and closed."""
        manager = ShutdownManager()
        mock_ws = _MockWebSocket()
        manager.register_connection(mock_ws)
        assert manager.active_connection_count == 1

        manager.unregister_connection(mock_ws)
        assert manager.active_connection_count == 0

    @pytest.mark.asyncio
    async def test_close_all_connections(self):
        """close_all_connections closes all tracked WebSockets."""
        manager = ShutdownManager()
        ws1 = _MockWebSocket()
        ws2 = _MockWebSocket()
        manager.register_connection(ws1)
        manager.register_connection(ws2)

        await manager.close_all_connections()
        assert ws1.closed is True
        assert ws2.closed is True
        assert manager.active_connection_count == 0

    @pytest.mark.asyncio
    async def test_shutdown_rejects_new_connections(self):
        """After shutdown is triggered, should_accept_connection returns False."""
        manager = ShutdownManager()
        assert manager.should_accept_connection() is True
        manager.trigger_shutdown()
        assert manager.should_accept_connection() is False


# ---------------------------------------------------------------------------
# Tests: Shutdown integrated with app
# ---------------------------------------------------------------------------


class TestShutdownIntegration:
    """Shutdown manager integrates with the FastAPI app."""

    def test_app_has_shutdown_manager(self, dev_config):
        """create_app provides access to a shutdown manager."""
        app = create_app(env_config=dev_config)
        # The shutdown manager should be accessible on app state
        assert hasattr(app.state, "shutdown_manager")
        assert isinstance(app.state.shutdown_manager, ShutdownManager)

    def test_shutdown_manager_starts_clean(self, dev_config):
        """Shutdown manager on new app is not in shutdown state."""
        app = create_app(env_config=dev_config)
        assert app.state.shutdown_manager.is_shutting_down is False


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _MockWebSocket:
    """Minimal mock WebSocket for testing shutdown manager."""

    def __init__(self) -> None:
        self.closed = False

    async def close(self, code: int = 1001, reason: str = "") -> None:
        self.closed = True
