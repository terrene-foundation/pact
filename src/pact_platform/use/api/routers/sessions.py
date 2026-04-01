# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Sessions API router — /api/v1/sessions.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from pact_platform.models import db, validate_record_id
from pact_platform.use.api.governance import governance_gate, is_governance_active
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.get("")
@limiter.limit(RATE_GET)
async def list_sessions(
    request: Request,
    request_id: Optional[str] = Query(None),
    worker_address: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """List sessions with optional filters."""
    filt: dict[str, Any] = {}
    if request_id:
        filt["request_id"] = request_id
    if worker_address:
        filt["worker_address"] = worker_address
    if status:
        filt["status"] = status

    records = await db.express.list("AgenticWorkSession", filt, limit=limit, offset=offset)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}


@router.get("/{session_id}")
@limiter.limit(RATE_GET)
async def get_session(request: Request, session_id: str) -> dict:
    """Get session detail."""
    validate_record_id(session_id)
    result = await db.express.read("AgenticWorkSession", session_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, "Session not found")
    return result


async def _resolve_session_org_address(session_id: str) -> str | None:
    """Resolve org_address for a session via 3-hop chain: session -> request -> objective."""
    session_rec = await db.express.read("AgenticWorkSession", session_id)
    if not session_rec or not session_rec.get("request_id"):
        return None
    req_rec = await db.express.read("AgenticRequest", session_rec["request_id"])
    if not req_rec or not req_rec.get("objective_id"):
        return None
    obj = await db.express.read("AgenticObjective", req_rec["objective_id"])
    if not obj:
        return None
    return obj.get("org_address")


@router.post("/{session_id}/pause", response_model=None)
@limiter.limit(RATE_POST)
async def pause_session(request: Request, session_id: str) -> dict | Response:
    """Pause a session."""
    validate_record_id(session_id)
    org_address = await _resolve_session_org_address(session_id)
    if org_address:
        held = await governance_gate(org_address, "pause_session", {"resource": "session"})
        if held is not None:
            return JSONResponse(content=held, status_code=202)
    elif is_governance_active():
        raise HTTPException(403, "Cannot resolve governance context — action blocked")
    return await db.express.update("AgenticWorkSession", session_id, {"status": "paused"})


@router.post("/{session_id}/resume", response_model=None)
@limiter.limit(RATE_POST)
async def resume_session(request: Request, session_id: str) -> dict | Response:
    """Resume a paused session."""
    validate_record_id(session_id)
    org_address = await _resolve_session_org_address(session_id)
    if org_address:
        held = await governance_gate(org_address, "resume_session", {"resource": "session"})
        if held is not None:
            return JSONResponse(content=held, status_code=202)
    elif is_governance_active():
        raise HTTPException(403, "Cannot resolve governance context — action blocked")
    return await db.express.update("AgenticWorkSession", session_id, {"status": "active"})
