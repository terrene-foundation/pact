# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Sessions API router — /api/v1/sessions."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from pact_platform.models import db

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _exec(wf) -> dict:
    results, _ = db.execute_workflow(wf)
    return results


@router.get("")
def list_sessions(
    request_id: Optional[str] = Query(None),
    worker_address: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
) -> dict:
    """List sessions with optional filters."""
    filt: dict[str, Any] = {}
    if request_id:
        filt["request_id"] = request_id
    if worker_address:
        filt["worker_address"] = worker_address
    if status:
        filt["status"] = status

    wf = db.create_workflow()
    wf.add_node(
        "AgenticWorkSessionListNode",
        "list",
        {
            "filter": filt,
            "limit": limit,
            "order_by": ["-created_at"],
        },
    )
    return _exec(wf)["list"]


@router.get("/{session_id}")
def get_session(session_id: str) -> dict:
    """Get session detail."""
    wf = db.create_workflow()
    wf.add_node("AgenticWorkSessionReadNode", "read", {"id": session_id})
    result = _exec(wf)["read"]
    if not result or result.get("found") is False or result.get("failed"):
        raise HTTPException(404, f"Session {session_id} not found")
    return result


@router.post("/{session_id}/pause")
def pause_session(session_id: str) -> dict:
    """Pause a session."""
    wf = db.create_workflow()
    wf.add_node(
        "AgenticWorkSessionUpdateNode",
        "update",
        {
            "filter": {"id": session_id},
            "fields": {"status": "paused"},
        },
    )
    return _exec(wf)["update"]


@router.post("/{session_id}/resume")
def resume_session(session_id: str) -> dict:
    """Resume a paused session."""
    wf = db.create_workflow()
    wf.add_node(
        "AgenticWorkSessionUpdateNode",
        "update",
        {
            "filter": {"id": session_id},
            "fields": {"status": "active"},
        },
    )
    return _exec(wf)["update"]
