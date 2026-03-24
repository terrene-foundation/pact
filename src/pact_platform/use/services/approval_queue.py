# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""DataFlow-backed approval queue for governance HELD actions.

Provides persistent storage for approval decisions with urgency-based
filtering and stale-decision expiry.  Every mutation flows through
DataFlow workflows for full audit trail.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from dataflow import DataFlow

logger = logging.getLogger(__name__)

__all__ = ["ApprovalQueueService"]


class ApprovalQueueService:
    """Persistent approval queue backed by the ``AgenticDecision`` model.

    Args:
        db: DataFlow instance.
    """

    def __init__(self, db: DataFlow) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit(
        self,
        request_id: str,
        session_id: str,
        agent_address: str,
        action: str,
        reason: str,
        constraint_dimension: str = "",
        urgency: str = "normal",
        envelope_version: int = 0,
    ) -> str:
        """Create a new ``AgenticDecision`` in ``pending`` status.

        Args:
            request_id: The request that triggered the hold.
            session_id: Active work session (may be empty).
            agent_address: D/T/R address of the agent.
            action: The action that was held.
            reason: Why governance held the action.
            constraint_dimension: Which constraint dimension triggered the
                hold (``financial``, ``operational``, etc.).
            urgency: ``low``, ``normal``, ``high``, or ``critical``.
            envelope_version: Envelope version for TOCTOU defense.

        Returns:
            The new decision ID.

        Raises:
            ValueError: On empty *agent_address* or *action*.
        """
        if not agent_address:
            raise ValueError("agent_address must not be empty")
        if not action:
            raise ValueError("action must not be empty")

        decision_id = f"dec-{uuid4().hex[:12]}"
        now_iso = datetime.now(UTC).isoformat()

        wf = self._db.create_workflow("submit_decision")
        self._db.add_node(
            wf,
            "AgenticDecision",
            "Create",
            "create",
            {
                "id": decision_id,
                "request_id": request_id,
                "session_id": session_id,
                "agent_address": agent_address,
                "action": action,
                "decision_type": "governance_hold",
                "status": "pending",
                "reason_held": reason,
                "constraint_dimension": constraint_dimension,
                "urgency": urgency,
                "envelope_version": envelope_version,
            },
        )
        self._db.execute_workflow(wf)

        logger.info(
            "Decision %s submitted (agent=%s action=%s urgency=%s)",
            decision_id,
            agent_address,
            action,
            urgency,
        )
        return decision_id

    # ------------------------------------------------------------------
    # Approve / Reject
    # ------------------------------------------------------------------

    def approve(
        self,
        decision_id: str,
        decided_by: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve a pending decision.

        Args:
            decision_id: The decision to approve.
            decided_by: Identity of the approver.
            reason: Optional reason for the approval.

        Returns:
            Dict with the updated decision fields.

        Raises:
            ValueError: If the decision is not found or not pending.
        """
        return self._resolve(decision_id, decided_by, "approved", reason)

    def reject(
        self,
        decision_id: str,
        decided_by: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject a pending decision.

        Args:
            decision_id: The decision to reject.
            decided_by: Identity of the reviewer.
            reason: Optional reason for the rejection.

        Returns:
            Dict with the updated decision fields.

        Raises:
            ValueError: If the decision is not found or not pending.
        """
        return self._resolve(decision_id, decided_by, "rejected", reason)

    # ------------------------------------------------------------------
    # Expiry
    # ------------------------------------------------------------------

    def expire_stale(self, max_age_hours: int = 24) -> int:
        """Mark pending decisions older than *max_age_hours* as expired.

        Args:
            max_age_hours: Maximum age before a pending decision is expired.

        Returns:
            The number of decisions that were expired.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        cutoff_iso = cutoff.isoformat()

        # Fetch all pending decisions
        wf = self._db.create_workflow("list_stale")
        self._db.add_node(
            wf,
            "AgenticDecision",
            "List",
            "stale",
            {"filter": {"status": "pending"}, "limit": 10000},
        )
        results, _ = self._db.execute_workflow(wf)
        records = results.get("stale", {}).get("records", [])

        expired_count = 0
        for record in records:
            created_at_str = record.get("created_at", "")
            if not created_at_str:
                continue
            # Compare ISO timestamps lexicographically (works for ISO 8601)
            if created_at_str < cutoff_iso:
                now_iso = datetime.now(UTC).isoformat()
                wf_expire = self._db.create_workflow("expire_decision")
                self._db.add_node(
                    wf_expire,
                    "AgenticDecision",
                    "Update",
                    "expire",
                    {
                        "filter": {"id": record["id"]},
                        "fields": {
                            "status": "expired",
                            "decided_at": now_iso,
                            "decision_reason": f"Expired after {max_age_hours}h",
                        },
                    },
                )
                self._db.execute_workflow(wf_expire)
                expired_count += 1
                logger.info("Decision %s expired (age > %dh)", record["id"], max_age_hours)

        return expired_count

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_pending(self, urgency: str | None = None) -> list[dict[str, Any]]:
        """List all pending decisions, optionally filtered by urgency.

        Args:
            urgency: If provided, only return decisions with this urgency.

        Returns:
            List of decision dicts.
        """
        filter_params: dict[str, Any] = {"status": "pending"}
        if urgency is not None:
            filter_params["urgency"] = urgency

        wf = self._db.create_workflow("list_pending")
        self._db.add_node(
            wf,
            "AgenticDecision",
            "List",
            "pending",
            {"filter": filter_params, "limit": 1000},
        )
        results, _ = self._db.execute_workflow(wf)
        return results.get("pending", {}).get("records", [])

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve(
        self,
        decision_id: str,
        decided_by: str,
        new_status: str,
        reason: str,
    ) -> dict[str, Any]:
        """Transition a pending decision to *new_status*.

        Reads the current decision, validates it is pending, then updates.

        Raises:
            ValueError: If the decision is not found or not in ``pending`` status.
        """
        if not decision_id:
            raise ValueError("decision_id must not be empty")
        if not decided_by:
            raise ValueError("decided_by must not be empty")

        # Read current state
        wf_read = self._db.create_workflow("read_decision")
        self._db.add_node(
            wf_read,
            "AgenticDecision",
            "Read",
            "read",
            {"id": decision_id},
        )
        results, _ = self._db.execute_workflow(wf_read)
        record = results.get("read", {})

        if not record.get("found", False) and not record.get("id"):
            raise ValueError(f"Decision '{decision_id}' not found")

        current_status = record.get("status", "")
        if current_status != "pending":
            raise ValueError(
                f"Decision '{decision_id}' is not pending (current status: {current_status})"
            )

        # Update
        now_iso = datetime.now(UTC).isoformat()
        wf_update = self._db.create_workflow("resolve_decision")
        self._db.add_node(
            wf_update,
            "AgenticDecision",
            "Update",
            "update",
            {
                "filter": {"id": decision_id},
                "fields": {
                    "status": new_status,
                    "decided_by": decided_by,
                    "decided_at": now_iso,
                    "decision_reason": reason,
                },
            },
        )
        self._db.execute_workflow(wf_update)

        logger.info(
            "Decision %s %s by %s: %s",
            decision_id,
            new_status,
            decided_by,
            reason,
        )
        return {
            "decision_id": decision_id,
            "status": new_status,
            "decided_by": decided_by,
            "decided_at": now_iso,
            "reason": reason,
        }
