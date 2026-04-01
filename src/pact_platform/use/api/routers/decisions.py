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

from pact_platform.models import (
    MAX_LONG_STRING,
    MAX_SHORT_STRING,
    db,
    validate_record_id,
    validate_string_length,
)
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
    validate_record_id(decision_id)
    result = await db.express.read("AgenticDecision", decision_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, "Decision not found")
    return result


async def _read_and_validate_pending(decision_id: str) -> dict:
    """Read a decision and verify it is in pending status.

    Raises:
        HTTPException 400: If decision_id is invalid.
        HTTPException 404: If decision is not found.
        HTTPException 409: If decision is not in pending status.
    """
    validate_record_id(decision_id)
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


async def _optimistic_lock_update(
    decision_id: str,
    new_status: str,
    decided_by: str,
    reason: str,
) -> dict:
    """Update a pending decision with optimistic locking on envelope_version.

    1. Read and validate the decision is pending (first read).
    2. Capture the current ``envelope_version``.
    3. Re-read to detect concurrent modification (second read).
    4. Update with ``envelope_version + 1`` only if nothing changed.

    The TOCTOU window between the second read and the update is greatly
    reduced compared to the original single-read pattern, and any concurrent
    mutation is detectable via the version increment.

    Raises:
        HTTPException 404: Decision not found.
        HTTPException 409: Decision was concurrently modified or is no longer pending.
    """
    current = await _read_and_validate_pending(decision_id)
    current_version = current.get("envelope_version", 0)

    # Re-read to narrow the TOCTOU window — detect concurrent modification
    recheck = await db.express.read("AgenticDecision", decision_id)
    if (
        not recheck
        or recheck.get("found") is False
        or recheck.get("status") != "pending"
        or recheck.get("envelope_version", 0) != current_version
    ):
        raise HTTPException(
            409,
            "Decision was modified concurrently — please retry",
        )

    await db.express.update(
        "AgenticDecision",
        decision_id,
        {
            "status": new_status,
            "decided_by": decided_by,
            "decision_reason": reason,
            "decided_at": datetime.now(UTC).isoformat(),
            "envelope_version": current_version + 1,
        },
    )

    # Return the full updated record for the caller
    updated = await db.express.read("AgenticDecision", decision_id)
    if not updated or updated.get("found") is False:
        raise HTTPException(500, "Decision update succeeded but read-back failed")
    return updated


@router.post("/{decision_id}/approve")
@limiter.limit(RATE_POST)
async def approve_decision(request: Request, decision_id: str, body: dict[str, Any]) -> dict:
    """Approve a pending decision with optimistic locking."""
    decided_by = body.get("decided_by", "")
    reason = body.get("reason", "")

    if not decided_by:
        raise HTTPException(400, "decided_by is required")
    validate_string_length(decided_by, "decided_by", MAX_SHORT_STRING)
    if reason:
        validate_string_length(reason, "reason", MAX_LONG_STRING)

    return await _optimistic_lock_update(decision_id, "approved", decided_by, reason)


@router.post("/{decision_id}/reject")
@limiter.limit(RATE_POST)
async def reject_decision(request: Request, decision_id: str, body: dict[str, Any]) -> dict:
    """Reject a pending decision with optimistic locking."""
    decided_by = body.get("decided_by", "")
    reason = body.get("reason", "")

    if not decided_by:
        raise HTTPException(400, "decided_by is required")
    validate_string_length(decided_by, "decided_by", MAX_SHORT_STRING)
    if reason:
        validate_string_length(reason, "reason", MAX_LONG_STRING)

    return await _optimistic_lock_update(decision_id, "rejected", decided_by, reason)
