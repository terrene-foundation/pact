# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reviews API router — /api/v1/reviews.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from pact_platform.models import (
    MAX_LONG_STRING,
    MAX_SHORT_STRING,
    db,
    validate_record_id,
    validate_string_length,
)
from pact_platform.use.api.governance import governance_gate, is_governance_active
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


async def _resolve_review_org_address(review_id: str) -> str | None:
    """Resolve org_address for a review via 3-hop chain: review -> request -> objective."""
    review_rec = await db.express.read("AgenticReviewDecision", review_id)
    if not review_rec or not review_rec.get("request_id"):
        return None
    req_rec = await db.express.read("AgenticRequest", review_rec["request_id"])
    if not req_rec or not req_rec.get("objective_id"):
        return None
    obj = await db.express.read("AgenticObjective", req_rec["objective_id"])
    if not obj:
        return None
    return obj.get("org_address")


@router.get("")
@limiter.limit(RATE_GET)
async def list_reviews(
    request: Request,
    request_id: Optional[str] = Query(None),
    verdict: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """List reviews."""
    filt: dict[str, Any] = {}
    if request_id:
        filt["request_id"] = request_id
    if verdict:
        filt["verdict"] = verdict

    records = await db.express.list("AgenticReviewDecision", filt, limit=limit, offset=offset)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}


@router.get("/{review_id}")
@limiter.limit(RATE_GET)
async def get_review(request: Request, review_id: str) -> dict:
    """Get review detail."""
    validate_record_id(review_id)
    result = await db.express.read("AgenticReviewDecision", review_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, "Review not found")
    return result


@router.post("/{review_id}/findings", status_code=201, response_model=None)
@limiter.limit(RATE_POST)
async def add_finding(request: Request, review_id: str, body: dict[str, Any]) -> dict | Response:
    """Add a finding to a review."""
    validate_record_id(review_id)
    fid = body.get("id") or uuid4().hex[:12]
    if body.get("id"):
        validate_record_id(fid)
    # Governance gate: resolve org_address via review -> request -> objective
    org_address = await _resolve_review_org_address(review_id)
    if org_address:
        held = await governance_gate(org_address, "add_finding", {"resource": "finding"})
        if held is not None:
            return JSONResponse(content=held, status_code=202)
    elif is_governance_active():
        raise HTTPException(403, "Cannot resolve governance context — action blocked")
    # H3 fix: input length validation
    for field_name in ("title", "category"):
        val = body.get(field_name, "")
        if val:
            validate_string_length(str(val), field_name, MAX_SHORT_STRING)
    for field_name in ("description", "remediation"):
        val = body.get(field_name, "")
        if val:
            validate_string_length(str(val), field_name, MAX_LONG_STRING)

    # H5 fix: validate severity enum
    _VALID_SEVERITIES = ("info", "low", "medium", "high", "critical")
    severity = body.get("severity", "info")
    if severity not in _VALID_SEVERITIES:
        raise HTTPException(400, f"severity must be one of: {', '.join(_VALID_SEVERITIES)}")

    return await db.express.create(
        "AgenticFinding",
        {
            "id": fid,
            "review_id": review_id,
            "request_id": body.get("request_id"),
            "severity": severity,
            "category": body.get("category", ""),
            "title": body.get("title", ""),
            "description": body.get("description", ""),
            "remediation": body.get("remediation", ""),
        },
    )


@router.post("/{review_id}/finalize", response_model=None)
@limiter.limit(RATE_POST)
async def finalize_review(
    request: Request, review_id: str, body: dict[str, Any]
) -> dict | Response:
    """Finalize a review with verdict."""
    validate_record_id(review_id)
    # Governance gate: resolve org_address via review -> request -> objective
    org_address = await _resolve_review_org_address(review_id)
    if org_address:
        held = await governance_gate(org_address, "finalize_review", {"resource": "review"})
        if held is not None:
            return JSONResponse(content=held, status_code=202)
    elif is_governance_active():
        raise HTTPException(403, "Cannot resolve governance context — action blocked")
    verdict = body.get("verdict", "")
    if verdict not in ("approved", "revision_required", "rejected"):
        raise HTTPException(400, "verdict must be: approved, revision_required, or rejected")

    comments = body.get("comments", "")
    if comments:
        validate_string_length(str(comments), "comments", MAX_LONG_STRING)

    return await db.express.update(
        "AgenticReviewDecision",
        review_id,
        {
            "verdict": verdict,
            "comments": comments,
        },
    )
