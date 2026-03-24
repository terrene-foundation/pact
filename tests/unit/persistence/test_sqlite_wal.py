# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for SQLite WAL mode concurrency (Task 2602).

Validates that:
- WAL mode is explicitly enabled on connection
- busy_timeout is set for concurrent access
- Journal size limit is configured to prevent unbounded WAL growth
- Concurrent reads/writes work correctly under WAL mode
"""

import threading

from pact_platform.trust.store.sqlite_store import SQLiteTrustStore

# ---------------------------------------------------------------------------
# WAL Mode Verification
# ---------------------------------------------------------------------------


class TestSQLiteWALMode:
    """WAL mode must be enabled on every connection."""

    def test_wal_mode_enabled_on_file_db(self, tmp_path):
        """File-based databases should have WAL journal mode."""
        db_path = tmp_path / "test_wal.db"
        store = SQLiteTrustStore(db_path=str(db_path))
        conn = store._get_connection()
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal", f"Expected WAL mode, got {result[0]}"
        store.close()

    def test_wal_mode_on_fresh_connection(self, tmp_path):
        """Each new connection should set WAL mode."""
        db_path = tmp_path / "test_wal_fresh.db"
        store = SQLiteTrustStore(db_path=str(db_path))
        # Get connection and verify
        conn = store._get_connection()
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"
        store.close()


# ---------------------------------------------------------------------------
# Busy Timeout
# ---------------------------------------------------------------------------


class TestSQLiteBusyTimeout:
    """busy_timeout must be set for concurrent access."""

    def test_busy_timeout_set(self, tmp_path):
        """busy_timeout should be set to a reasonable value (>= 5000ms)."""
        db_path = tmp_path / "test_timeout.db"
        store = SQLiteTrustStore(db_path=str(db_path))
        conn = store._get_connection()
        result = conn.execute("PRAGMA busy_timeout").fetchone()
        assert result[0] >= 5000, f"Expected busy_timeout >= 5000ms, got {result[0]}"
        store.close()


# ---------------------------------------------------------------------------
# Journal Size Limit
# ---------------------------------------------------------------------------


class TestSQLiteJournalSizeLimit:
    """Journal size limit should be set to prevent unbounded WAL growth."""

    def test_journal_size_limit_set(self, tmp_path):
        """journal_size_limit should be set to 64 MB (67108864 bytes)."""
        db_path = tmp_path / "test_journal.db"
        store = SQLiteTrustStore(db_path=str(db_path))
        conn = store._get_connection()
        result = conn.execute("PRAGMA journal_size_limit").fetchone()
        assert result[0] == 67108864, (
            f"Expected journal_size_limit=67108864 (64 MB), got {result[0]}"
        )
        store.close()


# ---------------------------------------------------------------------------
# Concurrent Access
# ---------------------------------------------------------------------------


class TestSQLiteConcurrentAccess:
    """WAL mode enables concurrent readers with a single writer."""

    def test_concurrent_reads_and_writes(self, tmp_path):
        """Multiple threads should be able to read/write without deadlocks."""
        db_path = tmp_path / "test_concurrent.db"
        store = SQLiteTrustStore(db_path=str(db_path))
        errors = []

        def writer(store, start, count):
            try:
                for i in range(start, start + count):
                    store.store_envelope(
                        f"env-{i}",
                        {"envelope_id": f"env-{i}", "agent_id": "agent-1"},
                    )
            except Exception as exc:
                errors.append(exc)

        def reader(store, expected_agent):
            try:
                store.list_envelopes(agent_id=expected_agent)
            except Exception as exc:
                errors.append(exc)

        threads = []
        # Two writer threads
        threads.append(threading.Thread(target=writer, args=(store, 0, 5)))
        threads.append(threading.Thread(target=writer, args=(store, 5, 5)))
        # Two reader threads
        threads.append(threading.Thread(target=reader, args=(store, "agent-1")))
        threads.append(threading.Thread(target=reader, args=(store, "agent-1")))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent access errors: {errors}"
        store.close()

    def test_concurrent_posture_writes(self, tmp_path):
        """Multiple threads appending posture changes should not conflict."""
        db_path = tmp_path / "test_posture_concurrent.db"
        store = SQLiteTrustStore(db_path=str(db_path))
        errors = []

        def append_posture(store, agent_id, count):
            try:
                for _ in range(count):
                    store.store_posture_change(
                        agent_id,
                        {
                            "agent_id": agent_id,
                            "from_posture": "supervised",
                            "to_posture": "shared_planning",
                        },
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=append_posture, args=(store, f"agent-{i}", 5)) for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent posture write errors: {errors}"
        # Each agent should have 5 posture changes
        for i in range(4):
            history = store.get_posture_history(f"agent-{i}")
            assert len(history) == 5, f"agent-{i} has {len(history)} entries, expected 5"
        store.close()
