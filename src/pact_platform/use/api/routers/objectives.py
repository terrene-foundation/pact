# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Objectives API router -- /api/v1/objectives."""

from __future__ import annotations

import math
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


def _exec(wf) -> dict:
    results, _ = db.execute_workflow(wf)
    return results


@router.post("", status_code=201)
def create_objective(body: dict[str, Any]) -> dict:
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

    wf = db.create_workflow()
    wf.add_node(
        "AgenticObjectiveCreateNode",
        "create",
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
    return _exec(wf)["create"]


@router.get("")
def list_objectives(
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

    wf = db.create_workflow()
    wf.add_node(
        "AgenticObjectiveListNode",
        "list",
        {
            "filter": filt,
            "limit": limit,
            "order_by": ["-created_at"],
        },
    )
    return _exec(wf)["list"]


@router.get("/{objective_id}")
def get_objective(objective_id: str) -> dict:
    """Get objective detail."""
    wf = db.create_workflow()
    wf.add_node("AgenticObjectiveReadNode", "read", {"id": objective_id})
    result = _exec(wf)["read"]
    if not result or result.get("found") is False or result.get("failed"):
        raise HTTPException(404, f"Objective {objective_id} not found")
    return result


@router.put("/{objective_id}")
def update_objective(objective_id: str, body: dict[str, Any]) -> dict:
    """Update an objective."""
    fields = {k: v for k, v in body.items() if k not in ("id", "created_at", "updated_at")}
    if "budget_usd" in fields:
        validate_finite(budget_usd=float(fields["budget_usd"]))
    # M2 fix: validate string lengths on update
    if "title" in fields:
        validate_string_length(str(fields["title"]), "title", MAX_SHORT_STRING)
    if "description" in fields:
        validate_string_length(str(fields["description"]), "description", MAX_LONG_STRING)

    wf = db.create_workflow()
    wf.add_node(
        "AgenticObjectiveUpdateNode",
        "update",
        {
            "filter": {"id": objective_id},
            "fields": fields,
        },
    )
    return _exec(wf)["update"]


@router.post("/{objective_id}/cancel")
def cancel_objective(objective_id: str) -> dict:
    """Cancel an objective."""
    wf = db.create_workflow()
    wf.add_node(
        "AgenticObjectiveUpdateNode",
        "update",
        {
            "filter": {"id": objective_id},
            "fields": {"status": "cancelled"},
        },
    )
    return _exec(wf)["update"]


@router.get("/{objective_id}/requests")
def get_objective_requests(objective_id: str) -> dict:
    """List requests for an objective."""
    wf = db.create_workflow()
    wf.add_node(
        "AgenticRequestListNode",
        "list",
        {
            "filter": {"objective_id": objective_id},
            "order_by": ["sequence_order"],
        },
    )
    return _exec(wf)["list"]


@router.get("/{objective_id}/cost")
def get_objective_cost(objective_id: str) -> dict:
    """Get cost summary for an objective."""
    wf = db.create_workflow()
    wf.add_node(
        "RunListNode",
        "runs",
        {
            "filter": {"request_id": objective_id},
        },
    )
    results = _exec(wf)
    runs = results["runs"].get("records", [])
    # C3 fix: NaN-safe summation -- corrupted DB values don't poison totals
    total = safe_sum_finite([r.get("cost_usd", 0.0) for r in runs])
    return {
        "objective_id": objective_id,
        "total_cost_usd": round(total, 6),
        "run_count": len(runs),
    }
