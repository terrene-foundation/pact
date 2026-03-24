# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Constraint envelope signing — Ed25519 cryptographic signing and verification
of constraint envelopes, ensuring agents cannot modify their assigned constraints.

Provides:
- SignedEnvelope: A constraint envelope with Ed25519 signature and tamper detection.
- EnvelopeVersionHistory: Version tracking for constraint envelope evolution.

Signatures cover all five CARE constraint dimensions (Financial, Operational,
Temporal, Data Access, Communication) plus envelope metadata, ensuring any
modification is detectable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, Field

from pact_platform.trust.constraint.envelope import ConstraintEnvelope
from pact_platform.trust._compat import canonical_serialize

logger = logging.getLogger(__name__)

# Default expiry for signed envelopes: 90 days
_DEFAULT_EXPIRY_DAYS = 90


def _serialize_for_signing(envelope: ConstraintEnvelope, signer_id: str, version: int) -> bytes:
    """Create a canonical byte representation of the signable content.

    Covers the full constraint envelope config (all five dimensions),
    plus the signer identity and version number. The config is serialized
    using RFC 8785 JCS (JSON Canonicalization Scheme) for deterministic output.

    M15/1504: Migrated from json.dumps(sort_keys=True) to JCS canonical_serialize.
    """
    # Serialize the full config (all five dimensions + id + description)
    config_data = json.loads(envelope.config.model_dump_json())
    # Include metadata that must also be protected
    signable = {
        "config": config_data,
        "signer_id": signer_id,
        "version": version,
    }
    return canonical_serialize(signable)


class SignedEnvelope(BaseModel):
    """A constraint envelope with cryptographic Ed25519 signature.

    Once signed, any modification to the envelope, signer identity, or
    version number is detectable via signature verification. Agents can
    read their signed envelopes but cannot modify them without detection.
    """

    envelope: ConstraintEnvelope
    signature: str = Field(description="Hex-encoded Ed25519 signature")
    signer_id: str = Field(description="Identifier of who signed this envelope")
    signed_at: datetime = Field(description="When the envelope was signed")
    version: int = Field(default=1, description="Envelope version number")
    previous_version_hash: str | None = Field(
        default=None, description="SHA-256 hash of the previous version for chain tracking"
    )
    canonical_version: str = Field(
        default="jcs-rfc8785",
        description="Canonical serialization format used for signing (M15/1504)",
    )

    def verify_signature(self, public_key: bytes) -> bool:
        """Verify the envelope has not been tampered with.

        Args:
            public_key: Raw Ed25519 public key bytes (32 bytes).

        Returns:
            True if the signature is valid for the current content, False otherwise.
        """
        try:
            pub = Ed25519PublicKey.from_public_bytes(public_key)
            payload = _serialize_for_signing(self.envelope, self.signer_id, self.version)
            signature_bytes = bytes.fromhex(self.signature)
            pub.verify(signature_bytes, payload)
            return True
        except (
            # Expected: cryptography raises InvalidSignature on mismatch
            Exception
        ) as exc:
            # RT13-H4: Log at warning level (not debug) so operators are
            # alerted to verification failures that may indicate tampering.
            logger.warning(
                "Signature verification failed for envelope '%s' signed by '%s': %s",
                self.envelope.id,
                self.signer_id,
                type(exc).__name__,
            )
            return False

    @classmethod
    def sign_envelope(
        cls,
        envelope: ConstraintEnvelope,
        signer_id: str,
        private_key: bytes,
    ) -> SignedEnvelope:
        """Sign a constraint envelope with Ed25519.

        Args:
            envelope: The constraint envelope to sign.
            signer_id: Identifier of the signer (e.g. authority, admin).
            private_key: Raw Ed25519 private key bytes (32 bytes).

        Returns:
            A SignedEnvelope with version 1 and the computed signature.

        Raises:
            ValueError: If the private key bytes are invalid.
        """
        version = 1
        payload = _serialize_for_signing(envelope, signer_id, version)

        try:
            priv = Ed25519PrivateKey.from_private_bytes(private_key)
        except Exception as exc:
            msg = f"Invalid Ed25519 private key: {exc}"
            raise ValueError(msg) from exc

        try:
            signature_bytes = priv.sign(payload)
            signature_hex = signature_bytes.hex()
        finally:
            # RT11-L5 / RT13: Remove reference to private key object after use
            del priv

        return cls(
            envelope=envelope,
            signature=signature_hex,
            signer_id=signer_id,
            signed_at=datetime.now(UTC),
            version=version,
            previous_version_hash=None,
        )

    def is_expired(self) -> bool:
        """Check if the signed envelope has expired.

        Default expiry is 90 days from the signed_at timestamp.

        Returns:
            True if the envelope was signed more than 90 days ago.
        """
        expiry = self.signed_at + timedelta(days=_DEFAULT_EXPIRY_DAYS)
        return datetime.now(UTC) > expiry

    def content_hash(self) -> str:
        """Compute SHA-256 hash of the signed envelope content.

        Used for version chain linking -- each new version references
        the content_hash of the previous version.
        """
        payload = _serialize_for_signing(self.envelope, self.signer_id, self.version)
        return hashlib.sha256(payload).hexdigest()


