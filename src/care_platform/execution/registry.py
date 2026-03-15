# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Agent registry — central registry for all platform agents.

Tracks agent registration, status, capabilities, team membership,
and activity timestamps. Supports lookup by ID, team, or capability,
and detects stale agents that have not been active recently.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Lifecycle status of a registered agent."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    INACTIVE = "inactive"


class AgentRecord(BaseModel):
    """Registry entry for a registered agent."""

    agent_id: str
    name: str
    role: str
    team_id: str = ""
    capabilities: list[str] = Field(default_factory=list)
    current_posture: str = "supervised"
    status: AgentStatus = AgentStatus.ACTIVE
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_active_at: datetime | None = None
    envelope_id: str | None = None


class AgentRegistry:
    """Registry for all platform agents.

    Provides registration, lookup, status management, and staleness
    detection for agents across all teams.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()  # RT9-02: thread-safe registry access
        self._agents: dict[str, AgentRecord] = {}

    def register(
        self,
        agent_id: str,
        name: str,
        role: str,
        team_id: str = "",
        capabilities: list[str] | None = None,
        posture: str = "supervised",
    ) -> AgentRecord:
        """Register an agent in the registry."""
        record = AgentRecord(
            agent_id=agent_id,
            name=name,
            role=role,
            team_id=team_id,
            capabilities=capabilities if capabilities is not None else [],
            current_posture=posture,
        )
        with self._lock:
            if agent_id in self._agents:
                raise ValueError(
                    f"Agent '{agent_id}' is already registered. Deregister first to re-register."
                )
            self._agents[agent_id] = record
        logger.info("Agent registered: agent_id=%s name=%s team=%s", agent_id, name, team_id)
        return record

    def deregister(self, agent_id: str) -> None:
        """Remove agent from the registry."""
        with self._lock:
            if agent_id not in self._agents:
                raise ValueError(f"Agent '{agent_id}' not found in registry. Cannot deregister.")
            del self._agents[agent_id]
        logger.info("Agent deregistered: agent_id=%s", agent_id)

    def get(self, agent_id: str) -> AgentRecord | None:
        """Look up agent by ID."""
        with self._lock:
            return self._agents.get(agent_id)

    def get_team(self, team_id: str) -> list[AgentRecord]:
        """Get all agents in a team."""
        with self._lock:
            return [r for r in self._agents.values() if r.team_id == team_id]

    def find_by_capability(self, capability: str) -> list[AgentRecord]:
        """Find agents with a specific capability."""
        with self._lock:
            return [r for r in self._agents.values() if capability in r.capabilities]

    def update_status(self, agent_id: str, status: AgentStatus) -> None:
        """Update agent status."""
        with self._lock:
            if agent_id not in self._agents:
                raise ValueError(f"Agent '{agent_id}' not found in registry. Cannot update status.")
            self._agents[agent_id].status = status
        logger.info("Agent status updated: agent_id=%s status=%s", agent_id, status.value)

    def active_agents(self) -> list[AgentRecord]:
        """Get all active agents across all teams."""
        with self._lock:
            return [r for r in self._agents.values() if r.status == AgentStatus.ACTIVE]

    def touch(self, agent_id: str) -> None:
        """Update last_active_at timestamp for an agent."""
        with self._lock:
            if agent_id not in self._agents:
                raise ValueError(f"Agent '{agent_id}' not found in registry. Cannot touch.")
            self._agents[agent_id].last_active_at = datetime.now(UTC)

    def stale_agents(self, threshold_hours: int = 24) -> list[AgentRecord]:
        """Find active agents that have not been active recently."""
        cutoff = datetime.now(UTC) - timedelta(hours=threshold_hours)
        with self._lock:
            snapshot = list(self._agents.values())
        stale: list[AgentRecord] = []
        for record in snapshot:
            if record.status != AgentStatus.ACTIVE:
                continue
            if record.last_active_at is not None:
                if record.last_active_at < cutoff:
                    stale.append(record)
            elif record.registered_at < cutoff:
                stale.append(record)
        return stale
