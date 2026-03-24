# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Management plane store — restricted interface for trust lifecycle operations.

The management plane handles:
- Genesis records (trust roots)
- Delegation records (trust extensions)
- Constraint envelopes (agent boundaries)
- Capability attestations
- Revocations

The management plane CANNOT write:
- Audit anchors (data plane responsibility)
- Posture changes (data plane responsibility)

The management plane CAN read all tables for oversight.
"""

from __future__ import annotations

import logging
from datetime import datetime

from pact_platform.trust.store.sqlite_store import SQLiteTrustStore
from pact_platform.trust.store_isolation.violations import PlaneViolationError

logger = logging.getLogger(__name__)


class ManagementPlaneStore:
    """Restricted store interface for management plane operations.

    Wraps a SQLiteTrustStore with write restrictions:
    - Allows writes to genesis, delegation, envelope, attestation, revocation tables.
    - Blocks writes to audit anchors and posture changes.
    - Allows reads from all tables.
    """

    def __init__(self, store: SQLiteTrustStore) -> None:
        """Initialize with an underlying store.

        Args:
            store: The shared SQLiteTrustStore instance.
        """
        self._store = store

    # --- Management writes (ALLOWED) ---

    def store_genesis(self, authority_id: str, data: dict) -> None:
        """Store a genesis record (trust root)."""
        self._store.store_genesis(authority_id, data)

    def store_delegation(self, delegation_id: str, data: dict) -> None:
        """Store a delegation record (trust extension)."""
        self._store.store_delegation(delegation_id, data)

    def store_envelope(self, envelope_id: str, data: dict) -> None:
        """Store a constraint envelope."""
        self._store.store_envelope(envelope_id, data)

    def store_attestation(self, attestation_id: str, data: dict) -> None:
        """Store a capability attestation."""
        self._store.store_attestation(attestation_id, data)

    def store_revocation(self, revocation_id: str, data: dict) -> None:
        """Store a revocation record."""
        self._store.store_revocation(revocation_id, data)

    def store_org_definition(self, org_id: str, data: dict) -> None:
        """Store an organization definition."""
        self._store.store_org_definition(org_id, data)

    # --- Data plane writes (BLOCKED) ---

    def store_audit_anchor(self, anchor_id: str, data: dict) -> None:
        """BLOCKED: Audit anchors are data plane responsibility.

        Raises:
            PlaneViolationError: Always, as this operation is not permitted.
        """
        raise PlaneViolationError(
            "management plane",
            "store_audit_anchor",
        )

    def store_posture_change(self, agent_id: str, data: dict) -> None:
        """BLOCKED: Posture changes are data plane responsibility.

        Raises:
            PlaneViolationError: Always, as this operation is not permitted.
        """
        raise PlaneViolationError(
            "management plane",
            "store_posture_change",
        )

    # --- Reads (ALL ALLOWED for oversight) ---

    def get_genesis(self, authority_id: str) -> dict | None:
        """Get a genesis record."""
        return self._store.get_genesis(authority_id)

    def get_delegation(self, delegation_id: str) -> dict | None:
        """Get a delegation record."""
        return self._store.get_delegation(delegation_id)

    def get_delegations_for(self, agent_id: str) -> list[dict]:
        """Get all delegations for an agent."""
        return self._store.get_delegations_for(agent_id)

    def get_envelope(self, envelope_id: str) -> dict | None:
        """Get a constraint envelope."""
        return self._store.get_envelope(envelope_id)

    def list_envelopes(self, agent_id: str | None = None) -> list[dict]:
        """List constraint envelopes."""
        return self._store.list_envelopes(agent_id)

    def get_attestation(self, attestation_id: str) -> dict | None:
        """Get a capability attestation."""
        return self._store.get_attestation(attestation_id)

    def get_attestations_for(self, agent_id: str) -> list[dict]:
        """Get all attestations for an agent."""
        return self._store.get_attestations_for(agent_id)

    def get_revocations(self, agent_id: str | None = None) -> list[dict]:
        """Get revocations."""
        return self._store.get_revocations(agent_id)

    def get_audit_anchor(self, anchor_id: str) -> dict | None:
        """Read an audit anchor (management can READ for oversight)."""
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
        """Query audit anchors (management can READ for oversight)."""
        return self._store.query_anchors(
            agent_id=agent_id,
            action=action,
            since=since,
            until=until,
            verification_level=verification_level,
            limit=limit,
        )

    def get_posture_history(self, agent_id: str) -> list[dict]:
        """Get posture history (management can READ for oversight)."""
        return self._store.get_posture_history(agent_id)

    def get_org_definition(self, org_id: str) -> dict | None:
        """Get an organization definition."""
        return self._store.get_org_definition(org_id)

    # --- Health ---

    def health_check(self) -> bool:
        """Check underlying store health."""
        return self._store.health_check()
