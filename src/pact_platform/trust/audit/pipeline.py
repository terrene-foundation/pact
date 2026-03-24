# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Audit pipeline — creates audit anchors for every agent action.

Integrates the audit anchor chain with the verification gradient and
constraint envelope evaluation to produce a complete audit trail.

Flow: action -> verify -> execute -> audit anchor

Each agent gets its own independent audit chain, enabling per-agent
integrity verification while supporting cross-agent team timelines.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from pact_platform.build.config.schema import VerificationLevel
from pact_platform.trust.audit.anchor import AuditAnchor, AuditChain

logger = logging.getLogger(__name__)


class ActionRecord(BaseModel):
    """Record of an agent action with full audit context.

    Captures the action, how it was classified by the verification gradient,
    the envelope evaluation outcome, and the final result.
    """

    action_id: str = Field(default_factory=lambda: f"act-{uuid4().hex[:8]}")
    agent_id: str
    action: str
    resource: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verification_result: VerificationLevel = Field(
        description="How the action was classified by the verification gradient"
    )
    envelope_evaluation: str = Field(
        description="Constraint envelope verdict: ALLOWED, DENIED, or NEAR_BOUNDARY"
    )
    result: str = Field(description="Action outcome: SUCCESS, FAILURE, or DENIED")
    reasoning: str = ""


