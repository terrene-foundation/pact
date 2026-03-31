# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Decisions API router -- /api/v1/decisions.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from pact_platform.models import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.get("")
async def list_decisions(
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

    records = await db.express.list("AgenticDecision", filt, limit=limit)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit}


@router.get("/stats")
async def get_decision_stats() -> dict:
    """Get decision statistics."""
    stats = {}
    for status in ("pending", "approved", "rejected", "expired"):
        stats[status] = await db.express.count("AgenticDecision", {"status": status})
    return {"stats": stats}


@router.get("/{decision_id}")
async def get_decision(decision_id: str) -> dict:
    """Get decision detail."""
    result = await db.express.read("AgenticDecision", decision_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, f"Decision {decision_id} not found")
    return result


async def _read_and_validate_pending(decision_id: str) -> dict:
    """Read a decision and verify it is in pending status.

    This prevents the approval queue bypass where an already-resolved
    decision (approved, rejected, expired) could be re-approved or
    re-rejected via a direct API call.

    Raises:
        HTTPException 404: If decision is not found.
        HTTPException 409: If decision is not in pending status.
    """
    result = await db.express.read("AgenticDecision", decision_id)

    if not result or result.get("found") is False:
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
async def approve_decision(decision_id: str, body: dict[str, Any]) -> dict:
    """Approve a pending decision.

    Reads the decision first to verify it is still in pending status,
    preventing the approval queue bypass (TOCTOU defense).
    """
    # C2 fix: verify pending status before allowing state transition
    await _read_and_validate_pending(decision_id)

    decided_by = body.get("decided_by", "")
    reason = body.get("reason", "")

    if not decided_by:
        raise HTTPException(400, "decided_by is required")

    return await db.express.update(
        "AgenticDecision",
        decision_id,
        {
            "status": "approved",
            "decided_by": decided_by,
            "decision_reason": reason,
            "decided_at": datetime.now(UTC).isoformat(),
        },
    )


@router.post("/{decision_id}/reject")
async def reject_decision(decision_id: str, body: dict[str, Any]) -> dict:
    """Reject a pending decision.

    Reads the decision first to verify it is still in pending status,
    preventing the approval queue bypass (TOCTOU defense).
    """
    # C2 fix: verify pending status before allowing state transition
    await _read_and_validate_pending(decision_id)

    decided_by = body.get("decided_by", "")
    reason = body.get("reason", "")

    if not decided_by:
        raise HTTPException(400, "decided_by is required")

    return await db.express.update(
        "AgenticDecision",
        decision_id,
        {
            "status": "rejected",
            "decided_by": decided_by,
            "decision_reason": reason,
            "decided_at": datetime.now(UTC).isoformat(),
        },
    )
