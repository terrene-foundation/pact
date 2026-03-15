# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Credential lifecycle management — verification tokens with TTL and revocation.

Manages short-lived verification tokens issued after trust chain verification.
Tokens have a configurable time-to-live (TTL) and can be revoked individually
or in bulk (during cascade revocation).
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class VerificationToken(BaseModel):
    """Short-lived token issued after trust chain verification.

    Tokens are valid only while within their TTL window and not revoked.
    Default TTL is 5 minutes (300 seconds).
    """

    token_id: str = Field(default_factory=lambda: f"vt-{uuid4().hex[:8]}")
    agent_id: str
    trust_score: float
    verification_level: str = Field(description="Verification level: QUICK, STANDARD, or FULL")
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    revoked: bool = False

    @classmethod
    def issue(
        cls,
        agent_id: str,
        trust_score: float,
        verification_level: str = "STANDARD",
        ttl_seconds: int = 300,
    ) -> VerificationToken:
        """Issue a new verification token with TTL.

        Args:
            agent_id: The agent this token is for.
            trust_score: The agent's trust score at time of issuance.
            verification_level: Level of verification performed (QUICK, STANDARD, FULL).
            ttl_seconds: Time-to-live in seconds (default 300 = 5 minutes).

        Returns:
            A new VerificationToken.
        """
        now = datetime.now(UTC)
        return cls(
            agent_id=agent_id,
            trust_score=trust_score,
            verification_level=verification_level,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

    @property
    def is_valid(self) -> bool:
        """Token is valid if not expired and not revoked."""
        if self.revoked:
            return False
        return datetime.now(UTC) <= self.expires_at

    def revoke(self) -> None:
        """Revoke this token immediately."""
        self.revoked = True
        logger.info(
            "Verification token %s for agent %s revoked",
            self.token_id,
            self.agent_id,
        )


class CredentialManager:
    """Manages verification tokens and credential lifecycle.

    Tracks one active token per agent, maintains history of past tokens,
    and supports bulk revocation for cascade scenarios.

    M23/2307: Supports token and key rotation with grace periods:
    - Token rotation: accept both old and new token during a grace period
    - Key rotation: sign with new key, verify with both during transition
    - Tracks rotation timestamps and enforces minimum rotation intervals
    """

    def __init__(
        self,
        default_ttl_seconds: int = 300,
        min_rotation_interval_seconds: float = 0.0,
    ):
        self._lock = threading.Lock()  # RT9-04: thread-safe credential access
        self.default_ttl = default_ttl_seconds
        self._min_rotation_interval = min_rotation_interval_seconds
        self._tokens: dict[str, VerificationToken] = {}  # agent_id -> current token
        self._token_history: list[VerificationToken] = []
        # M23/2307: Grace period tokens (old tokens still valid during rotation)
        self._grace_tokens: dict[str, VerificationToken] = {}  # agent_id -> old token
        self._grace_expiry: dict[str, datetime] = {}  # agent_id -> grace expiry time
        # M23/2307: Rotation timestamps
        self._last_rotation: dict[str, datetime] = {}  # agent_id -> last rotation time
        # M23/2307: Signing key management
        self._signing_keys: dict[str, list[dict]] = {}  # signer_id -> [key_info_dicts]
        self._key_rotation_times: dict[str, datetime] = {}  # signer_id -> last rotation

    def issue_token(
        self,
        agent_id: str,
        trust_score: float,
        verification_level: str = "STANDARD",
    ) -> VerificationToken:
        """Issue a new verification token for an agent.

        If the agent already has a token, the old token is moved to history
        and replaced with the new one.

        Args:
            agent_id: The agent to issue the token for.
            trust_score: The agent's current trust score.
            verification_level: Level of verification performed.

        Returns:
            The newly issued VerificationToken.
        """
        token = VerificationToken.issue(
            agent_id=agent_id,
            trust_score=trust_score,
            verification_level=verification_level,
            ttl_seconds=self.default_ttl,
        )
        with self._lock:
            # Move existing token to history if present
            existing = self._tokens.get(agent_id)
            if existing is not None:
                self._token_history.append(existing)
            self._tokens[agent_id] = token

        logger.info(
            "Issued verification token %s for agent %s (trust_score=%.2f, level=%s, ttl=%ds)",
            token.token_id,
            agent_id,
            trust_score,
            verification_level,
            self.default_ttl,
        )
        return token

    def get_valid_token(self, agent_id: str) -> VerificationToken | None:
        """Get the current valid token for an agent, or None if expired/missing.

        Args:
            agent_id: The agent to look up.

        Returns:
            The valid VerificationToken, or None if no valid token exists.
        """
        with self._lock:
            token = self._tokens.get(agent_id)
        if token is None:
            return None
        if not token.is_valid:
            return None
        return token

    def needs_reverification(self, agent_id: str) -> bool:
        """Check if agent needs re-verification (no valid token).

        Args:
            agent_id: The agent to check.

        Returns:
            True if the agent has no valid token and needs re-verification.
        """
        return self.get_valid_token(agent_id) is None

    def revoke_agent_tokens(self, agent_id: str) -> None:
        """Revoke all tokens for an agent (used during cascade revocation).

        Args:
            agent_id: The agent whose tokens should be revoked.
        """
        with self._lock:
            token = self._tokens.get(agent_id)
        if token is not None:
            token.revoke()
            logger.info("All tokens revoked for agent %s", agent_id)
        else:
            logger.debug("No active token found for agent %s during revocation", agent_id)

    def cleanup_expired(self) -> int:
        """Clean up expired tokens, return count removed.

        Removes tokens from the active token map that are no longer valid
        (expired or revoked). Does NOT remove from history.

        Returns:
            The number of tokens removed.
        """
        with self._lock:
            expired_agents = [
                agent_id for agent_id, token in self._tokens.items() if not token.is_valid
            ]
            for agent_id in expired_agents:
                removed_token = self._tokens.pop(agent_id)
                self._token_history.append(removed_token)
                logger.debug(
                    "Cleaned up expired token %s for agent %s",
                    removed_token.token_id,
                    agent_id,
                )
        if expired_agents:
            logger.info("Cleaned up %d expired token(s)", len(expired_agents))
        return len(expired_agents)

    # --- M23/2307: Token rotation ---

    def rotate_token(
        self,
        agent_id: str,
        trust_score: float,
        grace_period_seconds: int = 60,
        verification_level: str = "STANDARD",
    ) -> VerificationToken:
        """Rotate an agent's token with a grace period for the old token.

        During the grace period, both old and new tokens are accepted.
        After the grace period, the old token is invalidated.

        Args:
            agent_id: The agent whose token to rotate.
            trust_score: The agent's current trust score.
            grace_period_seconds: How long the old token remains valid (0 = immediate).
            verification_level: Verification level for the new token.

        Returns:
            The newly issued VerificationToken.

        Raises:
            ValueError: If no active token exists for the agent.
            ValueError: If rotation is attempted before the minimum interval.
        """
        with self._lock:
            old_token = self._tokens.get(agent_id)
            if old_token is None:
                raise ValueError(
                    f"No active token found for agent '{agent_id}'. "
                    f"Cannot rotate a non-existent token — use issue_token() first."
                )

            # Check minimum rotation interval
            last_rotation = self._last_rotation.get(agent_id)
            if last_rotation is not None and self._min_rotation_interval > 0:
                elapsed = (datetime.now(UTC) - last_rotation).total_seconds()
                if elapsed < self._min_rotation_interval:
                    raise ValueError(
                        f"Cannot rotate token for agent '{agent_id}': "
                        f"minimum rotation interval is {self._min_rotation_interval}s, "
                        f"but only {elapsed:.1f}s since last rotation."
                    )

            # Move old token to grace period
            if grace_period_seconds > 0:
                self._grace_tokens[agent_id] = old_token
                self._grace_expiry[agent_id] = datetime.now(UTC) + timedelta(
                    seconds=grace_period_seconds
                )
            else:
                # Immediate invalidation — revoke the old token
                old_token.revoke()

            # Move old to history
            self._token_history.append(old_token)

            # Issue new token
            new_token = VerificationToken.issue(
                agent_id=agent_id,
                trust_score=trust_score,
                verification_level=verification_level,
                ttl_seconds=self.default_ttl,
            )
            self._tokens[agent_id] = new_token
            self._last_rotation[agent_id] = datetime.now(UTC)

        logger.info(
            "Rotated token for agent %s: old=%s new=%s grace_period=%ds",
            agent_id,
            old_token.token_id,
            new_token.token_id,
            grace_period_seconds,
        )
        return new_token

    def validate_token(self, token_id: str) -> bool:
        """Validate a token by its ID, checking both active and grace tokens.

        Args:
            token_id: The token ID to validate.

        Returns:
            True if the token is valid (active or within grace period).
        """
        with self._lock:
            # Check active tokens
            for agent_id, token in self._tokens.items():
                if token.token_id == token_id and token.is_valid:
                    return True

            # Check grace period tokens
            for agent_id, token in self._grace_tokens.items():
                if token.token_id == token_id:
                    grace_end = self._grace_expiry.get(agent_id)
                    if grace_end is not None and datetime.now(UTC) <= grace_end:
                        if not token.revoked:
                            return True

        return False

    def last_rotation_time(self, agent_id: str) -> datetime | None:
        """Get the last rotation timestamp for an agent.

        Args:
            agent_id: The agent to check.

        Returns:
            The datetime of the last rotation, or None if never rotated.
        """
        with self._lock:
            return self._last_rotation.get(agent_id)

    # --- M23/2307: Ed25519 key rotation ---

    def register_signing_key(
        self,
        signer_id: str,
        key_bytes: bytes,
        key_version: str,
    ) -> None:
        """Register an Ed25519 signing key for a signer.

        Args:
            signer_id: Identifier for the signer.
            key_bytes: Raw 32-byte Ed25519 private key.
            key_version: Version identifier for the key.
        """
        with self._lock:
            if signer_id not in self._signing_keys:
                self._signing_keys[signer_id] = []

            self._signing_keys[signer_id].append(
                {
                    "key_bytes": key_bytes,
                    "key_version": key_version,
                    "registered_at": datetime.now(UTC),
                    "active": True,
                }
            )
            self._key_rotation_times[signer_id] = datetime.now(UTC)

        logger.info(
            "Registered signing key for signer '%s' (version: %s)",
            signer_id,
            key_version,
        )

    def rotate_signing_key(
        self,
        signer_id: str,
        new_key_bytes: bytes,
        key_version: str,
        grace_period_seconds: int = 60,
    ) -> None:
        """Rotate to a new Ed25519 signing key.

        During the grace period, both old and new keys are accepted for
        verification. New signatures use the new key.

        Args:
            signer_id: The signer whose key to rotate.
            new_key_bytes: Raw 32-byte Ed25519 private key.
            key_version: Version identifier for the new key.
            grace_period_seconds: How long old keys remain valid for verification.

        Raises:
            ValueError: If no key is registered for the signer.
        """
        with self._lock:
            if signer_id not in self._signing_keys or not self._signing_keys[signer_id]:
                raise ValueError(
                    f"No signing key registered for signer '{signer_id}'. "
                    f"Use register_signing_key() first."
                )

            # Mark old keys as inactive (but keep for verification during grace)
            for key_info in self._signing_keys[signer_id]:
                key_info["active"] = False
                key_info["grace_expires"] = datetime.now(UTC) + timedelta(
                    seconds=grace_period_seconds
                )

            # Add new key as active
            self._signing_keys[signer_id].append(
                {
                    "key_bytes": new_key_bytes,
                    "key_version": key_version,
                    "registered_at": datetime.now(UTC),
                    "active": True,
                }
            )
            self._key_rotation_times[signer_id] = datetime.now(UTC)

        logger.info(
            "Rotated signing key for signer '%s' to version '%s' (grace=%ds)",
            signer_id,
            key_version,
            grace_period_seconds,
        )
        # RT13-C3: Purge any already-expired keys from memory after rotation
        self.purge_expired_keys()

    def get_active_key_version(self, signer_id: str) -> str | None:
        """Get the active key version for a signer.

        Args:
            signer_id: The signer to look up.

        Returns:
            The version string of the active key, or None if no key is registered.
        """
        with self._lock:
            keys = self._signing_keys.get(signer_id, [])
            for key_info in reversed(keys):
                if key_info.get("active"):
                    return key_info["key_version"]
        return None

    def get_verification_keys(self, signer_id: str) -> list[dict]:
        """Get all keys valid for verification (active + grace period keys).

        Args:
            signer_id: The signer to look up.

        Returns:
            List of key info dicts with key_bytes and key_version.
        """
        with self._lock:
            keys = self._signing_keys.get(signer_id, [])
            now = datetime.now(UTC)
            valid_keys = []
            for key_info in keys:
                if key_info.get("active"):
                    valid_keys.append(key_info)
                elif "grace_expires" in key_info:
                    if key_info["grace_expires"] > now:
                        valid_keys.append(key_info)
            return valid_keys

    def last_key_rotation_time(self, signer_id: str) -> datetime | None:
        """Get the last key rotation timestamp for a signer.

        Args:
            signer_id: The signer to check.

        Returns:
            The datetime of the last key rotation, or None.
        """
        with self._lock:
            return self._key_rotation_times.get(signer_id)

    def purge_expired_keys(self) -> int:
        """Zero out and remove expired key material from memory.

        RT13-C3: Signing key bytes should not persist in memory indefinitely.
        This method zeroes the ``key_bytes`` buffer for any key whose grace
        period has elapsed, then removes the entry.  Call periodically (e.g.
        after each rotation or on a timer) to limit the exposure window.

        Returns:
            The number of key entries purged.
        """
        purged = 0
        now = datetime.now(UTC)
        with self._lock:
            for signer_id in list(self._signing_keys):
                remaining: list[dict] = []
                for key_info in self._signing_keys[signer_id]:
                    grace = key_info.get("grace_expires")
                    if not key_info.get("active") and grace is not None and grace <= now:
                        # Zero the key bytes before discarding
                        kb = key_info.get("key_bytes")
                        if isinstance(kb, (bytes, bytearray)):
                            # Replace with zeroed bytes of same length
                            key_info["key_bytes"] = b"\x00" * len(kb)
                        purged += 1
                    else:
                        remaining.append(key_info)
                self._signing_keys[signer_id] = remaining
        if purged:
            logger.info("RT13-C3: purged %d expired signing key(s) from memory", purged)
        return purged
