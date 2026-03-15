# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""M23 Security Hardening — tests for task 2307.

Tests secrets rotation for tokens and Ed25519 keys.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from care_platform.trust.credentials import CredentialManager


class TestTokenRotation:
    """Token rotation: accept both old and new token during a grace period."""

    def test_rotate_token_returns_new_token(self):
        """rotate_token should issue a new token and keep the old one valid during grace period."""
        mgr = CredentialManager(default_ttl_seconds=300)
        old_token = mgr.issue_token("agent-1", trust_score=0.9)

        new_token = mgr.rotate_token("agent-1", trust_score=0.95, grace_period_seconds=60)

        assert new_token.token_id != old_token.token_id
        assert new_token.is_valid

    def test_old_token_valid_during_grace_period(self):
        """The old token should still be valid during the grace period."""
        mgr = CredentialManager(default_ttl_seconds=300)
        old_token = mgr.issue_token("agent-1", trust_score=0.9)

        mgr.rotate_token("agent-1", trust_score=0.95, grace_period_seconds=60)

        # Old token should still validate during grace period
        assert mgr.validate_token(old_token.token_id) is True

    def test_old_token_invalid_after_grace_period(self):
        """The old token should be invalid after the grace period expires."""
        mgr = CredentialManager(default_ttl_seconds=300)
        old_token = mgr.issue_token("agent-1", trust_score=0.9)

        mgr.rotate_token("agent-1", trust_score=0.95, grace_period_seconds=0)

        # With 0 grace period, old token should be invalid immediately
        assert mgr.validate_token(old_token.token_id) is False

    def test_get_valid_token_returns_new_after_rotation(self):
        """get_valid_token should return the new token after rotation."""
        mgr = CredentialManager(default_ttl_seconds=300)
        mgr.issue_token("agent-1", trust_score=0.9)
        new_token = mgr.rotate_token("agent-1", trust_score=0.95, grace_period_seconds=60)

        current = mgr.get_valid_token("agent-1")
        assert current is not None
        assert current.token_id == new_token.token_id

    def test_rotation_tracks_timestamp(self):
        """Rotation should record the rotation timestamp."""
        mgr = CredentialManager(default_ttl_seconds=300)
        mgr.issue_token("agent-1", trust_score=0.9)

        before = datetime.now(UTC)
        mgr.rotate_token("agent-1", trust_score=0.95, grace_period_seconds=60)

        assert mgr.last_rotation_time("agent-1") is not None
        assert mgr.last_rotation_time("agent-1") >= before

    def test_rotation_enforces_minimum_interval(self):
        """Should raise error if rotating too frequently."""
        mgr = CredentialManager(
            default_ttl_seconds=300,
            min_rotation_interval_seconds=60,
        )
        mgr.issue_token("agent-1", trust_score=0.9)
        mgr.rotate_token("agent-1", trust_score=0.95, grace_period_seconds=10)

        with pytest.raises(ValueError, match="minimum rotation interval"):
            mgr.rotate_token("agent-1", trust_score=0.95, grace_period_seconds=10)

    def test_rotate_nonexistent_agent_raises(self):
        """Rotating a token for a non-existent agent should raise ValueError."""
        mgr = CredentialManager(default_ttl_seconds=300)

        with pytest.raises(ValueError, match="No active token"):
            mgr.rotate_token("nonexistent", trust_score=0.9, grace_period_seconds=60)


class TestKeyRotation:
    """Ed25519 key rotation: sign with new key, verify with both during transition."""

    def test_register_signing_key(self):
        """Should be able to register an Ed25519 signing key."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        mgr = CredentialManager(default_ttl_seconds=300)
        private_key = Ed25519PrivateKey.generate()
        key_bytes = private_key.private_bytes_raw()

        mgr.register_signing_key("signer-1", key_bytes, key_version="v1")

        assert mgr.get_active_key_version("signer-1") == "v1"

    def test_rotate_signing_key(self):
        """Should be able to rotate to a new signing key while keeping old key for verification."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        mgr = CredentialManager(default_ttl_seconds=300)
        old_key = Ed25519PrivateKey.generate()
        new_key = Ed25519PrivateKey.generate()

        mgr.register_signing_key("signer-1", old_key.private_bytes_raw(), key_version="v1")
        mgr.rotate_signing_key(
            "signer-1",
            new_key.private_bytes_raw(),
            key_version="v2",
            grace_period_seconds=60,
        )

        assert mgr.get_active_key_version("signer-1") == "v2"

    def test_verification_accepts_both_keys_during_transition(self):
        """During grace period, verification should accept signatures from both old and new key."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        mgr = CredentialManager(default_ttl_seconds=300)
        old_key = Ed25519PrivateKey.generate()
        new_key = Ed25519PrivateKey.generate()

        mgr.register_signing_key("signer-1", old_key.private_bytes_raw(), key_version="v1")
        mgr.rotate_signing_key(
            "signer-1",
            new_key.private_bytes_raw(),
            key_version="v2",
            grace_period_seconds=60,
        )

        # Both keys should be retrievable for verification
        all_keys = mgr.get_verification_keys("signer-1")
        assert len(all_keys) == 2

    def test_rotation_records_timestamp(self):
        """Key rotation should record the rotation timestamp."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        mgr = CredentialManager(default_ttl_seconds=300)
        key = Ed25519PrivateKey.generate()

        before = datetime.now(UTC)
        mgr.register_signing_key("signer-1", key.private_bytes_raw(), key_version="v1")

        assert mgr.last_key_rotation_time("signer-1") is not None
        assert mgr.last_key_rotation_time("signer-1") >= before
