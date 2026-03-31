# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Requests API router — /api/v1/requests.

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
    MAX_METADATA_SIZE,
    MAX_SHORT_STRING,
    db,
    validate_finite,
    validate_record_id,
    validate_string_length,
)
from pact_platform.use.api.governance import governance_gate
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

router = APIRouter(prefix="/api/v1/requests", tags=["requests"])


@router.post("", status_code=201, response_model=None)
@limiter.limit(RATE_POST)
async def submit_request(request: Request, body: dict[str, Any]) -> dict | Response:
    """Submit a new request."""
    rid = body.get("id") or uuid4().hex[:12]
    if body.get("id"):
        validate_record_id(rid)
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

    # H5 fix: validate enum-typed fields
    _VALID_PRIORITIES = ("low", "normal", "high", "critical")
    priority = body.get("priority", "normal")
    if priority not in _VALID_PRIORITIES:
        raise HTTPException(400, f"priority must be one of: {', '.join(_VALID_PRIORITIES)}")
    _VALID_ASSIGNED_TYPES = ("unassigned", "pool", "agent")
    assigned_type = body.get("assigned_type", "unassigned")
    if assigned_type not in _VALID_ASSIGNED_TYPES:
        raise HTTPException(
            400, f"assigned_type must be one of: {', '.join(_VALID_ASSIGNED_TYPES)}"
        )

    # Governance gate: resolve org_address from parent objective
    obj = await db.express.read("AgenticObjective", objective_id)
    if obj and obj.get("org_address"):
        held = await governance_gate(obj["org_address"], "submit_request", {"resource": "request"})
        if held is not None:
            return JSONResponse(content=held, status_code=202)

    return await db.express.create(
        "AgenticRequest",
        {
            "id": rid,
            "objective_id": objective_id,
            "title": title,
            "description": description,
            "assigned_to": body.get("assigned_to"),
            "assigned_type": assigned_type,
            "status": "pending",
            "priority": priority,
            "sequence_order": sequence_order,
            "depends_on": body.get("depends_on", {}),
            "envelope_id": body.get("envelope_id"),
            "deadline": body.get("deadline"),
            "metadata": _validate_metadata(body.get("metadata", {})),
        },
    )


def _validate_metadata(metadata: Any) -> dict:
    """Validate metadata dict size."""
    if not isinstance(metadata, dict):
        return {}
    import json as _json

    if len(_json.dumps(metadata)) > MAX_METADATA_SIZE:
        raise HTTPException(400, f"metadata exceeds maximum size of {MAX_METADATA_SIZE} bytes")
    return metadata


@router.get("")
@limiter.limit(RATE_GET)
async def list_requests(
    request: Request,
    status: Optional[str] = Query(None),
    objective_id: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """List requests with optional filters."""
    filt: dict[str, Any] = {}
    if status:
        filt["status"] = status
    if objective_id:
        filt["objective_id"] = objective_id
    if assigned_to:
        filt["assigned_to"] = assigned_to

    records = await db.express.list("AgenticRequest", filt, limit=limit, offset=offset)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}


@router.get("/{request_id}")
@limiter.limit(RATE_GET)
async def get_request(request: Request, request_id: str) -> dict:
    """Get request detail."""
    validate_record_id(request_id)
    result = await db.express.read("AgenticRequest", request_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, "Request not found")
    return result


@router.post("/{request_id}/cancel", response_model=None)
@limiter.limit(RATE_POST)
async def cancel_request(request: Request, request_id: str) -> dict | Response:
    """Cancel a request."""
    validate_record_id(request_id)
    req_rec = await db.express.read("AgenticRequest", request_id)
    if req_rec and req_rec.get("objective_id"):
        obj = await db.express.read("AgenticObjective", req_rec["objective_id"])
        if obj and obj.get("org_address"):
            held = await governance_gate(
                obj["org_address"], "cancel_request", {"resource": "request"}
            )
            if held is not None:
                return JSONResponse(content=held, status_code=202)
    return await db.express.update("AgenticRequest", request_id, {"status": "cancelled"})


@router.get("/{request_id}/sessions")
@limiter.limit(RATE_GET)
async def get_request_sessions(request: Request, request_id: str) -> dict:
    """List sessions for a request."""
    validate_record_id(request_id)
    records = await db.express.list("AgenticWorkSession", {"request_id": request_id})
    return {"records": records, "count": len(records), "limit": 100}


@router.get("/{request_id}/artifacts")
@limiter.limit(RATE_GET)
async def get_request_artifacts(request: Request, request_id: str) -> dict:
    """List artifacts for a request."""
    validate_record_id(request_id)
    records = await db.express.list("AgenticArtifact", {"request_id": request_id})
    return {"records": records, "count": len(records), "limit": 100}
