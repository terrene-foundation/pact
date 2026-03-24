# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""PACT API endpoint definitions and handler logic.

This module defines the API surface using plain Pydantic models (no FastAPI
or Nexus dependency required). When kailash-nexus is available, these
definitions can be connected to Nexus routes.

Endpoint schemas define the REST API surface:
    GET  /api/v1/teams                              - List all active teams
    GET  /api/v1/teams/{team_id}/agents             - List team agents
    GET  /api/v1/agents/{agent_id}/status            - Agent status and posture
    POST /api/v1/agents/{agent_id}/approve/{action_id} - Approve held action
    POST /api/v1/agents/{agent_id}/reject/{action_id}  - Reject held action
    GET  /api/v1/held-actions                       - List pending approvals
    GET  /api/v1/cost/report                        - API cost report

M18 Dashboard endpoints:
    GET  /api/v1/trust-chains                       - List all trust chains
    GET  /api/v1/trust-chains/{agent_id}            - Trust chain detail
    GET  /api/v1/envelopes/{envelope_id}            - Constraint envelope detail
    GET  /api/v1/workspaces                         - List all workspaces
    GET  /api/v1/bridges                            - List all bridges
    GET  /api/v1/verification/stats                 - Verification gradient stats

M36 Bridge management endpoints:
    POST /api/v1/bridges                            - Create a bridge
    GET  /api/v1/bridges/{bridge_id}                - Get bridge detail
    PUT  /api/v1/bridges/{bridge_id}/approve        - Approve a bridge (source or target)
    POST /api/v1/bridges/{bridge_id}/suspend        - Suspend an active bridge
    POST /api/v1/bridges/{bridge_id}/close          - Close a bridge
    GET  /api/v1/bridges/team/{team_id}             - List bridges for a team
    GET  /api/v1/bridges/{bridge_id}/audit          - Bridge audit trail

M13 ShadowEnforcer endpoints:
    GET  /api/v1/shadow/{agent_id}/metrics          - Shadow enforcement metrics
    GET  /api/v1/shadow/{agent_id}/report           - Shadow posture upgrade report

M42 Upgrade Evidence endpoints:
    GET  /api/v1/agents/{agent_id}/upgrade-evidence  - Upgrade evidence for posture upgrade
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pact_platform.trust.store.cost_tracking import CostTracker
from pact_platform.use.execution.approval import ApprovalQueue
from pact_platform.use.execution.registry import AgentRegistry

if TYPE_CHECKING:
    from typing import Any

    from pact_platform.build.config.schema import VerificationLevel
    from pact_platform.build.workspace.bridge import BridgeManager
    from pact_platform.build.workspace.models import WorkspaceRegistry
    from pact_platform.trust.audit.anchor import AuditChain
    from pact_platform.build.config.schema import ConstraintEnvelopeConfig
    from pact_platform.trust.store.posture_history import PostureHistoryStore

    # ShadowEnforcer was in a deleted module. Used only as an optional
    # dependency (duck-typed: .get_metrics(), .generate_report()).
    ShadowEnforcer = Any  # was: pact_platform.trust.shadow_enforcer.ShadowEnforcer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------


class EndpointDefinition(BaseModel):
    """Schema describing a single API endpoint."""

    method: str = Field(description="HTTP method (GET, POST, PUT, DELETE)")
    path: str = Field(description="URL path pattern")
    description: str = Field(default="", description="Human-readable description")


class ApiResponse(BaseModel):
    """Standardized API response wrapper."""

    status: str = Field(description="'ok' or 'error'")
    data: dict[str, Any] | None = Field(default=None, description="Response payload")
    error: str | None = Field(default=None, description="Error message if status is 'error'")


# ---------------------------------------------------------------------------
# Canonical endpoint definitions
# ---------------------------------------------------------------------------

_ENDPOINT_DEFINITIONS: list[EndpointDefinition] = [
    EndpointDefinition(
        method="GET",
        path="/api/v1/teams",
        description="List all active teams",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/teams/{team_id}/agents",
        description="List agents in a team",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/agents/{agent_id}/status",
        description="Get agent status and posture",
    ),
    EndpointDefinition(
        method="POST",
        path="/api/v1/agents/{agent_id}/approve/{action_id}",
        description="Approve a held action",
    ),
    EndpointDefinition(
        method="POST",
        path="/api/v1/agents/{agent_id}/reject/{action_id}",
        description="Reject a held action",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/held-actions",
        description="List all pending approval actions",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/cost/report",
        description="Get API cost report",
    ),
    # M18 Dashboard endpoints
    EndpointDefinition(
        method="GET",
        path="/api/v1/trust-chains",
        description="List all trust chains with status",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/trust-chains/{agent_id}",
        description="Get trust chain detail for an agent",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/envelopes/{envelope_id}",
        description="Get constraint envelope with all five dimensions",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/workspaces",
        description="List all workspaces with state and phase",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/bridges",
        description="List all cross-functional bridges with status",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/verification/stats",
        description="Get verification gradient counts by level",
    ),
    # M36 Bridge management endpoints
    EndpointDefinition(
        method="POST",
        path="/api/v1/bridges",
        description="Create a cross-functional bridge",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/bridges/{bridge_id}",
        description="Get bridge detail by ID",
    ),
    EndpointDefinition(
        method="PUT",
        path="/api/v1/bridges/{bridge_id}/approve",
        description="Approve a bridge (source or target side)",
    ),
    EndpointDefinition(
        method="POST",
        path="/api/v1/bridges/{bridge_id}/suspend",
        description="Suspend an active bridge",
    ),
    EndpointDefinition(
        method="POST",
        path="/api/v1/bridges/{bridge_id}/close",
        description="Close a bridge",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/bridges/team/{team_id}",
        description="List bridges for a specific team",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/bridges/{bridge_id}/audit",
        description="Get bridge audit trail",
    ),
    # M13 ShadowEnforcer endpoints
    EndpointDefinition(
        method="GET",
        path="/api/v1/shadow/{agent_id}/metrics",
        description="Get shadow enforcement metrics for an agent",
    ),
    EndpointDefinition(
        method="GET",
        path="/api/v1/shadow/{agent_id}/report",
        description="Get shadow enforcement posture upgrade report for an agent",
    ),
    # M42 Upgrade Evidence endpoint
    EndpointDefinition(
        method="GET",
        path="/api/v1/agents/{agent_id}/upgrade-evidence",
        description="Get upgrade evidence for posture upgrade evaluation",
    ),
]


