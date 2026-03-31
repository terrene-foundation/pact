# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Decisions API router -- /api/v1/decisions.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from pact_platform.models import db
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.get("")
@limiter.limit(RATE_GET)
async def list_decisions(
    request: Request,
    status: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    decision_type: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """List decisions with optional filters."""
    filt: dict[str, Any] = {}
    if status:
        filt["status"] = status
    if urgency:
        filt["urgency"] = urgency
    if decision_type:
        filt["decision_type"] = decision_type

    records = await db.express.list("AgenticDecision", filt, limit=limit, offset=offset)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}


@router.get("/stats")
@limiter.limit(RATE_GET)
async def get_decision_stats(request: Request) -> dict:
    """Get decision statistics."""
    stats = {}
    for status in ("pending", "approved", "rejected", "expired"):
        stats[status] = await db.express.count("AgenticDecision", {"status": status})
    return {"stats": stats}


@router.get("/{decision_id}")
@limiter.limit(RATE_GET)
async def get_decision(request: Request, decision_id: str) -> dict:
    """Get decision detail."""
    result = await db.express.read("AgenticDecision", decision_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, "Decision not found")
    return result


async def _read_and_validate_pending(decision_id: str) -> dict:
    """Read a decision and verify it is in pending status.

    Raises:
        HTTPException 404: If decision is not found.
        HTTPException 409: If decision is not in pending status.
    """
    result = await db.express.read("AgenticDecision", decision_id)

    if not result or result.get("found") is False:
        raise HTTPException(404, "Decision not found")

    current_status = result.get("status", "")
    if current_status != "pending":
        raise HTTPException(
            409,
            "Decision is not pending. Only pending decisions can be approved or rejected.",
        )

    return result


@router.post("/{decision_id}/approve")
@limiter.limit(RATE_POST)
async def approve_decision(request: Request, decision_id: str, body: dict[str, Any]) -> dict:
    """Approve a pending decision."""
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
@limiter.limit(RATE_POST)
async def reject_decision(request: Request, decision_id: str, body: dict[str, Any]) -> dict:
    """Reject a pending decision."""
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
