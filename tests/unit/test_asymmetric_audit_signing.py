# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for asymmetric (Ed25519) audit anchor signing.

Todo 1206: AuditAnchor and AuditChain must support Ed25519 signing alongside
the existing HMAC-SHA256 default. Ed25519 is opt-in via asymmetric=True.
Backward compatibility with HMAC is mandatory.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pact_platform.build.config.schema import VerificationLevel
from pact_platform.trust.audit.anchor import AuditAnchor, AuditChain

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ed25519_keypair() -> tuple[bytes, bytes]:
    """Generate an Ed25519 keypair, returning (private_key_bytes, public_key_bytes)."""
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes_raw()
    pub_bytes = priv.public_key().public_bytes_raw()
    return priv_bytes, pub_bytes


def _make_sealed_anchor(**overrides) -> AuditAnchor:
    """Create a sealed AuditAnchor with sensible defaults."""
    defaults = dict(
        anchor_id="test-0",
        sequence=0,
        agent_id="agent-a",
        action="read_data",
        verification_level=VerificationLevel.AUTO_APPROVED,
    )
    defaults.update(overrides)
    anchor = AuditAnchor(**defaults)
    anchor.seal()
    return anchor


# ===========================================================================
# Tier 1 (Unit) -- AuditAnchor Ed25519 signing
# ===========================================================================


class TestAuditAnchorEd25519Signing:
    """Ed25519 signing and verification on individual anchors."""

    def test_sign_asymmetric_sets_signature_and_signer(self):
        """sign(asymmetric=True) must populate signature and signer_id."""
        priv, _pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()

        anchor.sign(priv, "authority-1", asymmetric=True)

        assert anchor.signature is not None
        assert anchor.signer_id == "authority-1"

    def test_verify_asymmetric_signature_with_public_key(self):
        """verify_signature(public_key, asymmetric=True) must return True for valid sig."""
        priv, pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        assert anchor.verify_signature(pub, asymmetric=True) is True

    def test_verify_asymmetric_fails_with_wrong_key(self):
        """verify_signature must return False when a different public key is used."""
        priv, _pub = _make_ed25519_keypair()
        _other_priv, other_pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        assert anchor.verify_signature(other_pub, asymmetric=True) is False

    def test_verify_asymmetric_fails_when_content_tampered(self):
        """If the content_hash is modified after signing, verification must fail."""
        priv, pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        # Tamper with the result field and recompute hash to simulate attack
        original_sig = anchor.signature
        anchor.content_hash = "deadbeef" * 8  # tampered hash
        # signature was over the original content_hash, so verification fails
        assert anchor.verify_signature(pub, asymmetric=True) is False

    def test_sign_asymmetric_refuses_unsealed_anchor(self):
        """sign(asymmetric=True) must raise ValueError if anchor is not sealed."""
        priv, _pub = _make_ed25519_keypair()
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-a",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert not anchor.is_sealed

        with pytest.raises(ValueError, match="unsealed"):
            anchor.sign(priv, "authority-1", asymmetric=True)

    def test_sign_asymmetric_refuses_tampered_anchor(self):
        """sign(asymmetric=True) must refuse to sign if integrity check fails (post-seal tampering)."""
        priv, _pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        # Tamper after sealing
        anchor.result = "TAMPERED"

        with pytest.raises(ValueError, match="modified after sealing"):
            anchor.sign(priv, "authority-1", asymmetric=True)

    def test_signature_type_tracks_asymmetric(self):
        """When signed with Ed25519, signature_type must be 'ed25519'."""
        priv, _pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        assert anchor.signature_type == "ed25519"

    def test_is_signed_true_after_asymmetric_sign(self):
        """is_signed must return True after Ed25519 signing."""
        priv, _pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        assert anchor.is_signed is True


# ===========================================================================
# Tier 1 (Unit) -- HMAC backward compatibility
# ===========================================================================


