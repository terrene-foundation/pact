# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Request routing service — governance-gated dispatch to pools/agents.

Routes incoming requests through the GovernanceEngine before assigning
work.  BLOCKED actions are rejected immediately; HELD actions create an
AgenticDecision record for human review; AUTO_APPROVED / FLAGGED actions
are dispatched to the target pool.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pact_platform.models import db, validate_finite

if TYPE_CHECKING:
    from dataflow import DataFlow
    from pact.governance.engine import GovernanceEngine

logger = logging.getLogger(__name__)

__all__ = ["RequestRouterService"]


class RequestRouterService:
    """Routes requests through governance verification before pool dispatch.

    Args:
        db: DataFlow instance for persistence.
        governance_engine: Optional GovernanceEngine.  When ``None``,
            governance verification is skipped and requests are approved
            unconditionally.
    """

    def __init__(
        self,
        db: DataFlow,
        governance_engine: GovernanceEngine | None = None,
    ) -> None:
        self._db = db
        self._governance_engine = governance_engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route_request(
        self,
        request_id: str,
        org_address: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Route a request through governance and dispatch.

        1. If a governance engine is configured, call ``verify_action()``.
        2. Map the verdict to the appropriate outcome:
           - **blocked** -> reject immediately.
           - **held** -> persist an ``AgenticDecision`` for human review.
           - **auto_approved** / **flagged** -> assign to pool.
        3. If no governance engine is set, treat as auto-approved.

        Args:
            request_id: Existing ``AgenticRequest.id``.
            org_address: D/T/R address of the requesting role.
            action: The action being performed (e.g. ``"write"``).
            context: Optional context dict forwarded to governance
                (may include ``"cost"``, ``"resource"``, etc.).

        Returns:
            A dict describing the routing outcome.  Always contains
            ``"status"`` (``"blocked"``, ``"held"``, or ``"approved"``).

        Raises:
            ValueError: If *request_id* or *org_address* is empty.
        """
        if not request_id:
            raise ValueError("request_id must not be empty")
        if not org_address:
            raise ValueError("org_address must not be empty")

        ctx = context or {}

        # NaN-guard any cost value in the context before it reaches governance
        cost_val = ctx.get("cost")
        if cost_val is not None:
            validate_finite(cost=cost_val)

        # ----- Governance verification -----
        if self._governance_engine is not None:
            try:
                verdict = self._governance_engine.verify_action(
                    role_address=org_address,
                    action=action,
                    context=ctx if ctx else None,
                )
            except Exception:
                # Fail-closed: treat engine errors as BLOCKED
                logger.exception(
                    "Governance engine error for request %s — fail-closed to BLOCKED",
                    request_id,
                )
                return {
                    "status": "blocked",
                    "reason": "Governance engine internal error — fail-closed",
                    "request_id": request_id,
                }

            level = verdict.level

            if level == "blocked":
                logger.info(
                    "Request %s BLOCKED by governance: %s",
                    request_id,
                    verdict.reason,
                )
                return {
                    "status": "blocked",
                    "reason": verdict.reason,
                    "request_id": request_id,
                }

            if level == "held":
                decision_id = self._create_hold_decision(
                    request_id=request_id,
                    org_address=org_address,
                    action=action,
                    reason=verdict.reason,
                    envelope_version=verdict.envelope_version,
                )
                logger.info(
                    "Request %s HELD for approval (decision %s): %s",
                    request_id,
                    decision_id,
                    verdict.reason,
                )
                return {
                    "status": "held",
                    "decision_id": decision_id,
                    "reason": verdict.reason,
                    "request_id": request_id,
                }

            # auto_approved or flagged — fall through to assignment
            if level == "flagged":
                logger.warning(
                    "Request %s FLAGGED (proceeding): %s",
                    request_id,
                    verdict.reason,
                )

        # ----- Assign to pool -----
        pool_id = self._assign_to_pool(request_id, org_address)

        return {
            "status": "approved",
            "assigned_to": pool_id,
            "request_id": request_id,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _create_hold_decision(
        self,
        request_id: str,
        org_address: str,
        action: str,
        reason: str,
        envelope_version: str,
    ) -> str:
        """Persist an ``AgenticDecision`` for a HELD verdict."""
        decision_id = f"dec-{uuid4().hex[:12]}"

        wf = self._db.create_workflow("create_hold_decision")
        self._db.add_node(
            wf,
            "AgenticDecision",
            "Create",
            "create_decision",
            {
                "id": decision_id,
                "request_id": request_id,
                "agent_address": org_address,
                "action": action,
                "decision_type": "governance_hold",
                "status": "pending",
                "reason_held": reason,
                "urgency": "normal",
                "envelope_version": int(envelope_version) if envelope_version else 0,
            },
        )
        self._db.execute_workflow(wf)
        return decision_id

    def _assign_to_pool(self, request_id: str, org_address: str) -> str:
        """Find an active pool matching *org_address* and assign the request.

        If no pool is found, a transient ``"unassigned"`` pool id is returned
        so the caller can still proceed.
        """
        # Look up active pools for the org (best-effort match on org_id
        # prefix from the address).  The org_id is the first segment of the
        # address.
        org_id = org_address.split("-")[0] if "-" in org_address else org_address

        wf = self._db.create_workflow("find_pool")
        self._db.add_node(
            wf,
            "AgenticPool",
            "List",
            "list_pools",
            {"filter": {"org_id": org_id, "status": "active"}, "limit": 1},
        )
        results, _ = self._db.execute_workflow(wf)

        pool_data = results.get("list_pools", {})
        records = pool_data.get("records", [])

        if not records:
            logger.warning(
                "No active pool found for org_id=%s; request %s unassigned",
                org_id,
                request_id,
            )
            return "unassigned"

        pool_id = records[0]["id"]

        # Update the request's assignment
        wf2 = self._db.create_workflow("assign_request")
        self._db.add_node(
            wf2,
            "AgenticRequest",
            "Update",
            "assign",
            {
                "filter": {"id": request_id},
                "fields": {
                    "assigned_to": pool_id,
                    "assigned_type": "pool",
                    "status": "assigned",
                },
            },
        )
        self._db.execute_workflow(wf2)

        return pool_id
