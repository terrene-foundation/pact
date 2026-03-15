# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Cascade revocation management — surgical and cascade trust revocation.

Implements two revocation strategies:
- Surgical: Revoke a single agent's trust. Siblings and children unaffected.
- Cascade: Revoke an agent and ALL downstream agents in the delegation tree.

Revocation is forward-looking only — revoked agents can always be re-delegated
with a new trust chain.

EATP SDK Alignment (M24):
    This module integrates with ``eatp.revocation.broadcaster.RevocationBroadcaster``
    to publish revocation events to the EATP event bus. CARE-specific behaviors
    (reparenting, cooling-off, credential integration, persistent storage,
    delegation tree fallback, dead-letter persistence) are wrapped in thin
    EATP-GAP adapters.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field

from eatp.revocation.broadcaster import (
    InMemoryRevocationBroadcaster,
    RevocationBroadcaster,
    RevocationEvent,
    RevocationType,
)

from care_platform.trust.credentials import CredentialManager

from care_platform.persistence.store import TrustStore

if TYPE_CHECKING:
    from care_platform.constraint.cache import VerificationCache
    from care_platform.trust.bridge_trust import BridgeTrustManager
    from care_platform.trust.eatp_bridge import EATPBridge
    from care_platform.workspace.bridge import BridgeManager

logger = logging.getLogger(__name__)


class RevocationRecord(BaseModel):
    """Record of a trust revocation.

    Captures who was revoked, why, by whom, and which downstream agents
    were affected (for cascade revocations).
    """

    revocation_id: str = Field(default_factory=lambda: f"rev-{uuid4().hex[:8]}")
    agent_id: str
    reason: str
    revoker_id: str
    revoked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revocation_type: str = Field(description="'surgical' or 'cascade'")
    affected_agents: list[str] = Field(
        default_factory=list,
        description="Downstream agents also revoked (for cascade)",
    )