class TestAuditAnchorHMACBackwardCompatibility:
    """HMAC-SHA256 signing must remain the default and work exactly as before."""

    def test_default_sign_uses_hmac(self):
        """sign() without asymmetric flag must use HMAC-SHA256."""
        key = b"secret-key-for-hmac"
        anchor = _make_sealed_anchor()
        anchor.sign(key, "authority-hmac")

        # RT4-H11: signable now includes signature_type to prevent downgrade attacks
        signable = f"{anchor.content_hash}:{anchor.signature_type}"
        expected = hmac_mod.new(key, signable.encode(), hashlib.sha256).hexdigest()
        assert anchor.signature == expected

    def test_default_verify_uses_hmac(self):
        """verify_signature() without asymmetric flag must use HMAC-SHA256."""
        key = b"secret-key-for-hmac"
        anchor = _make_sealed_anchor()
        anchor.sign(key, "authority-hmac")

        assert anchor.verify_signature(key) is True

    def test_hmac_verify_fails_with_wrong_key(self):
        """HMAC verify must fail with a different key."""
        key = b"correct-key"
        wrong_key = b"wrong-key"
        anchor = _make_sealed_anchor()
        anchor.sign(key, "authority-hmac")

        assert anchor.verify_signature(wrong_key) is False

    def test_signature_type_tracks_hmac(self):
        """When signed with HMAC, signature_type must be 'hmac-sha256'."""
        key = b"secret-key"
        anchor = _make_sealed_anchor()
        anchor.sign(key, "authority-hmac")

        assert anchor.signature_type == "hmac-sha256"

    def test_sign_without_asymmetric_refuses_unsealed(self):
        """Default HMAC sign must still refuse unsealed anchors."""
        key = b"secret-key"
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-a",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        with pytest.raises(ValueError, match="unsealed"):
            anchor.sign(key, "authority-hmac")


# ===========================================================================
# Tier 1 (Unit) -- Cross-verification rejection
# ===========================================================================


class TestCrossVerificationRejection:
    """Verifying HMAC sigs with Ed25519 mode (and vice versa) must fail."""

    def test_hmac_sig_fails_asymmetric_verify(self):
        """An HMAC-signed anchor must fail when verified with asymmetric=True."""
        hmac_key = b"secret-key"
        _priv, pub = _make_ed25519_keypair()

        anchor = _make_sealed_anchor()
        anchor.sign(hmac_key, "authority-hmac")  # HMAC signing

        # Trying to verify as Ed25519 must fail
        assert anchor.verify_signature(pub, asymmetric=True) is False

    def test_ed25519_sig_fails_hmac_verify(self):
        """An Ed25519-signed anchor must fail when verified without asymmetric=True."""
        priv, _pub = _make_ed25519_keypair()
        hmac_key = b"secret-key"

        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-ed25519", asymmetric=True)  # Ed25519 signing

        # Trying to verify as HMAC must fail
        assert anchor.verify_signature(hmac_key) is False


# ===========================================================================
# Tier 1 (Unit) -- AuditChain with Ed25519
# ===========================================================================


