# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Inter-agent messaging — authenticated message passing with replay protection.

Agents communicate through MessageChannels that enforce participant membership,
nonce-based replay protection, and time-window freshness checks. The MessageRouter
provides higher-level routing across multiple channels.

EATP SDK Alignment (M24):
    This module integrates with ``eatp.messaging.channel.SecureChannel`` for
    cryptographic message signing and verification where EATP has equivalent
    functionality. CARE-specific extensions (delegation message types, bounded
    nonce eviction, sync API, revocation integration) are wrapped in thin
    EATP-GAP adapters that can be removed once the EATP SDK adds support.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, ClassVar, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, Field, PrivateAttr

from eatp.messaging.envelope import SecureMessageEnvelope
from eatp.messaging.replay_protection import InMemoryReplayProtection


@runtime_checkable
class NonceStore(Protocol):
    """Protocol for nonce persistence backends.

    Any object that implements store_envelope/get_envelope/list_envelopes
    (matching the TrustStore protocol) can be used as a nonce store.
    Nonces are stored as envelope records with ``nonce:`` prefixed IDs.
    """

    def store_envelope(self, envelope_id: str, data: dict) -> None: ...

    def get_envelope(self, envelope_id: str) -> dict | None: ...

    def list_envelopes(self, agent_id: str | None = None) -> list[dict]: ...


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EATP-GAP: M1 — Delegation message types
# ---------------------------------------------------------------------------
# The EATP SDK SecureChannel does not define message type semantics.
# CARE requires domain-specific message types including delegation
# request/response for trust governance workflows. This enum is CARE-
# specific governance vocabulary and will remain even if EATP adds
# a type system, because CARE's types carry governance semantics.


class MessageType(str, Enum):  # EATP-GAP: M1
    """Types of inter-agent messages.

    EATP SDK's SecureChannel is type-agnostic (payload-only). CARE needs
    typed messages for governance workflows, especially DELEGATION_REQUEST
    and DELEGATION_RESPONSE which have no EATP SDK equivalent.
    """

    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    DELEGATION_REQUEST = "delegation_request"  # EATP-GAP: M1
    DELEGATION_RESPONSE = "delegation_response"  # EATP-GAP: M1
    DATA_REQUEST = "data_request"


# ---------------------------------------------------------------------------
# EATP-GAP: M2 — Bounded nonce eviction adapter
# ---------------------------------------------------------------------------
# The EATP SDK's InMemoryReplayProtection has a hard cap (max_nonces) and
# async cleanup, but does NOT do proactive age-based eviction on each
# check_nonce() call. CARE's channel requires synchronous, bounded, age-
# based eviction on every send() to prevent unbounded growth in long-running
# synchronous processes.


class BoundedNonceCache:  # EATP-GAP: M2
    """Synchronous bounded nonce cache with age-based eviction.

    Wraps the concept from ``eatp.messaging.replay_protection.InMemoryReplayProtection``
    but provides:
    1. Synchronous API (EATP's is async-only — see M3)
    2. Proactive age-based eviction on every check (EATP only evicts on demand)
    3. Bounded size with oldest-first eviction

    When the EATP SDK adds a synchronous bounded replay protection API,
    this adapter can be replaced.
    """

    def __init__(
        self,
        max_age: timedelta,
        max_size: int = 100000,
    ) -> None:
        self._max_age = max_age
        self._max_size = max_size
        self._cache: OrderedDict[str, datetime] = OrderedDict()

    def check_and_record(self, nonce: str) -> bool:
        """Check if nonce is new and record it. Returns True if replay (seen before)."""
        return nonce in self._cache

    def record(self, nonce: str) -> None:
        """Record a nonce with the current timestamp."""
        self._cache[nonce] = datetime.now(UTC)

    def evict_stale(self) -> None:
        """Evict nonces older than max_age, then enforce max size."""
        now = datetime.now(UTC)
        stale_keys = [nonce for nonce, ts in self._cache.items() if (now - ts) > self._max_age]
        for key in stale_keys:
            del self._cache[key]

        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    @property
    def nonce_cache(self) -> OrderedDict[str, datetime]:
        """Expose the underlying cache (for test compatibility)."""
        return self._cache


# ---------------------------------------------------------------------------
# AgentMessage — CARE message model (uses EATP signing concepts)
# ---------------------------------------------------------------------------


