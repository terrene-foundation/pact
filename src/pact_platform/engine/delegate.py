# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""GovernedDelegate -- execute_node callback that enforces governance
before allowing GovernedSupervisor to proceed with node execution.

The delegate sits between the supervisor's plan execution loop and the
actual work.  For each node the supervisor wants to execute, the
delegate:

1. Resolves the D/T/R address from context (or uses the fixed role).
2. Calls ``GovernanceEngine.verify_action()`` with the action + context.
3. Routes the verdict:
   - **BLOCKED** -> raises ``GovernanceBlockedError`` (supervisor
     marks node as failed, triggers recovery / escalation).
   - **HELD** -> creates an ``AgenticDecision`` via the
     ``ApprovalBridge``, raises ``GovernanceHeldError`` (supervisor
     parks the node until human resolution).
   - **AUTO_APPROVED / FLAGGED** -> returns a success dict so the
     supervisor proceeds with the node.

Security note (H2): The delegate receives a restricted
``_GovernanceVerifier`` wrapper instead of the full GovernanceEngine.
This prevents the delegate (or any code that receives a reference to
the delegate) from calling mutation methods like ``set_role_envelope()``
or ``grant_clearance()`` on the engine.  Per rules/pact-governance.md
MUST NOT Rule 1: agents must not have access to mutable engine state.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any, Protocol

from pact_platform.models import validate_finite

if TYPE_CHECKING:
    from pact.governance.engine import GovernanceEngine
    from pact_platform.engine.approval_bridge import ApprovalBridge

logger = logging.getLogger(__name__)

__all__ = ["GovernedDelegate"]


class _GovernanceVerifier(Protocol):
    """Read-only interface for governance action verification.

    This protocol defines the minimal surface the GovernedDelegate
    needs from the GovernanceEngine.  The delegate never receives the
    engine directly -- only this restricted interface.
    """

    def verify_action(
        self,
        role_address: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Verify whether an action is permitted under governance."""
        ...


class _VerifierWrapper:
    """Wraps a GovernanceEngine to expose only verify_action().

    This is the enforcement mechanism for H2 (GovernedDelegate
    self-modification prevention).  Even if the delegate stores
    ``self._verifier``, it cannot call engine mutation methods because
    the wrapper does not expose them.

    Args:
        engine: The full GovernanceEngine instance.
    """

    __slots__ = ("_verify_fn",)

    def __init__(self, engine: GovernanceEngine) -> None:
        # Bind only the verify_action method -- no reference to engine
        self._verify_fn = engine.verify_action

    def verify_action(
        self,
        role_address: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        return self._verify_fn(
            role_address=role_address,
            action=action,
            context=context,
        )


class GovernedDelegate:
    """Execute-node callback that enforces governance before execution.

    Designed to be passed as the ``execute_node`` argument to
    ``GovernedSupervisor.run()``.

    The delegate receives a read-only verifier wrapper (not the full
    GovernanceEngine), preventing self-modification attacks where agent
    code could call ``engine.set_role_envelope()`` or
    ``engine.grant_clearance()`` via the delegate reference.

    Args:
        governance_engine: The GovernanceEngine instance for action
            verification.  Internally wrapped to expose only
            ``verify_action()``.
        approval_bridge: The ApprovalBridge for creating AgenticDecision
            records when verdicts are HELD.
        role_address: The D/T/R address of the agent executing the plan.
            Individual nodes may override this via ``context["role_address"]``.
    """

    def __init__(
        self,
        governance_engine: GovernanceEngine,
        approval_bridge: ApprovalBridge,
        role_address: str,
    ) -> None:
        # H2 fix: wrap the engine in a read-only verifier
        self._verifier = _VerifierWrapper(governance_engine)
        self._approval_bridge = approval_bridge
        self._role_address = role_address

    def __call__(
        self,
        node_id: str,
        action: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify governance and return approval status.

        This is the callback signature expected by
        ``GovernedSupervisor.run(execute_node=...)``.

        Args:
            node_id: The plan node identifier being executed.
            action: The action the node wants to perform.
            context: Execution context -- may include ``"cost"``,
                ``"resource"``, ``"role_address"`` (override),
                ``"request_id"``, ``"session_id"``.

        Returns:
            Dict with ``"approved": True``, ``"level"``, and ``"reason"``
            when the action is AUTO_APPROVED or FLAGGED.

        Raises:
            GovernanceBlockedError: When the verdict is BLOCKED.
            GovernanceHeldError: When the verdict is HELD and an
                AgenticDecision has been created for human review.
        """
        # Allow per-node role override from context
        role_addr = context.get("role_address", self._role_address)

        # NaN-guard any cost value before it reaches the governance engine
        cost_val = context.get("cost")
        if cost_val is not None and isinstance(cost_val, (int, float)):
            validate_finite(cost=cost_val)

        daily_total = context.get("daily_total")
        if daily_total is not None and isinstance(daily_total, (int, float)):
            validate_finite(daily_total=daily_total)

        # Verify with governance engine (fail-closed internally)
        verdict = self._verifier.verify_action(
            role_address=role_addr,
            action=action,
            context=context if context else None,
        )

        if verdict.level == "blocked":
            from pact.governance import GovernanceBlockedError

            logger.warning(
                "GovernedDelegate: BLOCKED node='%s' action='%s' role='%s' -- %s",
                node_id,
                action,
                role_addr,
                verdict.reason,
            )
            raise GovernanceBlockedError(verdict)

        if verdict.level == "held":
            # Create AgenticDecision for human approval via the bridge
            decision_id = self._approval_bridge.create_decision(
                role_address=role_addr,
                action=action,
                verdict=verdict,
                request_id=context.get("request_id"),
                session_id=context.get("session_id"),
            )

            from pact.governance import GovernanceHeldError

            logger.info(
                "GovernedDelegate: HELD node='%s' action='%s' role='%s' " "decision_id='%s' -- %s",
                node_id,
                action,
                role_addr,
                decision_id,
                verdict.reason,
            )
            raise GovernanceHeldError(verdict)

        # AUTO_APPROVED or FLAGGED -- proceed
        if verdict.level == "flagged":
            logger.warning(
                "GovernedDelegate: FLAGGED node='%s' action='%s' role='%s' -- %s",
                node_id,
                action,
                role_addr,
                verdict.reason,
            )
        else:
            logger.debug(
                "GovernedDelegate: AUTO_APPROVED node='%s' action='%s' role='%s'",
                node_id,
                action,
                role_addr,
            )

        return {
            "approved": True,
            "level": verdict.level,
            "reason": verdict.reason,
        }
