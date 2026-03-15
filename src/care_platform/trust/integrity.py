# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Trust chain integrity — hash-chain verification for trust records.

M17-1701: Provides cryptographic hash chaining for tamper detection across
trust chain records (genesis, delegation). Each record's hash includes
the previous record's hash, creating a tamper-evident chain.

Components:
- TrustRecordHash: Deterministic SHA-256 hash computation for trust records.
- TrustChainIntegrity: Builds and verifies hash-linked chains of trust records.
- IntegrityCheckResult / IntegrityViolation: Structured verification results.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class IntegrityViolation(BaseModel):
    """A single integrity violation found during chain verification."""

    record_index: int = Field(description="Index of the record with the violation")
    expected_hash: str = Field(description="Hash that was expected (stored)")
    actual_hash: str = Field(description="Hash that was recomputed from the data")
    description: str = Field(description="Human-readable description of the violation")


class IntegrityCheckResult(BaseModel):
    """Result of verifying a trust chain's integrity."""

    is_valid: bool = Field(description="Whether the chain is intact")
    violations: list[IntegrityViolation] = Field(
        default_factory=list,
        description="List of violations found (empty if valid)",
    )
    records_checked: int = Field(
        default=0,
        description="Number of records that were checked",
    )


# ---------------------------------------------------------------------------
# TrustRecordHash — deterministic hashing
# ---------------------------------------------------------------------------


class TrustRecordHash:
    """Computes deterministic SHA-256 hashes for trust records.

    The hash is computed over:
    1. The canonical JSON representation of the record data.
    2. (Optionally) The hash of the previous record in the chain.

    This ensures that any modification to any record in the chain
    will be detected during verification.
    """

    @staticmethod
    def compute(data: dict[str, Any], previous_hash: str | None = None) -> str:
        """Compute a SHA-256 hash for a trust record.

        Args:
            data: The record data to hash.
            previous_hash: Hash of the previous record in the chain. When
                provided, it is included in the hash input to chain records.

        Returns:
            The hex-encoded SHA-256 digest.
        """
        # Canonical JSON: sorted keys, no whitespace, deterministic output
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)

        hasher = hashlib.sha256()
        if previous_hash is not None:
            hasher.update(previous_hash.encode("utf-8"))
        hasher.update(canonical.encode("utf-8"))

        return hasher.hexdigest()


# ---------------------------------------------------------------------------
# _ChainRecord — internal record wrapper
# ---------------------------------------------------------------------------


class _ChainRecord:
    """Internal wrapper holding a record's data and computed hash."""

    __slots__ = ("data", "record_hash", "previous_hash")

    def __init__(
        self,
        data: dict[str, Any],
        record_hash: str,
        previous_hash: str | None,
    ) -> None:
        self.data = data
        self.record_hash = record_hash
        self.previous_hash = previous_hash


# ---------------------------------------------------------------------------
# TrustChainIntegrity — chain builder and verifier
# ---------------------------------------------------------------------------


class TrustChainIntegrity:
    """Builds and verifies hash-linked chains of trust records.

    Usage:
        chain = TrustChainIntegrity()
        chain.append_record(genesis_data)
        chain.append_record(delegation_data)
        result = chain.verify()
        assert result.is_valid
    """

    def __init__(self) -> None:
        self._records: list[_ChainRecord] = []

    @property
    def length(self) -> int:
        """Number of records in the chain."""
        return len(self._records)

    @property
    def head_hash(self) -> str:
        """Hash of the most recently appended record.

        Raises:
            ValueError: If the chain is empty.
        """
        if not self._records:
            raise ValueError(
                "Cannot get head_hash of an empty chain. "
                "Append at least one record before accessing head_hash."
            )
        return self._records[-1].record_hash

    def get_hash(self, index: int) -> str:
        """Get the hash of a record at a specific index.

        Args:
            index: Zero-based index into the chain.

        Returns:
            The hex-encoded hash at that position.

        Raises:
            IndexError: If the index is out of range.
        """
        if index < 0 or index >= len(self._records):
            raise IndexError(
                f"Record index {index} is out of range "
                f"(chain length is {len(self._records)})"
            )
        return self._records[index].record_hash

    def append_record(self, data: dict[str, Any]) -> str:
        """Append a trust record to the chain.

        The record's hash is computed from its data and the previous
        record's hash (if any), creating a tamper-evident link.

        Args:
            data: The trust record data (genesis, delegation, etc.).

        Returns:
            The computed hash for the appended record.
        """
        previous_hash = self._records[-1].record_hash if self._records else None
        record_hash = TrustRecordHash.compute(data, previous_hash=previous_hash)

        record = _ChainRecord(
            data=data,
            record_hash=record_hash,
            previous_hash=previous_hash,
        )
        self._records.append(record)

        logger.debug(
            "Appended record %d to integrity chain (hash=%s, previous=%s)",
            len(self._records) - 1,
            record_hash[:12],
            previous_hash[:12] if previous_hash else "None",
        )

        return record_hash

    def verify(self) -> IntegrityCheckResult:
        """Verify the integrity of the entire chain.

        Recomputes every record's hash from its data and the previous
        record's hash, then compares against the stored hash. Any
        mismatch indicates tampering.

        Returns:
            IntegrityCheckResult with is_valid and any violations.
        """
        if not self._records:
            return IntegrityCheckResult(
                is_valid=True,
                violations=[],
                records_checked=0,
            )

        violations: list[IntegrityViolation] = []

        for i, record in enumerate(self._records):
            # Determine expected previous hash
            if i == 0:
                expected_previous = None
            else:
                expected_previous = self._records[i - 1].record_hash

            # Check that the previous_hash pointer is correct
            if record.previous_hash != expected_previous:
                violations.append(
                    IntegrityViolation(
                        record_index=i,
                        expected_hash=expected_previous or "(none)",
                        actual_hash=record.previous_hash or "(none)",
                        description=(
                            f"Record {i}: previous_hash pointer mismatch — "
                            f"expected '{expected_previous or '(none)'}', "
                            f"got '{record.previous_hash or '(none)'}'"
                        ),
                    )
                )

            # Recompute the hash from current data
            recomputed = TrustRecordHash.compute(
                record.data, previous_hash=expected_previous
            )

            if recomputed != record.record_hash:
                violations.append(
                    IntegrityViolation(
                        record_index=i,
                        expected_hash=record.record_hash,
                        actual_hash=recomputed,
                        description=(
                            f"Record {i}: content hash mismatch — "
                            f"stored '{record.record_hash[:16]}...', "
                            f"recomputed '{recomputed[:16]}...'"
                        ),
                    )
                )

        return IntegrityCheckResult(
            is_valid=len(violations) == 0,
            violations=violations,
            records_checked=len(self._records),
        )
