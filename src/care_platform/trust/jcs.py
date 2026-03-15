# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""JCS canonical serialization (RFC 8785) — shared utility for deterministic hashing.

Provides a single canonical_hash() function that all content_hash implementations
should use for consistency. Based on the ``jcs`` library which implements
RFC 8785 JSON Canonicalization Scheme.
"""

from __future__ import annotations

import hashlib

import jcs as _jcs


def canonical_serialize(data: dict) -> bytes:
    """Serialize a dict to RFC 8785 canonical JSON bytes.

    Args:
        data: The dictionary to serialize.

    Returns:
        Canonical JSON bytes per RFC 8785.

    Raises:
        TypeError: If the data cannot be serialized.
    """
    return _jcs.canonicalize(data)


def canonical_hash(data: dict) -> str:
    """Compute SHA-256 hash of RFC 8785 canonical JSON.

    Args:
        data: The dictionary to hash.

    Returns:
        64-character hex SHA-256 digest of the canonical JSON bytes.

    Raises:
        TypeError: If the data cannot be serialized.
    """
    canonical_bytes = canonical_serialize(data)
    return hashlib.sha256(canonical_bytes).hexdigest()
