# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Objectives API router -- /api/v1/objectives.

Uses DataFlow Express API for all CRUD operations (23x faster than
workflow primitives for single-operation endpoints).
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from pact_platform.models import (
    MAX_LONG_STRING,
    MAX_SHORT_STRING,
    db,
    safe_sum_finite,
    validate_finite,
    validate_string_length,
)

router = APIRouter(prefix="/api/v1/objectives", tags=["objectives"])


@router.post("", status_code=201)
async def create_objective(body: dict[str, Any]) -> dict:
    """Create a new objective."""
    oid = body.get("id") or uuid4().hex[:12]
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
            "metadata": body.get("metadata", {}),
        },
    )


@router.get("")
async def list_objectives(
    status: Optional[str] = Query(None),
    org_address: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
) -> dict:
    """List objectives with optional filters."""
    filt: dict[str, Any] = {}
    if status:
        filt["status"] = status
    if org_address:
        filt["org_address"] = org_address

    records = await db.express.list("AgenticObjective", filt, limit=limit)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit}


@router.get("/{objective_id}")
async def get_objective(objective_id: str) -> dict:
    """Get objective detail."""
    result = await db.express.read("AgenticObjective", objective_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, f"Objective {objective_id} not found")
    return result


@router.put("/{objective_id}")
async def update_objective(objective_id: str, body: dict[str, Any]) -> dict:
    """Update an objective."""
    fields = {k: v for k, v in body.items() if k not in ("id", "created_at", "updated_at")}
    if "budget_usd" in fields:
        validate_finite(budget_usd=float(fields["budget_usd"]))
    # M2 fix: validate string lengths on update
    if "title" in fields:
        validate_string_length(str(fields["title"]), "title", MAX_SHORT_STRING)
    if "description" in fields:
        validate_string_length(str(fields["description"]), "description", MAX_LONG_STRING)

    return await db.express.update("AgenticObjective", objective_id, fields)


@router.post("/{objective_id}/cancel")
async def cancel_objective(objective_id: str) -> dict:
    """Cancel an objective."""
    return await db.express.update("AgenticObjective", objective_id, {"status": "cancelled"})


@router.get("/{objective_id}/requests")
async def get_objective_requests(objective_id: str) -> dict:
    """List requests for an objective."""
    records = await db.express.list("AgenticRequest", {"objective_id": objective_id})
    records.sort(key=lambda r: r.get("sequence_order", 0))
    return {"records": records, "count": len(records), "limit": 100}


@router.get("/{objective_id}/cost")
async def get_objective_cost(objective_id: str) -> dict:
    """Get cost summary for an objective."""
    runs = await db.express.list("Run", {"request_id": objective_id})
    # C3 fix: NaN-safe summation -- corrupted DB values don't poison totals
    total = safe_sum_finite([r.get("cost_usd", 0.0) for r in runs])
    return {
        "objective_id": objective_id,
        "total_cost_usd": round(total, 6),
        "run_count": len(runs),
    }
