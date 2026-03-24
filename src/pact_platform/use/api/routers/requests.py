# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Requests API router — /api/v1/requests."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from pact_platform.models import db

router = APIRouter(prefix="/api/v1/requests", tags=["requests"])


def _exec(wf) -> dict:
    results, _ = db.execute_workflow(wf)
    return results


@router.post("", status_code=201)
def submit_request(body: dict[str, Any]) -> dict:
    """Submit a new request."""
    rid = body.get("id") or uuid4().hex[:12]
    objective_id = body.get("objective_id", "")
    title = body.get("title", "")
    if not objective_id or not title:
        raise HTTPException(400, "objective_id and title are required")

    wf = db.create_workflow()
    wf.add_node(
        "AgenticRequestCreateNode",
        "create",
        {
            "id": rid,
            "objective_id": objective_id,
            "title": title,
            "description": body.get("description", ""),
            "assigned_to": body.get("assigned_to"),
            "assigned_type": body.get("assigned_type", "unassigned"),
            "status": "pending",
            "priority": body.get("priority", "normal"),
            "sequence_order": body.get("sequence_order", 0),
            "depends_on": body.get("depends_on", {}),
            "envelope_id": body.get("envelope_id"),
            "deadline": body.get("deadline"),
            "metadata": body.get("metadata", {}),
        },
    )
    return _exec(wf)["create"]


@router.get("")
def list_requests(
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

    wf = db.create_workflow()
    wf.add_node(
        "AgenticRequestListNode",
        "list",
        {
            "filter": filt,
            "limit": limit,
            "order_by": ["-created_at"],
        },
    )
    return _exec(wf)["list"]


@router.get("/{request_id}")
def get_request(request_id: str) -> dict:
    """Get request detail."""
    wf = db.create_workflow()
    wf.add_node("AgenticRequestReadNode", "read", {"id": request_id})
    result = _exec(wf)["read"]
    if not result or result.get("found") is False or result.get("failed"):
        raise HTTPException(404, f"Request {request_id} not found")
    return result


@router.post("/{request_id}/cancel")
def cancel_request(request_id: str) -> dict:
    """Cancel a request."""
    wf = db.create_workflow()
    wf.add_node(
        "AgenticRequestUpdateNode",
        "update",
        {
            "filter": {"id": request_id},
            "fields": {"status": "cancelled"},
        },
    )
    return _exec(wf)["update"]


@router.get("/{request_id}/sessions")
def get_request_sessions(request_id: str) -> dict:
    """List sessions for a request."""
    wf = db.create_workflow()
    wf.add_node(
        "AgenticWorkSessionListNode",
        "list",
        {
            "filter": {"request_id": request_id},
        },
    )
    return _exec(wf)["list"]


@router.get("/{request_id}/artifacts")
def get_request_artifacts(request_id: str) -> dict:
    """List artifacts for a request."""
    wf = db.create_workflow()
    wf.add_node(
        "AgenticArtifactListNode",
        "list",
        {
            "filter": {"request_id": request_id},
        },
    )
    return _exec(wf)["list"]
