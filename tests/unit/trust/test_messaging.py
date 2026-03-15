# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for inter-agent messaging with replay protection."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from care_platform.trust.messaging import (
    AgentMessage,
    MessageChannel,
    MessageRouter,
    MessageType,
)


class TestAgentMessage:
    """Tier 1 unit tests for AgentMessage model."""

    def test_message_authenticity_verification(self):
        """An untampered message should pass authenticity verification."""
        msg = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"action": "review_document"},
        )
        assert msg.message_id.startswith("msg-")
        assert msg.verify_authenticity() is True

    def test_tampered_message_fails_verification(self):
        """Modifying message fields after creation should fail authenticity check."""
        msg = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.NOTIFICATION,
            payload={"alert": "threshold_breach"},
        )
        # Tamper with sender
        msg.sender_id = "agent-malicious"
        assert msg.verify_authenticity() is False

    def test_multiple_message_types_work(self):
        """All message types should create valid messages."""
        for msg_type in MessageType:
            msg = AgentMessage(
                sender_id="agent-alpha",
                recipient_id="agent-beta",
                message_type=msg_type,
                payload={"type_test": msg_type.value},
            )
            assert msg.verify_authenticity() is True
            assert msg.message_type == msg_type


class TestMessageChannel:
    """Tier 1 unit tests for MessageChannel."""

    def _make_channel(self, participants=None, max_age_minutes=5):
        """Helper to create a channel with participants."""
        return MessageChannel(
            participant_ids=participants or ["agent-alpha", "agent-beta"],
            max_message_age=timedelta(minutes=max_age_minutes),
        )

    def test_send_message_between_participants_succeeds(self):
        """A message between valid participants should be accepted."""
        channel = self._make_channel()
        msg = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"data": "hello"},
        )
        result = channel.send(msg)
        assert result is True
        assert len(channel.messages) == 1

    def test_message_from_non_participant_rejected(self):
        """A message from an agent not in the channel should be rejected."""
        channel = self._make_channel()
        msg = AgentMessage(
            sender_id="agent-outsider",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"data": "intrusion attempt"},
        )
        result = channel.send(msg)
        assert result is False
        assert len(channel.messages) == 0

    def test_message_to_non_participant_rejected(self):
        """A message to an agent not in the channel should be rejected."""
        channel = self._make_channel()
        msg = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-outsider",
            message_type=MessageType.REQUEST,
            payload={"data": "wrong recipient"},
        )
        result = channel.send(msg)
        assert result is False
        assert len(channel.messages) == 0

    def test_replay_attack_same_nonce_rejected(self):
        """Sending a message with the same nonce twice should be rejected."""
        channel = self._make_channel()
        fixed_nonce = uuid4().hex
        msg1 = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"data": "original"},
            nonce=fixed_nonce,
        )
        msg2 = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"data": "replay"},
            nonce=fixed_nonce,
        )
        assert channel.send(msg1) is True
        assert channel.send(msg2) is False  # replay rejected
        assert len(channel.messages) == 1

    def test_old_message_outside_time_window_rejected(self):
        """A message older than max_message_age should be rejected."""
        channel = self._make_channel(max_age_minutes=5)
        old_timestamp = datetime.now(UTC) - timedelta(minutes=10)
        msg = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"data": "stale message"},
            timestamp=old_timestamp,
        )
        result = channel.send(msg)
        assert result is False
        assert len(channel.messages) == 0

    def test_is_replay_detects_seen_nonces(self):
        """is_replay should detect nonces that have already been seen."""
        channel = self._make_channel()
        msg = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"data": "test"},
        )
        # Before sending, not a replay
        assert channel.is_replay(msg) is False
        # Send it
        channel.send(msg)
        # Now it is a replay
        assert channel.is_replay(msg) is True

    def test_receive_filters_by_recipient(self):
        """receive() should return only messages for the specified recipient."""
        channel = MessageChannel(
            participant_ids=["agent-alpha", "agent-beta", "agent-gamma"],
        )
        msg1 = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.NOTIFICATION,
            payload={"info": "for beta"},
        )
        msg2 = AgentMessage(
            sender_id="agent-alpha",
            recipient_id="agent-gamma",
            message_type=MessageType.NOTIFICATION,
            payload={"info": "for gamma"},
        )
        channel.send(msg1)
        channel.send(msg2)

        beta_messages = channel.receive("agent-beta")
        assert len(beta_messages) == 1
        assert beta_messages[0].payload["info"] == "for beta"

        gamma_messages = channel.receive("agent-gamma")
        assert len(gamma_messages) == 1
        assert gamma_messages[0].payload["info"] == "for gamma"