class TestAuditChainAsymmetricSigning:
    """AuditChain.append must support asymmetric signing."""

    def test_append_with_asymmetric_signing(self):
        """append(asymmetric=True) must produce Ed25519-signed anchors."""
        priv, pub = _make_ed25519_keypair()
        chain = AuditChain(chain_id="chain-1")

        anchor = chain.append(
            agent_id="agent-a",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
            signing_key=priv,
            signer_id="authority-1",
            asymmetric=True,
        )

        assert anchor.is_signed
        assert anchor.signature_type == "ed25519"
        assert anchor.verify_signature(pub, asymmetric=True) is True

    def test_append_default_still_uses_hmac(self):
        """append() without asymmetric must still produce HMAC-signed anchors."""
        hmac_key = b"secret-key"
        chain = AuditChain(chain_id="chain-2")

        anchor = chain.append(
            agent_id="agent-a",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
            signing_key=hmac_key,
            signer_id="authority-hmac",
        )

        assert anchor.is_signed
        assert anchor.signature_type == "hmac-sha256"
        assert anchor.verify_signature(hmac_key) is True

    def test_mixed_chain_integrity(self):
        """A chain with both HMAC and Ed25519 anchors must pass integrity checks."""
        hmac_key = b"secret-key"
        priv, pub = _make_ed25519_keypair()
        chain = AuditChain(chain_id="chain-mixed")

        # Anchor 0: HMAC
        chain.append(
            agent_id="agent-a",
            action="action-1",
            verification_level=VerificationLevel.AUTO_APPROVED,
            signing_key=hmac_key,
            signer_id="authority-hmac",
        )

        # Anchor 1: Ed25519
        chain.append(
            agent_id="agent-a",
            action="action-2",
            verification_level=VerificationLevel.FLAGGED,
            signing_key=priv,
            signer_id="authority-ed25519",
            asymmetric=True,
        )

        # Anchor 2: HMAC again
        chain.append(
            agent_id="agent-b",
            action="action-3",
            verification_level=VerificationLevel.AUTO_APPROVED,
            signing_key=hmac_key,
            signer_id="authority-hmac",
        )

        valid, errors = chain.verify_chain_integrity()
        assert valid is True, f"Chain integrity failed: {errors}"
        assert len(chain.anchors) == 3

    def test_chain_append_unsigned_still_works(self):
        """append() without signing_key must still produce unsigned anchors."""
        chain = AuditChain(chain_id="chain-unsigned")

        anchor = chain.append(
            agent_id="agent-a",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        assert anchor.is_signed is False
        assert anchor.signature is None
        assert anchor.signature_type is None


# ===========================================================================
# Tier 1 (Unit) -- Serialization round-trip
# ===========================================================================


class TestSignatureTypeSerialization:
    """signature_type must survive Pydantic model_dump / model round-trip."""

    def test_ed25519_signature_type_in_model_dump(self):
        """model_dump must include signature_type='ed25519' for Ed25519-signed anchors."""
        priv, _pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        data = anchor.model_dump(mode="json")
        assert data["signature_type"] == "ed25519"

    def test_hmac_signature_type_in_model_dump(self):
        """model_dump must include signature_type='hmac-sha256' for HMAC-signed anchors."""
        key = b"secret-key"
        anchor = _make_sealed_anchor()
        anchor.sign(key, "authority-hmac")

        data = anchor.model_dump(mode="json")
        assert data["signature_type"] == "hmac-sha256"

    def test_unsigned_signature_type_in_model_dump(self):
        """model_dump must include signature_type=None for unsigned anchors."""
        anchor = _make_sealed_anchor()

        data = anchor.model_dump(mode="json")
        assert data["signature_type"] is None


# ===========================================================================
# Tier 1 (Unit) -- RT4-H11: Signature type downgrade prevention
# ===========================================================================


class TestSignatureTypeDowngradePrevention:
    """RT4-H11: signature_type must be included in signed payload to prevent downgrade."""

    def test_downgrade_ed25519_to_hmac_detected(self):
        """Changing signature_type from ed25519 to hmac-sha256 after signing must fail verification."""
        priv, pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        assert anchor.signature_type == "ed25519"

        # Attacker changes signature_type to hmac-sha256
        anchor.signature_type = "hmac-sha256"

        # Verification must fail because signature_type is part of signed content
        assert anchor.verify_signature(pub, asymmetric=True) is False

    def test_downgrade_hmac_to_ed25519_detected(self):
        """Changing signature_type from hmac-sha256 to ed25519 after signing must fail verification."""
        hmac_key = b"secret-key"
        anchor = _make_sealed_anchor()
        anchor.sign(hmac_key, "authority-hmac")

        assert anchor.signature_type == "hmac-sha256"

        # Attacker changes signature_type
        anchor.signature_type = "ed25519"

        # Verification with original key and mode must fail
        assert anchor.verify_signature(hmac_key) is False

    def test_signature_type_set_before_signing(self):
        """signature_type must be set BEFORE the signature is computed, not after."""
        priv, pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        # If signature_type is included in the signable content, it was set before signing.
        # Verify this by confirming that the signable content includes the type.
        signable = f"{anchor.content_hash}:{anchor.signature_type}"
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        ed_pub = Ed25519PublicKey.from_public_bytes(pub)
        sig_bytes = bytes.fromhex(anchor.signature)
        # This should NOT raise — proving the signature covers content_hash:signature_type
        ed_pub.verify(sig_bytes, signable.encode("utf-8"))


# ===========================================================================
# Tier 1 (Unit) -- RT4-M12: Auto-detect signature type in verify_signature
# ===========================================================================


class TestAutoDetectSignatureType:
    """RT4-M12: verify_signature should auto-detect from stored signature_type."""

    def test_auto_detect_hmac(self):
        """verify_signature without asymmetric param should auto-detect HMAC and pass."""
        key = b"secret-key-for-hmac"
        anchor = _make_sealed_anchor()
        anchor.sign(key, "authority-hmac")

        # Call verify_signature WITHOUT specifying asymmetric — should auto-detect
        assert anchor.verify_signature(key) is True

    def test_auto_detect_ed25519(self):
        """verify_signature without asymmetric param should auto-detect Ed25519 and pass."""
        priv, pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        # Call verify_signature WITHOUT specifying asymmetric — should auto-detect
        assert anchor.verify_signature(pub) is True

    def test_auto_detect_ed25519_wrong_key_fails(self):
        """Auto-detected Ed25519 verification fails with wrong key."""
        priv, _pub = _make_ed25519_keypair()
        _other_priv, other_pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        # Wrong key with auto-detection should fail
        assert anchor.verify_signature(other_pub) is False

    def test_explicit_asymmetric_overrides_auto_detect(self):
        """Explicit asymmetric=True/False should override auto-detection."""
        priv, pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        # Explicit asymmetric=True should work
        assert anchor.verify_signature(pub, asymmetric=True) is True

        # Explicit asymmetric=False with HMAC key should fail (wrong mode)
        hmac_key = b"some-key"
        assert anchor.verify_signature(hmac_key, asymmetric=False) is False


# ===========================================================================
# Tier 1 (Unit) -- RT4-M10: Key versioning for rotation support
# ===========================================================================


class TestKeyVersioning:
    """RT4-M10: Anchors should support key_version for key rotation."""

    def test_key_version_stored_on_sign(self):
        """sign() with key_version should store it on the anchor."""
        priv, _pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True, key_version="v2")

        assert anchor.key_version == "v2"

    def test_key_version_defaults_to_none(self):
        """sign() without key_version should leave it as None."""
        priv, _pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True)

        assert anchor.key_version is None

    def test_different_key_versions_verify_independently(self):
        """Anchors signed with different key versions can each be verified."""
        priv_v1, pub_v1 = _make_ed25519_keypair()
        priv_v2, pub_v2 = _make_ed25519_keypair()

        anchor_v1 = _make_sealed_anchor(anchor_id="test-v1")
        anchor_v1.sign(priv_v1, "authority-1", asymmetric=True, key_version="v1")

        anchor_v2 = _make_sealed_anchor(anchor_id="test-v2")
        anchor_v2.sign(priv_v2, "authority-1", asymmetric=True, key_version="v2")

        assert anchor_v1.verify_signature(pub_v1, asymmetric=True) is True
        assert anchor_v2.verify_signature(pub_v2, asymmetric=True) is True

        # Cross-verification fails (different keys)
        assert anchor_v1.verify_signature(pub_v2, asymmetric=True) is False
        assert anchor_v2.verify_signature(pub_v1, asymmetric=True) is False

    def test_key_version_in_chain_append(self):
        """AuditChain.append should pass through key_version."""
        priv, _pub = _make_ed25519_keypair()
        chain = AuditChain(chain_id="chain-keyed")

        anchor = chain.append(
            agent_id="agent-a",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
            signing_key=priv,
            signer_id="authority-1",
            asymmetric=True,
            key_version="v3",
        )

        assert anchor.key_version == "v3"

    def test_key_version_in_model_dump(self):
        """key_version must survive model_dump serialization."""
        priv, _pub = _make_ed25519_keypair()
        anchor = _make_sealed_anchor()
        anchor.sign(priv, "authority-1", asymmetric=True, key_version="v2")

        data = anchor.model_dump(mode="json")
        assert data["key_version"] == "v2"


