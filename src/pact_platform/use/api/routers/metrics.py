# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Platform metrics API router -- /api/v1/platform/metrics.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query, Request

from pact_platform.models import db, safe_sum_finite
from pact_platform.use.api.rate_limit import RATE_GET, limiter

router = APIRouter(prefix="/api/v1/platform/metrics", tags=["metrics"])


@router.get("/cost")
@limiter.limit(RATE_GET)
async def get_cost_metrics(
    request: Request,
    agent_address: Optional[str] = Query(None),
    period_days: int = Query(30),
) -> dict:
    """Get cost metrics."""
    filt: dict[str, Any] = {}
    if agent_address:
        filt["agent_address"] = agent_address

    runs = await db.express.list("Run", filt, limit=10000)
    total = safe_sum_finite([r.get("cost_usd", 0.0) for r in runs])
    tokens_in = safe_sum_finite([r.get("input_tokens", 0) for r in runs])
    tokens_out = safe_sum_finite([r.get("output_tokens", 0) for r in runs])
    return {
        "total_cost_usd": round(total, 6),
        "run_count": len(runs),
        "total_input_tokens": int(tokens_in),
        "total_output_tokens": int(tokens_out),
    }


@router.get("/throughput")
@limiter.limit(RATE_GET)
async def get_throughput_metrics(request: Request) -> dict:
    """Get throughput metrics."""
    stats = {}
    for status in ("running", "completed", "failed"):
        stats[status] = await db.express.count("Run", {"status": status})
    return {"throughput": stats}


@router.get("/governance")
@limiter.limit(RATE_GET)
async def get_governance_verdicts(request: Request) -> dict:
    """Get governance verdict distribution."""
    stats = {}
    for status in ("pending", "approved", "rejected", "expired"):
        stats[status] = await db.express.count("AgenticDecision", {"status": status})
    return {"governance_verdicts": stats}


@router.get("/budget")
@limiter.limit(RATE_GET)
async def get_budget_utilization(request: Request) -> dict:
    """Get budget utilization across objectives."""
    objectives = await db.express.list("AgenticObjective", {"status": "active"}, limit=1000)
    total_budget = safe_sum_finite([o.get("budget_usd", 0.0) for o in objectives])
    return {
        "active_objectives": len(objectives),
        "total_budget_usd": round(total_budget, 2),
    }
