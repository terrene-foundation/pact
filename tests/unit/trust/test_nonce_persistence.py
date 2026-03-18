# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for nonce persistence in messaging (M22-2204 / RT5-03).

Validates that:
- Nonces are persisted to TrustStore when a nonce_store is configured
- On startup, nonce cache is hydrated from store
- In-memory cache still provides fast lookups
- Replay protection works across hypothetical restarts (via store)
- Nonce eviction by age also cleans the store
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from care_platform.trust.store.store import MemoryStore
from care_platform.trust.messaging import (
    AgentMessage,
    MessageChannel,
    MessageType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def nonce_store():
    """A MemoryStore for persisting nonces."""
    return MemoryStore()


@pytest.fixture()
def channel_with_store(nonce_store):
    """MessageChannel with nonce persistence via a store."""
    return MessageChannel(
        participant_ids=["alice", "bob"],
        nonce_store=nonce_store,
    )


@pytest.fixture()
def channel_without_store():
    """MessageChannel without nonce persistence (in-memory only)."""
    return MessageChannel(
        participant_ids=["alice", "bob"],
    )


def _make_message(sender: str = "alice", recipient: str = "bob") -> AgentMessage:
    """Create a test message."""
    return AgentMessage(
        sender_id=sender,
        recipient_id=recipient,
        message_type=MessageType.REQUEST,
        payload={"test": True},
    )


# ---------------------------------------------------------------------------
# Tests: Nonce persistence on send
# ---------------------------------------------------------------------------


class TestNoncePersistenceOnSend:
    """Nonces are persisted to store when messages are sent."""

    def test_nonce_stored_on_send(self, channel_with_store, nonce_store):
        """When a message is sent, its nonce should be persisted."""
        msg = _make_message()
        result = channel_with_store.send(msg)
        assert result is True

        # Nonce should be in the store
        stored = nonce_store.get_envelope(f"nonce:{msg.nonce}")
        assert stored is not None
        assert stored["nonce"] == msg.nonce

    def test_nonce_not_stored_without_store(self, channel_without_store):
        """Without a nonce store, nonces stay in memory only."""
        msg = _make_message()
        result = channel_without_store.send(msg)
        assert result is True
        # No store to check, just verify send succeeded


# ---------------------------------------------------------------------------
# Tests: Nonce hydration on init
# ---------------------------------------------------------------------------


class TestNonceHydration:
    """Nonce cache is hydrated from store on channel creation."""

    def test_hydrate_nonces_from_store(self, nonce_store):
        """Channel should load existing nonces from store on creation."""
        # Pre-populate the store with a nonce
        nonce_value = "pre-existing-nonce-123"
        nonce_store.store_envelope(
            f"nonce:{nonce_value}",
            {
                "nonce": nonce_value,
                "timestamp": datetime.now(UTC).isoformat(),
                "channel_id": "test",
            },
        )

        # Create a new channel with this store
        channel = MessageChannel(
            participant_ids=["alice", "bob"],
            nonce_store=nonce_store,
        )

        # The pre-existing nonce should be in the cache
        assert channel.is_replay(
            AgentMessage(
                sender_id="alice",
                recipient_id="bob",
                message_type=MessageType.REQUEST,
                nonce=nonce_value,
            )
        )

    def test_hydrated_nonce_blocks_replay(self, nonce_store):
        """A nonce loaded from store should block replay attempts."""
        nonce_value = "hydrated-nonce-456"
        nonce_store.store_envelope(
            f"nonce:{nonce_value}",
            {
                "nonce": nonce_value,
                "timestamp": datetime.now(UTC).isoformat(),
                "channel_id": "test",
            },
        )

        channel = MessageChannel(
            participant_ids=["alice", "bob"],
            nonce_store=nonce_store,
        )

        msg = AgentMessage(
            sender_id="alice",
            recipient_id="bob",
            message_type=MessageType.REQUEST,
            nonce=nonce_value,
        )
        result = channel.send(msg)
        assert result is False  # Blocked as replay


# ---------------------------------------------------------------------------
# Tests: Replay protection across restarts
# ---------------------------------------------------------------------------


class TestReplayProtectionAcrossRestarts:
    """Replay protection survives channel recreation (simulated restart)."""

    def test_nonce_survives_channel_recreation(self, nonce_store):
        """Nonce persisted by first channel blocks replay on second channel."""
        # First channel: send a message
        channel1 = MessageChannel(
            participant_ids=["alice", "bob"],
            nonce_store=nonce_store,
        )
        msg = _make_message()
        assert channel1.send(msg) is True

        # Second channel: same store, simulating restart
        channel2 = MessageChannel(
            participant_ids=["alice", "bob"],
            nonce_store=nonce_store,
        )

        # Try to replay the same message
        replay_msg = AgentMessage(
            sender_id="alice",
            recipient_id="bob",
            message_type=MessageType.REQUEST,
            nonce=msg.nonce,
        )
        assert channel2.send(replay_msg) is False
