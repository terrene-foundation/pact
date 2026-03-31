# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Sessions API router — /api/v1/sessions.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from pact_platform.models import db
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
    result = await db.express.read("AgenticWorkSession", session_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, "Session not found")
    return result


@router.post("/{session_id}/pause")
@limiter.limit(RATE_POST)
async def pause_session(request: Request, session_id: str) -> dict:
    """Pause a session."""
    return await db.express.update("AgenticWorkSession", session_id, {"status": "paused"})


@router.post("/{session_id}/resume")
@limiter.limit(RATE_POST)
async def resume_session(request: Request, session_id: str) -> dict:
    """Resume a paused session."""
    return await db.express.update("AgenticWorkSession", session_id, {"status": "active"})
