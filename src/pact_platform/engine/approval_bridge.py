# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""ApprovalBridge — connects HELD verdicts to the DataFlow-backed
approval queue.

When the GovernanceEngine returns a HELD verdict (action near a soft
limit, requiring human judgment), the ApprovalBridge persists an
``AgenticDecision`` record via DataFlow.  This record appears in the
platform's approval queue (dashboard and API), where a human can
approve or reject it.

The bridge also provides ``approve()`` and ``reject()`` methods for
resolving pending decisions, which update the record and log the
resolution for audit.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pact_platform.models import validate_finite

if TYPE_CHECKING:
    from dataflow import DataFlow
    from pact.governance import GovernanceVerdict

logger = logging.getLogger(__name__)

__all__ = ["ApprovalBridge"]


class ApprovalBridge:
    """Creates and resolves AgenticDecisions when governance returns HELD.

    Args:
        db: DataFlow instance for persistence (from ``pact_platform.models``).
    """

    def __init__(self, db: DataFlow) -> None:
        self._db = db

    def create_decision(
        self,
        role_address: str,
        action: str,
        verdict: GovernanceVerdict,
        request_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Create an AgenticDecision from a HELD verdict.

        Persists the decision record in DataFlow so it appears in the
        platform's approval queue.

        Args:
            role_address: The D/T/R address of the agent whose action
                was held.
            action: The action that triggered the HELD verdict.
            verdict: The full GovernanceVerdict from the engine.
            request_id: Optional AgenticRequest ID for linking.
            session_id: Optional AgenticWorkSession ID for linking.

        Returns:
            The generated decision ID (``"dec-XXXXXXXXXXXX"``).
        """
        decision_id = f"dec-{uuid4().hex[:12]}"
        now_iso = datetime.now(UTC).isoformat()

        # Extract constraint dimension from audit details if available
        constraint_dimension = ""
        constraint_details: dict[str, Any] = {}
        audit = verdict.audit_details or {}
        if "dimension" in audit:
            constraint_dimension = str(audit["dimension"])
        if "constraint_details" in audit:
            constraint_details = dict(audit["constraint_details"])

        # Extract envelope version for TOCTOU defense
        envelope_version = 0
        if verdict.envelope_version:
            try:
                envelope_version = int(verdict.envelope_version)
            except (ValueError, TypeError):
                envelope_version = 0

        # NaN-guard any numeric values in the constraint details
        for key, val in constraint_details.items():
            if isinstance(val, (int, float)):
                if not math.isfinite(float(val)):
                    raise ValueError(
                        f"Constraint detail '{key}' must be finite, got {val!r}. "
                        f"NaN/Inf values bypass governance checks."
                    )

        wf = self._db.create_workflow("create_hold_decision")
        self._db.add_node(
            wf,
            "AgenticDecision",
            "Create",
            "create_decision",
            {
                "id": decision_id,
                "request_id": request_id or "",
                "session_id": session_id or "",
                "agent_address": role_address,
                "action": action,
                "decision_type": "governance_hold",
                "status": "pending",
                "reason_held": verdict.reason,
                "constraint_dimension": constraint_dimension,
                "constraint_details": constraint_details,
                "urgency": "normal",
                "envelope_version": envelope_version,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
        )
        self._db.execute_workflow(wf)

        logger.info(
            "ApprovalBridge: created HELD decision '%s' for role='%s' "
            "action='%s' — %s",
            decision_id,
            role_address,
            action,
            verdict.reason,
        )

        return decision_id

    def approve(
        self,
        decision_id: str,
        decided_by: str,
        reason: str,
    ) -> None:
        """Approve a pending decision.

        Updates the AgenticDecision status to ``"approved"`` and records
        who approved it and why.

        Args:
            decision_id: The decision to approve.
            decided_by: Identifier of the human/role who approved.
            reason: Explanation for the approval.

        Raises:
            ValueError: If decision_id is empty.
        """
        if not decision_id:
            raise ValueError("decision_id must not be empty")
        if not decided_by:
            raise ValueError("decided_by must not be empty")

        now_iso = datetime.now(UTC).isoformat()

        wf = self._db.create_workflow("approve_decision")
        self._db.add_node(
            wf,
            "AgenticDecision",
            "Update",
            "approve",
            {
                "filter": {"id": decision_id},
                "fields": {
                    "status": "approved",
                    "decided_by": decided_by,
                    "decided_at": now_iso,
                    "decision_reason": reason,
                    "updated_at": now_iso,
                },
            },
        )
        self._db.execute_workflow(wf)

        logger.info(
            "ApprovalBridge: APPROVED decision '%s' by '%s' — %s",
            decision_id,
            decided_by,
            reason,
        )

    def reject(
        self,
        decision_id: str,
        decided_by: str,
        reason: str,
    ) -> None:
        """Reject a pending decision.

        Updates the AgenticDecision status to ``"rejected"`` and records
        who rejected it and why.

        Args:
            decision_id: The decision to reject.
            decided_by: Identifier of the human/role who rejected.
            reason: Explanation for the rejection.

        Raises:
            ValueError: If decision_id is empty.
        """
        if not decision_id:
            raise ValueError("decision_id must not be empty")
        if not decided_by:
            raise ValueError("decided_by must not be empty")

        now_iso = datetime.now(UTC).isoformat()

        wf = self._db.create_workflow("reject_decision")
        self._db.add_node(
            wf,
            "AgenticDecision",
            "Update",
            "reject",
            {
                "filter": {"id": decision_id},
                "fields": {
                    "status": "rejected",
                    "decided_by": decided_by,
                    "decided_at": now_iso,
                    "decision_reason": reason,
                    "updated_at": now_iso,
                },
            },
        )
        self._db.execute_workflow(wf)

        logger.info(
            "ApprovalBridge: REJECTED decision '%s' by '%s' — %s",
            decision_id,
            decided_by,
            reason,
        )

    def get_pending(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve pending decisions for the approval queue.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of AgenticDecision dicts with ``status == "pending"``.
        """
        wf = self._db.create_workflow("list_pending_decisions")
        self._db.add_node(
            wf,
            "AgenticDecision",
            "List",
            "list_pending",
            {
                "filter": {"status": "pending"},
                "limit": limit,
            },
        )
        results, _ = self._db.execute_workflow(wf)
        records = results.get("list_pending", {}).get("records", [])
        return records