class TestMessageRouter:
    """Tier 1 unit tests for MessageRouter."""

    def test_create_channel(self):
        """Router should create a channel with the given participants."""
        router = MessageRouter()
        channel = router.create_channel(["agent-alpha", "agent-beta"])
        assert channel.channel_id.startswith("ch-")
        assert "agent-alpha" in channel.participant_ids
        assert "agent-beta" in channel.participant_ids
        assert channel.channel_id in router.channels

    def test_send_message_creates_channel_automatically(self):
        """Router should auto-create a channel when none exists for the pair."""
        router = MessageRouter()
        msg = router.send_message(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"action": "start_review"},
        )
        assert msg is not None
        assert msg.sender_id == "agent-alpha"
        assert msg.recipient_id == "agent-beta"
        assert len(router.channels) == 1

    def test_send_message_reuses_existing_channel(self):
        """Router should reuse an existing channel for the same participants."""
        router = MessageRouter()
        router.send_message(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"action": "first"},
        )
        router.send_message(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"action": "second"},
        )
        assert len(router.channels) == 1

    def test_revoked_sender_cannot_send_messages(self):
        """A revoked agent should not be able to send messages."""
        router = MessageRouter()
        router.revoke_sender("agent-compromised")
        msg = router.send_message(
            sender_id="agent-compromised",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"action": "malicious"},
        )
        assert msg is None

    def test_get_messages_for_agent_across_channels(self):
        """get_messages_for should aggregate messages from all channels."""
        router = MessageRouter()
        router.send_message(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.NOTIFICATION,
            payload={"info": "from alpha"},
        )
        router.send_message(
            sender_id="agent-gamma",
            recipient_id="agent-beta",
            message_type=MessageType.NOTIFICATION,
            payload={"info": "from gamma"},
        )
        beta_messages = router.get_messages_for("agent-beta")
        assert len(beta_messages) == 2

    def test_revoke_sender_after_channel_creation(self):
        """Revoking a sender after channel creation should block future messages."""
        router = MessageRouter()
        # First message succeeds
        msg1 = router.send_message(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"action": "allowed"},
        )
        assert msg1 is not None

        # Revoke the sender
        router.revoke_sender("agent-alpha")

        # Second message fails
        msg2 = router.send_message(
            sender_id="agent-alpha",
            recipient_id="agent-beta",
            message_type=MessageType.REQUEST,
            payload={"action": "blocked"},
        )
        assert msg2 is None

    def test_delegation_message_types(self):
        """Delegation-specific message types should work through the router."""
        router = MessageRouter()
        request = router.send_message(
            sender_id="team-lead",
            recipient_id="agent-worker",
            message_type=MessageType.DELEGATION_REQUEST,
            payload={"task": "process_report", "constraints": {"max_spend": 100}},
        )
        assert request is not None
        assert request.message_type == MessageType.DELEGATION_REQUEST

        response = router.send_message(
            sender_id="agent-worker",
            recipient_id="team-lead",
            message_type=MessageType.DELEGATION_RESPONSE,
            payload={"status": "accepted", "task": "process_report"},
        )
        assert response is not None
        assert response.message_type == MessageType.DELEGATION_RESPONSE
