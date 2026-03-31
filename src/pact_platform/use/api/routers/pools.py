# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pools API router -- /api/v1/pools.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request

from pact_platform.models import (
    MAX_CONCURRENT_UPPER,
    MAX_LONG_STRING,
    MAX_POOL_MEMBERS,
    MAX_SHORT_STRING,
    db,
    safe_sum_finite,
    validate_string_length,
)
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

router = APIRouter(prefix="/api/v1/pools", tags=["pools"])


@router.post("", status_code=201)
@limiter.limit(RATE_POST)
async def create_pool(request: Request, body: dict[str, Any]) -> dict:
    """Create a new pool."""
    pid = body.get("id") or uuid4().hex[:12]
    org_id = body.get("org_id", "")
    name = body.get("name", "")
    if not org_id or not name:
        raise HTTPException(400, "org_id and name are required")

    validate_string_length(org_id, "org_id", MAX_SHORT_STRING)
    validate_string_length(name, "name", MAX_SHORT_STRING)
    description = body.get("description", "")
    if description:
        validate_string_length(description, "description", MAX_LONG_STRING)

    max_concurrent = body.get("max_concurrent", 5)
    if not isinstance(max_concurrent, int) or max_concurrent < 1:
        raise HTTPException(400, "max_concurrent must be a positive integer")
    if max_concurrent > MAX_CONCURRENT_UPPER:
        raise HTTPException(400, f"max_concurrent must not exceed {MAX_CONCURRENT_UPPER}")

    return await db.express.create(
        "AgenticPool",
        {
            "id": pid,
            "org_id": org_id,
            "name": name,
            "description": description,
            "pool_type": body.get("pool_type", "agent"),
            "routing_strategy": body.get("routing_strategy", "round_robin"),
            "max_concurrent": max_concurrent,
        },
    )


@router.get("")
@limiter.limit(RATE_GET)
async def list_pools(
    request: Request,
    org_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """List pools."""
    filt: dict[str, Any] = {}
    if org_id:
        filt["org_id"] = org_id
    if status:
        filt["status"] = status

    records = await db.express.list("AgenticPool", filt, limit=limit, offset=offset)
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}


@router.get("/{pool_id}")
@limiter.limit(RATE_GET)
async def get_pool(request: Request, pool_id: str) -> dict:
    """Get pool detail."""
    result = await db.express.read("AgenticPool", pool_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, "Pool not found")
    return result


@router.post("/{pool_id}/members", status_code=201)
@limiter.limit(RATE_POST)
async def add_member(request: Request, pool_id: str, body: dict[str, Any]) -> dict:
    """Add a member to a pool."""
    current_count = await db.express.count(
        "AgenticPoolMembership", {"pool_id": pool_id, "status": "active"}
    )
    if current_count >= MAX_POOL_MEMBERS:
        raise HTTPException(429, f"Pool has reached the maximum of {MAX_POOL_MEMBERS} members")

    member_address = body.get("member_address", "")
    if not member_address:
        raise HTTPException(400, "member_address is required")
    validate_string_length(member_address, "member_address", MAX_SHORT_STRING)

    max_concurrent = body.get("max_concurrent", 3)
    if not isinstance(max_concurrent, int) or max_concurrent < 1:
        raise HTTPException(400, "max_concurrent must be a positive integer")
    if max_concurrent > MAX_CONCURRENT_UPPER:
        raise HTTPException(400, f"max_concurrent must not exceed {MAX_CONCURRENT_UPPER}")

    mid = body.get("id") or uuid4().hex[:12]
    return await db.express.create(
        "AgenticPoolMembership",
        {
            "id": mid,
            "pool_id": pool_id,
            "member_address": member_address,
            "member_type": body.get("member_type", "agent"),
            "capabilities": body.get("capabilities", {}),
            "max_concurrent": max_concurrent,
        },
    )


@router.delete("/{pool_id}/members/{member_id}")
@limiter.limit(RATE_POST)
async def remove_member(request: Request, pool_id: str, member_id: str) -> dict:
    """Remove a member from a pool."""
    deleted = await db.express.delete("AgenticPoolMembership", member_id)
    return {"deleted": deleted, "id": member_id}


@router.get("/{pool_id}/capacity")
@limiter.limit(RATE_GET)
async def get_pool_capacity(request: Request, pool_id: str) -> dict:
    """Get pool capacity info."""
    members = await db.express.list(
        "AgenticPoolMembership", {"pool_id": pool_id, "status": "active"}
    )
    total_capacity = safe_sum_finite([m.get("max_concurrent", 0) for m in members])
    total_active = safe_sum_finite([m.get("active_count", 0) for m in members])
    return {
        "pool_id": pool_id,
        "member_count": len(members),
        "total_capacity": int(total_capacity),
        "total_active": int(total_active),
        "available": int(total_capacity - total_active),
    }
