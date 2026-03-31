# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reviews API router — /api/v1/reviews.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request

from pact_platform.models import MAX_LONG_STRING, MAX_SHORT_STRING, db, validate_string_length
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


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
    result = await db.express.read("AgenticReviewDecision", review_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, "Review not found")
    return result


@router.post("/{review_id}/findings", status_code=201)
@limiter.limit(RATE_POST)
async def add_finding(request: Request, review_id: str, body: dict[str, Any]) -> dict:
    """Add a finding to a review."""
    fid = body.get("id") or uuid4().hex[:12]
    # H3 fix: input length validation
    for field_name in ("title", "category"):
        val = body.get(field_name, "")
        if val:
            validate_string_length(str(val), field_name, MAX_SHORT_STRING)
    for field_name in ("description", "remediation"):
        val = body.get(field_name, "")
        if val:
            validate_string_length(str(val), field_name, MAX_LONG_STRING)
    return await db.express.create(
        "AgenticFinding",
        {
            "id": fid,
            "review_id": review_id,
            "request_id": body.get("request_id"),
            "severity": body.get("severity", "info"),
            "category": body.get("category", ""),
            "title": body.get("title", ""),
            "description": body.get("description", ""),
            "remediation": body.get("remediation", ""),
        },
    )


@router.post("/{review_id}/finalize")
@limiter.limit(RATE_POST)
async def finalize_review(request: Request, review_id: str, body: dict[str, Any]) -> dict:
    """Finalize a review with verdict."""
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
