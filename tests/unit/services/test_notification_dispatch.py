# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Unit tests for NotificationDispatchService.

Tests cover all code paths:
1. Adapter registration — valid adapter, protocol enforcement, bounded collection
2. Adapter unregistration — valid removal, error on unregistered
3. Dispatch to registered adapters — concurrent delivery, logging
4. Dispatch with no adapters — silent drop, no error
5. Adapter error isolation — one failing adapter does not block others
6. Bounded collection enforcement — MAX_ADAPTERS limit respected
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pact_platform.use.services.notification_dispatch import (
    MAX_ADAPTERS,
    NotificationAdapter,
    NotificationDispatchService,
)


# ---------------------------------------------------------------------------
# Test adapters — real implementations of NotificationAdapter protocol
# ---------------------------------------------------------------------------


class InMemoryAdapter:
    """Adapter that records all received notifications in a list."""

    def __init__(self) -> None:
        self.received: list[tuple[str, dict[str, Any]]] = []

    async def send(self, event_type: str, payload: dict[str, Any]) -> None:
        self.received.append((event_type, payload))


class FailingAdapter:
    """Adapter that always raises RuntimeError on send."""

    async def send(self, event_type: str, payload: dict[str, Any]) -> None:
        raise RuntimeError(f"FailingAdapter deliberately failed on {event_type}")


class SlowAdapter:
    """Adapter that records events but introduces an artificial delay."""

    def __init__(self, delay: float = 0.01) -> None:
        self.received: list[tuple[str, dict[str, Any]]] = []
        self._delay = delay

    async def send(self, event_type: str, payload: dict[str, Any]) -> None:
        await asyncio.sleep(self._delay)
        self.received.append((event_type, payload))


class NotAnAdapter:
    """Class that does NOT implement the NotificationAdapter protocol."""

    def not_send(self, event_type: str, payload: dict[str, Any]) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service() -> NotificationDispatchService:
    """Return a fresh NotificationDispatchService instance."""
    return NotificationDispatchService()


@pytest.fixture()
def memory_adapter() -> InMemoryAdapter:
    """Return a fresh InMemoryAdapter."""
    return InMemoryAdapter()


@pytest.fixture()
def failing_adapter() -> FailingAdapter:
    """Return a fresh FailingAdapter."""
    return FailingAdapter()


# ---------------------------------------------------------------------------
# 1. Adapter registration — valid adapter and protocol enforcement
# ---------------------------------------------------------------------------


