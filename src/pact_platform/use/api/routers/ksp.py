# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Knowledge Share Policy (KSP) API router -- /api/v1/ksp.

Provides endpoints for creating and listing KSPs through the
GovernanceEngine.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from pact_platform.models import validate_record_id
from pact_platform.use.api.governance import governance_gate
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ksp", tags=["ksp"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    """Inject the GovernanceEngine reference."""
    global _engine
    _engine = engine


@router.post("")
@limiter.limit(RATE_POST)
async def create_ksp(request: Request, body: dict[str, Any]) -> dict:
    """Create a Knowledge Share Policy.

    Body:
        {
            "id": "ksp-eng-to-ops",
            "source_address": "D1",
            "target_address": "D2",
            "max_classification": "confidential",
            "compartments": []                     (optional, default [])
        }
    """
    ksp_id = body.get("id", "")
    source_address = body.get("source_address", "")
    target_address = body.get("target_address", "")
    max_classification = body.get("max_classification", "")
    compartments = body.get("compartments", [])

    if not ksp_id or not isinstance(ksp_id, str):
        raise HTTPException(400, detail="id is required and must be a non-empty string")
    if not source_address or not isinstance(source_address, str):
        raise HTTPException(400, detail="source_address is required and must be a non-empty string")
    if not target_address or not isinstance(target_address, str):
        raise HTTPException(400, detail="target_address is required and must be a non-empty string")
    if not max_classification or not isinstance(max_classification, str):
        raise HTTPException(
            400, detail="max_classification is required and must be a non-empty string"
        )

    validate_record_id(ksp_id)

    # Validate D/T/R grammar on source and target addresses
    try:
        from pact.governance import Address

        Address.parse(source_address)
        Address.parse(target_address)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    # Validate classification level
    try:
        from pact_platform.build.config.schema import ConfidentialityLevel

        classification = ConfidentialityLevel(max_classification)
    except (ValueError, KeyError):
        valid = ["public", "restricted", "confidential", "secret", "top_secret"]
        raise HTTPException(
            400, detail=f"Invalid max_classification '{max_classification}'. Valid: {valid}"
        )

    if _engine is None:
        raise HTTPException(503, detail="No governance engine configured")

    # Governance gate — mutation requires approval
    held = await governance_gate(
        source_address,
        "create_ksp",
        {"target_address": target_address, "max_classification": max_classification},
    )
    if held is not None:
        return held

    try:
        from pact.governance import KnowledgeSharePolicy

        ksp = KnowledgeSharePolicy(
            id=ksp_id,
            source_unit_address=source_address,
            target_unit_address=target_address,
            max_classification=classification,
            compartments=frozenset(compartments) if compartments else frozenset(),
        )
        _engine.create_ksp(ksp)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to create KSP '%s': %s", ksp_id, exc)
        raise HTTPException(400, detail="Failed to create KSP")

    return {
        "status": "ok",
        "data": {
            "id": ksp_id,
            "source_address": source_address,
            "target_address": target_address,
            "max_classification": max_classification,
            "compartments": list(compartments),
        },
    }


@router.get("")
@limiter.limit(RATE_GET)
async def list_ksps(request: Request) -> dict:
    """List all Knowledge Share Policies.

    Returns all KSPs from the engine's store if queryable, or 501
    if the engine does not expose a listing method.
    """
    if _engine is None:
        raise HTTPException(503, detail="No governance engine configured")

    # Try to access the KSP store for listing
    ksp_store = getattr(_engine, "_ksp_store", None)
    if ksp_store is None:
        raise HTTPException(
            501, detail="KSP listing not available — engine does not expose KSP store"
        )

    try:
        list_method = getattr(ksp_store, "list_all", None) or getattr(ksp_store, "all", None)
        if list_method is None:
            # Fallback: try to iterate the store's internal data
            data = getattr(ksp_store, "_data", None)
            if data is None:
                raise HTTPException(501, detail="KSP listing not available")
            raw_ksps = list(data.values())
        else:
            raw_ksps = list_method()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to list KSPs: %s", exc)
        raise HTTPException(500, detail="Failed to list KSPs")

    ksps = []
    for ksp in raw_ksps:
        ksps.append(
            {
                "id": getattr(ksp, "id", ""),
                "source_unit_address": getattr(ksp, "source_unit_address", ""),
                "target_unit_address": getattr(ksp, "target_unit_address", ""),
                "max_classification": (
                    getattr(ksp, "max_classification", "").value
                    if hasattr(getattr(ksp, "max_classification", None), "value")
                    else str(getattr(ksp, "max_classification", ""))
                ),
                "active": getattr(ksp, "active", True),
            }
        )

    return {
        "status": "ok",
        "data": {
            "ksps": ksps,
            "count": len(ksps),
        },
    }
