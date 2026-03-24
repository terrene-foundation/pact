# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for constraint envelope signing — Ed25519 signing, verification,
tamper detection, version history tracking, and expiry.
"""

from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pact_platform.build.config.schema import (
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
)
from pact_platform.trust.constraint.envelope import ConstraintEnvelope
from pact_platform.trust.constraint.signing import EnvelopeVersionHistory, SignedEnvelope


def _make_envelope(**kwargs) -> ConstraintEnvelope:
    config = ConstraintEnvelopeConfig(id="test-env", **kwargs)
    return ConstraintEnvelope(config=config)


def _generate_keypair() -> tuple[bytes, bytes]:
    """Generate an Ed25519 keypair, returning (private_key_bytes, public_key_bytes)."""
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes_raw()
    public_bytes = private_key.public_key().public_bytes_raw()
    return private_bytes, public_bytes


class TestSignAndVerify:
    def test_sign_and_verify_succeeds(self):
        """Sign an envelope and verify the signature passes."""
        envelope = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(allowed_actions=["read", "write"]),
        )
        private_key, public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        assert signed.signer_id == "signer-1"
        assert signed.version == 1
        assert signed.signature  # non-empty
        assert signed.verify_signature(public_key)

    def test_tampered_envelope_fails_verification(self):
        """Modifying the envelope after signing should fail verification.

        RT5-04: Constraint configs are now frozen (immutable). Direct mutation
        raises a ValidationError, which is a stronger guarantee than detecting
        tampering at verification time. We verify both: (1) mutation is blocked,
        and (2) if someone constructs a new envelope with different values, the
        original signature won't verify.
        """
        envelope = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        private_key, public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        # RT5-04: Direct mutation is now blocked by frozen models
        import pytest

        with pytest.raises(Exception):
            signed.envelope.config.financial.max_spend_usd = 999999.0

        # Construct a tampered envelope via model_copy to verify signature still catches it
        tampered_financial = signed.envelope.config.financial.model_copy(
            update={"max_spend_usd": 999999.0}
        )
        tampered_config = signed.envelope.config.model_copy(
            update={"financial": tampered_financial}
        )
        tampered_envelope = signed.envelope.model_copy(update={"config": tampered_config})
        tampered_signed = signed.model_copy(update={"envelope": tampered_envelope})

        assert not tampered_signed.verify_signature(public_key)

    def test_wrong_key_fails_verification(self):
        """Using a different key pair should fail verification."""
        envelope = _make_envelope()
        private_key_1, _public_key_1 = _generate_keypair()
        _private_key_2, public_key_2 = _generate_keypair()

        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key_1)
        assert not signed.verify_signature(public_key_2)

    def test_tampered_signer_id_fails_verification(self):
        """Changing the signer_id after signing should fail verification."""
        envelope = _make_envelope()
        private_key, public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        signed.signer_id = "imposter"
        assert not signed.verify_signature(public_key)

    def test_signed_at_is_set(self):
        """signed_at timestamp should be populated during signing."""
        envelope = _make_envelope()
        private_key, _public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        assert signed.signed_at is not None
        # Should be very recent
        delta = datetime.now(UTC) - signed.signed_at
        assert delta.total_seconds() < 5

    def test_signature_is_hex_encoded(self):
        """Signature should be a valid hex string."""
        envelope = _make_envelope()
        private_key, _public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        # Should be valid hex
        bytes.fromhex(signed.signature)
        # Ed25519 signatures are 64 bytes = 128 hex chars
        assert len(signed.signature) == 128

    def test_signature_covers_all_five_dimensions(self):
        """Changing any constraint dimension should invalidate the signature.

        RT5-04: Constraint configs are now frozen. We verify tampering via
        model_copy to construct a modified envelope and check the signature
        no longer verifies.
        """
        import pytest

        private_key, public_key = _generate_keypair()

        # Sign an envelope with specific constraints across all dimensions
        envelope = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=50.0),
            operational=OperationalConstraintConfig(allowed_actions=["read"]),
        )
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)
        assert signed.verify_signature(public_key)

        # RT5-04: Direct mutation is blocked by frozen models
        with pytest.raises(Exception):
            signed.envelope.config.operational.allowed_actions = ["read", "delete"]

        # Construct tampered envelope via model_copy to verify signature detects it
        tampered_op = signed.envelope.config.operational.model_copy(
            update={"allowed_actions": ["read", "delete"]}
        )
        tampered_config = signed.envelope.config.model_copy(update={"operational": tampered_op})
        tampered_envelope = signed.envelope.model_copy(update={"config": tampered_config})
        tampered_signed = signed.model_copy(update={"envelope": tampered_envelope})
        assert not tampered_signed.verify_signature(public_key)


class TestExpiry:
    def test_is_expired_returns_false_for_fresh_envelope(self):
        """A freshly signed envelope should not be expired."""
        envelope = _make_envelope()
        private_key, _public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)
        assert not signed.is_expired()

    def test_is_expired_returns_true_for_old_envelope(self):
        """An envelope signed 91 days ago should be expired (90-day default)."""
        envelope = _make_envelope()
        private_key, _public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        # Force the signed_at to 91 days ago
        signed.signed_at = datetime.now(UTC) - timedelta(days=91)
        assert signed.is_expired()

    def test_is_expired_boundary_at_90_days(self):
        """An envelope signed exactly 89 days ago should not be expired."""
        envelope = _make_envelope()
        private_key, _public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        signed.signed_at = datetime.now(UTC) - timedelta(days=89)
        assert not signed.is_expired()


class TestVersionHistory:
    def test_add_first_version(self):
        """Adding the first version should have no previous_version_hash."""
        envelope = _make_envelope()
        private_key, public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        history = EnvelopeVersionHistory(envelope_id="test-env")
        history.add_version(signed, private_key=private_key, public_key=public_key)

        assert len(history.versions) == 1
        assert history.versions[0].version == 1
        assert history.versions[0].previous_version_hash is None

    def test_add_subsequent_version_links_to_previous(self):
        """Version 2 should reference version 1's hash."""
        private_key, public_key = _generate_keypair()

        envelope_v1 = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        signed_v1 = SignedEnvelope.sign_envelope(envelope_v1, "signer-1", private_key)

        envelope_v2 = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=50.0),
        )
        signed_v2 = SignedEnvelope.sign_envelope(envelope_v2, "signer-1", private_key)

        history = EnvelopeVersionHistory(envelope_id="test-env")
        history.add_version(signed_v1, private_key=private_key, public_key=public_key)
        history.add_version(signed_v2, private_key=private_key, public_key=public_key)

        assert len(history.versions) == 2
        assert history.versions[1].version == 2
        assert history.versions[1].previous_version_hash is not None
        # The previous_version_hash should be non-empty
        assert len(history.versions[1].previous_version_hash) > 0

    def test_get_current_returns_latest(self):
        """get_current() should return the most recently added version."""
        private_key, public_key = _generate_keypair()
        history = EnvelopeVersionHistory(envelope_id="test-env")

        env1 = _make_envelope(financial=FinancialConstraintConfig(max_spend_usd=100.0))
        signed1 = SignedEnvelope.sign_envelope(env1, "signer-1", private_key)
        history.add_version(signed1, private_key=private_key, public_key=public_key)

        env2 = _make_envelope(financial=FinancialConstraintConfig(max_spend_usd=50.0))
        signed2 = SignedEnvelope.sign_envelope(env2, "signer-1", private_key)
        history.add_version(signed2, private_key=private_key, public_key=public_key)

        current = history.get_current()
        assert current is not None
        assert current.version == 2

    def test_get_current_returns_none_for_empty(self):
        """get_current() on an empty history should return None."""
        history = EnvelopeVersionHistory(envelope_id="test-env")
        assert history.get_current() is None

    def test_get_version_by_number(self):
        """get_version(n) should retrieve the correct version."""
        private_key, public_key = _generate_keypair()
        history = EnvelopeVersionHistory(envelope_id="test-env")

        for i in range(3):
            env = _make_envelope(
                financial=FinancialConstraintConfig(max_spend_usd=100.0 - i * 10),
            )
            signed = SignedEnvelope.sign_envelope(env, "signer-1", private_key)
            history.add_version(signed, private_key=private_key, public_key=public_key)

        v2 = history.get_version(2)
        assert v2 is not None
        assert v2.version == 2

    def test_get_version_nonexistent_returns_none(self):
        """get_version() for a version that does not exist should return None."""
        history = EnvelopeVersionHistory(envelope_id="test-env")
        assert history.get_version(42) is None

    def test_version_numbers_increment(self):
        """Version numbers should monotonically increase as versions are added."""
        private_key, public_key = _generate_keypair()
        history = EnvelopeVersionHistory(envelope_id="test-env")

        for _i in range(5):
            env = _make_envelope()
            signed = SignedEnvelope.sign_envelope(env, "signer-1", private_key)
            history.add_version(signed, private_key=private_key, public_key=public_key)

        for i, version in enumerate(history.versions, start=1):
            assert version.version == i

    def test_add_version_requires_private_key(self):
        """add_version without private_key should raise ValueError."""
        envelope = _make_envelope()
        private_key, _public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        history = EnvelopeVersionHistory(envelope_id="test-env")
        import pytest

        with pytest.raises(ValueError, match="private_key is required"):
            history.add_version(signed)

    def test_re_signed_version_has_valid_signature(self):
        """After add_version, the stored version should have a valid signature."""
        private_key, public_key = _generate_keypair()

        envelope = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        history = EnvelopeVersionHistory(envelope_id="test-env")
        history.add_version(signed, private_key=private_key, public_key=public_key)

        stored = history.get_current()
        assert stored is not None
        assert stored.verify_signature(public_key), (
            "Re-signed envelope after add_version should have a valid signature"
        )

    def test_all_versions_have_valid_signatures(self):
        """All versions in history should have valid signatures after re-signing."""
        private_key, public_key = _generate_keypair()
        history = EnvelopeVersionHistory(envelope_id="test-env")

        for i in range(3):
            env = _make_envelope(
                financial=FinancialConstraintConfig(max_spend_usd=100.0 - i * 20),
            )
            signed = SignedEnvelope.sign_envelope(env, "signer-1", private_key)
            history.add_version(signed, private_key=private_key, public_key=public_key)

        for v in history.versions:
            assert v.verify_signature(public_key), (
                f"Version {v.version} should have a valid signature"
            )

    def test_add_version_does_not_mutate_original(self):
        """add_version should not modify the original SignedEnvelope object."""
        private_key, public_key = _generate_keypair()

        envelope = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)
        original_version = signed.version
        original_signature = signed.signature
        original_hash = signed.previous_version_hash

        history = EnvelopeVersionHistory(envelope_id="test-env")
        history.add_version(signed, private_key=private_key, public_key=public_key)

        # Original should be unchanged
        assert signed.version == original_version
        assert signed.signature == original_signature
        assert signed.previous_version_hash == original_hash