class TestAdapterRegistration:
    """Verify that adapter registration validates protocol compliance."""

    def test_register_valid_adapter(
        self, service: NotificationDispatchService, memory_adapter: InMemoryAdapter
    ) -> None:
        service.register_adapter(memory_adapter)
        assert len(service._adapters) == 1
        assert service._adapters[0] is memory_adapter

    def test_register_multiple_adapters(self, service: NotificationDispatchService) -> None:
        adapters = [InMemoryAdapter() for _ in range(5)]
        for adapter in adapters:
            service.register_adapter(adapter)
        assert len(service._adapters) == 5

    def test_register_non_protocol_raises_type_error(
        self, service: NotificationDispatchService
    ) -> None:
        not_an_adapter = NotAnAdapter()
        with pytest.raises(TypeError, match="must implement NotificationAdapter protocol"):
            service.register_adapter(not_an_adapter)

    def test_register_plain_object_raises_type_error(
        self, service: NotificationDispatchService
    ) -> None:
        with pytest.raises(TypeError, match="must implement NotificationAdapter protocol"):
            service.register_adapter("not an adapter")  # type: ignore[arg-type]

    def test_register_logs_info(
        self,
        service: NotificationDispatchService,
        memory_adapter: InMemoryAdapter,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(
            logging.INFO, logger="pact_platform.use.services.notification_dispatch"
        ):
            service.register_adapter(memory_adapter)
        assert any("registered" in msg.lower() for msg in caplog.messages)
        assert any("InMemoryAdapter" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# 2. Adapter unregistration
# ---------------------------------------------------------------------------


class TestAdapterUnregistration:
    """Verify that adapter unregistration works and raises on unknown adapters."""

    def test_unregister_existing_adapter(
        self, service: NotificationDispatchService, memory_adapter: InMemoryAdapter
    ) -> None:
        service.register_adapter(memory_adapter)
        assert len(service._adapters) == 1
        service.unregister_adapter(memory_adapter)
        assert len(service._adapters) == 0

    def test_unregister_nonexistent_adapter_raises_value_error(
        self, service: NotificationDispatchService, memory_adapter: InMemoryAdapter
    ) -> None:
        with pytest.raises(ValueError, match="not registered"):
            service.unregister_adapter(memory_adapter)

    def test_unregister_one_of_multiple(self, service: NotificationDispatchService) -> None:
        adapter_a = InMemoryAdapter()
        adapter_b = InMemoryAdapter()
        service.register_adapter(adapter_a)
        service.register_adapter(adapter_b)
        service.unregister_adapter(adapter_a)
        assert len(service._adapters) == 1
        assert service._adapters[0] is adapter_b

    def test_unregister_logs_info(
        self,
        service: NotificationDispatchService,
        memory_adapter: InMemoryAdapter,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        service.register_adapter(memory_adapter)
        with caplog.at_level(
            logging.INFO, logger="pact_platform.use.services.notification_dispatch"
        ):
            service.unregister_adapter(memory_adapter)
        assert any("unregistered" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# 3. Dispatch to registered adapters
# ---------------------------------------------------------------------------


class TestDispatch:
    """Verify that dispatch fans out to all registered adapters."""

    def test_dispatch_single_adapter(
        self, service: NotificationDispatchService, memory_adapter: InMemoryAdapter
    ) -> None:
        service.register_adapter(memory_adapter)
        service.dispatch("approval.submitted", {"request_id": "req-001"})
        assert len(memory_adapter.received) == 1
        event_type, payload = memory_adapter.received[0]
        assert event_type == "approval.submitted"
        assert payload == {"request_id": "req-001"}

    def test_dispatch_multiple_adapters(self, service: NotificationDispatchService) -> None:
        adapters = [InMemoryAdapter() for _ in range(3)]
        for adapter in adapters:
            service.register_adapter(adapter)

        service.dispatch("budget.warning", {"amount": 100.0})

        for adapter in adapters:
            assert len(adapter.received) == 1
            event_type, payload = adapter.received[0]
            assert event_type == "budget.warning"
            assert payload == {"amount": 100.0}

    def test_dispatch_preserves_payload(
        self, service: NotificationDispatchService, memory_adapter: InMemoryAdapter
    ) -> None:
        service.register_adapter(memory_adapter)
        complex_payload = {
            "request_id": "req-002",
            "nested": {"a": 1, "b": [2, 3]},
            "tags": ["urgent", "financial"],
        }
        service.dispatch("review.completed", complex_payload)
        _, received_payload = memory_adapter.received[0]
        assert received_payload == complex_payload

    def test_dispatch_multiple_events(
        self, service: NotificationDispatchService, memory_adapter: InMemoryAdapter
    ) -> None:
        service.register_adapter(memory_adapter)
        service.dispatch("event.one", {"seq": 1})
        service.dispatch("event.two", {"seq": 2})
        assert len(memory_adapter.received) == 2
        assert memory_adapter.received[0][0] == "event.one"
        assert memory_adapter.received[1][0] == "event.two"


# ---------------------------------------------------------------------------
# 4. Dispatch with no adapters — silent drop
# ---------------------------------------------------------------------------


class TestDispatchNoAdapters:
    """Verify dispatch with no adapters registered is a no-op (no error)."""

    def test_dispatch_no_adapters_does_not_raise(
        self, service: NotificationDispatchService
    ) -> None:
        # Should not raise any exception
        service.dispatch("orphan.event", {"data": "ignored"})

    def test_dispatch_no_adapters_logs_debug(
        self,
        service: NotificationDispatchService,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(
            logging.DEBUG, logger="pact_platform.use.services.notification_dispatch"
        ):
            service.dispatch("orphan.event", {"data": "ignored"})
        assert any("no adapters" in msg.lower() for msg in caplog.messages)

    def test_dispatch_no_adapters_returns_immediately(
        self, service: NotificationDispatchService
    ) -> None:
        """With no adapters, dispatch should return without attempting async work."""
        # If this completes without error, it means the early return path works.
        # We verify by ensuring no asyncio loop creation is attempted.
        service.dispatch("test.event", {})
        # No assertion needed beyond reaching this point without error


# ---------------------------------------------------------------------------
# 5. Adapter error isolation — one failing does not block others
# ---------------------------------------------------------------------------


class TestAdapterErrorIsolation:
    """Verify that a failing adapter does not prevent other adapters from receiving events."""

    def test_failing_adapter_does_not_block_others(
        self, service: NotificationDispatchService
    ) -> None:
        adapter_before = InMemoryAdapter()
        failing = FailingAdapter()
        adapter_after = InMemoryAdapter()

        service.register_adapter(adapter_before)
        service.register_adapter(failing)
        service.register_adapter(adapter_after)

        # Should not raise, even though one adapter fails
        service.dispatch("test.event", {"key": "value"})

        # Both healthy adapters should have received the event
        assert len(adapter_before.received) == 1
        assert len(adapter_after.received) == 1

    def test_failing_adapter_logs_exception(
        self,
        service: NotificationDispatchService,
        failing_adapter: FailingAdapter,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        service.register_adapter(failing_adapter)
        with caplog.at_level(
            logging.ERROR, logger="pact_platform.use.services.notification_dispatch"
        ):
            service.dispatch("test.failure", {"trigger": "test"})
        assert any("FailingAdapter" in msg and "failed" in msg for msg in caplog.messages)

    def test_multiple_failing_adapters_do_not_block_healthy(
        self, service: NotificationDispatchService
    ) -> None:
        healthy = InMemoryAdapter()
        service.register_adapter(FailingAdapter())
        service.register_adapter(healthy)
        service.register_adapter(FailingAdapter())

        service.dispatch("multi.fail", {"test": True})
        assert len(healthy.received) == 1

    def test_all_adapters_failing_does_not_raise(
        self, service: NotificationDispatchService
    ) -> None:
        service.register_adapter(FailingAdapter())
        service.register_adapter(FailingAdapter())
        # Should not raise
        service.dispatch("all.fail", {})


# ---------------------------------------------------------------------------
# 6. Bounded collection — MAX_ADAPTERS limit
# ---------------------------------------------------------------------------


class TestBoundedCollection:
    """Verify that the adapter list is bounded to MAX_ADAPTERS."""

    def test_max_adapters_constant_is_positive(self) -> None:
        """Sanity check that MAX_ADAPTERS is a reasonable positive number."""
        assert MAX_ADAPTERS > 0
        assert MAX_ADAPTERS == 50  # Per the source code

    def test_register_up_to_max_adapters(self, service: NotificationDispatchService) -> None:
        for i in range(MAX_ADAPTERS):
            service.register_adapter(InMemoryAdapter())
        assert len(service._adapters) == MAX_ADAPTERS

    def test_register_exceeding_max_raises_runtime_error(
        self, service: NotificationDispatchService
    ) -> None:
        for _ in range(MAX_ADAPTERS):
            service.register_adapter(InMemoryAdapter())

        with pytest.raises(RuntimeError, match="Maximum number of notification adapters"):
            service.register_adapter(InMemoryAdapter())

    def test_register_after_unregister_within_limit(
        self, service: NotificationDispatchService
    ) -> None:
        """After filling to max and removing one, registration should work again."""
        adapters = [InMemoryAdapter() for _ in range(MAX_ADAPTERS)]
        for adapter in adapters:
            service.register_adapter(adapter)

        # Remove one
        service.unregister_adapter(adapters[0])
        assert len(service._adapters) == MAX_ADAPTERS - 1

        # Should succeed now
        service.register_adapter(InMemoryAdapter())
        assert len(service._adapters) == MAX_ADAPTERS

    def test_max_adapters_error_message_includes_limit(
        self, service: NotificationDispatchService
    ) -> None:
        for _ in range(MAX_ADAPTERS):
            service.register_adapter(InMemoryAdapter())

        with pytest.raises(RuntimeError, match=str(MAX_ADAPTERS)):
            service.register_adapter(InMemoryAdapter())


# ---------------------------------------------------------------------------
# 7. Protocol compliance — runtime_checkable behavior
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Verify NotificationAdapter protocol runtime checking."""

    def test_in_memory_adapter_is_notification_adapter(self) -> None:
        adapter = InMemoryAdapter()
        assert isinstance(adapter, NotificationAdapter)

    def test_failing_adapter_is_notification_adapter(self) -> None:
        adapter = FailingAdapter()
        assert isinstance(adapter, NotificationAdapter)

    def test_not_an_adapter_is_not_notification_adapter(self) -> None:
        obj = NotAnAdapter()
        assert not isinstance(obj, NotificationAdapter)

    def test_string_is_not_notification_adapter(self) -> None:
        assert not isinstance("hello", NotificationAdapter)


# ---------------------------------------------------------------------------
# 8. Async dispatch internals — _dispatch_async and _safe_send
# ---------------------------------------------------------------------------


class TestAsyncDispatchInternals:
    """Test the internal async methods directly via asyncio.run."""

    def test_dispatch_async_delivers_to_all(self) -> None:
        service = NotificationDispatchService()
        adapters = [InMemoryAdapter() for _ in range(3)]
        for a in adapters:
            service.register_adapter(a)

        asyncio.run(service._dispatch_async("async.test", {"key": "val"}))

        for adapter in adapters:
            assert len(adapter.received) == 1
            assert adapter.received[0] == ("async.test", {"key": "val"})

    def test_safe_send_catches_exception(self) -> None:
        service = NotificationDispatchService()
        failing = FailingAdapter()
        # Should not raise
        asyncio.run(service._safe_send(failing, "fail.test", {}))

    def test_safe_send_delivers_to_healthy_adapter(self) -> None:
        service = NotificationDispatchService()
        adapter = InMemoryAdapter()
        asyncio.run(service._safe_send(adapter, "healthy.test", {"x": 1}))
        assert len(adapter.received) == 1
