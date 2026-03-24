# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Data plane store — restricted interface for operational data operations.

The data plane handles:
- Audit anchors (tamper-evident action records)
- Posture changes (trust posture transitions)

The data plane CANNOT write:
- Genesis records (management plane responsibility)
- Delegation records (management plane responsibility)
- Constraint envelopes (management plane responsibility)
- Capability attestations (management plane responsibility)
- Revocations (management plane responsibility)

The data plane CAN read all tables for constraint evaluation and chain walking.
"""

from __future__ import annotations

import logging
from datetime import datetime

from pact_platform.trust.store.sqlite_store import SQLiteTrustStore
from pact_platform.trust.store_isolation.violations import PlaneViolationError

logger = logging.getLogger(__name__)


class DataPlaneStore:
    """Restricted store interface for data plane operations.

    Wraps a SQLiteTrustStore with write restrictions:
    - Allows writes to audit anchors and posture changes.
    - Blocks writes to genesis, delegation, envelope, attestation, and revocation tables.
    - Allows reads from all tables.
    """

    def __init__(self, store: SQLiteTrustStore) -> None:
        """Initialize with an underlying store.

        Args:
            store: The shared SQLiteTrustStore instance.
        """
        self._store = store

    # --- Data plane writes (ALLOWED) ---

    def store_audit_anchor(self, anchor_id: str, data: dict) -> None:
        """Store an audit anchor (append-only)."""
        self._store.store_audit_anchor(anchor_id, data)

    def store_posture_change(self, agent_id: str, data: dict) -> None:
        """Store a posture change record (append-only)."""
        self._store.store_posture_change(agent_id, data)

    # --- Management plane writes (BLOCKED) ---

    def store_genesis(self, authority_id: str, data: dict) -> None:
        """BLOCKED: Genesis records are management plane responsibility.

        Raises:
            PlaneViolationError: Always, as this operation is not permitted.
        """
        raise PlaneViolationError(
            "data plane",
            "store_genesis",
        )

    def store_delegation(self, delegation_id: str, data: dict) -> None:
        """BLOCKED: Delegation records are management plane responsibility.

        Raises:
            PlaneViolationError: Always, as this operation is not permitted.
        """
        raise PlaneViolationError(
            "data plane",
            "store_delegation",
        )

    def store_envelope(self, envelope_id: str, data: dict) -> None:
        """BLOCKED: Constraint envelopes are management plane responsibility.

        Raises:
            PlaneViolationError: Always, as this operation is not permitted.
        """
        raise PlaneViolationError(
            "data plane",
            "store_envelope",
        )

    def store_attestation(self, attestation_id: str, data: dict) -> None:
        """BLOCKED: Capability attestations are management plane responsibility.

        Raises:
            PlaneViolationError: Always, as this operation is not permitted.
        """
        raise PlaneViolationError(
            "data plane",
            "store_attestation",
        )

    def store_revocation(self, revocation_id: str, data: dict) -> None:
        """BLOCKED: Revocations are management plane responsibility.

        Raises:
            PlaneViolationError: Always, as this operation is not permitted.
        """
        raise PlaneViolationError(
            "data plane",
            "store_revocation",
        )

    # --- Reads (ALL ALLOWED for constraint evaluation and chain walking) ---

    def get_audit_anchor(self, anchor_id: str) -> dict | None:
        """Get an audit anchor."""
        return self._store.get_audit_anchor(anchor_id)

    def query_anchors(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        verification_level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit anchors with filtering."""
        return self._store.query_anchors(
            agent_id=agent_id,
            action=action,
            since=since,
            until=until,
            verification_level=verification_level,
            limit=limit,
        )

    def get_posture_history(self, agent_id: str) -> list[dict]:
        """Get posture change history for an agent."""
        return self._store.get_posture_history(agent_id)

    def get_genesis(self, authority_id: str) -> dict | None:
        """Read a genesis record (data plane can READ for chain verification)."""
        return self._store.get_genesis(authority_id)

    def get_delegation(self, delegation_id: str) -> dict | None:
        """Read a delegation record (data plane can READ for chain walking)."""
        return self._store.get_delegation(delegation_id)

    def get_delegations_for(self, agent_id: str) -> list[dict]:
        """Get all delegations for an agent (data plane can READ for chain walking)."""
        return self._store.get_delegations_for(agent_id)

    def get_envelope(self, envelope_id: str) -> dict | None:
        """Read a constraint envelope (data plane can READ for evaluation)."""
        return self._store.get_envelope(envelope_id)

    def list_envelopes(self, agent_id: str | None = None) -> list[dict]:
        """List constraint envelopes (data plane can READ for evaluation)."""
        return self._store.list_envelopes(agent_id)

    def get_attestation(self, attestation_id: str) -> dict | None:
        """Read an attestation (data plane can READ for verification)."""
        return self._store.get_attestation(attestation_id)

    def get_attestations_for(self, agent_id: str) -> list[dict]:
        """Get attestations for an agent (data plane can READ for verification)."""
        return self._store.get_attestations_for(agent_id)

    def get_revocations(self, agent_id: str | None = None) -> list[dict]:
        """Get revocations (data plane can READ for verification)."""
        return self._store.get_revocations(agent_id)

    def get_org_definition(self, org_id: str) -> dict | None:
        """Get an organization definition."""
        return self._store.get_org_definition(org_id)

    # --- Health ---

    def health_check(self) -> bool:
        """Check underlying store health."""
        return self._store.health_check()
