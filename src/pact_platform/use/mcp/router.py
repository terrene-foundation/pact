# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""FastAPI router for MCP governance endpoints.

Provides POST /api/v1/mcp/evaluate — evaluates an MCP tool call against
governance and returns a verdict dict.

Usage:
    from pact_platform.use.mcp.router import create_mcp_router

    router = create_mcp_router()
    app.include_router(router, prefix="/api/v1/mcp")
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from pact.mcp import McpAuditTrail, McpGovernanceConfig, McpGovernanceEnforcer, McpToolPolicy
from pact.mcp.enforcer import DefaultPolicy, McpActionContext

logger = logging.getLogger(__name__)

__all__ = ["create_mcp_router"]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class McpEvaluateRequest(BaseModel):
    """Request body for POST /api/v1/mcp/evaluate."""

    tool_name: str = Field(..., description="Name of the MCP tool to evaluate")
    args: dict[str, Any] = Field(default_factory=dict, description="Tool call arguments")
    agent_address: str = Field(..., description="D/T/R address of the calling agent")


class McpEvaluateResponse(BaseModel):
    """Response body for POST /api/v1/mcp/evaluate."""

    level: str = Field(..., description="Verdict: auto_approved, flagged, held, or blocked")
    tool_name: str = Field(..., description="Tool that was evaluated")
    agent_address: str = Field(..., description="Agent that requested the call")
    reason: str = Field(..., description="Human-readable reason for the verdict")
    timestamp: str = Field(..., description="ISO-8601 timestamp of the evaluation")
    policy_snapshot: dict[str, Any] | None = Field(
        default=None, description="Policy state at evaluation time"
    )


# ---------------------------------------------------------------------------
# Module-level enforcer (default-deny, no tools registered)
# ---------------------------------------------------------------------------

_enforcer: McpGovernanceEnforcer | None = None
_audit_trail: McpAuditTrail | None = None


def _get_enforcer() -> tuple[McpGovernanceEnforcer, McpAuditTrail]:
    """Return or create the module-level enforcer and audit trail.

    The default enforcer uses DENY policy with no registered tools,
    meaning all tool calls are blocked until tools are explicitly registered
    via ``PlatformMcpGovernance``.
    """
    global _enforcer, _audit_trail
    if _enforcer is None:
        config = McpGovernanceConfig(default_policy=DefaultPolicy.DENY)
        _enforcer = McpGovernanceEnforcer(config)
        _audit_trail = McpAuditTrail()
    return _enforcer, _audit_trail


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def create_mcp_router() -> APIRouter:
    """Create a FastAPI router with MCP governance endpoints.

    Returns:
        APIRouter with POST /evaluate mounted.
    """
    router = APIRouter(tags=["mcp"])

    @router.post("/evaluate", response_model=McpEvaluateResponse)
    async def evaluate_tool_call(request: McpEvaluateRequest) -> McpEvaluateResponse:
        """Evaluate an MCP tool call against governance.

        Returns a verdict (auto_approved, flagged, held, or blocked) with
        a human-readable reason. Uses default-deny policy: unregistered
        tools are blocked.
        """
        enforcer, audit_trail = _get_enforcer()

        context = McpActionContext(
            tool_name=request.tool_name,
            args=request.args,
            agent_id=request.agent_address,
        )

        decision = enforcer.check_tool_call(context)

        # Record in audit trail
        audit_trail.record(
            tool_name=request.tool_name,
            agent_id=request.agent_address,
            decision=decision.level,
            reason=decision.reason,
        )

        if decision.level == "blocked":
            logger.warning(
                "MCP evaluate: blocked tool=%s agent=%s reason=%s",
                request.tool_name,
                request.agent_address,
                decision.reason,
            )
        else:
            logger.info(
                "MCP evaluate: %s tool=%s agent=%s",
                decision.level,
                request.tool_name,
                request.agent_address,
            )

        return McpEvaluateResponse(
            level=decision.level,
            tool_name=decision.tool_name,
            agent_address=request.agent_address,
            reason=decision.reason,
            timestamp=decision.timestamp.isoformat(),
            policy_snapshot=decision.policy_snapshot,
        )

    return router
