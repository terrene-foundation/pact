# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Bridge Trust — wires Cross-Functional Bridges into the EATP trust layer.

Provides:
- BridgeDelegation: wraps EATP DelegationRecord with bridge context
- BridgeTrustRecord: bilateral trust establishment result
- BridgeTrustManager: thread-safe registry of bridge delegations with
  bilateral trust establishment (ESTABLISH + DELEGATE)

Bridge trust establishment creates a pair of linked DelegationRecords —
one per team — ensuring that both authorities sign the bridge agreement
before the bridge can carry data.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel, Field

from care_platform.build.workspace.bridge import BridgeType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class BridgeDelegation(BaseModel):
    """Wraps an EATP DelegationRecord with Cross-Functional Bridge context.

    Links a delegation to the bridge it supports, tracking which teams
    are connected and whether the delegation has been revoked.
    """

    delegation_id: str
    bridge_id: str
    source_team: str
    target_team: str
    bridge_type: BridgeType
    delegation_record: Any  # EATP DelegationRecord (dataclass with unresolved forward refs)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revoked: bool = False

    model_config = {"arbitrary_types_allowed": True}


class BridgeTrustRecord(BaseModel):
    """Result of bilateral trust establishment for a Cross-Functional Bridge.

    Contains the pair of BridgeDelegation records — one for the source
    team's authority and one for the target team's authority — that
    together form the trust foundation for a bridge.
    """

    bridge_id: str
    source_delegation: BridgeDelegation
    target_delegation: BridgeDelegation
    established_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# BridgeTrustManager
# ---------------------------------------------------------------------------


