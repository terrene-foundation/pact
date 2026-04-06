# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Decisions API router -- /api/v1/decisions.

Uses DataFlow Express API for all CRUD operations.
Supports multi-approver decisions via optional MultiApproverService
injection (Issue #25).
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
from pact_platform.use.services.multi_approver import MultiApproverService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])

_approver_service: MultiApproverService | None = None


def set_approver_service(service: MultiApproverService) -> None:
    """Inject the MultiApproverService for multi-approver decisions."""
    global _approver_service
    _approver_service = service


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
    """Approve a pending decision.

    For multi-approver decisions (required_approvals > 1) with a
    configured MultiApproverService, individual approvals are recorded
    and the decision is only resolved when the threshold is met.

    For single-approver decisions or when no MultiApproverService is
    configured, falls through to direct optimistic-lock update.
    """
    decided_by = body.get("decided_by", "")
    reason = body.get("reason", "")

    if not decided_by:
        raise HTTPException(400, "decided_by is required")
    validate_string_length(decided_by, "decided_by", MAX_SHORT_STRING)
    if reason:
        validate_string_length(reason, "reason", MAX_LONG_STRING)

    # Multi-approver path: delegate to service if available and decision
    # requires more than one approval.
    if _approver_service is not None:
        validate_record_id(decision_id)
        decision = await db.express.read("AgenticDecision", decision_id)
        if not decision or decision.get("found") is False:
            raise HTTPException(404, "Decision not found")
        if decision.get("status") != "pending":
            raise HTTPException(
                409,
                "Decision is not pending. Only pending decisions can be approved or rejected.",
            )

        required = decision.get("required_approvals", 1)
        if required > 1:
            try:
                result = await _approver_service.record_approval(
                    decision_id=decision_id,
                    approver_address=decided_by,
                    approver_identity=decided_by,
                    reason=reason,
                )
            except ValueError as exc:
                raise HTTPException(409, detail=str(exc))

            if result.get("current_approvals", 0) >= required:
                # Quorum met -- update with optimistic lock to prevent
                # concurrent final-approval race (H8 fix)
                recheck = await db.express.read("AgenticDecision", decision_id)
                if (
                    not recheck
                    or recheck.get("found") is False
                    or recheck.get("status") != "pending"
                ):
                    raise HTTPException(
                        409,
                        "Decision was modified concurrently — please retry",
                    )
                current_version = recheck.get("envelope_version", 0)
                await db.express.update(
                    "AgenticDecision",
                    decision_id,
                    {
                        "status": "approved",
                        "decided_by": decided_by,
                        "decision_reason": reason,
                        "decided_at": datetime.now(UTC).isoformat(),
                        "current_approvals": result["current_approvals"],
                        "envelope_version": current_version + 1,
                    },
                )
                updated = await db.express.read("AgenticDecision", decision_id)
                if not updated or updated.get("found") is False:
                    raise HTTPException(500, "Decision update succeeded but read-back failed")
                return updated

            # Partial approval -- return progress
            return {
                "status": "partial_approval",
                "decision_id": decision_id,
                "approval_id": result.get("approval_id", ""),
                "current_approvals": result["current_approvals"],
                "required_approvals": required,
                "message": (
                    f"Approval recorded ({result['current_approvals']}/{required}). "
                    f"Waiting for more approvals."
                ),
            }

    # Single-approver path (or no multi-approver service configured)
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


@router.get("/{decision_id}/approvals")
@limiter.limit(RATE_GET)
async def list_decision_approvals(request: Request, decision_id: str) -> dict:
    """List individual approval records for a decision.

    Returns all ApprovalRecord entries (approved and rejected votes)
    for the given decision, enabling audit trail inspection for
    multi-approver workflows.
    """
    validate_record_id(decision_id)

    # Verify the decision exists
    decision = await db.express.read("AgenticDecision", decision_id)
    if not decision or decision.get("found") is False:
        raise HTTPException(404, "Decision not found")

    records = await db.express.list("ApprovalRecord", {"decision_id": decision_id}, limit=1000)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    return {
        "records": records,
        "count": len(records),
        "decision_id": decision_id,
        "required_approvals": decision.get("required_approvals", 1),
        "current_approvals": decision.get("current_approvals", 0),
    }
