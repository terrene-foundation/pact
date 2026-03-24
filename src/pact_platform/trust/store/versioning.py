# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Constraint envelope version tracking and diffing.

Provides an append-only version history for constraint envelopes with
content-hash chaining and human-readable diffs between any two versions.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# The five CARE constraint dimensions whose changes we track.
_DIMENSIONS = ("financial", "operational", "temporal", "data_access", "communication")


class EnvelopeDiff(BaseModel):
    """Diff between two constraint envelope versions for a single field."""

    dimension: str
    field: str
    old_value: str
    new_value: str
    description: str = Field(description="Human-readable change summary")


class EnvelopeVersion(BaseModel):
    """A versioned snapshot of a constraint envelope."""

    version: int
    envelope_id: str
    data: dict
    content_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str
    reason: str = ""
    previous_version_hash: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_content_hash(data: dict) -> str:
    """Deterministic SHA-256 hash of *data* serialized as sorted JSON."""
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _diff_dimension(
    dimension: str,
    old_section: dict[str, Any] | None,
    new_section: dict[str, Any] | None,
) -> list[EnvelopeDiff]:
    """Compare two dimension sub-dicts and return per-field diffs."""
    old_section = old_section or {}
    new_section = new_section or {}

    all_keys = set(old_section.keys()) | set(new_section.keys())
    diffs: list[EnvelopeDiff] = []

    for key in sorted(all_keys):
        old_val = old_section.get(key)
        new_val = new_section.get(key)
        if old_val == new_val:
            continue

        old_str = str(old_val) if old_val is not None else "<unset>"
        new_str = str(new_val) if new_val is not None else "<unset>"
        description = (
            f"{dimension.replace('_', ' ').title()} {key} changed from {old_str} to {new_str}"
        )
        diffs.append(
            EnvelopeDiff(
                dimension=dimension,
                field=key,
                old_value=old_str,
                new_value=new_str,
                description=description,
            )
        )

    return diffs


# ---------------------------------------------------------------------------
# VersionTracker
# ---------------------------------------------------------------------------


class VersionTracker:
    """Tracks constraint envelope version history.

    Each call to :meth:`record_version` appends an immutable
    :class:`EnvelopeVersion` whose ``content_hash`` chains to the
    previous version, forming a tamper-evident version history.
    """

    def __init__(self) -> None:
        self._versions: dict[str, list[EnvelopeVersion]] = {}  # envelope_id -> versions

    def record_version(
        self,
        envelope_id: str,
        data: dict,
        created_by: str,
        reason: str = "",
    ) -> EnvelopeVersion:
        """Record a new version of a constraint envelope.

        Returns the newly created :class:`EnvelopeVersion`.
        """
        history = self._versions.setdefault(envelope_id, [])
        previous_hash: str | None = None
        if history:
            previous_hash = history[-1].content_hash

        version_number = len(history) + 1
        content_hash = _compute_content_hash(data)

        version = EnvelopeVersion(
            version=version_number,
            envelope_id=envelope_id,
            data=data,
            content_hash=content_hash,
            created_by=created_by,
            reason=reason,
            previous_version_hash=previous_hash,
        )
        history.append(version)
        logger.info(
            "Recorded version %d for envelope %s (hash=%s, by=%s)",
            version_number,
            envelope_id,
            content_hash[:12],
            created_by,
        )
        return version

    def get_history(self, envelope_id: str) -> list[EnvelopeVersion]:
        """Get full version history for an envelope, ordered by version number."""
        return list(self._versions.get(envelope_id, []))

    def get_current(self, envelope_id: str) -> EnvelopeVersion | None:
        """Get the current (latest) version, or None if no versions exist."""
        history = self._versions.get(envelope_id, [])
        if not history:
            return None
        return history[-1]

    def get_version(self, envelope_id: str, version: int) -> EnvelopeVersion | None:
        """Get a specific version by number, or None if not found."""
        history = self._versions.get(envelope_id, [])
        for v in history:
            if v.version == version:
                return v
        return None

    def compute_diff(
        self,
        envelope_id: str,
        v1: int,
        v2: int,
    ) -> list[EnvelopeDiff]:
        """Compute a diff between two versions of the same envelope.

        Raises :class:`KeyError` if the envelope or either version is not found.
        """
        if envelope_id not in self._versions:
            raise KeyError(f"No versions found for envelope '{envelope_id}'")

        ver1 = self.get_version(envelope_id, v1)
        ver2 = self.get_version(envelope_id, v2)

        if ver1 is None:
            raise KeyError(f"Version {v1} not found for envelope '{envelope_id}'")
        if ver2 is None:
            raise KeyError(f"Version {v2} not found for envelope '{envelope_id}'")

        diffs: list[EnvelopeDiff] = []
        for dim in _DIMENSIONS:
            old_section = ver1.data.get(dim)
            new_section = ver2.data.get(dim)
            if isinstance(old_section, dict) or isinstance(new_section, dict):
                diffs.extend(
                    _diff_dimension(
                        dim,
                        old_section if isinstance(old_section, dict) else None,
                        new_section if isinstance(new_section, dict) else None,
                    )
                )

        return diffs
