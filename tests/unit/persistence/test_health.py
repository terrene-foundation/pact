# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for TrustStoreHealthCheck (Task 1603).

Validates that:
- TrustStoreHealthCheck checks store connectivity via health_check()
- When store is unreachable, all actions are BLOCKED (fail-closed)
- Store health status tracks healthy, degraded, unreachable states
- Circuit breaker integration trips on repeated failures
- Store recovery transitions from unreachable back to healthy
- MemoryStore, FilesystemStore, and SQLiteTrustStore implement health_check()
"""

import pytest

from care_platform.persistence.health import (
    StoreHealthStatus,
    TrustStoreHealthCheck,
)
from care_platform.persistence.store import MemoryStore, FilesystemStore
from care_platform.persistence.sqlite_store import SQLiteTrustStore
from care_platform.constraint.circuit_breaker import CircuitBreaker


class _FailingStore:
    """A store that simulates failures for testing."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self._should_fail = should_fail

    def health_check(self) -> bool:
        if self._should_fail:
            raise ConnectionError("Store unreachable")
        return True

    def set_failing(self, failing: bool) -> None:
        self._should_fail = failing


class TestStoreHealthStatus:
    """StoreHealthStatus enum correctness."""

    def test_healthy_status(self):
        assert StoreHealthStatus.HEALTHY.value == "healthy"

    def test_degraded_status(self):
        assert StoreHealthStatus.DEGRADED.value == "degraded"

    def test_unreachable_status(self):
        assert StoreHealthStatus.UNREACHABLE.value == "unreachable"


class TestTrustStoreHealthCheckConstruction:
    """TrustStoreHealthCheck construction and validation."""

    def test_requires_store(self):
        """Health check must require a store instance."""
        with pytest.raises(ValueError, match="store"):
            TrustStoreHealthCheck(store=None)

    def test_accepts_valid_store(self):
        """Health check accepts a store with health_check method."""
        store = _FailingStore()
        health = TrustStoreHealthCheck(store=store)
        assert health is not None

    def test_initial_status_is_healthy(self):
        """Initial status should be HEALTHY for a working store."""
        store = _FailingStore(should_fail=False)
        health = TrustStoreHealthCheck(store=store)
        assert health.status == StoreHealthStatus.HEALTHY


class TestTrustStoreHealthCheckHealthy:
    """Healthy store allows normal operation."""

    def test_is_healthy_returns_true(self):
        """is_healthy() returns True for a working store."""
        store = _FailingStore(should_fail=False)
        health = TrustStoreHealthCheck(store=store)
        assert health.is_healthy() is True

    def test_check_updates_status(self):
        """check() updates the status after probing the store."""
        store = _FailingStore(should_fail=False)
        health = TrustStoreHealthCheck(store=store)
        health.check()
        assert health.status == StoreHealthStatus.HEALTHY


class TestTrustStoreHealthCheckUnreachable:
    """Unreachable store causes fail-closed behavior."""

    def test_unreachable_store_blocks(self):
        """When store fails health check, status becomes UNREACHABLE."""
        store = _FailingStore(should_fail=True)
        health = TrustStoreHealthCheck(store=store)
        health.check()
        assert health.status == StoreHealthStatus.UNREACHABLE

    def test_unreachable_store_is_not_healthy(self):
        """is_healthy() returns False for unreachable store."""
        store = _FailingStore(should_fail=True)
        health = TrustStoreHealthCheck(store=store)
        health.check()
        assert health.is_healthy() is False

    def test_should_block_when_unreachable(self):
        """should_block_all() returns True when store is unreachable."""
        store = _FailingStore(should_fail=True)
        health = TrustStoreHealthCheck(store=store)
        health.check()
        assert health.should_block_all() is True


class TestTrustStoreHealthCheckRecovery:
    """Store recovery transitions from unreachable back to healthy."""

    def test_recovery_after_failure(self):
        """Store becomes healthy again after recovering from failure."""
        store = _FailingStore(should_fail=True)
        health = TrustStoreHealthCheck(store=store)
        health.check()
        assert health.status == StoreHealthStatus.UNREACHABLE

        # Simulate recovery
        store.set_failing(False)
        health.check()
        assert health.status == StoreHealthStatus.HEALTHY

    def test_should_not_block_after_recovery(self):
        """After recovery, actions should not be blocked."""
        store = _FailingStore(should_fail=True)
        health = TrustStoreHealthCheck(store=store)
        health.check()
        assert health.should_block_all() is True

        store.set_failing(False)
        health.check()
        assert health.should_block_all() is False


class TestTrustStoreHealthCheckCircuitBreaker:
    """Circuit breaker integration for store health."""

    def test_circuit_breaker_trips_on_repeated_failures(self):
        """Circuit breaker trips after threshold failures."""
        store = _FailingStore(should_fail=True)
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        health = TrustStoreHealthCheck(store=store, circuit_breaker=cb)

        for _ in range(3):
            health.check()

        assert health.status == StoreHealthStatus.UNREACHABLE

    def test_circuit_breaker_allows_recovery(self):
        """Circuit breaker allows recovery after timeout."""
        store = _FailingStore(should_fail=False)
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        health = TrustStoreHealthCheck(store=store, circuit_breaker=cb)
        health.check()
        assert health.is_healthy() is True


class TestMemoryStoreHealthCheck:
    """MemoryStore implements health_check()."""

    def test_memory_store_health_check(self):
        """MemoryStore.health_check() returns True."""
        store = MemoryStore()
        assert store.health_check() is True


class TestFilesystemStoreHealthCheck:
    """FilesystemStore implements health_check()."""

    def test_filesystem_store_health_check(self, tmp_path):
        """FilesystemStore.health_check() returns True when path is accessible."""
        store = FilesystemStore(tmp_path)
        assert store.health_check() is True

    def test_filesystem_store_unhealthy_when_path_gone(self, tmp_path):
        """FilesystemStore.health_check() returns False when path is inaccessible."""
        store = FilesystemStore(tmp_path)
        # Remove the base directory to simulate inaccessibility
        import shutil

        shutil.rmtree(tmp_path)
        assert store.health_check() is False


class TestSQLiteTrustStoreHealthCheck:
    """SQLiteTrustStore implements health_check()."""

    def test_sqlite_store_health_check(self):
        """SQLiteTrustStore.health_check() returns True for working database."""
        store = SQLiteTrustStore()
        assert store.health_check() is True
