# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Bridge audit anchoring — dual-anchored audit records for Cross-Functional Bridge actions.

When an action crosses a bridge boundary, both the source and target
teams need audit records. This module creates paired audit anchors:
- Source-side anchor is the commit point (always created)
- Target-side anchor is best-effort (may fail without blocking)
- Cross-team reference hashes link the two anchors for correlation

The source-first pattern ensures that at least one side has a verifiable
record of the bridge action, even if the target team's audit system is
temporarily unavailable.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BridgeAuditAnchor(BaseModel):
    """Audit anchor for a Cross-Functional Bridge action.

    Contains hashes from both sides of the bridge for cross-team
    correlation. The source_anchor_hash is always present (commit point).
    The target_anchor_hash is best-effort — it may be None if the
    target team's audit system was unavailable.
    """

    anchor_id: str = Field(default_factory=lambda: f"ba-{uuid4().hex[:8]}")
    bridge_id: str
    source_team: str
    target_team: str
    action: str
    source_anchor_hash: str
    target_anchor_hash: str | None = None
    counterpart_anchor_hash: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


async def create_bridge_audit_pair(
    eatp_bridge: object,
    bridge_id: str,
    source_team: str,
    target_team: str,
    source_agent_id: str,
    target_agent_id: str,
    action: str,
    resource: str,
    result: str,
) -> BridgeAuditAnchor:
    """Create dual-anchored audit records for a bridge action.

    Source-side anchor is created first as the commit point.
    Target-side anchor is best-effort — failure does not block the action.
    Cross-team reference hashes are stored in both anchors' metadata.

    Args:
        eatp_bridge: An EATPBridge instance (typed as object to avoid
            circular imports — must have record_audit() method).
        bridge_id: The bridge through which the action occurred.
        source_team: Identifier of the source team.
        target_team: Identifier of the target team.
        source_agent_id: Agent performing the action on the source side.
        target_agent_id: Agent on the target side of the bridge.
        action: The bridge action being audited.
        resource: The resource being acted upon.
        result: Action result — "SUCCESS", "FAILURE", "DENIED", or "PARTIAL".

    Returns:
        BridgeAuditAnchor with source hash (always) and target hash (best-effort).
    """
    # Duck-type: eatp_bridge must have an async record_audit() method.
    # The old EATPBridge class (pact_platform.trust.eatp_bridge) is deleted;
    # callers now pass kailash.trust.TrustOperations or an equivalent.
    if not hasattr(eatp_bridge, "record_audit"):
        raise TypeError(
            f"eatp_bridge must have a record_audit() method, " f"got {type(eatp_bridge).__name__}"
        )

    bridge = eatp_bridge

    # Generate a cross-reference token that both anchors share
    cross_ref = f"bridge-xref-{uuid4().hex[:12]}"

    # --- Source-side anchor (commit point) ---
    source_anchor = await bridge.record_audit(
        agent_id=source_agent_id,
        action=f"bridge:{action}",
        resource=resource,
        result=result,
        reasoning=f"Bridge action via {bridge_id} (source-side anchor, xref={cross_ref})",
    )
    source_anchor_hash = _compute_anchor_hash(source_anchor.id, source_agent_id, action, bridge_id)

    # --- Target-side anchor (best-effort) ---
    target_anchor_hash: str | None = None
    try:
        target_anchor = await bridge.record_audit(
            agent_id=target_agent_id,
            action=f"bridge:{action}",
            resource=resource,
            result=result,
            reasoning=f"Bridge action via {bridge_id} (target-side anchor, xref={cross_ref})",
        )
        target_anchor_hash = _compute_anchor_hash(
            target_anchor.id, target_agent_id, action, bridge_id
        )
    except Exception as exc:
        logger.warning(
            "Target-side audit anchor failed for bridge %s (best-effort): %s",
            bridge_id,
            exc,
        )

    # Build the counterpart cross-reference hash
    counterpart_hash: str | None = None
    if source_anchor_hash and target_anchor_hash:
        counterpart_hash = _compute_counterpart_hash(source_anchor_hash, target_anchor_hash)

    bridge_anchor = BridgeAuditAnchor(
        bridge_id=bridge_id,
        source_team=source_team,
        target_team=target_team,
        action=action,
        source_anchor_hash=source_anchor_hash,
        target_anchor_hash=target_anchor_hash,
        counterpart_anchor_hash=counterpart_hash,
    )

    logger.info(
        "Bridge audit anchor created for %s: source_hash=%s, target_hash=%s, counterpart=%s",
        bridge_id,
        source_anchor_hash[:16] + "...",
        (target_anchor_hash[:16] + "...") if target_anchor_hash else "None",
        (counterpart_hash[:16] + "...") if counterpart_hash else "None",
    )

    return bridge_anchor


def _compute_anchor_hash(anchor_id: str, agent_id: str, action: str, bridge_id: str) -> str:
    """Compute a hash for an individual audit anchor.

    Args:
        anchor_id: The EATP audit anchor ID.
        agent_id: The agent that performed the action.
        action: The action performed.
        bridge_id: The bridge through which the action occurred.

    Returns:
        SHA-256 hex digest of the anchor content.
    """
    content = f"{anchor_id}:{agent_id}:{action}:{bridge_id}"
    return hashlib.sha256(content.encode()).hexdigest()


def _compute_counterpart_hash(source_hash: str, target_hash: str) -> str:
    """Compute a cross-reference hash linking source and target anchors.

    This hash proves that both anchors were created as part of the same
    bridge action. Either side can verify the counterpart by recomputing
    this hash from the other side's anchor hash.

    Args:
        source_hash: Hash of the source-side anchor.
        target_hash: Hash of the target-side anchor.

    Returns:
        SHA-256 hex digest of the combined hashes.
    """
    content = f"{source_hash}:{target_hash}"
    return hashlib.sha256(content.encode()).hexdigest()