class AuditPipeline:
    """Pipeline that creates audit anchors for every agent action.

    Flow: action -> verify -> execute -> audit anchor

    Each agent gets its own independent audit chain. This enables:
    - Per-agent integrity verification
    - Per-agent audit export
    - Cross-agent team timelines
    """

    def __init__(self, chain: AuditChain | None = None) -> None:
        self.chain = chain or AuditChain(chain_id=f"pipeline-{uuid4().hex[:8]}")
        self._agent_chains: dict[str, AuditChain] = {}
        # RT2-15: Linked external chains (e.g., middleware audit chains)
        self._linked_chains: dict[str, AuditChain] = {}

    def record_action(
        self,
        agent_id: str,
        action: str,
        verification_level: VerificationLevel,
        result: str = "SUCCESS",
        resource: str = "",
        reasoning: str = "",
    ) -> AuditAnchor:
        """Record an action as an audit anchor in the agent's chain.

        Creates a sealed audit anchor in the per-agent chain, capturing
        the action, verification level, result, and any additional context.

        Args:
            agent_id: The agent performing the action.
            action: Description of the action taken.
            verification_level: How the action was classified.
            result: Outcome of the action (SUCCESS, FAILURE, DENIED).
            resource: The resource being acted upon (file path, endpoint, etc.).
            reasoning: Why this verification level was assigned.

        Returns:
            The sealed AuditAnchor that was appended to the agent's chain.
        """
        agent_chain = self.get_agent_chain(agent_id)

        metadata: dict[str, Any] = {}
        if resource:
            metadata["resource"] = resource
        if reasoning:
            metadata["reasoning"] = reasoning

        anchor = agent_chain.append(
            agent_id=agent_id,
            action=action,
            verification_level=verification_level,
            result=result,
            metadata=metadata,
        )

        logger.debug(
            "Recorded action '%s' for agent '%s' at verification level '%s' -> %s",
            action,
            agent_id,
            verification_level.value,
            result,
        )

        return anchor

    def link_chain(self, chain_id: str, chain: AuditChain) -> None:
        """RT2-15: Register an external audit chain for unified timeline access.

        Links an external chain (e.g., a middleware's AuditChain) so that
        export_for_review() and get_team_timeline() can include its anchors.
        This unifies the dual audit chains (per-agent pipeline chains and
        the middleware verification chain) without merging their storage.

        Args:
            chain_id: Identifier for the linked chain.
            chain: The AuditChain to link.
        """
        self._linked_chains[chain_id] = chain
        logger.info("Linked external audit chain: %s", chain_id)

    def get_linked_chain(self, chain_id: str) -> AuditChain | None:
        """Get a linked external chain by ID.

        Args:
            chain_id: Identifier of the linked chain.

        Returns:
            The linked AuditChain or None if not found.
        """
        return self._linked_chains.get(chain_id)

    def get_agent_chain(self, agent_id: str) -> AuditChain:
        """Get or create per-agent audit chain.

        Args:
            agent_id: The agent whose chain to retrieve.

        Returns:
            The AuditChain for the specified agent. Creates a new empty
            chain if the agent has no prior actions.
        """
        if agent_id not in self._agent_chains:
            self._agent_chains[agent_id] = AuditChain(chain_id=f"agent-{agent_id}")
        return self._agent_chains[agent_id]

    def verify_agent_integrity(self, agent_id: str) -> tuple[bool, list[str]]:
        """Verify integrity of an agent's audit chain.

        Walks the agent's chain and verifies every anchor's content hash
        and chain linkage. Detects tampering, gaps, and reordering.

        Args:
            agent_id: The agent whose chain to verify.

        Returns:
            A tuple of (is_valid, error_messages). If is_valid is True,
            error_messages will be empty.
        """
        if agent_id not in self._agent_chains:
            # No chain exists -- vacuously valid
            return True, []

        chain = self._agent_chains[agent_id]
        return chain.verify_chain_integrity()

    def export_for_review(
        self,
        *,
        agent_id: str | None = None,
        since: datetime | None = None,
        verification_levels: list[VerificationLevel] | None = None,
    ) -> list[dict[str, Any]]:
        """Export audit records for external review.

        Collects anchors from per-agent chains with optional filtering.
        Filters are combined with AND logic.

        Args:
            agent_id: Filter to a specific agent (None for all agents).
            since: Filter to anchors at or after this timestamp.
            verification_levels: Filter to specific verification levels.

        Returns:
            List of serialized anchor dictionaries suitable for external review.
        """
        # Determine which agent chains to include
        if agent_id is not None:
            if agent_id not in self._agent_chains:
                return []
            chains_to_export = {agent_id: self._agent_chains[agent_id]}
        else:
            chains_to_export = self._agent_chains

        results: list[dict[str, Any]] = []

        for chain in chains_to_export.values():
            for anchor in chain.anchors:
                # Apply since filter
                if since is not None and anchor.timestamp < since:
                    continue

                # Apply verification_levels filter
                if (
                    verification_levels is not None
                    and anchor.verification_level not in verification_levels
                ):
                    continue

                results.append(anchor.model_dump(mode="json"))

        # RT2-15: Include anchors from linked chains
        for linked_chain in self._linked_chains.values():
            for anchor in linked_chain.anchors:
                if since is not None and anchor.timestamp < since:
                    continue
                if (
                    verification_levels is not None
                    and anchor.verification_level not in verification_levels
                ):
                    continue
                if agent_id is not None and anchor.agent_id != agent_id:
                    continue
                results.append(anchor.model_dump(mode="json"))

        return results

    def get_team_timeline(self, agent_ids: list[str]) -> list[AuditAnchor]:
        """Get chronological timeline of all actions across specified agents.

        Collects all anchors from the requested agents' chains and sorts
        them by timestamp to produce a unified team timeline.

        Args:
            agent_ids: List of agent IDs to include in the timeline.

        Returns:
            List of AuditAnchors sorted by timestamp (ascending).
        """
        all_anchors: list[AuditAnchor] = []

        for aid in agent_ids:
            if aid in self._agent_chains:
                all_anchors.extend(self._agent_chains[aid].anchors)

        # RT2-15: Include matching anchors from linked chains
        agent_id_set = set(agent_ids)
        for linked_chain in self._linked_chains.values():
            for anchor in linked_chain.anchors:
                if anchor.agent_id in agent_id_set:
                    all_anchors.append(anchor)

        all_anchors.sort(key=lambda a: a.timestamp)
        return all_anchors