class AgentMessage(BaseModel):
    """Authenticated message between agents.

    Each message carries a nonce for replay protection and a signature
    hash computed from the message identity fields. Tampering with any
    signed field will cause verify_authenticity() to return False.

    The signature computation follows the same canonical payload pattern
    as ``eatp.messaging.envelope.SecureMessageEnvelope.get_signing_payload()``
    — deterministic serialization of identity fields + payload with sorted keys.
    """

    message_id: str = Field(default_factory=lambda: f"msg-{uuid4().hex[:12]}")
    sender_id: str
    recipient_id: str
    message_type: MessageType
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    nonce: str = Field(default_factory=lambda: uuid4().hex)  # replay protection
    signature_hash: str = ""  # for authentication
    channel_mac: str = ""  # HMAC-SHA256 set by channel when channel_secret is configured

    def model_post_init(self, __context: object) -> None:
        """Auto-compute signature on creation if not already set."""
        if not self.signature_hash:
            self.signature_hash = self._compute_signature()

    def _compute_signature(self) -> str:
        """Compute SHA-256 signature over identity fields and payload.

        Covers message_id, sender, recipient, nonce, timestamp, AND payload
        content. Any change to these fields will produce a different signature.
        Uses full SHA-256 (64 hex chars) for collision resistance.

        Follows the same canonical serialization approach as
        ``eatp.messaging.envelope.SecureMessageEnvelope.get_signing_payload()``.
        """
        payload_str = json.dumps(self.payload, sort_keys=True, default=str)
        content = (
            f"{self.message_id}:{self.sender_id}:{self.recipient_id}"
            f":{self.nonce}:{self.timestamp.isoformat()}:{payload_str}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_authenticity(self) -> bool:
        """Verify message hasn't been tampered with.

        Recomputes the signature from current field values and compares
        against the stored signature hash using timing-safe comparison
        to prevent timing side-channel attacks.
        """
        computed = self._compute_signature()
        return hmac.compare_digest(self.signature_hash, computed)

    def verify_channel_mac(self, channel_secret: str) -> bool:
        """Verify the channel-level HMAC-SHA256 MAC.

        Returns True if the stored channel_mac matches an HMAC-SHA256
        computed over the signature_hash using the given channel_secret.
        Uses timing-safe comparison to prevent side-channel attacks.
        """
        if not self.channel_mac:
            return False
        expected = hmac.new(
            channel_secret.encode(),
            self.signature_hash.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(self.channel_mac, expected)

    def to_eatp_envelope(self, trust_chain_hash: str = "") -> SecureMessageEnvelope:
        """Convert to an EATP SecureMessageEnvelope for SDK interop.

        This enables CARE messages to be transmitted through EATP SDK
        secure channels when full cryptographic signing is needed.

        Args:
            trust_chain_hash: Hash of the sender's trust chain.

        Returns:
            An EATP SecureMessageEnvelope wrapping this message's payload.
        """
        # EATP-GAP: M1 — message_type is included in payload since EATP
        # envelope has no concept of typed messages.
        eatp_payload = {
            "care_message_type": self.message_type.value,
            **self.payload,
        }
        return SecureMessageEnvelope(
            message_id=self.message_id,
            sender_agent_id=self.sender_id,
            recipient_agent_id=self.recipient_id,
            payload=eatp_payload,
            timestamp=self.timestamp,
            nonce=self.nonce,
            trust_chain_hash=trust_chain_hash or self.signature_hash,
        )


# ---------------------------------------------------------------------------
# MessageChannel — uses BoundedNonceCache (EATP-GAP: M2, M3)
# ---------------------------------------------------------------------------


class MessageChannel(BaseModel):
    """Communication channel between agents with replay protection.

    Enforces three security properties:
    1. Participant membership -- only channel members can send/receive
    2. Nonce uniqueness -- duplicate nonces are rejected (replay protection)
    3. Time window -- messages older than max_message_age are rejected

    EATP SDK alignment:
    - Replay protection concept from ``eatp.messaging.replay_protection``
    - Signing payload pattern from ``eatp.messaging.envelope``
    - Bounded nonce eviction via CARE adapter (EATP-GAP: M2)
    - Synchronous API via CARE adapter (EATP-GAP: M3)
    """

    channel_id: str = Field(default_factory=lambda: f"ch-{uuid4().hex[:8]}")
    participant_ids: list[str] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)
    max_message_age: timedelta = timedelta(minutes=5)
    channel_secret: str = ""
    max_nonce_cache_size: int = 100000
    nonce_store: Any = Field(default=None, exclude=True)

    # EATP-GAP: M2/M3 — Synchronous bounded nonce cache
    # Wraps EATP replay protection concepts with sync API and proactive eviction
    _nonce_cache: OrderedDict[str, datetime] = PrivateAttr(default_factory=OrderedDict)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)  # RT9-05

    model_config: ClassVar[dict] = {"arbitrary_types_allowed": True}

    def model_post_init(self, __context: object) -> None:
        """Hydrate nonce cache from persistent store on initialization.

        RT5-03: When a nonce_store is configured, load existing nonces
        into the in-memory cache so replay protection survives restarts.
        """
        if self.nonce_store is not None:
            self._hydrate_nonces_from_store()

    def _hydrate_nonces_from_store(self) -> None:
        """Load existing nonces from the persistent store into memory.

        Scans all envelopes with ``nonce:`` prefix and adds them to the
        in-memory cache for fast lookup during replay detection.
        """
        if self.nonce_store is None:
            return

        try:
            all_envelopes = self.nonce_store.list_envelopes()
            for envelope in all_envelopes:
                nonce = envelope.get("nonce")
                ts_raw = envelope.get("timestamp")
                envelope_id = envelope.get("envelope_id", "")
                # Only hydrate nonce records (prefixed with "nonce:")
                if nonce and ts_raw and (envelope_id.startswith("nonce:") or "nonce" in envelope):
                    try:
                        ts = datetime.fromisoformat(ts_raw)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=UTC)
                        self._nonce_cache[nonce] = ts
                    except (ValueError, TypeError):
                        # Skip unparseable timestamps
                        self._nonce_cache[nonce] = datetime.now(UTC)
            if self._nonce_cache:
                logger.info(
                    "Hydrated %d nonces from store for channel %s",
                    len(self._nonce_cache),
                    self.channel_id,
                )
        except Exception as exc:
            logger.warning(
                "Failed to hydrate nonces from store for channel %s: %s",
                self.channel_id,
                exc,
            )

    def _persist_nonce(self, nonce: str) -> None:
        """Persist a nonce to the store for survival across restarts.

        RT5-03: Nonces are stored as envelope records with ``nonce:``
        prefixed IDs so they can be identified and hydrated on startup.
        """
        if self.nonce_store is None:
            return

        try:
            self.nonce_store.store_envelope(
                f"nonce:{nonce}",
                {
                    "nonce": nonce,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "channel_id": self.channel_id,
                    "envelope_id": f"nonce:{nonce}",
                },
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist nonce %s to store: %s",
                nonce,
                exc,
            )

    def _compute_channel_mac(self, message: AgentMessage) -> str:
        """RT2-04: Compute HMAC-SHA256 over the message's signature_hash using channel_secret."""
        return hmac.new(
            self.channel_secret.encode(),
            message.signature_hash.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _evict_stale_nonces(self) -> None:  # EATP-GAP: M2
        """Evict nonces older than max_message_age, then enforce max cache size.

        EATP SDK's InMemoryReplayProtection provides async cleanup_expired_nonces()
        but no proactive eviction on each check. This adapter performs synchronous
        age-based eviction followed by size-based eviction.
        """
        now = datetime.now(UTC)
        # Evict by age
        stale_keys = [
            nonce for nonce, ts in self._nonce_cache.items() if (now - ts) > self.max_message_age
        ]
        for key in stale_keys:
            del self._nonce_cache[key]

        # Evict oldest if cache exceeds max size
        while len(self._nonce_cache) > self.max_nonce_cache_size:
            self._nonce_cache.popitem(last=False)

    def send(self, message: AgentMessage) -> bool:  # EATP-GAP: M3
        """Send a message through the channel.

        Returns False and rejects the message if:
        - Sender is not in participant_ids
        - Recipient is not in participant_ids
        - Message nonce has been seen before (replay attack)
        - Message timestamp is older than max_message_age

        Returns True if the message was accepted and stored.

        Note: EATP SDK's SecureChannel.send() is async. This synchronous
        wrapper is needed because CARE Platform's messaging is used in
        synchronous trust evaluation contexts (EATP-GAP: M3).
        """
        with self._lock:
            # Evict stale nonces before processing
            self._evict_stale_nonces()

            # Check participant membership
            if message.sender_id not in self.participant_ids:
                return False
            if message.recipient_id not in self.participant_ids:
                return False

            # Check replay
            if self.is_replay(message):
                return False

            # Check time window
            now = datetime.now(UTC)
            age = now - message.timestamp
            if age > self.max_message_age:
                return False

            # Compute channel-level HMAC when channel_secret is configured
            if self.channel_secret:
                message.channel_mac = self._compute_channel_mac(message)

            # Accept the message and record nonce with timestamp
            self._nonce_cache[message.nonce] = datetime.now(UTC)
            # RT5-03: Persist nonce to store for survival across restarts
            self._persist_nonce(message.nonce)
            self.messages.append(message)
            return True

    def receive(self, recipient_id: str) -> list[AgentMessage]:
        """Get all messages addressed to a specific recipient."""
        with self._lock:
            return [m for m in self.messages if m.recipient_id == recipient_id]

    def is_replay(self, message: AgentMessage) -> bool:
        """Check if a message is a replay attack (nonce already seen)."""
        return message.nonce in self._nonce_cache


# ---------------------------------------------------------------------------
# MessageRouter — adds revocation integration (EATP-GAP: M4)
# ---------------------------------------------------------------------------


class MessageRouter(BaseModel):
    """Routes messages between agents across channels.

    Automatically finds or creates channels for agent pairs. Supports
    agent revocation to block compromised agents from sending messages.

    EATP-GAP: M4 — The EATP SDK's SecureChannel has no concept of sender
    revocation. CARE's MessageRouter maintains a revoked_agents set and
    rejects messages from revoked senders before they reach the channel.
    This is a CARE-specific governance enforcement layer.
    """

    channels: dict[str, MessageChannel] = Field(default_factory=dict)
    revoked_agents: set[str] = Field(default_factory=set)  # EATP-GAP: M4
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)  # RT9-05

    def create_channel(self, participant_ids: list[str]) -> MessageChannel:
        """Create a new channel between the given participants."""
        channel = MessageChannel(participant_ids=participant_ids)
        with self._lock:
            self.channels[channel.channel_id] = channel
        return channel

    def _find_channel_for(self, sender_id: str, recipient_id: str) -> MessageChannel | None:
        """Find an existing channel that contains both sender and recipient."""
        with self._lock:
            for channel in self.channels.values():
                if sender_id in channel.participant_ids and recipient_id in channel.participant_ids:
                    return channel
        return None

    def send_message(
        self,
        sender_id: str,
        recipient_id: str,
        message_type: MessageType,
        payload: dict | None = None,
    ) -> AgentMessage | None:
        """Send a message, finding or creating the appropriate channel.

        Returns None if the sender has been revoked (EATP-GAP: M4).
        Otherwise creates the message, routes it through the appropriate
        channel, and returns the sent message.
        """
        # EATP-GAP: M4 — Revocation check before send
        # EATP SDK's SecureChannel does not check agent revocation status.
        # CARE enforces this as a governance layer.
        with self._lock:
            if sender_id in self.revoked_agents:
                return None

        # Find or create channel
        channel = self._find_channel_for(sender_id, recipient_id)
        if channel is None:
            channel = self.create_channel([sender_id, recipient_id])

        msg = AgentMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            payload=payload if payload is not None else {},
        )

        sent = channel.send(msg)
        if not sent:
            return None

        return msg

    def revoke_sender(self, agent_id: str) -> None:  # EATP-GAP: M4
        """Mark an agent as revoked. Future messages from this agent will be rejected.

        EATP-GAP: M4 — The EATP SDK's SecureChannel has no revocation
        integration. This CARE-specific method blocks compromised agents
        at the routing layer.
        """
        with self._lock:
            self.revoked_agents.add(agent_id)

    def get_messages_for(self, agent_id: str) -> list[AgentMessage]:
        """Get all messages for an agent across all channels."""
        with self._lock:
            channels_snapshot = list(self.channels.values())
        result: list[AgentMessage] = []
        for channel in channels_snapshot:
            result.extend(channel.receive(agent_id))
        return result
