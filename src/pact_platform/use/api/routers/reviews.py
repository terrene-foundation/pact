# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reviews API router — /api/v1/reviews."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from pact_platform.models import db

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


def _exec(wf) -> dict:
    results, _ = db.execute_workflow(wf)
    return results


@router.get("")
def list_reviews(
    request_id: Optional[str] = Query(None),
    verdict: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
) -> dict:
    """List reviews."""
    filt: dict[str, Any] = {}
    if request_id:
        filt["request_id"] = request_id
    if verdict:
        filt["verdict"] = verdict

    wf = db.create_workflow()
    wf.add_node(
        "AgenticReviewDecisionListNode",
        "list",
        {
            "filter": filt,
            "limit": limit,
            "order_by": ["-created_at"],
        },
    )
    return _exec(wf)["list"]


@router.get("/{review_id}")
def get_review(review_id: str) -> dict:
    """Get review detail."""
    wf = db.create_workflow()
    wf.add_node("AgenticReviewDecisionReadNode", "read", {"id": review_id})
    result = _exec(wf)["read"]
    if not result or result.get("found") is False or result.get("failed"):
        raise HTTPException(404, f"Review {review_id} not found")
    return result


@router.post("/{review_id}/findings", status_code=201)
def add_finding(review_id: str, body: dict[str, Any]) -> dict:
    """Add a finding to a review."""
    fid = body.get("id") or uuid4().hex[:12]
    wf = db.create_workflow()
    wf.add_node(
        "AgenticFindingCreateNode",
        "create",
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
    return _exec(wf)["create"]


@router.post("/{review_id}/finalize")
def finalize_review(review_id: str, body: dict[str, Any]) -> dict:
    """Finalize a review with verdict."""
    verdict = body.get("verdict", "")
    if verdict not in ("approved", "revision_required", "rejected"):
        raise HTTPException(400, "verdict must be: approved, revision_required, or rejected")

    wf = db.create_workflow()
    wf.add_node(
        "AgenticReviewDecisionUpdateNode",
        "update",
        {
            "filter": {"id": review_id},
            "fields": {
                "verdict": verdict,
                "comments": body.get("comments", ""),
            },
        },
    )
    return _exec(wf)["update"]