class RevocationManager:
    """Manages surgical and cascade revocation of agent trust.

    Tracks a delegation tree (parent -> children) and uses it to determine
    which agents are downstream when a cascade revocation is triggered.
    Integrates with CredentialManager to revoke verification tokens.

    EATP SDK Integration:
        Uses ``eatp.revocation.broadcaster.RevocationBroadcaster`` to publish
        revocation events so that other EATP-aware components (e.g.,
        TrustRevocationList) can react in real time.

    EATP-GAP adapters:
        - R1: Reparenting on surgical revocation (RT9-07)
        - R2: Cooling-off period before re-delegation
        - R3: CredentialManager integration (key/token revocation)
        - R4: Persistent storage for revocation events
        - R5: Local delegation tree fallback when EATP bridge is unavailable
        - R6: Dead-letter persistence for failed broadcasts
    """

    def __init__(
        self,
        credential_manager: CredentialManager | None = None,
        eatp_bridge: EATPBridge | None = None,
        verification_cache: VerificationCache | None = None,
        bridge_manager: BridgeManager | None = None,
        min_cooling_off_hours: int = 0,
        trust_store: TrustStore | None = None,
        revocation_broadcaster: RevocationBroadcaster | None = None,
        bridge_trust_manager: BridgeTrustManager | None = None,
    ) -> None:
        # EATP-GAP: R3 — Credential integration
        # The EATP SDK's RevocationBroadcaster does not integrate with
        # credential/token revocation. CARE ties credential revocation
        # to agent revocation.
        self.credentials = credential_manager or CredentialManager()
        self._eatp_bridge = eatp_bridge
        # RT2-02: Cache reference for invalidation on revoke
        self._verification_cache = verification_cache
        # RT2-05: Bridge manager for revoking bridges on cascade
        self._bridge_manager = bridge_manager
        # M33-3302: Bridge trust manager for revoking bridge delegations
        self._bridge_trust_manager: BridgeTrustManager | None = bridge_trust_manager
        # EATP-GAP: R2 — Cooling-off period before re-delegation
        self._min_cooling_off_hours = min_cooling_off_hours
        # EATP-GAP: R4 — Persistent store for revocation records
        self._trust_store = trust_store

        # EATP SDK integration: RevocationBroadcaster for event publishing
        # Uses InMemoryRevocationBroadcaster if none provided.
        self._broadcaster: RevocationBroadcaster = (
            revocation_broadcaster or InMemoryRevocationBroadcaster()
        )

        self._revocation_log: list[RevocationRecord] = []
        # EATP-GAP: R5 — Local delegation tree as fallback when bridge unavailable
        self._delegation_tree: dict[str, list[str]] = {}  # parent -> [children]
        # RT6-07: Secondary index for O(1) is_revoked() lookups instead of
        # iterating through every revocation record on every call.
        self._revoked_ids: set[str] = set()
        # RT7-01: Thread safety for _revoked_ids, _revocation_log, _delegation_tree
        self._lock = threading.Lock()
        # EATP-GAP: R4 — Hydrate in-memory log from store on startup
        self._hydrate_from_store()
        # RT6-04: Hydrate delegation tree from store on startup
        self._hydrate_delegation_tree()

    def _broadcast_revocation_event(  # EATP-GAP: R6
        self,
        record: RevocationRecord,
        revocation_type: RevocationType,
    ) -> None:
        """Publish a revocation event to the EATP event bus.

        Uses ``eatp.revocation.broadcaster.RevocationBroadcaster.broadcast()``
        to notify subscribers. On failure, logs the error (EATP-GAP: R6 —
        the EATP SDK does not persist dead letters to a durable store;
        CARE logs the failure for auditability).

        Args:
            record: The CARE RevocationRecord to broadcast.
            revocation_type: The EATP RevocationType classification.
        """
        event = RevocationEvent(
            event_id=record.revocation_id,
            revocation_type=revocation_type,
            target_id=record.agent_id,
            revoked_by=record.revoker_id,
            reason=record.reason,
            affected_agents=list(record.affected_agents),
        )
        try:
            self._broadcaster.broadcast(event)
        except Exception as exc:
            # EATP-GAP: R6 — Dead-letter persistence for failed broadcasts
            # The EATP SDK's InMemoryRevocationBroadcaster tracks dead letters
            # in memory but does not persist them. CARE logs the failure so
            # the revocation record (already persisted via R4) can be
            # rebroadcast later.
            logger.error(
                "EATP-GAP R6: Failed to broadcast revocation event %s: %s. "
                "Revocation record is persisted and can be rebroadcast.",
                record.revocation_id,
                exc,
            )

    def _hydrate_from_store(self) -> None:  # EATP-GAP: R4
        """RT5-11: Load existing revocation records from the TrustStore into memory.

        Called on initialization so that revocation history survives restarts.
        Also populates the RT6-07 _revoked_ids secondary index.
        No-op when no trust store is configured.

        EATP-GAP: R4 — The EATP SDK's RevocationBroadcaster does not
        provide persistent storage for revocation events. CARE persists
        to TrustStore and hydrates on startup.
        """
        if self._trust_store is None:
            return

        persisted = self._trust_store.get_revocations()
        for data in persisted:
            try:
                record = RevocationRecord(
                    revocation_id=data["revocation_id"],
                    agent_id=data["agent_id"],
                    reason=data["reason"],
                    revoker_id=data["revoker_id"],
                    revoked_at=data.get("revoked_at", datetime.now(UTC)),
                    revocation_type=data["revocation_type"],
                    affected_agents=data.get("affected_agents", []),
                )
                self._revocation_log.append(record)
                # RT6-07: Populate secondary index during hydration
                self._revoked_ids.add(record.agent_id)
                self._revoked_ids.update(record.affected_agents)
            except (KeyError, TypeError) as exc:
                logger.warning(
                    "Failed to hydrate revocation record from store: %s — data=%r",
                    exc,
                    data,
                )

        if persisted:
            logger.info(
                "Hydrated %d revocation record(s) from TrustStore",
                len(persisted),
            )

    def _persist_to_store(self, record: RevocationRecord) -> None:  # EATP-GAP: R4
        """RT5-11: Persist a revocation record to the TrustStore if configured.

        EATP-GAP: R4 — The EATP SDK does not persist revocation events
        to durable storage. CARE persists to TrustStore.
        """
        if self._trust_store is not None:
            self._trust_store.store_revocation(record.revocation_id, record.model_dump(mode="json"))

    def _hydrate_delegation_tree(self) -> None:  # EATP-GAP: R5
        """RT6-04: Reconstruct the delegation tree from a persisted snapshot.

        Loads the delegation tree from a single well-known delegation record
        (``revmgr-delegation-tree``) in the TrustStore. No-op when no trust
        store is configured or when an EATP bridge provides the authoritative
        delegation tree.

        EATP-GAP: R5 — The EATP SDK does not provide a fallback delegation
        tree when the bridge is unavailable. CARE maintains a local copy.
        """
        if self._trust_store is None:
            return

        # RT7-04: Always hydrate local tree as fallback, even when bridge is configured.
        # The bridge may be unavailable at runtime (network error, etc.) so the local
        # tree must be ready as a fallback for get_downstream_agents().

        try:
            data = self._trust_store.get_delegation("revmgr-delegation-tree")
            if data is None:
                return

            tree = data.get("tree", {})
            count = 0
            for delegator, delegatees in tree.items():
                if not isinstance(delegatees, list):
                    continue
                if delegator not in self._delegation_tree:
                    self._delegation_tree[delegator] = []
                for delegatee in delegatees:
                    if delegatee not in self._delegation_tree[delegator]:
                        self._delegation_tree[delegator].append(delegatee)
                        count += 1

            if count:
                logger.info(
                    "RT6-04: Hydrated %d delegation relationship(s) from TrustStore",
                    count,
                )

        except Exception as exc:
            logger.warning("RT6-04: Failed to hydrate delegation tree from store: %s", exc)

    def _persist_delegation_tree(self) -> None:
        """RT6-04: Persist the full delegation tree as a single TrustStore record."""
        if self._trust_store is None:
            return

        self._trust_store.store_delegation(
            "revmgr-delegation-tree",
            {
                "delegation_id": "revmgr-delegation-tree",
                "tree": self._delegation_tree,
            },
        )

    def register_delegation(self, delegator_id: str, delegatee_id: str) -> None:
        """Register a delegation relationship for revocation tracking.

        Args:
            delegator_id: The parent agent (delegator).
            delegatee_id: The child agent (delegatee).
        """
        # RT8-04: Snapshot tree under lock, persist outside to avoid I/O under lock
        needs_persist = False
        with self._lock:
            if delegator_id not in self._delegation_tree:
                self._delegation_tree[delegator_id] = []
            if delegatee_id not in self._delegation_tree[delegator_id]:
                self._delegation_tree[delegator_id].append(delegatee_id)
                needs_persist = True
        if needs_persist:
            # RT6-04: Persist the tree so cascade revocation works after restart
            self._persist_delegation_tree()
            logger.info("Registered delegation: %s -> %s", delegator_id, delegatee_id)

    def surgical_revoke(self, agent_id: str, reason: str, revoker_id: str) -> RevocationRecord:
        """Revoke a single agent's trust. Siblings unaffected.

        Only the target agent's tokens are revoked. Children and siblings
        in the delegation tree are not touched. If an EATP bridge is
        configured, the agent is also revoked in the bridge.

        EATP-GAP: R1 — Reparents the agent's children to the agent's parent
        to preserve cascade discoverability. The EATP SDK does not support
        reparenting on surgical revocation.

        EATP-GAP: R3 — Revokes the agent's verification tokens via
        CredentialManager. The EATP SDK does not integrate with credential
        lifecycle management.

        Args:
            agent_id: The agent to revoke.
            reason: Why the agent is being revoked.
            revoker_id: ID of the authority performing the revocation.

        Returns:
            A RevocationRecord documenting the revocation.
        """
        # EATP-GAP: R3 — Credential revocation
        self.credentials.revoke_agent_tokens(agent_id)

        # Propagate revocation to EATP bridge if configured
        if self._eatp_bridge is not None:
            self._eatp_bridge.revoke_agent(agent_id)

        # RT2-02: Invalidate verification cache
        if self._verification_cache is not None:
            self._verification_cache.invalidate(agent_id)

        record = RevocationRecord(
            agent_id=agent_id,
            reason=reason,
            revoker_id=revoker_id,
            revocation_type="surgical",
            affected_agents=[],
        )
        # RT7-01: Thread-safe mutations to shared state
        with self._lock:
            self._revocation_log.append(record)
            self._revoked_ids.add(agent_id)
            # EATP-GAP: R1 — Reparent the agent's children to the agent's parent
            # instead of orphaning them. This preserves cascade discoverability —
            # if the grandparent is later cascade-revoked, the reparented children
            # will still be found.
            # The EATP SDK has no reparenting support on surgical revocation.
            children = self._delegation_tree.pop(agent_id, None) or []
            # Find the agent's parent by scanning for who lists this agent as a child
            parent_id: str | None = None
            for candidate_parent, candidate_children in self._delegation_tree.items():
                if agent_id in candidate_children:
                    parent_id = candidate_parent
                    break
            if parent_id is not None and children:
                # Reparent: move the agent's children to its parent
                self._delegation_tree[parent_id] = [
                    c for c in self._delegation_tree[parent_id] if c != agent_id
                ] + children
            elif parent_id is not None:
                # No children to reparent, just remove the agent from parent's list
                self._delegation_tree[parent_id] = [
                    c for c in self._delegation_tree[parent_id] if c != agent_id
                ]
            # If no parent (agent is a root), children become roots — nothing to reparent to

        # RT8-04/RT8-07: Persist delegation tree outside lock (I/O)
        self._persist_delegation_tree()
        # EATP-GAP: R4 — Persist to store if configured
        self._persist_to_store(record)

        # EATP SDK: Broadcast revocation event to EATP event bus
        self._broadcast_revocation_event(record, RevocationType.AGENT_REVOKED)

        logger.info(
            "Surgical revocation: agent=%s, reason='%s', revoker=%s",
            agent_id,
            reason,
            revoker_id,
        )
        return record

    def cascade_revoke(self, agent_id: str, reason: str, revoker_id: str) -> RevocationRecord:
        """Revoke an agent and ALL downstream agents.

        Finds all agents downstream of the target in the delegation tree
        and revokes each one's tokens. Records the cascade with the full
        list of affected agents.

        EATP-GAP: R3 — Revokes tokens for all affected agents via
        CredentialManager.

        Args:
            agent_id: The root agent to revoke (cascade starts here).
            reason: Why the cascade is being triggered.
            revoker_id: ID of the authority performing the revocation.

        Returns:
            A RevocationRecord documenting the cascade revocation.
        """
        # EATP-GAP: R3 — Credential revocation for target
        self.credentials.revoke_agent_tokens(agent_id)
        # Propagate revocation to EATP bridge if configured
        if self._eatp_bridge is not None:
            self._eatp_bridge.revoke_agent(agent_id)

        # Find and revoke all downstream agents
        downstream = self.get_downstream_agents(agent_id)
        for downstream_id in downstream:
            # EATP-GAP: R3 — Credential revocation for each downstream agent
            self.credentials.revoke_agent_tokens(downstream_id)
            if self._eatp_bridge is not None:
                self._eatp_bridge.revoke_agent(downstream_id)
            # RT2-02: Invalidate verification cache for each downstream agent
            if self._verification_cache is not None:
                self._verification_cache.invalidate(downstream_id)

        # RT2-02: Invalidate cache for the root agent too
        if self._verification_cache is not None:
            self._verification_cache.invalidate(agent_id)

        # RT2-05: Revoke bridges for affected teams if bridge manager is configured
        if self._bridge_manager is not None:
            # Revoke bridges involving the agent_id as team identifier
            self._bridge_manager.revoke_team_bridges(agent_id, f"Cascade revocation: {reason}")

        record = RevocationRecord(
            agent_id=agent_id,
            reason=reason,
            revoker_id=revoker_id,
            revocation_type="cascade",
            affected_agents=downstream,
        )
        # RT7-01: Thread-safe mutations to shared state
        with self._lock:
            self._revocation_log.append(record)
            self._revoked_ids.add(agent_id)
            self._revoked_ids.update(downstream)

            # RT7-15: Clear delegation tree entries for revoked agents so that
            # stale relationships do not persist if the agent is later re-delegated.
            all_revoked = {agent_id} | set(downstream)
            for revoked_id in all_revoked:
                self._delegation_tree.pop(revoked_id, None)
            # Also remove revoked agents as children of any parent
            for parent, children in self._delegation_tree.items():
                self._delegation_tree[parent] = [c for c in children if c not in all_revoked]

        # RT8-04: Persist outside lock to avoid I/O under lock
        self._persist_delegation_tree()
        # EATP-GAP: R4 — Persist to store if configured
        self._persist_to_store(record)

        # EATP SDK: Broadcast cascade revocation event to EATP event bus
        self._broadcast_revocation_event(record, RevocationType.CASCADE_REVOCATION)

        logger.info(
            "Cascade revocation: agent=%s, affected=%d downstream agents, reason='%s', revoker=%s",
            agent_id,
            len(downstream),
            reason,
            revoker_id,
        )
        return record

    def revoke_bridge_delegations(
        self,
        bridge_id: str,
        reason: str,
        revoker_id: str,
    ) -> list[str]:
        """Revoke all delegations granted through a specific bridge.

        When a bridge is suspended or closed, revoke the bridge delegations
        (not the agents themselves). When an agent is revoked, this can also
        be called to revoke that agent's bridge delegations.

        Uses BridgeTrustManager to find delegations by bridge_id and marks
        each one as revoked. Records a RevocationRecord for auditability.

        Args:
            bridge_id: The bridge whose delegations should be revoked.
            reason: Human-readable reason for the revocation.
            revoker_id: ID of the authority performing the revocation.

        Returns:
            List of revoked delegation IDs.
        """
        if self._bridge_trust_manager is None:
            logger.warning(
                "M33-3302: Cannot revoke bridge delegations — " "no BridgeTrustManager configured"
            )
            return []

        revoked_delegations = self._bridge_trust_manager.revoke_bridge_delegations(
            bridge_id, reason
        )
        revoked_ids = [d.delegation_id for d in revoked_delegations]

        if revoked_ids:
            record = RevocationRecord(
                agent_id=f"bridge:{bridge_id}",
                reason=reason,
                revoker_id=revoker_id,
                revocation_type="bridge_delegation",
                affected_agents=revoked_ids,
            )
            with self._lock:
                self._revocation_log.append(record)

            self._persist_to_store(record)
            self._broadcast_revocation_event(record, RevocationType.AGENT_REVOKED)

            # RT12-009: Invalidate verification cache for bridge agent IDs
            if self._verification_cache is not None:
                self._verification_cache.invalidate(f"bridge:{bridge_id}")

            logger.info(
                "M33-3302: Revoked %d bridge delegation(s) for bridge %s — reason: %s",
                len(revoked_ids),
                bridge_id,
                reason,
            )

        return revoked_ids

    def get_downstream_agents(self, agent_id: str) -> list[str]:
        """Get all agents downstream of this agent in the delegation tree.

        RT4-L5: When an EATPBridge is configured, uses the bridge's delegation
        tree (the authoritative source) instead of the local ``_delegation_tree``.
        This eliminates duplicate bookkeeping between RevocationManager and
        EATPBridge.

        EATP-GAP: R5 — When the bridge is unavailable (network error, etc.),
        falls back to the local delegation tree. The EATP SDK does not
        provide a fallback mechanism.

        Uses breadth-first traversal to find all descendants.

        Args:
            agent_id: The root agent to start from.

        Returns:
            A list of all downstream agent IDs (not including the root).
        """
        # RT4-L5: Use bridge tree when available; fall back to local tree
        tree: dict[str, list[str]] = {}
        use_local = True
        if self._eatp_bridge is not None and hasattr(self._eatp_bridge, "get_delegation_tree"):
            try:
                tree = self._eatp_bridge.get_delegation_tree()
                use_local = False
            except Exception as exc:
                # EATP-GAP: R5 — Fallback to local tree when bridge unavailable
                logger.warning(
                    "RT7-04: EATP bridge get_delegation_tree() failed, "
                    "falling back to local delegation tree: %s",
                    exc,
                )

        # RT8-02: Snapshot local tree under lock for thread-safe traversal
        if use_local:
            with self._lock:
                tree = {k: list(v) for k, v in self._delegation_tree.items()}

        downstream: list[str] = []
        queue: deque[str] = deque()

        # Seed the queue with direct children
        children = tree.get(agent_id, [])
        queue.extend(children)

        visited: set[str] = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            downstream.append(current)
            # Add this agent's children to the queue
            grandchildren = tree.get(current, [])
            queue.extend(grandchildren)

        return downstream

    def is_revoked(self, agent_id: str) -> bool:
        """Check if an agent has been revoked.

        RT6-07: Uses the ``_revoked_ids`` secondary index for O(1) lookup
        instead of iterating through every revocation record. Falls back
        to the TrustStore for agents not yet in the index (e.g. records
        persisted by another process).

        Args:
            agent_id: The agent to check.

        Returns:
            True if the agent has been revoked.
        """
        # RT6-07: O(1) check against the secondary index
        # RT7-01: Lock-free fast path -- set membership is safe to read
        # under CPython GIL; the lock is only needed for the mutation path.
        if agent_id in self._revoked_ids:
            return True

        # EATP-GAP: R4 — Fall back to persistent store for agents not in the index
        # (e.g. records stored by a different process or before hydration)
        if self._trust_store is not None:
            persisted = self._trust_store.get_revocations()
            for data in persisted:
                if data.get("agent_id") == agent_id:
                    # RT7-01: Thread-safe cache update
                    with self._lock:
                        self._revoked_ids.add(agent_id)
                    return True
                if agent_id in data.get("affected_agents", []):
                    with self._lock:
                        self._revoked_ids.add(agent_id)
                    return True

        return False

    def get_revocation_log(self, agent_id: str | None = None) -> list[RevocationRecord]:
        """Get revocation history, optionally filtered by agent.

        RT7-11: When filtering by agent_id, also returns records where the
        agent appears in ``affected_agents`` (cascade-revoked agents).

        Args:
            agent_id: If provided, filter to revocations where this agent is
                either the primary target or a cascade-affected agent.

        Returns:
            A list of RevocationRecords.
        """
        # RT7-01: Thread-safe read of _revocation_log
        with self._lock:
            if agent_id is None:
                return list(self._revocation_log)
            return [
                r
                for r in self._revocation_log
                if r.agent_id == agent_id or agent_id in r.affected_agents
            ]

    def can_redelegate(self, agent_id: str) -> bool:  # EATP-GAP: R2
        """Check if a revoked agent can be re-delegated (new chain).

        EATP-GAP: R2 — When min_cooling_off_hours is configured, recently-revoked
        agents must wait before re-delegation. The EATP SDK has no temporal
        re-delegation constraints. Without a cooling-off period, revocation
        is forward-looking only and re-delegation is always allowed.

        Args:
            agent_id: The agent to check.

        Returns:
            True if re-delegation is permitted, False if still in cooling-off.
        """
        if self._min_cooling_off_hours <= 0:
            return True
        # RT8-01: Thread-safe read of _revocation_log
        with self._lock:
            # Find the most recent revocation for this agent
            for record in reversed(self._revocation_log):
                if record.agent_id == agent_id or agent_id in record.affected_agents:
                    hours_since = (datetime.now(UTC) - record.revoked_at).total_seconds() / 3600
                    if hours_since < self._min_cooling_off_hours:
                        return False
                    break
        return True
