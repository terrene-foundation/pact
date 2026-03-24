# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Audit query interface — structured queries and reports over audit history.

Provides :class:`AuditQuery` for filtering audit anchors and
:class:`AuditReport` for generating compliance and team summaries.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from pact_platform.trust.store.store import TrustStore

logger = logging.getLogger(__name__)


class AuditQuery:
    """Query interface for audit history backed by a :class:`TrustStore`.

    The *store* argument is required. This class never silently falls
    back to a default store — explicit is better than implicit.
    """

    def __init__(self, *, store: TrustStore) -> None:
        self.store = store

    def by_agent(self, agent_id: str, limit: int = 100) -> list[dict]:
        """Get audit anchors for a specific agent."""
        return self.store.query_anchors(agent_id=agent_id, limit=limit)

    def by_time_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 100,
    ) -> list[dict]:
        """Get audit anchors within a time range."""
        return self.store.query_anchors(since=start, until=end, limit=limit)

    def by_verification_level(self, level: str, limit: int = 100) -> list[dict]:
        """Get audit anchors at a specific verification level."""
        return self.store.query_anchors(verification_level=level, limit=limit)

    def filter(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        verification_level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Combined filter query — all parameters are optional."""
        return self.store.query_anchors(
            agent_id=agent_id,
            action=action,
            since=since,
            until=until,
            verification_level=verification_level,
            limit=limit,
        )

    def aggregate_by_agent(self, since: datetime | None = None) -> dict[str, int]:
        """Count actions per agent, optionally filtering by time."""
        anchors = self.store.query_anchors(since=since, limit=10_000)
        counts: Counter[str] = Counter()
        for anchor in anchors:
            agent = anchor.get("agent_id")
            if agent:
                counts[agent] += 1
        return dict(counts)

    def held_actions(self, since: datetime | None = None) -> list[dict]:
        """Get all HELD actions, optionally since a given time."""
        return self.store.query_anchors(
            verification_level="HELD",
            since=since,
            limit=10_000,
        )


class AuditReport:
    """Generate audit reports from query results."""

    def __init__(self, query: AuditQuery) -> None:
        self.query = query

    def team_summary(self, agent_ids: list[str], days: int = 7) -> dict:
        """Generate team activity summary for the last *days* days.

        Returns a dict with:
        - ``agent_counts``: actions per agent
        - ``total_actions``: total action count across agents
        - ``held_count``: number of HELD actions
        - ``period_days``: the time window in days
        """
        since = datetime.now(UTC) - timedelta(days=days)
        agent_counts: dict[str, int] = {}
        total = 0

        for agent_id in agent_ids:
            anchors = self.query.filter(agent_id=agent_id, since=since, limit=10_000)
            agent_counts[agent_id] = len(anchors)
            total += len(anchors)

        held = self.query.held_actions(since=since)
        held_for_team = [h for h in held if h.get("agent_id") in agent_ids]

        return {
            "agent_counts": agent_counts,
            "total_actions": total,
            "held_count": len(held_for_team),
            "period_days": days,
        }

    def compliance_check(self, agent_ids: list[str]) -> dict:
        """Check compliance: held actions and chain integrity indicators.

        Returns a dict with:
        - ``agents_checked``: list of agents checked
        - ``held_actions_count``: total held actions across agents
        - ``has_unresolved_held``: True if any held actions exist
        """
        held_total = 0
        for agent_id in agent_ids:
            held = self.query.filter(
                agent_id=agent_id,
                verification_level="HELD",
                limit=10_000,
            )
            held_total += len(held)

        return {
            "agents_checked": agent_ids,
            "held_actions_count": held_total,
            "has_unresolved_held": held_total > 0,
        }
