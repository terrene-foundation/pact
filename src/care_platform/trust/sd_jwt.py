# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""SD-JWT selective disclosure — confidentiality-based field disclosure.

Implements a minimal SD-JWT-like selective disclosure mechanism where fields
in trust chain elements (delegation records, attestations, etc.) are disclosed
or redacted based on the viewer's confidentiality clearance level.

Fields above the viewer's clearance are replaced with SHA-256 hashes of their
content (salted), allowing integrity verification without revealing the value.

No external SD-JWT libraries are used — this is a lightweight implementation
using existing crypto primitives (hashlib).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from pydantic import BaseModel, Field

from care_platform.config.schema import ConfidentialityLevel
from care_platform.trust.jcs import canonical_hash

# Numeric ordering for confidentiality comparisons.
_CONFIDENTIALITY_ORDER: dict[ConfidentialityLevel, int] = {
    ConfidentialityLevel.PUBLIC: 0,
    ConfidentialityLevel.RESTRICTED: 1,
    ConfidentialityLevel.CONFIDENTIAL: 2,
    ConfidentialityLevel.SECRET: 3,
    ConfidentialityLevel.TOP_SECRET: 4,
}


class SelectiveDisclosureJWT(BaseModel):
    """A selective disclosure JWT-like structure.

    Contains the original claims, per-field classifications, per-field salts,
    and an overall integrity hash. Fields can be disclosed or redacted based
    on the viewer's confidentiality clearance level.
    """

    issuer_claims: dict[str, Any] = Field(
        description="The full claims (all fields with their actual values)"
    )
    field_classifications: dict[str, ConfidentialityLevel] = Field(
        description="Per-field confidentiality classification"
    )
    field_salts: dict[str, str] = Field(description="Per-field random salt for hash computation")
    integrity_hash: str = Field(
        description="SHA-256 hash of the canonical claims for tamper detection"
    )

    def disclose(self, viewer_level: ConfidentialityLevel) -> dict[str, Any]:
        """Disclose fields based on the viewer's confidentiality clearance.

        Fields at or below the viewer's clearance level are returned as-is.
        Fields above the viewer's clearance are replaced with the SHA-256 hash
        of (salt + field_name + json_value), allowing integrity verification
        without revealing the actual value.

        Args:
            viewer_level: The viewer's confidentiality clearance level.

        Returns:
            A dict with disclosed fields as values and redacted fields as hashes.
        """
        viewer_order = _CONFIDENTIALITY_ORDER[viewer_level]
        result: dict[str, Any] = {}

        for field_name, value in self.issuer_claims.items():
            field_level = self.field_classifications.get(field_name, ConfidentialityLevel.PUBLIC)
            field_order = _CONFIDENTIALITY_ORDER[field_level]

            if field_order <= viewer_order:
                # Viewer has sufficient clearance — disclose
                result[field_name] = value
            else:
                # Viewer lacks clearance — return hash
                salt = self.field_salts.get(field_name, "")
                result[field_name] = _hash_field(salt, field_name, value)

        return result

    def verify_integrity(self) -> bool:
        """Verify the SD-JWT has not been tampered with.

        Recomputes the integrity hash from the current issuer_claims and
        compares it against the stored hash using timing-safe comparison.

        Returns:
            True if the claims are intact, False if tampered.
        """
        computed = _compute_integrity_hash(self.issuer_claims)
        return hmac.compare_digest(self.integrity_hash, computed)


class SDJWTBuilder:
    """Builder for creating SD-JWT instances from records with field classifications."""

    def create(
        self,
        record: dict[str, Any],
        field_classifications: dict[str, ConfidentialityLevel],
    ) -> SelectiveDisclosureJWT:
        """Create an SD-JWT from a record with per-field classifications.

        Args:
            record: The record data (e.g., a delegation record as a dict).
            field_classifications: Per-field confidentiality classification.
                Fields not listed default to PUBLIC.

        Returns:
            A SelectiveDisclosureJWT with salts and integrity hash computed.
        """
        # Generate a random salt for each field
        field_salts: dict[str, str] = {}
        for field_name in record:
            field_salts[field_name] = secrets.token_hex(16)

        integrity_hash = _compute_integrity_hash(record)

        return SelectiveDisclosureJWT(
            issuer_claims=dict(record),
            field_classifications=field_classifications,
            field_salts=field_salts,
            integrity_hash=integrity_hash,
        )


def _hash_field(salt: str, field_name: str, value: Any) -> str:
    """Compute SHA-256 hash of salt + field_name + JSON-serialized value.

    This hash replaces the actual value for viewers without sufficient clearance,
    allowing them to verify a field exists and matches without seeing its content.

    Args:
        salt: Random salt for this field.
        field_name: The field name.
        value: The field value (will be JSON-serialized).

    Returns:
        64-character hex SHA-256 digest.
    """
    value_str = json.dumps(value, sort_keys=True, default=str)
    content = f"{salt}:{field_name}:{value_str}"
    return hashlib.sha256(content.encode()).hexdigest()


def _compute_integrity_hash(claims: dict[str, Any]) -> str:
    """Compute SHA-256 integrity hash of the full claims dict using JCS (RFC 8785).

    Args:
        claims: The claims dict to hash.

    Returns:
        64-character hex SHA-256 digest.
    """
    return canonical_hash(claims)