class EnvelopeVersionHistory(BaseModel):
    """Track constraint envelope versions for audit.

    Maintains an ordered list of signed envelope versions. Each new version
    is linked to the previous via its content hash, forming a verifiable
    version chain.
    """

    envelope_id: str = Field(description="The envelope being tracked")
    versions: list[SignedEnvelope] = Field(default_factory=list)

    def add_version(
        self,
        signed_envelope: SignedEnvelope,
        private_key: bytes | None = None,
        public_key: bytes | None = None,
    ) -> None:
        """Add a new version, linking it to the previous version.

        Creates a new SignedEnvelope copy with updated version number and
        previous_version_hash, then re-signs it to maintain signature validity.
        The original signed_envelope is NOT mutated.

        Args:
            signed_envelope: The signed envelope to add as a new version.
            private_key: Raw Ed25519 private key bytes (32 bytes) for re-signing.
                Required to maintain cryptographic integrity after version/hash update.
            public_key: Raw Ed25519 public key bytes (32 bytes) for verification.
                Used to verify the re-signed envelope is valid.

        Raises:
            ValueError: If private_key is not provided (required for re-signing).
        """
        if private_key is None:
            raise ValueError(
                "private_key is required to re-sign the envelope after updating "
                "version and previous_version_hash"
            )

        new_version_number = len(self.versions) + 1

        previous_hash: str | None = None
        if self.versions:
            previous = self.versions[-1]
            previous_hash = previous.content_hash()

        # Create the canonical payload for the new version
        payload = _serialize_for_signing(
            signed_envelope.envelope, signed_envelope.signer_id, new_version_number
        )

        # Sign the new version
        try:
            priv = Ed25519PrivateKey.from_private_bytes(private_key)
        except Exception as exc:
            msg = f"Invalid Ed25519 private key: {exc}"
            raise ValueError(msg) from exc

        try:
            new_signature = priv.sign(payload).hex()
        finally:
            # RT11-L5 / RT13: Remove reference to private key object after use
            del priv

        # Create a fresh SignedEnvelope (no mutation of the original)
        re_signed = SignedEnvelope(
            envelope=signed_envelope.envelope,
            signature=new_signature,
            signer_id=signed_envelope.signer_id,
            signed_at=datetime.now(UTC),
            version=new_version_number,
            previous_version_hash=previous_hash,
        )

        # Verify the re-signed envelope if public_key is provided
        if public_key is not None:
            if not re_signed.verify_signature(public_key):
                raise ValueError(
                    "Re-signed envelope failed signature verification — "
                    "private_key and public_key may not match"
                )

        self.versions.append(re_signed)

    def get_current(self) -> SignedEnvelope | None:
        """Get the current (latest) version.

        Returns:
            The most recently added SignedEnvelope, or None if no versions exist.
        """
        if not self.versions:
            return None
        return self.versions[-1]

    def get_version(self, version: int) -> SignedEnvelope | None:
        """Get a specific version by version number.

        Args:
            version: The 1-based version number to retrieve.

        Returns:
            The matching SignedEnvelope, or None if that version does not exist.
        """
        for v in self.versions:
            if v.version == version:
                return v
        return None
