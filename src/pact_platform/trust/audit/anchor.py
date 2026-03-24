# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Audit anchor model — tamper-evident records of agent actions.

Each anchor contains a hash of its content plus the hash of the previous anchor,
forming an integrity chain that can be verified for tampering or gaps.

Supports two signing modes:
- HMAC-SHA256 (default, symmetric) — the original signing mechanism.
- Ed25519 (opt-in, asymmetric) — uses the same Ed25519 primitives as
  pact.trust.constraint.signing for consistency across the platform.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

from pact_platform.build.config.schema import VerificationLevel

logger = logging.getLogger(__name__)


class AuditAnchor(BaseModel):
    """A single tamper-evident record in the audit chain.

    EATP Element 5 — every agent action produces an audit anchor that
    records what happened, who did it, what the verification result was,
    and chains to the previous anchor for integrity verification.

    RT-13: Supports optional signing via sign() and verify_signature().
    """

    anchor_id: str = Field(description="Unique anchor identifier")
    sequence: int = Field(ge=0, description="Sequence number in the chain")
    previous_hash: str | None = Field(
        default=None, description="Hash of the previous anchor (None for genesis)"
    )
    agent_id: str
    action: str
    verification_level: VerificationLevel
    envelope_id: str | None = None
    result: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str = Field(default="", description="SHA-256 hash of this anchor's content")
    # RT-13: Signing fields
    signature: str | None = Field(default=None, description="Signature of content_hash")
    signer_id: str | None = Field(default=None, description="ID of the signing authority")
    signature_type: str | None = Field(
        default=None,
        description="Signing algorithm: 'hmac-sha256' or 'ed25519' (None when unsigned)",
    )
    # RT4-M10: Key version for rotation support
    key_version: str | None = Field(
        default=None,
        description="Version of the signing key (for key rotation)",
    )
    # M23/2310: EATP completeness fields
    delegation_chain_ref: str | None = Field(
        default=None,
        description="Reference to the delegation chain that authorized this action",
    )
    constraint_envelope_ref: str | None = Field(
        default=None,
        description="Reference to the constraint envelope that was evaluated",
    )
    verification_reason: str = Field(
        default="",
        description="Human-readable reason for the verification level determination",
    )
    agent_trust_posture: str | None = Field(
        default=None,
        description="Agent's trust posture at the time of this action (e.g., 'supervised')",
    )

    def compute_hash(self) -> str:
        """Compute the content hash for this anchor.

        RT2-24: Includes metadata in the hash to prevent post-seal tampering.
        M23/2310: Includes EATP completeness fields in the hash.
        """
        content = (
            f"{self.anchor_id}:{self.sequence}:{self.previous_hash or 'genesis'}:"
            f"{self.agent_id}:{self.action}:{self.verification_level.value}:"
            f"{self.envelope_id or ''}:{self.result}:{self.timestamp.isoformat()}"
        )
        # M23/2310: Include EATP fields in hash
        content += (
            f":{self.delegation_chain_ref or ''}"
            f":{self.constraint_envelope_ref or ''}"
            f":{self.verification_reason}"
            f":{self.agent_trust_posture or ''}"
        )
        # RT2-24: Include metadata in hash so it cannot be modified after sealing
        if self.metadata:
            meta_str = json.dumps(self.metadata, sort_keys=True, default=str)
            content += f":{meta_str}"
        return hashlib.sha256(content.encode()).hexdigest()

    def seal(self) -> None:
        """Seal this anchor by computing and storing its content hash."""
        self.content_hash = self.compute_hash()

    @property
    def is_sealed(self) -> bool:
        return bool(self.content_hash)

    def verify_integrity(self) -> bool:
        """Verify this anchor's hash matches its content."""
        if not self.is_sealed:
            return False
        return hmac.compare_digest(self.content_hash, self.compute_hash())

    def sign(
        self,
        signing_key: bytes,
        signer_id: str,
        *,
        asymmetric: bool = False,
        key_version: str | None = None,
    ) -> None:
        """Sign this anchor's content_hash.

        RT4-H11: The signature covers ``content_hash:signature_type`` so that
        the algorithm cannot be downgraded without invalidating the signature.

        Args:
            signing_key: Key bytes.  For HMAC this is the shared secret.
                For Ed25519 this is the 32-byte raw private key.
            signer_id: Identifier of the signing authority.
            asymmetric: When True, use Ed25519 instead of HMAC-SHA256.
            key_version: Optional key version identifier for rotation support (RT4-M10).

        Raises:
            ValueError: If the anchor is not sealed or has been tampered with.
        """
        if not self.is_sealed:
            raise ValueError("Cannot sign an unsealed anchor — call seal() first")
        # RT2-25: Verify integrity before signing to catch post-seal field tampering
        if not self.verify_integrity():
            raise ValueError(
                "Anchor content has been modified after sealing — "
                "integrity check failed, refusing to sign tampered anchor"
            )

        # RT4-H11: Include signature_type in the signed content to prevent
        # signature downgrade attacks (switching hmac-sha256 ↔ ed25519).
        if asymmetric:
            self.signature_type = "ed25519"
            signable = f"{self.content_hash}:{self.signature_type}"
            self.signature = _ed25519_sign(signing_key, signable)
        else:
            self.signature_type = "hmac-sha256"
            signable = f"{self.content_hash}:{self.signature_type}"
            self.signature = hmac.new(signing_key, signable.encode(), hashlib.sha256).hexdigest()
        self.signer_id = signer_id
        self.key_version = key_version

    def verify_signature(self, verification_key: bytes, *, asymmetric: bool | None = None) -> bool:
        """Verify the anchor's signature.

        RT4-M12: When *asymmetric* is ``None`` (the default), auto-detects
        the algorithm from :attr:`signature_type`.  Explicit ``True``/``False``
        overrides auto-detection.

        RT4-H11: Verification covers ``content_hash:signature_type`` — the same
        payload that :meth:`sign` uses.

        Args:
            verification_key: For HMAC this is the shared secret key.
                For Ed25519 this is the 32-byte raw public key.
            asymmetric: ``True`` for Ed25519, ``False`` for HMAC, or ``None``
                to auto-detect from ``self.signature_type``.

        Returns:
            True if the signature is valid, False otherwise.
        """
        if not self.signature or not self.is_sealed:
            return False

        # RT4-M12: Auto-detect from stored signature_type when not explicit
        if asymmetric is None:
            asymmetric = self.signature_type == "ed25519"

        signable = f"{self.content_hash}:{self.signature_type}"
        if asymmetric:
            return _ed25519_verify(verification_key, signable, self.signature)
        else:
            expected = hmac.new(verification_key, signable.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(self.signature, expected)

    @property
    def is_signed(self) -> bool:
        """Whether this anchor has been signed."""
        return self.signature is not None


class AuditChain(BaseModel):
    """An ordered chain of audit anchors with integrity verification.

    RT4-L4: This implementation uses a linear chain where each anchor links to
    the previous one via previous_hash, providing O(n) full-chain verification.
    A future enhancement could adopt a Merkle tree structure for O(log n)
    individual-anchor verification and efficient partial proofs, at the cost of
    additional implementation complexity.
    """

    chain_id: str
    anchors: list[AuditAnchor] = Field(default_factory=list)
    # RT7-08: Thread-safe append to prevent hash chain corruption from
    # concurrent appends reading the same sequence/previous_hash.
    _chain_lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    @property
    def length(self) -> int:
        return len(self.anchors)

    @property
    def latest(self) -> AuditAnchor | None:
        return self.anchors[-1] if self.anchors else None

    def append(
        self,
        agent_id: str,
        action: str,
        verification_level: VerificationLevel,
        *,
        envelope_id: str | None = None,
        result: str = "",
        metadata: dict[str, Any] | None = None,
        signing_key: bytes | None = None,
        signer_id: str | None = None,
        asymmetric: bool = False,
        key_version: str | None = None,
        delegation_chain_ref: str | None = None,
        constraint_envelope_ref: str | None = None,
        verification_reason: str = "",
        agent_trust_posture: str | None = None,
    ) -> AuditAnchor:
        """Create and append a new sealed (and optionally signed) anchor.

        Args:
            signing_key: If provided, the anchor is signed after sealing.
            signer_id: Required when signing_key is provided.
            asymmetric: When True and signing_key is provided, use Ed25519
                instead of HMAC-SHA256.
            key_version: Optional key version for rotation support (RT4-M10).
            delegation_chain_ref: M23/2310 — reference to the delegation chain.
            constraint_envelope_ref: M23/2310 — reference to the constraint envelope.
            verification_reason: M23/2310 — reason for the verification level.
            agent_trust_posture: M23/2310 — agent's trust posture.
        """
        with self._chain_lock:
            sequence = len(self.anchors)
            previous_hash = self.anchors[-1].content_hash if self.anchors else None

            anchor = AuditAnchor(
                anchor_id=f"{self.chain_id}-{sequence}",
                sequence=sequence,
                previous_hash=previous_hash,
                agent_id=agent_id,
                action=action,
                verification_level=verification_level,
                envelope_id=envelope_id,
                result=result,
                metadata=metadata or {},
                delegation_chain_ref=delegation_chain_ref,
                constraint_envelope_ref=constraint_envelope_ref,
                verification_reason=verification_reason,
                agent_trust_posture=agent_trust_posture,
            )
            anchor.seal()
            # RT-13: Auto-sign when key provided
            if signing_key is not None and signer_id is not None:
                anchor.sign(signing_key, signer_id, asymmetric=asymmetric, key_version=key_version)
            self.anchors.append(anchor)
            return anchor

    def checkpoint(self) -> dict[str, Any]:
        """Create a checkpoint of the current chain state for recovery (RT4-H8).

        Returns a dict capturing the chain_id, length, latest hash, latest
        sequence, and timestamp.  This can be used to detect gaps or
        corruption when comparing against a restored chain.
        """
        latest = self.latest
        return {
            "chain_id": self.chain_id,
            "length": self.length,
            "latest_hash": latest.content_hash if latest else None,
            "latest_sequence": latest.sequence if latest else -1,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def verify_against_checkpoint(self, checkpoint: dict[str, Any]) -> bool:
        """Verify the chain is consistent with a prior checkpoint (RT4-H8).

        Checks that:
        - The chain_id matches.
        - The chain has at least as many anchors as the checkpoint recorded.
        - The anchor at the checkpoint's latest_sequence has the expected hash.

        Returns:
            True if the chain is consistent with the checkpoint.
        """
        if checkpoint.get("chain_id") != self.chain_id:
            return False
        cp_length = checkpoint.get("length", 0)
        if self.length < cp_length:
            return False
        if cp_length == 0:
            return True
        cp_seq = checkpoint.get("latest_sequence", -1)
        if cp_seq < 0 or cp_seq >= self.length:
            return False
        return self.anchors[cp_seq].content_hash == checkpoint.get("latest_hash")

    def verify_chain_integrity(self) -> tuple[bool, list[str]]:
        """Walk the chain and verify every anchor's integrity.

        Returns (is_valid, list of error messages).
        """
        errors: list[str] = []

        for i, anchor in enumerate(self.anchors):
            # Check sequence
            if anchor.sequence != i:
                errors.append(
                    f"Anchor {i}: sequence mismatch (expected {i}, got {anchor.sequence})"
                )

            # Check seal
            if not anchor.verify_integrity():
                errors.append(f"Anchor {i}: content hash mismatch (tampered?)")

            # Check chain linkage
            if i == 0:
                if anchor.previous_hash is not None:
                    errors.append("Anchor 0: genesis anchor should have no previous_hash")
            else:
                expected_prev = self.anchors[i - 1].content_hash
                if anchor.previous_hash != expected_prev:
                    errors.append(
                        f"Anchor {i}: previous_hash doesn't match anchor {i - 1} (gap or reorder?)"
                    )

        return len(errors) == 0, errors

    def filter_by_agent(self, agent_id: str) -> list[AuditAnchor]:
        """Get all anchors for a specific agent."""
        return [a for a in self.anchors if a.agent_id == agent_id]

    def filter_by_level(self, level: VerificationLevel) -> list[AuditAnchor]:
        """Get all anchors at a specific verification level."""
        return [a for a in self.anchors if a.verification_level == level]

    def export(
        self,
        *,
        agent_id: str | None = None,
        since: datetime | None = None,
        redact_metadata: bool = False,
    ) -> list[dict[str, Any]]:
        """Export chain for external audit with optional filtering and redaction.

        Args:
            agent_id: Filter to this agent's anchors only.
            since: Filter to anchors at or after this timestamp.
            redact_metadata: When True, replace metadata values containing
                'reason' key with '[REDACTED]' and remove keys containing
                'token' or 'secret' for confidentiality-aware export.
        """
        anchors = self.anchors
        if agent_id:
            anchors = [a for a in anchors if a.agent_id == agent_id]
        if since:
            anchors = [a for a in anchors if a.timestamp >= since]

        exported = [a.model_dump(mode="json") for a in anchors]

        if redact_metadata:
            for item in exported:
                if "metadata" in item and isinstance(item["metadata"], dict):
                    item["metadata"] = _redact_metadata(item["metadata"])

        return exported


def _ed25519_sign(private_key_bytes: bytes, content_hash: str) -> str:
    """Sign a content hash with Ed25519, returning a hex-encoded signature.

    Reuses the same Ed25519 primitives as pact.trust.constraint.signing
    for consistency across the platform.

    Args:
        private_key_bytes: 32-byte raw Ed25519 private key.
        content_hash: The content hash string to sign.

    Returns:
        Hex-encoded Ed25519 signature string.

    Raises:
        ValueError: If the private key bytes are invalid.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    try:
        priv = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    except Exception as exc:
        msg = f"Invalid Ed25519 private key for audit anchor signing: {exc}"
        raise ValueError(msg) from exc

    try:
        signature_bytes = priv.sign(content_hash.encode("utf-8"))
        return signature_bytes.hex()
    finally:
        # RT11-L5 / RT13: Remove reference to private key object after use
        del priv


def _ed25519_verify(public_key_bytes: bytes, content_hash: str, signature_hex: str) -> bool:
    """Verify an Ed25519 signature on a content hash.

    Args:
        public_key_bytes: 32-byte raw Ed25519 public key.
        content_hash: The content hash string that was signed.
        signature_hex: Hex-encoded Ed25519 signature.

    Returns:
        True if the signature is valid, False otherwise.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        pub = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        signature_bytes = bytes.fromhex(signature_hex)
        pub.verify(signature_bytes, content_hash.encode("utf-8"))
        return True
    except Exception as exc:
        # RT13-H4: Log at warning level so operators see verification failures
        logger.warning(
            "Ed25519 signature verification failed for content_hash '%s...': %s",
            content_hash[:16],
            type(exc).__name__,
        )
        return False


def _redact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from metadata for confidentiality-aware export.

    - Keys containing 'reason' have their values replaced with '[REDACTED]'
    - Keys containing 'token', 'secret', 'private', 'credential', or 'password' are removed entirely
    - RT2-27: Recursively processes nested dicts
    - RT5-31: Traverses lists containing dicts
    """
    redacted: dict[str, Any] = {}
    for key, value in metadata.items():
        key_lower = key.lower()
        if any(
            s in key_lower
            for s in (
                "token",
                "secret",
                "private_key",
                "signing_key",
                "api_key",
                "encryption_key",
                "private",
                "credential",
                "password",
            )
        ):
            continue  # remove entirely
        if "reason" in key_lower:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            # RT2-27: Recurse into nested dicts
            redacted[key] = _redact_metadata(value)
        elif isinstance(value, list):
            # RT5-31: Traverse lists containing dicts
            redacted[key] = [
                _redact_metadata(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            redacted[key] = value
    return redacted
