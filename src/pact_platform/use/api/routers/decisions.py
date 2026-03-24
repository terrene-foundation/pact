# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Decisions API router -- /api/v1/decisions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from pact_platform.models import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


def _exec(wf) -> dict:
    results, _ = db.execute_workflow(wf)
    return results


@router.get("")
def list_decisions(
    status: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    decision_type: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
) -> dict:
    """List decisions with optional filters."""
    filt: dict[str, Any] = {}
    if status:
        filt["status"] = status
    if urgency:
        filt["urgency"] = urgency
    if decision_type:
        filt["decision_type"] = decision_type

    wf = db.create_workflow()
    wf.add_node(
        "AgenticDecisionListNode",
        "list",
        {
            "filter": filt,
            "limit": limit,
            "order_by": ["-created_at"],
        },
    )
    return _exec(wf)["list"]


@router.get("/stats")
def get_decision_stats() -> dict:
    """Get decision statistics."""
    stats = {}
    for status in ("pending", "approved", "rejected", "expired"):
        wf = db.create_workflow()
        wf.add_node(
            "AgenticDecisionListNode",
            "list",
            {
                "filter": {"status": status},
                "limit": 0,
            },
        )
        result = _exec(wf)["list"]
        stats[status] = result.get("total", len(result.get("records", [])))
    return {"stats": stats}


@router.get("/{decision_id}")
def get_decision(decision_id: str) -> dict:
    """Get decision detail."""
    wf = db.create_workflow()
    wf.add_node("AgenticDecisionReadNode", "read", {"id": decision_id})
    result = _exec(wf)["read"]
    if not result or result.get("found") is False or result.get("failed"):
        raise HTTPException(404, f"Decision {decision_id} not found")
    return result


def _read_and_validate_pending(decision_id: str) -> dict:
    """Read a decision and verify it is in pending status.

    This prevents the approval queue bypass where an already-resolved
    decision (approved, rejected, expired) could be re-approved or
    re-rejected via a direct API call.

    Raises:
        HTTPException 404: If decision is not found.
        HTTPException 409: If decision is not in pending status.
    """
    wf = db.create_workflow()
    wf.add_node("AgenticDecisionReadNode", "read", {"id": decision_id})
    result = _exec(wf)["read"]

    if not result or result.get("found") is False or result.get("failed"):
        raise HTTPException(404, f"Decision {decision_id} not found")

    current_status = result.get("status", "")
    if current_status != "pending":
        raise HTTPException(
            409,
            f"Decision {decision_id} is not pending "
            f"(current status: {current_status}). "
            f"Only pending decisions can be approved or rejected.",
        )

    return result


@router.post("/{decision_id}/approve")
def approve_decision(decision_id: str, body: dict[str, Any]) -> dict:
    """Approve a pending decision.

    Reads the decision first to verify it is still in pending status,
    preventing the approval queue bypass (TOCTOU defense).
    """
    # C2 fix: verify pending status before allowing state transition
    _read_and_validate_pending(decision_id)

    decided_by = body.get("decided_by", "")
    reason = body.get("reason", "")

    if not decided_by:
        raise HTTPException(400, "decided_by is required")

    wf = db.create_workflow()
    wf.add_node(
        "AgenticDecisionUpdateNode",
        "update",
        {
            "filter": {"id": decision_id},
            "fields": {
                "status": "approved",
                "decided_by": decided_by,
                "decision_reason": reason,
                "decided_at": datetime.now(UTC).isoformat(),
            },
        },
    )
    return _exec(wf)["update"]


@router.post("/{decision_id}/reject")
def reject_decision(decision_id: str, body: dict[str, Any]) -> dict:
    """Reject a pending decision.

    Reads the decision first to verify it is still in pending status,
    preventing the approval queue bypass (TOCTOU defense).
    """
    # C2 fix: verify pending status before allowing state transition
    _read_and_validate_pending(decision_id)

    decided_by = body.get("decided_by", "")
    reason = body.get("reason", "")

    if not decided_by:
        raise HTTPException(400, "decided_by is required")

    wf = db.create_workflow()
    wf.add_node(
        "AgenticDecisionUpdateNode",
        "update",
        {
            "filter": {"id": decision_id},
            "fields": {
                "status": "rejected",
                "decided_by": decided_by,
                "decision_reason": reason,
                "decided_at": datetime.now(UTC).isoformat(),
            },
        },
    )
    return _exec(wf)["update"]
