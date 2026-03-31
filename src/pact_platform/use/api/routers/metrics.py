# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Platform metrics API router -- /api/v1/platform/metrics.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query

from pact_platform.models import db, safe_sum_finite

router = APIRouter(prefix="/api/v1/platform/metrics", tags=["metrics"])


@router.get("/cost")
async def get_cost_metrics(
    agent_address: Optional[str] = Query(None),
    period_days: int = Query(30),
) -> dict:
    """Get cost metrics."""
    filt: dict[str, Any] = {}
    if agent_address:
        filt["agent_address"] = agent_address

    runs = await db.express.list("Run", filt, limit=10000)
    # C3 fix: NaN-safe summation -- corrupted DB values don't poison totals
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
async def get_throughput_metrics() -> dict:
    """Get throughput metrics."""
    stats = {}
    for status in ("running", "completed", "failed"):
        stats[status] = await db.express.count("Run", {"status": status})
    return {"throughput": stats}


@router.get("/governance")
async def get_governance_verdicts() -> dict:
    """Get governance verdict distribution."""
    stats = {}
    for status in ("pending", "approved", "rejected", "expired"):
        stats[status] = await db.express.count("AgenticDecision", {"status": status})
    return {"governance_verdicts": stats}


@router.get("/budget")
async def get_budget_utilization() -> dict:
    """Get budget utilization across objectives."""
    objectives = await db.express.list("AgenticObjective", {"status": "active"}, limit=1000)
    # C3 fix: NaN-safe summation
    total_budget = safe_sum_finite([o.get("budget_usd", 0.0) for o in objectives])
    return {
        "active_objectives": len(objectives),
        "total_budget_usd": round(total_budget, 2),
    }