# ---------------------------------------------------------------------------
# PactAPI — handler logic
# ---------------------------------------------------------------------------


class PactAPI:
    """API handler that takes core platform components and exposes endpoint logic.

    All methods return an ``ApiResponse``. No HTTP framework dependency —
    when Nexus is available, each method maps to a Nexus route handler.

    Args:
        registry: AgentRegistry for agent/team queries.
        approval_queue: ApprovalQueue for held-action management.
        cost_tracker: CostTracker for spend reporting.
        workspace_registry: Optional WorkspaceRegistry for workspace queries (M18).
        bridge_manager: Optional BridgeManager for bridge queries (M18).
        envelope_registry: Optional dict mapping envelope IDs to ConstraintEnvelopeConfig (M18).
        verification_stats: Optional dict mapping VerificationLevel to counts (M18).
        posture_store: Optional PostureHistoryStore for posture history queries (M18).
        shadow_enforcer: Optional ShadowEnforcer for shadow evaluation metrics (M13).

    Raises:
        ValueError: If any required component is None.
    """

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        approval_queue: ApprovalQueue,
        cost_tracker: CostTracker,
        workspace_registry: WorkspaceRegistry | None = None,
        bridge_manager: BridgeManager | None = None,
        envelope_registry: dict[str, ConstraintEnvelopeConfig] | None = None,
        verification_stats: dict[VerificationLevel, int] | None = None,
        posture_store: PostureHistoryStore | None = None,
        shadow_enforcer: ShadowEnforcer | None = None,
        audit_chain: AuditChain | None = None,
    ) -> None:
        if registry is None:
            raise ValueError(
                "PactAPI requires a non-None AgentRegistry. "
                "Provide a registry instance — do not pass None."
            )
        if approval_queue is None:
            raise ValueError(
                "PactAPI requires a non-None ApprovalQueue. "
                "Provide an approval_queue instance — do not pass None."
            )
        if cost_tracker is None:
            raise ValueError(
                "PactAPI requires a non-None CostTracker. "
                "Provide a cost_tracker instance — do not pass None."
            )

        self._registry = registry
        self._approval_queue = approval_queue
        self._cost_tracker = cost_tracker
        # M18 dashboard components (optional for backward compatibility)
        self._workspace_registry = workspace_registry
        self._bridge_manager = bridge_manager
        self._envelope_registry = envelope_registry
        self._verification_stats = verification_stats
        self._posture_store = posture_store
        self._shadow_enforcer = shadow_enforcer
        # L9: Audit chain for trends computation
        self._audit_chain = audit_chain

    @property
    def endpoints(self) -> list[EndpointDefinition]:
        """Return all defined endpoint schemas."""
        return list(_ENDPOINT_DEFINITIONS)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def list_teams(self) -> ApiResponse:
        """List all unique team IDs from the agent registry."""
        agents = self._registry.active_agents()
        team_ids = sorted({a.team_id for a in agents if a.team_id})
        return ApiResponse(status="ok", data={"teams": team_ids})

    def list_agents(self, team_id: str) -> ApiResponse:
        """List all agents in a team.

        Args:
            team_id: The team to query.

        Returns:
            ApiResponse with agents list (empty if team not found).
        """
        records = self._registry.get_team(team_id)
        agents = [
            {
                "agent_id": r.agent_id,
                "name": r.name,
                "role": r.role,
                "posture": r.current_posture,
                "status": r.status.value,
            }
            for r in records
        ]
        return ApiResponse(status="ok", data={"agents": agents})

    def agent_status(self, agent_id: str) -> ApiResponse:
        """Get status and details for a specific agent.

        Args:
            agent_id: The agent to query.

        Returns:
            ApiResponse with agent details, or error if not found.
        """
        record = self._registry.get(agent_id)
        if record is None:
            logger.warning("agent_status: agent '%s' not found in registry", agent_id)
            return ApiResponse(
                status="error",
                error=f"Agent '{agent_id}' not found in registry",
            )
        return ApiResponse(
            status="ok",
            data={
                "agent_id": record.agent_id,
                "name": record.name,
                "role": record.role,
                "team_id": record.team_id,
                "posture": record.current_posture,
                "status": record.status.value,
                "capabilities": record.capabilities,
            },
        )

    def approve_action(
        self,
        agent_id: str,
        action_id: str,
        approver_id: str,
        reason: str = "",
    ) -> ApiResponse:
        """Approve a held action.

        RT13-C2 trust boundary note: The REST API uses bearer-token
        authentication (validated in server.py middleware) as its trust
        boundary.  When ``AuthenticatedApprovalQueue`` is used, the runtime
        path requires Ed25519 ``SignedDecision`` payloads for cryptographic
        proof.  The API path is a *separate* trust boundary — the bearer
        token proves the caller's identity, so re-signing is not required.
        Both paths audit the approver_id for traceability.

        Args:
            agent_id: The agent whose action is being approved.
            action_id: The pending action to approve.
            approver_id: Who is approving.
            reason: Optional reason for approval.

        Returns:
            ApiResponse with approval result, or error if action not found.
        """
        try:
            # RT10-C1: Validate agent ownership BEFORE mutating state
            pending = [p for p in self._approval_queue.pending if p.action_id == action_id]
            if not pending:
                return ApiResponse(
                    status="error",
                    error=f"Action '{action_id}' not found in pending queue",
                )
            if pending[0].agent_id != agent_id:
                logger.warning(
                    "API: approve_action agent mismatch — action %s belongs to %s, not %s",
                    action_id,
                    pending[0].agent_id,
                    agent_id,
                )
                return ApiResponse(
                    status="error",
                    error=f"Action '{action_id}' does not belong to agent '{agent_id}'",
                )
            pa = self._approval_queue.approve(action_id, approver_id, reason)
            logger.info(
                "API: action approved — action_id=%s agent=%s approver=%s",
                action_id,
                agent_id,
                approver_id,
            )
            return ApiResponse(
                status="ok",
                data={
                    "action_id": pa.action_id,
                    "decision": "approved",
                    "decided_by": pa.decided_by,
                },
            )
        except ValueError as e:
            logger.warning(
                "API: approve_action failed — action_id=%s error=%s",
                action_id,
                str(e),
            )
            return ApiResponse(status="error", error=str(e))

    def reject_action(
        self,
        agent_id: str,
        action_id: str,
        approver_id: str,
        reason: str = "",
    ) -> ApiResponse:
        """Reject a held action.

        Args:
            agent_id: The agent whose action is being rejected.
            action_id: The pending action to reject.
            approver_id: Who is rejecting.
            reason: Optional reason for rejection.

        Returns:
            ApiResponse with rejection result, or error if action not found.
        """
        try:
            # RT10-C1: Validate agent ownership BEFORE mutating state
            pending = [p for p in self._approval_queue.pending if p.action_id == action_id]
            if not pending:
                return ApiResponse(
                    status="error",
                    error=f"Action '{action_id}' not found in pending queue",
                )
            if pending[0].agent_id != agent_id:
                logger.warning(
                    "API: reject_action agent mismatch — action %s belongs to %s, not %s",
                    action_id,
                    pending[0].agent_id,
                    agent_id,
                )
                return ApiResponse(
                    status="error",
                    error=f"Action '{action_id}' does not belong to agent '{agent_id}'",
                )
            pa = self._approval_queue.reject(action_id, approver_id, reason)
            logger.info(
                "API: action rejected — action_id=%s agent=%s approver=%s",
                action_id,
                agent_id,
                approver_id,
            )
            return ApiResponse(
                status="ok",
                data={
                    "action_id": pa.action_id,
                    "decision": "rejected",
                    "decided_by": pa.decided_by,
                },
            )
        except ValueError as e:
            logger.warning(
                "API: reject_action failed — action_id=%s error=%s",
                action_id,
                str(e),
            )
            return ApiResponse(status="error", error=str(e))

    def held_actions(self) -> ApiResponse:
        """List all pending approval actions."""
        pending = self._approval_queue.pending
        actions = [
            {
                "action_id": pa.action_id,
                "agent_id": pa.agent_id,
                "team_id": pa.team_id,
                "action": pa.action,
                "reason": pa.reason,
                "urgency": pa.urgency.value,
                "submitted_at": pa.submitted_at.isoformat(),
            }
            for pa in pending
        ]
        return ApiResponse(status="ok", data={"actions": actions})

    def cost_report(
        self,
        *,
        team_id: str | None = None,
        agent_id: str | None = None,
        days: int = 30,
    ) -> ApiResponse:
        """Get API cost report.

        Args:
            team_id: Optional team filter.
            agent_id: Optional agent filter.
            days: Number of days to include (default 30).

        Returns:
            ApiResponse with cost report data.
        """
        report = self._cost_tracker.spend_report(
            team_id=team_id,
            agent_id=agent_id,
            days=days,
        )
        return ApiResponse(
            status="ok",
            data={
                "total_cost": str(report.total_cost),
                "period_days": report.period_days,
                "total_calls": report.total_calls,
                "by_agent": {k: str(v) for k, v in report.by_agent.items()},
                "by_model": {k: str(v) for k, v in report.by_model.items()},
                "by_day": {k: str(v) for k, v in report.by_day.items()},
                "alerts_triggered": report.alerts_triggered,
            },
        )

    # ------------------------------------------------------------------
    # M18 Dashboard Handlers
    # ------------------------------------------------------------------

    def list_trust_chains(self) -> ApiResponse:
        """List all agents with trust chain status information.

        Returns an entry per registered agent with their ID, name, team,
        posture, and status. Uses the agent registry which is always
        available.

        Returns:
            ApiResponse with a list of trust chain summaries.
        """
        agents = self._registry.active_agents()
        chains = [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "team_id": a.team_id,
                "posture": a.current_posture,
                "status": a.status.value,
            }
            for a in agents
        ]
        return ApiResponse(status="ok", data={"trust_chains": chains})

    def get_trust_chain_detail(self, agent_id: str) -> ApiResponse:
        """Get trust chain detail for a specific agent.

        Args:
            agent_id: The agent to query.

        Returns:
            ApiResponse with agent trust chain details, or error if not found.
        """
        record = self._registry.get(agent_id)
        if record is None:
            logger.warning(
                "get_trust_chain_detail: agent '%s' not found in registry",
                agent_id,
            )
            return ApiResponse(
                status="error",
                error=f"Agent '{agent_id}' not found in registry",
            )
        return ApiResponse(
            status="ok",
            data={
                "agent_id": record.agent_id,
                "name": record.name,
                "role": record.role,
                "team_id": record.team_id,
                "posture": record.current_posture,
                "status": record.status.value,
                "capabilities": record.capabilities,
            },
        )

    def get_envelope(self, envelope_id: str) -> ApiResponse:
        """Get constraint envelope detail with all five CARE dimensions.

        Args:
            envelope_id: The envelope ID to look up.

        Returns:
            ApiResponse with full envelope data across all five dimensions,
            or error if envelope_registry is not configured or ID not found.
        """
        if self._envelope_registry is None:
            logger.warning("get_envelope: envelope_registry not configured on PactAPI")
            return ApiResponse(
                status="error",
                error=(
                    "Dashboard endpoint unavailable: envelope_registry not "
                    "provided to PactAPI. Pass envelope_registry to enable "
                    "this endpoint."
                ),
            )

        envelope = self._envelope_registry.get(envelope_id)
        if envelope is None:
            logger.warning(
                "get_envelope: envelope '%s' not found in registry",
                envelope_id,
            )
            return ApiResponse(
                status="error",
                error=f"Envelope '{envelope_id}' not found in envelope registry",
            )

        config = envelope
        return ApiResponse(
            status="ok",
            data={
                "envelope_id": config.id,
                "description": config.description,
                "financial": {
                    "max_spend_usd": config.financial.max_spend_usd,
                    "api_cost_budget_usd": config.financial.api_cost_budget_usd,
                    "requires_approval_above_usd": config.financial.requires_approval_above_usd,
                },
                "operational": {
                    "allowed_actions": list(config.operational.allowed_actions),
                    "blocked_actions": list(config.operational.blocked_actions),
                    "max_actions_per_day": config.operational.max_actions_per_day,
                },
                "temporal": {
                    "active_hours_start": config.temporal.active_hours_start,
                    "active_hours_end": config.temporal.active_hours_end,
                    "timezone": config.temporal.timezone,
                    "blackout_periods": list(config.temporal.blackout_periods),
                },
                "data_access": {
                    "read_paths": list(config.data_access.read_paths),
                    "write_paths": list(config.data_access.write_paths),
                    "blocked_data_types": list(config.data_access.blocked_data_types),
                },
                "communication": {
                    "internal_only": config.communication.internal_only,
                    "allowed_channels": list(config.communication.allowed_channels),
                    "external_requires_approval": config.communication.external_requires_approval,
                },
            },
        )

    def list_workspaces(self) -> ApiResponse:
        """List all workspaces with their state and CO methodology phase.

        Returns:
            ApiResponse with a list of workspace summaries, or error if
            workspace_registry is not configured.
        """
        if self._workspace_registry is None:
            logger.warning("list_workspaces: workspace_registry not configured on PactAPI")
            return ApiResponse(
                status="error",
                error=(
                    "Dashboard endpoint unavailable: workspace_registry not "
                    "provided to PactAPI. Pass workspace_registry to enable "
                    "this endpoint."
                ),
            )

        workspaces = self._workspace_registry.list_active()
        ws_list = [
            {
                "id": ws.id,
                "path": ws.path,
                "description": ws.config.description,
                "state": ws.workspace_state.value,
                "phase": ws.current_phase.value,
                "team_id": ws.team_id or "",
            }
            for ws in workspaces
        ]
        return ApiResponse(status="ok", data={"workspaces": ws_list})

    def list_bridges(self) -> ApiResponse:
        """List all cross-functional bridges with their status.

        Returns:
            ApiResponse with a list of bridge summaries, or error if
            bridge_manager is not configured.
        """
        if self._bridge_manager is None:
            logger.warning("list_bridges: bridge_manager not configured on PactAPI")
            return ApiResponse(
                status="error",
                error=(
                    "Dashboard endpoint unavailable: bridge_manager not "
                    "provided to PactAPI. Pass bridge_manager to enable "
                    "this endpoint."
                ),
            )

        all_bridges = self._bridge_manager.list_all_bridges()
        bridge_list = [
            {
                "bridge_id": b.bridge_id,
                "bridge_type": b.bridge_type.value,
                "source_team_id": b.source_team_id,
                "target_team_id": b.target_team_id,
                "purpose": b.purpose,
                "status": b.status.value,
                "created_at": b.created_at.isoformat(),
            }
            for b in all_bridges
        ]
        return ApiResponse(status="ok", data={"bridges": bridge_list})

    def verification_stats_report(self) -> ApiResponse:
        """Get verification gradient counts by level.

        Returns:
            ApiResponse with counts for AUTO_APPROVED, FLAGGED, HELD,
            BLOCKED, and a total, or error if verification_stats is
            not configured.
        """
        if self._verification_stats is None:
            logger.warning(
                "verification_stats_report: verification_stats not configured on PactAPI"
            )
            return ApiResponse(
                status="error",
                error=(
                    "Dashboard endpoint unavailable: verification_stats not "
                    "provided to PactAPI. Pass verification_stats to enable "
                    "this endpoint."
                ),
            )

        from pact_platform.build.config.schema import VerificationLevel

        auto = self._verification_stats.get(VerificationLevel.AUTO_APPROVED, 0)
        flagged = self._verification_stats.get(VerificationLevel.FLAGGED, 0)
        held = self._verification_stats.get(VerificationLevel.HELD, 0)
        blocked = self._verification_stats.get(VerificationLevel.BLOCKED, 0)
        total = auto + flagged + held + blocked

        return ApiResponse(
            status="ok",
            data={
                "AUTO_APPROVED": auto,
                "FLAGGED": flagged,
                "HELD": held,
                "BLOCKED": blocked,
                "total": total,
            },
        )

    def dashboard_trends(self) -> ApiResponse:
        """Compute 7-day daily verification counts from audit anchor timestamps.

        Groups audit records by date and verification level for the last 7 days.
        Returns arrays suitable for sparkline rendering in the dashboard.

        Returns:
            ApiResponse with dates and per-level count arrays.
        """
        from datetime import UTC, datetime, timedelta

        from pact_platform.build.config.schema import VerificationLevel

        now = datetime.now(UTC)
        # Build the 7-day date range (oldest first)
        dates: list[str] = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            dates.append(day.strftime("%Y-%m-%d"))

        # Initialize counts per date per level
        counts: dict[str, dict[str, int]] = {
            d: {"auto_approved": 0, "flagged": 0, "held": 0, "blocked": 0} for d in dates
        }

        level_key_map = {
            VerificationLevel.AUTO_APPROVED: "auto_approved",
            VerificationLevel.FLAGGED: "flagged",
            VerificationLevel.HELD: "held",
            VerificationLevel.BLOCKED: "blocked",
        }

        if self._audit_chain is not None:
            for anchor in self._audit_chain.anchors:
                day_str = anchor.timestamp.strftime("%Y-%m-%d")
                if day_str in counts:
                    key = level_key_map.get(anchor.verification_level)
                    if key:
                        counts[day_str][key] += 1

        return ApiResponse(
            status="ok",
            data={
                "dates": dates,
                "auto_approved": [counts[d]["auto_approved"] for d in dates],
                "flagged": [counts[d]["flagged"] for d in dates],
                "held": [counts[d]["held"] for d in dates],
                "blocked": [counts[d]["blocked"] for d in dates],
            },
        )

    def posture_history(self, agent_id: str) -> ApiResponse:
        """Get posture change history for an agent.

        Args:
            agent_id: The agent whose posture history to retrieve.

        Returns:
            ApiResponse with posture change records, or error if posture_store
            is not configured.
        """
        if self._posture_store is None:
            return ApiResponse(
                status="error",
                error="Posture history unavailable: posture_store not provided to PactAPI.",
            )

        records = self._posture_store.get_history(agent_id)
        return ApiResponse(
            status="ok",
            data={
                "agent_id": agent_id,
                "records": [
                    {
                        "record_id": r.record_id,
                        "agent_id": r.agent_id,
                        "from_posture": r.from_posture,
                        "to_posture": r.to_posture,
                        "direction": r.direction,
                        "trigger": (
                            r.trigger.value if hasattr(r.trigger, "value") else str(r.trigger)
                        ),
                        "changed_by": r.changed_by,
                        "changed_at": r.changed_at.isoformat(),
                        "reason": r.reason,
                    }
                    for r in records
                ],
                "count": len(records),
            },
        )

    # ------------------------------------------------------------------
    # M36 Bridge Management Handlers
    # ------------------------------------------------------------------

    def _bridge_to_detail(self, b: Any) -> dict[str, Any]:
        """Convert a Bridge model to a detailed dict representation.

        Args:
            b: A Bridge instance from the workspace.bridge module.

        Returns:
            Dictionary with full bridge details including permissions and approval state.
        """
        return {
            "bridge_id": b.bridge_id,
            "bridge_type": b.bridge_type.value,
            "source_team_id": b.source_team_id,
            "target_team_id": b.target_team_id,
            "purpose": b.purpose,
            "status": b.status.value,
            "created_at": b.created_at.isoformat(),
            "created_by": b.created_by,
            "approved_by_source": b.approved_by_source,
            "approved_by_target": b.approved_by_target,
            "valid_until": b.valid_until.isoformat() if b.valid_until else None,
            "one_time_use": b.one_time_use,
            "used": b.used,
            # RT13-009: Redact payload contents — expose only presence/size
            # to prevent information leakage through the bridge detail API.
            "has_request_payload": bool(b.request_payload),
            "has_response_payload": b.response_payload is not None,
            "responded_at": b.responded_at.isoformat() if b.responded_at else None,
            "permissions": {
                "read_paths": list(b.effective_permissions.read_paths),
                "write_paths": list(b.effective_permissions.write_paths),
                "message_types": list(b.effective_permissions.message_types),
                "requires_attribution": b.effective_permissions.requires_attribution,
            },
            "replaced_by": b.replaced_by,
            "replacement_for": b.replacement_for,
            "access_log_count": len(b.access_log),
        }

    def create_bridge(self, data: dict[str, Any]) -> ApiResponse:
        """Create a cross-functional bridge.

        Args:
            data: Bridge creation parameters containing bridge_type, source_team_id,
                target_team_id, purpose, and optional permissions, valid_days,
                request_payload.

        Returns:
            ApiResponse with the created bridge details.
        """
        if self._bridge_manager is None:
            logger.warning("create_bridge: bridge_manager not configured on PactAPI")
            return ApiResponse(
                status="error",
                error=("Bridge management unavailable: bridge_manager not provided to PactAPI."),
            )

        bridge_type = data.get("bridge_type", "")
        source_team_id = data.get("source_team_id", "")
        target_team_id = data.get("target_team_id", "")
        purpose = data.get("purpose", "")

        if not bridge_type or not source_team_id or not target_team_id or not purpose:
            return ApiResponse(
                status="error",
                error=(
                    "Missing required fields: bridge_type, source_team_id, "
                    "target_team_id, and purpose are all required."
                ),
            )

        # RT12-006: Validate field types
        if not all(
            isinstance(f, str) for f in [bridge_type, source_team_id, target_team_id, purpose]
        ):
            return ApiResponse(
                status="error",
                error="bridge_type, source_team_id, target_team_id, and purpose must be strings.",
            )

        # RT13-H7: Input length validation to prevent memory exhaustion
        max_len = 256
        for label, value in [
            ("source_team_id", source_team_id),
            ("target_team_id", target_team_id),
            ("purpose", purpose),
            ("bridge_type", bridge_type),
        ]:
            if len(value) > max_len:
                return ApiResponse(
                    status="error",
                    error=f"{label} exceeds maximum length of {max_len} characters.",
                )

        # RT13-001: Prevent self-bridges
        if source_team_id == target_team_id:
            return ApiResponse(
                status="error",
                error=(
                    f"Cannot create a bridge from team '{source_team_id}' to itself. "
                    f"Cross-Functional Bridges connect different teams."
                ),
            )

        # Build BridgePermission from data
        from pact_platform.build.workspace.bridge import BridgePermission

        perms_data = data.get("permissions", {})
        permissions = BridgePermission(
            read_paths=perms_data.get("read_paths", []),
            write_paths=perms_data.get("write_paths", []),
            message_types=perms_data.get("message_types", []),
        )

        try:
            if bridge_type == "standing":
                bridge = self._bridge_manager.create_standing_bridge(
                    source_team=source_team_id,
                    target_team=target_team_id,
                    purpose=purpose,
                    permissions=permissions,
                    created_by=data.get("created_by", "api"),
                )
            elif bridge_type == "scoped":
                valid_days = data.get("valid_days", 7)
                # RT12-006: Bound valid_days to prevent negative or excessive values
                if not isinstance(valid_days, int) or valid_days < 1 or valid_days > 365:
                    return ApiResponse(
                        status="error",
                        error="valid_days must be an integer between 1 and 365.",
                    )
                bridge = self._bridge_manager.create_scoped_bridge(
                    source_team=source_team_id,
                    target_team=target_team_id,
                    purpose=purpose,
                    permissions=permissions,
                    created_by=data.get("created_by", "api"),
                    valid_days=valid_days,
                )
            elif bridge_type == "ad_hoc":
                request_payload = data.get("request_payload", {})
                # RT12-006: Limit request_payload size
                import json as _json

                if len(_json.dumps(request_payload, default=str)) > 65536:
                    return ApiResponse(
                        status="error",
                        error="request_payload exceeds 64KB size limit.",
                    )
                bridge = self._bridge_manager.create_adhoc_bridge(
                    source_team=source_team_id,
                    target_team=target_team_id,
                    purpose=purpose,
                    request_payload=request_payload,
                    created_by=data.get("created_by", "api"),
                )
            else:
                return ApiResponse(
                    status="error",
                    error=(
                        f"Invalid bridge_type '{bridge_type}'. "
                        f"Must be 'standing', 'scoped', or 'ad_hoc'."
                    ),
                )
        except Exception as exc:
            logger.warning("create_bridge: failed — %s", exc)
            return ApiResponse(status="error", error=str(exc))

        logger.info(
            "API: bridge created — bridge_id=%s type=%s",
            bridge.bridge_id,
            bridge_type,
        )
        return ApiResponse(status="ok", data=self._bridge_to_detail(bridge))

    def get_bridge(self, bridge_id: str) -> ApiResponse:
        """Get detailed bridge information by ID.

        Args:
            bridge_id: The bridge identifier.

        Returns:
            ApiResponse with bridge details, or error if not found.
        """
        if self._bridge_manager is None:
            logger.warning("get_bridge: bridge_manager not configured on PactAPI")
            return ApiResponse(
                status="error",
                error=("Bridge management unavailable: bridge_manager not provided to PactAPI."),
            )

        bridge = self._bridge_manager.get_bridge(bridge_id)
        if bridge is None:
            logger.warning("get_bridge: bridge '%s' not found", bridge_id)
            return ApiResponse(
                status="error",
                error=f"Bridge '{bridge_id}' not found",
            )

        return ApiResponse(status="ok", data=self._bridge_to_detail(bridge))

    def approve_bridge(self, bridge_id: str, side: str, approver_id: str) -> ApiResponse:
        """Approve a bridge on source or target side.

        Args:
            bridge_id: The bridge to approve.
            side: Either 'source' or 'target'.
            approver_id: Identifier of the approver.

        Returns:
            ApiResponse with updated bridge details, or error if not found or invalid side.
        """
        if self._bridge_manager is None:
            return ApiResponse(
                status="error",
                error="Bridge management unavailable: bridge_manager not provided.",
            )

        if side not in ("source", "target"):
            return ApiResponse(
                status="error",
                error=f"Invalid side '{side}'. Must be 'source' or 'target'.",
            )

        # RT12-012 / RT13-C1: Verify approver belongs to the correct team.
        # Reject unauthorized approvers to enforce bilateral trust requirement.
        # L1-FIX: Use proper registry lookup instead of substring check.
        bridge_obj = self._bridge_manager.get_bridge(bridge_id)
        if bridge_obj is None:
            return ApiResponse(status="error", error=f"Bridge '{bridge_id}' not found")
        expected_team = bridge_obj.source_team_id if side == "source" else bridge_obj.target_team_id
        if expected_team and approver_id:
            # Look up the approver in the agent registry and verify team membership
            team_members = self._registry.get_team(expected_team)
            team_member_ids = {r.agent_id for r in team_members}
            if approver_id not in team_member_ids:
                logger.warning(
                    "RT13-C1: approve_bridge REJECTED — approver_id '%s' is not a registered "
                    "member of %s team '%s'. Bilateral trust requires team-verified approvers.",
                    approver_id,
                    side,
                    expected_team,
                )
                return ApiResponse(
                    status="error",
                    error=f"Approver '{approver_id}' is not authorized to approve the {side} "
                    f"side of this bridge. Only members of team '{expected_team}' may approve.",
                )

        try:
            if side == "source":
                bridge = self._bridge_manager.approve_bridge_source(bridge_id, approver_id)
            else:
                bridge = self._bridge_manager.approve_bridge_target(bridge_id, approver_id)
        except ValueError as exc:
            logger.warning(
                "API: approve_bridge failed — bridge_id=%s side=%s error=%s",
                bridge_id,
                side,
                exc,
            )
            return ApiResponse(status="error", error=str(exc))

        logger.info(
            "API: bridge approved — bridge_id=%s side=%s approver=%s status=%s",
            bridge_id,
            side,
            approver_id,
            bridge.status.value,
        )
        return ApiResponse(status="ok", data=self._bridge_to_detail(bridge))

    def suspend_bridge_action(self, bridge_id: str, reason: str) -> ApiResponse:
        """Suspend an active bridge.

        Args:
            bridge_id: The bridge to suspend.
            reason: Human-readable reason for suspension.

        Returns:
            ApiResponse with updated bridge details, or error if invalid state.
        """
        if self._bridge_manager is None:
            return ApiResponse(
                status="error",
                error="Bridge management unavailable: bridge_manager not provided.",
            )

        if not reason:
            return ApiResponse(
                status="error",
                error="A reason is required to suspend a bridge.",
            )

        try:
            bridge = self._bridge_manager.suspend_bridge(bridge_id, reason)
        except ValueError as exc:
            logger.warning(
                "API: suspend_bridge failed — bridge_id=%s error=%s",
                bridge_id,
                exc,
            )
            return ApiResponse(status="error", error=str(exc))

        logger.info(
            "API: bridge suspended — bridge_id=%s reason=%s",
            bridge_id,
            reason,
        )
        return ApiResponse(status="ok", data=self._bridge_to_detail(bridge))

    def close_bridge_action(self, bridge_id: str, reason: str) -> ApiResponse:
        """Close a bridge.

        Args:
            bridge_id: The bridge to close.
            reason: Human-readable reason for closure.

        Returns:
            ApiResponse with updated bridge details, or error if invalid state.
        """
        if self._bridge_manager is None:
            return ApiResponse(
                status="error",
                error="Bridge management unavailable: bridge_manager not provided.",
            )

        if not reason:
            return ApiResponse(
                status="error",
                error="A reason is required to close a bridge.",
            )

        try:
            bridge = self._bridge_manager.close_bridge(bridge_id, reason)
        except ValueError as exc:
            logger.warning(
                "API: close_bridge failed — bridge_id=%s error=%s",
                bridge_id,
                exc,
            )
            return ApiResponse(status="error", error=str(exc))

        logger.info(
            "API: bridge closed — bridge_id=%s reason=%s",
            bridge_id,
            reason,
        )
        return ApiResponse(status="ok", data=self._bridge_to_detail(bridge))

    def list_bridges_by_team(self, team_id: str) -> ApiResponse:
        """List all bridges for a specific team (as source or target).

        Args:
            team_id: The team identifier.

        Returns:
            ApiResponse with list of bridge summaries for the team.
        """
        if self._bridge_manager is None:
            return ApiResponse(
                status="error",
                error="Bridge management unavailable: bridge_manager not provided.",
            )

        bridges = self._bridge_manager.get_bridges_for_team(team_id)
        bridge_list = [
            {
                "bridge_id": b.bridge_id,
                "bridge_type": b.bridge_type.value,
                "source_team_id": b.source_team_id,
                "target_team_id": b.target_team_id,
                "purpose": b.purpose,
                "status": b.status.value,
                "created_at": b.created_at.isoformat(),
            }
            for b in bridges
        ]
        return ApiResponse(status="ok", data={"bridges": bridge_list})

    def bridge_audit(
        self,
        bridge_id: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ApiResponse:
        """Get the audit trail for a specific bridge.

        Returns entries from the bridge's access_log with optional date
        filtering and pagination.

        Args:
            bridge_id: The bridge to query.
            start_date: Optional ISO date string to filter entries after this date.
            end_date: Optional ISO date string to filter entries before this date.
            limit: Maximum number of records to return (default 100).
            offset: Pagination offset (default 0).

        Returns:
            ApiResponse with filtered and paginated audit entries.
        """
        if self._bridge_manager is None:
            return ApiResponse(
                status="error",
                error="Bridge management unavailable: bridge_manager not provided.",
            )

        bridge = self._bridge_manager.get_bridge(bridge_id)
        if bridge is None:
            logger.warning("bridge_audit: bridge '%s' not found", bridge_id)
            return ApiResponse(
                status="error",
                error=f"Bridge '{bridge_id}' not found",
            )

        entries = list(bridge.access_log)

        # RT12-011: Filter by date range using datetime parsing for correctness
        if start_date:
            from datetime import datetime as _dt

            try:
                start_dt = _dt.fromisoformat(start_date.replace("Z", "+00:00"))
                entries = [
                    e
                    for e in entries
                    if _dt.fromisoformat(e.get("timestamp", "1970-01-01").replace("Z", "+00:00"))
                    >= start_dt
                ]
            except (ValueError, TypeError):
                pass  # Invalid date format — skip filtering
        if end_date:
            from datetime import datetime as _dt

            try:
                end_dt = _dt.fromisoformat(end_date.replace("Z", "+00:00"))
                entries = [
                    e
                    for e in entries
                    if _dt.fromisoformat(e.get("timestamp", "9999-12-31").replace("Z", "+00:00"))
                    <= end_dt
                ]
            except (ValueError, TypeError):
                pass  # Invalid date format — skip filtering

        total = len(entries)
        entries = entries[offset : offset + limit]

        return ApiResponse(
            status="ok",
            data={
                "bridge_id": bridge_id,
                "entries": entries,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )

    # ------------------------------------------------------------------
    # M13 ShadowEnforcer Handlers
    # ------------------------------------------------------------------

    def shadow_metrics(self, agent_id: str) -> ApiResponse:
        """Get shadow enforcement metrics for an agent.

        Returns rolling metrics from the ShadowEnforcer including pass rate,
        block rate, and per-dimension breakdowns.

        Args:
            agent_id: The agent to get shadow metrics for.

        Returns:
            ApiResponse with shadow metrics data, or error if shadow_enforcer
            is not configured or no evaluations exist for the agent.
        """
        if self._shadow_enforcer is None:
            logger.warning("shadow_metrics: shadow_enforcer not configured on PactAPI")
            return ApiResponse(
                status="error",
                error=(
                    "Shadow metrics unavailable: shadow_enforcer not provided "
                    "to PactAPI. Pass shadow_enforcer to enable this endpoint."
                ),
            )

        try:
            metrics = self._shadow_enforcer.get_metrics(agent_id)
        except KeyError as exc:
            logger.warning(
                "shadow_metrics: no evaluations for agent '%s': %s",
                agent_id,
                exc,
            )
            return ApiResponse(status="error", error=str(exc))

        return ApiResponse(
            status="ok",
            data={
                "agent_id": metrics.agent_id,
                "total_evaluations": metrics.total_evaluations,
                "auto_approved_count": metrics.auto_approved_count,
                "flagged_count": metrics.flagged_count,
                "held_count": metrics.held_count,
                "blocked_count": metrics.blocked_count,
                "pass_rate": metrics.pass_rate,
                "block_rate": metrics.block_rate,
                "change_rate": metrics.change_rate,
                "dimension_trigger_counts": dict(metrics.dimension_trigger_counts),
                "window_start": metrics.window_start.isoformat(),
                "window_end": metrics.window_end.isoformat(),
            },
        )

    def shadow_report(self, agent_id: str) -> ApiResponse:
        """Get shadow enforcement posture upgrade report for an agent.

        Generates a report with statistics and upgrade eligibility
        recommendation based on shadow evaluation history.

        Args:
            agent_id: The agent to generate the report for.

        Returns:
            ApiResponse with shadow report data, or error if shadow_enforcer
            is not configured or no evaluations exist for the agent.
        """
        if self._shadow_enforcer is None:
            logger.warning("shadow_report: shadow_enforcer not configured on PactAPI")
            return ApiResponse(
                status="error",
                error=(
                    "Shadow report unavailable: shadow_enforcer not provided "
                    "to PactAPI. Pass shadow_enforcer to enable this endpoint."
                ),
            )

        try:
            report = self._shadow_enforcer.generate_report(agent_id)
        except KeyError as exc:
            logger.warning(
                "shadow_report: no evaluations for agent '%s': %s",
                agent_id,
                exc,
            )
            return ApiResponse(status="error", error=str(exc))

        return ApiResponse(
            status="ok",
            data={
                "agent_id": report.agent_id,
                "evaluation_period_days": report.evaluation_period_days,
                "total_evaluations": report.total_evaluations,
                "pass_rate": report.pass_rate,
                "block_rate": report.block_rate,
                "hold_rate": report.hold_rate,
                "flag_rate": report.flag_rate,
                "dimension_breakdown": dict(report.dimension_breakdown),
                "upgrade_eligible": report.upgrade_eligible,
                "upgrade_blockers": list(report.upgrade_blockers),
                "recommendation": report.recommendation,
            },
        )

    # ------------------------------------------------------------------
    # M42 Upgrade Evidence Handler
    # ------------------------------------------------------------------

    def upgrade_evidence(self, agent_id: str) -> ApiResponse:
        """Get upgrade evidence for an agent's posture upgrade evaluation.

        Combines agent registry data with ShadowEnforcer metrics to provide
        the evidence needed for the PostureUpgradeWizard frontend component.

        The response includes total operations, success rate, ShadowEnforcer
        pass rate, incident count, and an upgrade recommendation based on
        the UPGRADE_REQUIREMENTS from pact_platform.trust.posture.

        Args:
            agent_id: The agent to get upgrade evidence for.

        Returns:
            ApiResponse with upgrade evidence data, or error if the agent
            is not found or the shadow_enforcer is not configured.
        """
        # Validate the agent exists in the registry
        record = self._registry.get(agent_id)
        if record is None:
            logger.warning(
                "upgrade_evidence: agent '%s' not found in registry",
                agent_id,
            )
            return ApiResponse(
                status="error",
                error=f"Agent '{agent_id}' not found in registry",
            )

        # Require shadow_enforcer for metrics
        if self._shadow_enforcer is None:
            logger.warning("upgrade_evidence: shadow_enforcer not configured on PactAPI")
            return ApiResponse(
                status="error",
                error=(
                    "Upgrade evidence unavailable: shadow_enforcer not provided "
                    "to PactAPI. Pass shadow_enforcer to enable this endpoint."
                ),
            )

        # Get shadow metrics for the agent
        try:
            metrics = self._shadow_enforcer.get_metrics(agent_id)
        except KeyError:
            logger.warning(
                "upgrade_evidence: no shadow evaluations for agent '%s'",
                agent_id,
            )
            return ApiResponse(
                status="error",
                error=(
                    f"No shadow evaluation data available for agent '{agent_id}'. "
                    f"The agent must have shadow evaluations to generate upgrade evidence."
                ),
            )

        # Compute total operations and successful operations from shadow metrics
        total_operations = metrics.total_evaluations
        # Successful = auto_approved + flagged (actions that would have passed)
        successful_operations = metrics.auto_approved_count + metrics.flagged_count
        shadow_pass_rate = metrics.pass_rate

        # Incidents = blocked count (actions that would have been denied)
        incidents = metrics.blocked_count

        # Determine the current posture and target posture
        current_posture = record.current_posture

        # Compute target posture (next in the autonomy ladder)
        from pact_platform.build.config.schema import TrustPostureLevel

        posture_ladder = [
            TrustPostureLevel.PSEUDO_AGENT,
            TrustPostureLevel.SUPERVISED,
            TrustPostureLevel.SHARED_PLANNING,
            TrustPostureLevel.CONTINUOUS_INSIGHT,
            TrustPostureLevel.DELEGATED,
        ]
        # Find current posture level in the ladder
        current_level = None
        for level in posture_ladder:
            if level.value == current_posture:
                current_level = level
                break

        if current_level is None:
            # Unknown posture level
            target_posture = None
        else:
            idx = posture_ladder.index(current_level)
            if idx < len(posture_ladder) - 1:
                target_posture = posture_ladder[idx + 1].value
            else:
                target_posture = None  # Already at highest posture

        # Determine recommendation based on UPGRADE_REQUIREMENTS
        recommendation = self._compute_upgrade_recommendation(
            current_level=current_level,
            total_operations=total_operations,
            successful_operations=successful_operations,
            shadow_pass_rate=shadow_pass_rate,
            incidents=incidents,
        )

        return ApiResponse(
            status="ok",
            data={
                "agent_id": agent_id,
                "total_operations": total_operations,
                "successful_operations": successful_operations,
                "shadow_enforcer_pass_rate": shadow_pass_rate,
                "incidents": incidents,
                "recommendation": recommendation,
                "current_posture": current_posture,
                "target_posture": target_posture,
            },
        )

    def _compute_upgrade_recommendation(
        self,
        *,
        current_level: Any,
        total_operations: int,
        successful_operations: int,
        shadow_pass_rate: float,
        incidents: int,
    ) -> str:
        """Compute upgrade recommendation based on UPGRADE_REQUIREMENTS.

        Returns one of: "eligible", "not_eligible", "needs_review".

        Args:
            current_level: The TrustPostureLevel of the agent.
            total_operations: Total operations from shadow evaluations.
            successful_operations: Successfully completed operations.
            shadow_pass_rate: ShadowEnforcer pass rate (0.0 to 1.0).
            incidents: Number of blocked/denied operations.

        Returns:
            A recommendation string.
        """
        from pact_platform.build.config.schema import TrustPostureLevel
        from pact_platform.trust._compat import UPGRADE_REQUIREMENTS

        if current_level is None:
            return "not_eligible"

        # Determine the target posture for upgrade requirements
        posture_ladder = [
            TrustPostureLevel.PSEUDO_AGENT,
            TrustPostureLevel.SUPERVISED,
            TrustPostureLevel.SHARED_PLANNING,
            TrustPostureLevel.CONTINUOUS_INSIGHT,
            TrustPostureLevel.DELEGATED,
        ]

        idx = posture_ladder.index(current_level)
        if idx >= len(posture_ladder) - 1:
            return "not_eligible"  # Already at highest posture

        target_level = posture_ladder[idx + 1]
        requirements = UPGRADE_REQUIREMENTS.get(target_level)
        if requirements is None:
            return "needs_review"

        # Check each requirement
        success_rate = successful_operations / total_operations if total_operations > 0 else 0.0

        blockers = []

        min_ops = requirements.get("min_operations", 0)
        if total_operations < min_ops:
            blockers.append(f"operations ({total_operations} < {min_ops})")

        min_rate = requirements.get("min_success_rate", 0.0)
        if success_rate < min_rate:
            blockers.append(f"success_rate ({success_rate:.2f} < {min_rate:.2f})")

        if requirements.get("shadow_enforcer_required"):
            min_shadow = requirements.get("shadow_pass_rate", 0.0)
            if shadow_pass_rate < min_shadow:
                blockers.append(f"shadow_pass_rate ({shadow_pass_rate:.2f} < {min_shadow:.2f})")

        max_incidents = requirements.get("max_incidents")
        if max_incidents is not None and incidents > max_incidents:
            blockers.append(f"incidents ({incidents} > {max_incidents})")

        if not blockers:
            return "eligible"
        elif len(blockers) <= 1:
            return "needs_review"
        else:
            return "not_eligible"


# Backward-compatible alias (renamed in TODO-0004)
PlatformAPI = PactAPI