class BridgeTrustManager:
    """Thread-safe registry of bridge delegations with bilateral trust establishment.

    Manages the EATP trust layer for Cross-Functional Bridges:
    - Maintains a registry of BridgeDelegation records indexed by bridge_id
    - Establishes bilateral trust between source and target team authorities
    - Supports revocation of all delegations for a bridge
    - Provides lookup of delegations by bridge_id
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # bridge_id -> list of BridgeDelegation records
        self._delegations: dict[str, list[BridgeDelegation]] = {}

    def register_delegation(self, delegation: BridgeDelegation) -> None:
        """Register a BridgeDelegation in the registry.

        Args:
            delegation: The BridgeDelegation to register.
        """
        with self._lock:
            if delegation.bridge_id not in self._delegations:
                self._delegations[delegation.bridge_id] = []
            self._delegations[delegation.bridge_id].append(delegation)
        logger.info(
            "Registered bridge delegation %s for bridge %s (%s -> %s)",
            delegation.delegation_id,
            delegation.bridge_id,
            delegation.source_team,
            delegation.target_team,
        )

    def get_delegations(self, bridge_id: str) -> list[BridgeDelegation]:
        """Look up all delegations for a bridge.

        Args:
            bridge_id: The bridge whose delegations to retrieve.

        Returns:
            List of BridgeDelegation records for the bridge (empty if none found).
        """
        with self._lock:
            return list(self._delegations.get(bridge_id, []))

    def revoke_bridge_delegations(self, bridge_id: str, reason: str) -> list[BridgeDelegation]:
        """Revoke all delegations for a bridge.

        Marks each BridgeDelegation as revoked. Does not remove them from
        the registry — revoked records are preserved for audit.

        Args:
            bridge_id: The bridge whose delegations to revoke.
            reason: Human-readable reason for the revocation.

        Returns:
            List of BridgeDelegation records that were revoked.
        """
        revoked: list[BridgeDelegation] = []
        with self._lock:
            delegations = self._delegations.get(bridge_id, [])
            for delegation in delegations:
                if not delegation.revoked:
                    delegation.revoked = True
                    revoked.append(delegation)
        if revoked:
            logger.info(
                "Revoked %d delegation(s) for bridge %s — reason: %s",
                len(revoked),
                bridge_id,
                reason,
            )
        return revoked

    def all_delegations(self) -> list[BridgeDelegation]:
        """Return all registered delegations across all bridges.

        Returns:
            Flat list of all BridgeDelegation records.
        """
        with self._lock:
            return [d for delegations in self._delegations.values() for d in delegations]

    async def establish_bridge_trust(
        self,
        bridge_id: str,
        source_authority_id: str,
        target_authority_id: str,
        bridge_type: BridgeType,
        source_team: str,
        target_team: str,
        eatp_bridge: object,
        bridge_envelope: object | None = None,
    ) -> BridgeTrustRecord:
        """Establish bilateral trust for a Cross-Functional Bridge.

        Both teams' authorities sign the bridge agreement by creating a
        pair of linked DelegationRecords through the EATP bridge. The
        source authority delegates bridge-scoped access to the target team,
        and the target authority delegates bridge-scoped access back to
        the source team.

        Args:
            bridge_id: Unique identifier of the bridge.
            source_authority_id: EATP agent/authority ID for the source team.
            target_authority_id: EATP agent/authority ID for the target team.
            bridge_type: Type of Cross-Functional Bridge (STANDING, SCOPED, AD_HOC).
            source_team: Human-readable source team identifier.
            target_team: Human-readable target team identifier.
            eatp_bridge: An EATPBridge instance (typed as object to avoid
                circular imports — must have record_audit() method).
            bridge_envelope: Optional ConstraintEnvelopeConfig for the bridge.
                When provided, the EATP delegation records use these constraints
                instead of a minimal placeholder, ensuring the trust chain
                reflects the actual bridge constraints (RT13-09).

        Returns:
            BridgeTrustRecord containing both delegation records.

        Raises:
            RuntimeError: If the EATP bridge is not initialized or delegation fails.
        """
        from care_platform.trust.eatp_bridge import EATPBridge

        if not isinstance(eatp_bridge, EATPBridge):
            raise TypeError(
                f"eatp_bridge must be an EATPBridge instance, got {type(eatp_bridge).__name__}"
            )

        # Source authority creates delegation for the bridge (source -> target direction)
        source_delegation_record = await _create_bridge_delegation_record(
            eatp_bridge=eatp_bridge,
            delegator_id=source_authority_id,
            bridge_id=bridge_id,
            bridge_type=bridge_type,
            direction="source_to_target",
            envelope_override=bridge_envelope,
        )

        source_delegation = BridgeDelegation(
            delegation_id=f"bd-{uuid4().hex[:8]}",
            bridge_id=bridge_id,
            source_team=source_team,
            target_team=target_team,
            bridge_type=bridge_type,
            delegation_record=source_delegation_record,
        )

        # Target authority creates delegation for the bridge (target -> source direction)
        target_delegation_record = await _create_bridge_delegation_record(
            eatp_bridge=eatp_bridge,
            delegator_id=target_authority_id,
            bridge_id=bridge_id,
            bridge_type=bridge_type,
            direction="target_to_source",
            envelope_override=bridge_envelope,
        )

        target_delegation = BridgeDelegation(
            delegation_id=f"bd-{uuid4().hex[:8]}",
            bridge_id=bridge_id,
            source_team=source_team,
            target_team=target_team,
            bridge_type=bridge_type,
            delegation_record=target_delegation_record,
        )

        # RT12-013 / RT13: Register delegations via asyncio.to_thread to avoid
        # blocking the event loop with the threading.Lock inside register_delegation
        await asyncio.to_thread(self.register_delegation, source_delegation)
        await asyncio.to_thread(self.register_delegation, target_delegation)

        record = BridgeTrustRecord(
            bridge_id=bridge_id,
            source_delegation=source_delegation,
            target_delegation=target_delegation,
        )

        # RT13-06: Record dual audit anchors for bilateral trust establishment.
        # Both sides need a verifiable record per EATP Audit Anchor requirements.
        await eatp_bridge.record_audit(
            agent_id=source_authority_id,
            action="bridge_trust_established",
            resource=bridge_id,
            result="SUCCESS",
            reasoning=f"Bilateral trust established for {bridge_type.value} bridge "
            f"between {source_team} and {target_team} (source-side anchor)",
        )
        await eatp_bridge.record_audit(
            agent_id=target_authority_id,
            action="bridge_trust_established",
            resource=bridge_id,
            result="SUCCESS",
            reasoning=f"Bilateral trust established for {bridge_type.value} bridge "
            f"between {source_team} and {target_team} (target-side anchor)",
        )

        logger.info(
            "Bridge trust established for %s: %s (%s) <-> %s (%s)",
            bridge_id,
            source_team,
            source_authority_id,
            target_team,
            target_authority_id,
        )

        return record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_bridge_delegation_record(
    eatp_bridge: object,
    delegator_id: str,
    bridge_id: str,
    bridge_type: BridgeType,
    direction: str,
    envelope_override: object | None = None,
) -> Any:
    """Create a DelegationRecord for one side of a bridge trust agreement.

    Uses the EATP bridge's record_audit to create a verifiable record
    of the bridge delegation, then returns a synthetic DelegationRecord
    that represents the bridge trust commitment.

    Args:
        eatp_bridge: The EATPBridge instance.
        delegator_id: The authority creating the delegation.
        bridge_id: The bridge this delegation supports.
        bridge_type: Type of Cross-Functional Bridge.
        direction: "source_to_target" or "target_to_source".
        envelope_override: Optional ConstraintEnvelopeConfig to use instead
            of the default minimal envelope. When provided (RT13-09), the
            EATP delegation record uses these constraints, ensuring the trust
            chain reflects the actual bridge constraints.

    Returns:
        An EATP DelegationRecord for this side of the bridge.
    """
    from care_platform.build.config.schema import (
        AgentConfig,
        CommunicationConstraintConfig,
        ConstraintEnvelopeConfig,
        DataAccessConstraintConfig,
        FinancialConstraintConfig,
        OperationalConstraintConfig,
        TemporalConstraintConfig,
    )
    from care_platform.trust.eatp_bridge import EATPBridge

    bridge = cast(EATPBridge, eatp_bridge)

    # Create a bridge-scoped agent config representing the bridge endpoint
    bridge_agent_id = f"bridge:{bridge_id}:{direction}"
    agent_config = AgentConfig(
        id=bridge_agent_id,
        name=f"Bridge {bridge_id} ({direction})",
        role=f"Cross-Functional Bridge endpoint ({bridge_type.value})",
        constraint_envelope=f"envelope-bridge-{bridge_id}",
        capabilities=["bridge_read", "bridge_write", "bridge_message"],
    )

    # RT13-09: Use the provided bridge envelope if available, otherwise
    # fall back to a minimal placeholder envelope. The override ensures
    # that the EATP delegation record's constraints match the actual
    # bridge constraints computed by compute_bridge_envelope().
    if envelope_override is not None and isinstance(envelope_override, ConstraintEnvelopeConfig):
        envelope_config = ConstraintEnvelopeConfig(
            id=f"envelope-bridge-{bridge_id}-{direction}",
            description=f"Bridge {bridge_id} {direction} constraint envelope (from bridge envelope)",
            financial=envelope_override.financial,
            operational=envelope_override.operational,
            temporal=envelope_override.temporal,
            data_access=envelope_override.data_access,
            communication=envelope_override.communication,
        )
    else:
        # Fallback: minimal placeholder envelope for backward compatibility
        envelope_config = ConstraintEnvelopeConfig(
            id=f"envelope-bridge-{bridge_id}-{direction}",
            description=f"Bridge {bridge_id} {direction} constraint envelope",
            financial=FinancialConstraintConfig(max_spend_usd=0.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["bridge_read", "bridge_write", "bridge_message"],
            ),
            temporal=TemporalConstraintConfig(),
            data_access=DataAccessConstraintConfig(),
            communication=CommunicationConstraintConfig(internal_only=True),
        )

    delegation_record = await bridge.delegate(
        delegator_id=delegator_id,
        delegate_agent_config=agent_config,
        envelope_config=envelope_config,
    )

    return delegation_record
