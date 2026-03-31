# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Objectives API router -- /api/v1/objectives.

Uses DataFlow Express API for all CRUD operations (23x faster than
workflow primitives for single-operation endpoints).
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
    safe_sum_finite,
    validate_finite,
    validate_record_id,
    validate_string_length,
)
from pact_platform.use.api.governance import governance_gate
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

router = APIRouter(prefix="/api/v1/objectives", tags=["objectives"])


@router.post("", status_code=201, response_model=None)
@limiter.limit(RATE_POST)
async def create_objective(request: Request, body: dict[str, Any]) -> dict | Response:
    """Create a new objective."""
    oid = body.get("id") or uuid4().hex[:12]
    if body.get("id"):
        validate_record_id(oid)
    org_address = body.get("org_address", "")
    title = body.get("title", "")
    if not org_address or not title:
        raise HTTPException(400, "org_address and title are required")

    # M2 fix: input length validation
    validate_string_length(org_address, "org_address", MAX_SHORT_STRING)
    validate_string_length(title, "title", MAX_SHORT_STRING)
    description = body.get("description", "")
    if description:
        validate_string_length(description, "description", MAX_LONG_STRING)

    budget = float(body.get("budget_usd", 0.0))
    validate_finite(budget_usd=budget)

    metadata = body.get("metadata", {})
    if isinstance(metadata, dict):
        import json as _json

        if len(_json.dumps(metadata)) > MAX_METADATA_SIZE:
            raise HTTPException(400, f"metadata exceeds maximum size of {MAX_METADATA_SIZE} bytes")
    else:
        metadata = {}

    # Governance gate: verify the submitter's authority to create objectives
    held = await governance_gate(
        org_address, "create_objective", {"cost": budget, "resource": "objective"}
    )
    if held is not None:
        return JSONResponse(content=held, status_code=202)

    return await db.express.create(
        "AgenticObjective",
        {
            "id": oid,
            "org_address": org_address,
            "title": title,
            "description": description,
            "submitted_by": body.get("submitted_by", ""),
            "status": body.get("status", "draft"),
            "priority": body.get("priority", "normal"),
            "budget_usd": budget,
            "deadline": body.get("deadline"),
            "parent_objective_id": body.get("parent_objective_id"),
            "metadata": metadata,
        },
    )


@router.get("")
@limiter.limit(RATE_GET)
async def list_objectives(
    request: Request,
    status: Optional[str] = Query(None),
    org_address: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """List objectives with optional filters."""
    filt: dict[str, Any] = {}
    if status:
        filt["status"] = status
    if org_address:
        filt["org_address"] = org_address

    records = await db.express.list("AgenticObjective", filt, limit=limit, offset=offset)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}


@router.get("/{objective_id}")
@limiter.limit(RATE_GET)
async def get_objective(request: Request, objective_id: str) -> dict:
    """Get objective detail."""
    validate_record_id(objective_id)
    result = await db.express.read("AgenticObjective", objective_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, "Objective not found")
    return result


@router.put("/{objective_id}", response_model=None)
@limiter.limit(RATE_POST)
async def update_objective(
    request: Request, objective_id: str, body: dict[str, Any]
) -> dict | Response:
    """Update an objective."""
    validate_record_id(objective_id)
    fields = {k: v for k, v in body.items() if k not in ("id", "created_at", "updated_at")}
    if "budget_usd" in fields:
        validate_finite(budget_usd=float(fields["budget_usd"]))
    if "title" in fields:
        validate_string_length(str(fields["title"]), "title", MAX_SHORT_STRING)
    if "description" in fields:
        validate_string_length(str(fields["description"]), "description", MAX_LONG_STRING)

    # Governance gate: verify authority to modify objectives (especially budget changes)
    existing = await db.express.read("AgenticObjective", objective_id)
    if existing and existing.get("org_address"):
        ctx: dict[str, Any] = {"resource": "objective"}
        if "budget_usd" in fields:
            ctx["cost"] = float(fields["budget_usd"])
        held = await governance_gate(existing["org_address"], "update_objective", ctx)
        if held is not None:
            return JSONResponse(content=held, status_code=202)

    return await db.express.update("AgenticObjective", objective_id, fields)


@router.post("/{objective_id}/cancel", response_model=None)
@limiter.limit(RATE_POST)
async def cancel_objective(request: Request, objective_id: str) -> dict | Response:
    """Cancel an objective."""
    validate_record_id(objective_id)
    existing = await db.express.read("AgenticObjective", objective_id)
    if existing and existing.get("org_address"):
        held = await governance_gate(
            existing["org_address"], "cancel_objective", {"resource": "objective"}
        )
        if held is not None:
            return JSONResponse(content=held, status_code=202)
    return await db.express.update("AgenticObjective", objective_id, {"status": "cancelled"})


@router.get("/{objective_id}/requests")
@limiter.limit(RATE_GET)
async def get_objective_requests(request: Request, objective_id: str) -> dict:
    """List requests for an objective."""
    validate_record_id(objective_id)
    records = await db.express.list("AgenticRequest", {"objective_id": objective_id})
    records.sort(key=lambda r: r.get("sequence_order", 0))
    return {"records": records, "count": len(records), "limit": 100}


@router.get("/{objective_id}/cost")
@limiter.limit(RATE_GET)
async def get_objective_cost(request: Request, objective_id: str) -> dict:
    """Get cost summary for an objective.

    Aggregates cost across all requests belonging to this objective,
    then across all runs belonging to those requests.
    """
    validate_record_id(objective_id)
    # Step 1: get all request IDs for this objective
    reqs = await db.express.list("AgenticRequest", {"objective_id": objective_id})
    req_ids = [r.get("id") for r in reqs if r.get("id")]

    # Step 2: get all runs for those requests
    all_runs: list[dict] = []
    for rid in req_ids:
        runs = await db.express.list("Run", {"request_id": rid})
        all_runs.extend(runs)

    # C3 fix: NaN-safe summation -- corrupted DB values don't poison totals
    total = safe_sum_finite([r.get("cost_usd", 0.0) for r in all_runs])
    return {
        "objective_id": objective_id,
        "total_cost_usd": round(total, 6),
        "run_count": len(all_runs),
        "request_count": len(req_ids),
    }
