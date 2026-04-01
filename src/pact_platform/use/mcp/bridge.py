# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Platform MCP governance bridge.

Bridges the L1 ``pact.mcp.McpGovernanceEnforcer`` to the platform's
governance config by:

1. Accepting org-level tool policies and configuring the L1 enforcer
2. Providing ``evaluate_tool_call()`` that delegates to L1 and wraps
   the result with platform-level audit logging
3. Maintaining an ``McpAuditTrail`` for inspection and export

Architecture::

    Platform (L3)                          L1 (pact.mcp)
    +-------------------------------+      +---------------------------+
    | PlatformMcpGovernance         |      | McpGovernanceEnforcer     |
    |   .evaluate_tool_call()  -----|----->|   .check_tool_call()      |
    |   .get_audit_trail()          |      | McpAuditTrail             |
    |   .status()                   |      | McpToolPolicy             |
    +-------------------------------+      +---------------------------+

Usage:
    from pact_platform.use.mcp.bridge import PlatformMcpGovernance

    gov = PlatformMcpGovernance(
        engine=governance_engine,
        tool_policies=[
            {"tool_name": "web_search", "clearance_required": "public"},
            {"tool_name": "db_write", "clearance_required": "confidential"},
        ],
    )

    result = gov.evaluate_tool_call("web_search", {"query": "test"}, "D1-R1")
    # {"level": "auto_approved", "tool_name": "web_search", ...}
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pact.mcp import McpAuditTrail, McpGovernanceConfig, McpGovernanceEnforcer, McpToolPolicy
from pact.mcp.enforcer import DefaultPolicy, McpActionContext

_TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")

logger = logging.getLogger(__name__)

__all__ = ["PlatformMcpGovernance"]


class PlatformMcpGovernance:
    """Bridge between the platform governance config and the L1 MCP enforcer.

    Takes an org config's tool policies and configures the L1
    ``McpGovernanceEnforcer``. Provides ``evaluate_tool_call()`` that
    delegates to L1 and wraps results with platform audit logging.

    Args:
        engine: A GovernanceEngine instance. Required (raises ValueError if None).
        tool_policies: List of tool policy dicts, each with at least
            ``tool_name`` and optionally ``clearance_required``, ``max_cost``,
            ``allowed_args``, ``denied_args``, ``rate_limit``, ``description``.

    Raises:
        ValueError: If engine is None.
    """

    def __init__(
        self,
        engine: Any,
        tool_policies: list[dict[str, Any]],
    ) -> None:
        if engine is None:
            raise ValueError(
                "PlatformMcpGovernance requires a governance engine instance; "
                "received None. Load an org first."
            )

        self._engine = engine
        self._config = McpGovernanceConfig(default_policy=DefaultPolicy.DENY)
        self._enforcer = McpGovernanceEnforcer(self._config)
        self._audit_trail = McpAuditTrail()
        self._registered_tool_names: set[str] = set()

        # Register tool policies from org config
        for policy_dict in tool_policies:
            tool_name = policy_dict["tool_name"]
            if not tool_name or not _TOOL_NAME_RE.match(tool_name):
                raise ValueError(
                    f"Invalid MCP tool name '{tool_name}': must match "
                    f"[a-zA-Z0-9_.-]+ (no path separators, spaces, or special characters)"
                )
            policy = McpToolPolicy(
                tool_name=tool_name,
                clearance_required=policy_dict.get("clearance_required"),
                max_cost=policy_dict.get("max_cost"),
                allowed_args=frozenset(policy_dict.get("allowed_args", [])),
                denied_args=frozenset(policy_dict.get("denied_args", [])),
                rate_limit=policy_dict.get("rate_limit"),
                description=policy_dict.get("description", ""),
            )
            self._enforcer.register_tool(policy)
            self._registered_tool_names.add(tool_name)
            logger.debug("Registered MCP tool policy: %s", tool_name)

    @property
    def engine(self) -> Any:
        """Return the underlying GovernanceEngine."""
        return self._engine

    def is_configured(self) -> bool:
        """Return True if MCP governance is configured and ready."""
        return self._engine is not None

    def registered_tools(self) -> set[str]:
        """Return the set of registered tool names."""
        return set(self._registered_tool_names)

    def evaluate_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        agent_address: str,
    ) -> dict[str, Any]:
        """Evaluate an MCP tool call against governance.

        Delegates to the L1 ``McpGovernanceEnforcer.check_tool_call()``
        and wraps the result with platform-level audit logging.

        Args:
            tool_name: Name of the MCP tool being invoked.
            args: Arguments passed to the tool.
            agent_address: D/T/R address of the calling agent.

        Returns:
            Dict with keys: level, tool_name, agent_address, reason, timestamp,
            and optionally policy_snapshot.
        """
        context = McpActionContext(
            tool_name=tool_name,
            args=args,
            agent_id=agent_address,
        )

        decision = self._enforcer.check_tool_call(context)

        # Record in L1 audit trail
        self._audit_trail.record(
            tool_name=tool_name,
            agent_id=agent_address,
            decision=decision.level,
            reason=decision.reason,
        )

        # Platform-level audit logging
        if decision.level == "blocked":
            logger.warning(
                "MCP tool call blocked: tool=%s agent=%s reason=%s",
                tool_name,
                agent_address,
                decision.reason,
            )
        else:
            logger.info(
                "MCP tool call %s: tool=%s agent=%s",
                decision.level,
                tool_name,
                agent_address,
            )

        return {
            "level": decision.level,
            "tool_name": decision.tool_name,
            "agent_address": agent_address,
            "reason": decision.reason,
            "timestamp": decision.timestamp.isoformat(),
            "policy_snapshot": decision.policy_snapshot,
        }

    def get_audit_trail(self) -> list[dict[str, Any]]:
        """Return the MCP audit trail as a list of dicts.

        Returns:
            List of audit entry dicts, each with tool_name, agent_id,
            decision, reason, timestamp.
        """
        entries = self._audit_trail.to_list()
        return [
            {
                "tool_name": e.tool_name,
                "agent_id": e.agent_id,
                "decision": e.decision,
                "reason": e.reason,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in entries
        ]

    def status(self) -> dict[str, Any]:
        """Return MCP governance status information.

        Returns:
            Dict with configured, tool_count, org_name, registered_tools.
        """
        return {
            "configured": self.is_configured(),
            "tool_count": len(self._registered_tool_names),
            "org_name": getattr(self._engine, "org_name", "unknown"),
            "registered_tools": sorted(self._registered_tool_names),
        }
