# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Dual-binding signing — each reasoning trace is cryptographically bound
both to its parent record AND to the trust chain genesis.

This ensures that:
1. A trace cannot be moved between delegation records (parent binding)
2. A trace cannot be moved between trust chains (genesis binding)

Both bindings are SHA-256 hashes of (trace_hash + target_hash), ensuring
that any change to either the trace or the target invalidates the binding.
"""

from __future__ import annotations

import hashlib
import hmac

from pydantic import BaseModel, Field


class DualBinding(BaseModel):
    """Cryptographic dual binding for a reasoning trace.

    Binds a trace to both its parent record (delegation or audit anchor)
    and the trust chain genesis record. Both bindings must verify for
    the trace to be considered valid within the chain.
    """

    parent_binding: str = Field(
        description="SHA-256 hash binding trace to its parent record"
    )
    genesis_binding: str = Field(
        description="SHA-256 hash binding trace to the trust chain genesis"
    )

    @classmethod
    def create(
        cls,
        trace_hash: str,
        parent_record_hash: str,
        genesis_hash: str,
    ) -> DualBinding:
        """Create a dual binding for a reasoning trace.

        Args:
            trace_hash: The content hash of the reasoning trace.
            parent_record_hash: The content hash of the parent record
                (delegation record or audit anchor).
            genesis_hash: The content hash of the trust chain genesis record.

        Returns:
            A DualBinding with both parent and genesis bindings computed.
        """
        parent_binding = _compute_binding(trace_hash, parent_record_hash)
        genesis_binding = _compute_binding(trace_hash, genesis_hash)

        return cls(
            parent_binding=parent_binding,
            genesis_binding=genesis_binding,
        )

    def verify_parent_binding(
        self, trace_hash: str, parent_record_hash: str
    ) -> bool:
        """Verify that the trace is correctly bound to the parent record.

        Args:
            trace_hash: The content hash of the reasoning trace.
            parent_record_hash: The content hash of the parent record.

        Returns:
            True if the binding matches, False otherwise.
        """
        expected = _compute_binding(trace_hash, parent_record_hash)
        return hmac.compare_digest(self.parent_binding, expected)

    def verify_genesis_binding(
        self, trace_hash: str, genesis_hash: str
    ) -> bool:
        """Verify that the trace is correctly bound to the genesis record.

        Args:
            trace_hash: The content hash of the reasoning trace.
            genesis_hash: The content hash of the genesis record.

        Returns:
            True if the binding matches, False otherwise.
        """
        expected = _compute_binding(trace_hash, genesis_hash)
        return hmac.compare_digest(self.genesis_binding, expected)

    def combined_hash(self) -> str:
        """Compute a combined hash of both bindings.

        Useful for including the dual binding in higher-level integrity checks.

        Returns:
            64-character hex SHA-256 digest of both bindings combined.
        """
        content = f"{self.parent_binding}:{self.genesis_binding}"
        return hashlib.sha256(content.encode()).hexdigest()


def _compute_binding(trace_hash: str, target_hash: str) -> str:
    """Compute a SHA-256 binding hash between a trace and a target record.

    Args:
        trace_hash: The content hash of the reasoning trace.
        target_hash: The content hash of the target record.

    Returns:
        64-character hex SHA-256 digest of the binding.
    """
    content = f"{trace_hash}:{target_hash}"
    return hashlib.sha256(content.encode()).hexdigest()