# ===========================================================================
# Tier 1 (Unit) -- RT4-H8: Audit chain checkpointing
# ===========================================================================


class TestAuditChainCheckpointing:
    """RT4-H8: AuditChain should support checkpoint/restore for recovery."""

    def test_checkpoint_empty_chain(self):
        """Checkpoint of empty chain should have length 0 and no latest hash."""
        chain = AuditChain(chain_id="chain-empty")
        cp = chain.checkpoint()

        assert cp["chain_id"] == "chain-empty"
        assert cp["length"] == 0
        assert cp["latest_hash"] is None
        assert cp["latest_sequence"] == -1
        assert "timestamp" in cp

    def test_checkpoint_captures_state(self):
        """Checkpoint should capture chain_id, length, latest hash, and latest sequence."""
        chain = AuditChain(chain_id="chain-cp")
        anchor = chain.append(
            agent_id="agent-a",
            action="action-1",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        cp = chain.checkpoint()

        assert cp["chain_id"] == "chain-cp"
        assert cp["length"] == 1
        assert cp["latest_hash"] == anchor.content_hash
        assert cp["latest_sequence"] == 0
        assert "timestamp" in cp

    def test_verify_against_checkpoint_valid(self):
        """Chain that has grown since checkpoint should still verify."""
        chain = AuditChain(chain_id="chain-verify")
        chain.append(
            agent_id="agent-a",
            action="action-1",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        cp = chain.checkpoint()

        # Add more anchors after checkpoint
        chain.append(
            agent_id="agent-a",
            action="action-2",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        assert chain.verify_against_checkpoint(cp) is True

    def test_verify_against_checkpoint_unchanged(self):
        """Chain at same state as checkpoint should verify."""
        chain = AuditChain(chain_id="chain-same")
        chain.append(
            agent_id="agent-a",
            action="action-1",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        cp = chain.checkpoint()

        assert chain.verify_against_checkpoint(cp) is True

    def test_verify_against_checkpoint_tampered(self):
        """Chain with tampered anchor at checkpoint position should fail verification."""
        chain = AuditChain(chain_id="chain-tamper")
        chain.append(
            agent_id="agent-a",
            action="action-1",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        cp = chain.checkpoint()

        # Tamper with the anchor at the checkpoint position
        chain.anchors[0].content_hash = "deadbeef" * 8

        assert chain.verify_against_checkpoint(cp) is False

    def test_verify_against_checkpoint_shortened(self):
        """Chain shorter than checkpoint should fail verification."""
        chain = AuditChain(chain_id="chain-short")
        chain.append(
            agent_id="agent-a",
            action="action-1",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        chain.append(
            agent_id="agent-a",
            action="action-2",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        cp = chain.checkpoint()

        # Remove an anchor (simulating truncation)
        chain.anchors.pop()

        assert chain.verify_against_checkpoint(cp) is False

    def test_verify_against_checkpoint_wrong_chain_id(self):
        """Checkpoint from a different chain should fail verification."""
        chain = AuditChain(chain_id="chain-a")
        chain.append(
            agent_id="agent-a",
            action="action-1",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        other_chain = AuditChain(chain_id="chain-b")
        other_chain.append(
            agent_id="agent-a",
            action="action-1",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        cp = other_chain.checkpoint()

        assert chain.verify_against_checkpoint(cp) is False
