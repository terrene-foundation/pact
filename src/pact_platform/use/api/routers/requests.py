# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Requests API router — /api/v1/requests.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from pact_platform.models import (
    MAX_LONG_STRING,
    MAX_SHORT_STRING,
    db,
    validate_finite,
    validate_string_length,
)

router = APIRouter(prefix="/api/v1/requests", tags=["requests"])


@router.post("", status_code=201)
async def submit_request(body: dict[str, Any]) -> dict:
    """Submit a new request."""
    rid = body.get("id") or uuid4().hex[:12]
    objective_id = body.get("objective_id", "")
    title = body.get("title", "")
    if not objective_id or not title:
        raise HTTPException(400, "objective_id and title are required")

    # H2 fix: input length validation
    validate_string_length(objective_id, "objective_id", MAX_SHORT_STRING)
    validate_string_length(title, "title", MAX_SHORT_STRING)
    description = body.get("description", "")
    if description:
        validate_string_length(description, "description", MAX_LONG_STRING)

    # H5 fix: validate sequence_order is a finite integer
    sequence_order = body.get("sequence_order", 0)
    if not isinstance(sequence_order, int):
        raise HTTPException(400, "sequence_order must be an integer")
    validate_finite(sequence_order=sequence_order)

    return await db.express.create(
        "AgenticRequest",
        {
            "id": rid,
            "objective_id": objective_id,
            "title": title,
            "description": description,
            "assigned_to": body.get("assigned_to"),
            "assigned_type": body.get("assigned_type", "unassigned"),
            "status": "pending",
            "priority": body.get("priority", "normal"),
            "sequence_order": sequence_order,
            "depends_on": body.get("depends_on", {}),
            "envelope_id": body.get("envelope_id"),
            "deadline": body.get("deadline"),
            "metadata": body.get("metadata", {}),
        },
    )


@router.get("")
async def list_requests(
    status: Optional[str] = Query(None),
    objective_id: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
) -> dict:
    """List requests with optional filters."""
    filt: dict[str, Any] = {}
    if status:
        filt["status"] = status
    if objective_id:
        filt["objective_id"] = objective_id
    if assigned_to:
        filt["assigned_to"] = assigned_to

    records = await db.express.list("AgenticRequest", filt, limit=limit)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit}


@router.get("/{request_id}")
async def get_request(request_id: str) -> dict:
    """Get request detail."""
    result = await db.express.read("AgenticRequest", request_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, f"Request {request_id} not found")
    return result


@router.post("/{request_id}/cancel")
async def cancel_request(request_id: str) -> dict:
    """Cancel a request."""
    return await db.express.update("AgenticRequest", request_id, {"status": "cancelled"})


@router.get("/{request_id}/sessions")
async def get_request_sessions(request_id: str) -> dict:
    """List sessions for a request."""
    records = await db.express.list("AgenticWorkSession", {"request_id": request_id})
    return {"records": records, "count": len(records), "limit": 100}


@router.get("/{request_id}/artifacts")
async def get_request_artifacts(request_id: str) -> dict:
    """List artifacts for a request."""
    records = await db.express.list("AgenticArtifact", {"request_id": request_id})
    return {"records": records, "count": len(records), "limit": 100}
