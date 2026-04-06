# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Clearance management API router -- /api/v1/clearance.

Provides endpoints for granting, revoking, and querying knowledge
clearances through the GovernanceEngine.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from pact_platform.models import validate_record_id
from pact_platform.use.api.governance import governance_gate
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/clearance", tags=["clearance"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    """Inject the GovernanceEngine reference."""
    global _engine
    _engine = engine


@router.post("/grant")
@limiter.limit(RATE_POST)
async def grant_clearance(request: Request, body: dict[str, Any]) -> dict:
    """Grant a knowledge clearance to a role.

    Body:
        {
            "role_address": "D1-R1-T1-R1",
            "level": "confidential",
            "compartments": ["finance"],   (optional, default [])
            "nda_signed": false             (optional, default false)
        }
    """
    role_address = body.get("role_address", "")
    level = body.get("level", "")
    compartments = body.get("compartments", [])
    nda_signed = body.get("nda_signed", False)

    if not role_address or not isinstance(role_address, str):
        raise HTTPException(400, detail="role_address is required and must be a non-empty string")
    if not level or not isinstance(level, str):
        raise HTTPException(400, detail="level is required and must be a non-empty string")

    # Validate D/T/R grammar
    try:
        from pact.governance import Address

        Address.parse(role_address)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    # Validate level as a ConfidentialityLevel enum value
    try:
        from pact_platform.build.config.schema import ConfidentialityLevel

        clearance_level = ConfidentialityLevel(level)
    except (ValueError, KeyError):
        valid = ["public", "restricted", "confidential", "secret", "top_secret"]
        raise HTTPException(400, detail=f"Invalid clearance level '{level}'. Valid: {valid}")

    if _engine is None:
        raise HTTPException(503, detail="No governance engine configured")

    # SECRET and TOP_SECRET clearances MUST go through the vetting workflow
    # (POST /api/v1/vetting/submit) which enforces multi-approver quorum.
    # This prevents FSM bypass via the direct grant endpoint.
    if level in ("secret", "top_secret"):
        raise HTTPException(
            400,
            detail=(
                f"Clearance level '{level}' requires the vetting workflow. "
                f"Use POST /api/v1/vetting/submit instead."
            ),
        )

    # Governance gate — mutation requires approval
    held = await governance_gate(role_address, "grant_clearance", {"level": level})
    if held is not None:
        return held

    try:
        from pact.governance import RoleClearance

        clr = RoleClearance(
            role_address=role_address,
            max_clearance=clearance_level,
            compartments=frozenset(compartments) if compartments else frozenset(),
            nda_signed=bool(nda_signed),
        )
        _engine.grant_clearance(role_address, clr)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to grant clearance for %s: %s", role_address, exc)
        raise HTTPException(400, detail="Failed to grant clearance")

    return {
        "status": "ok",
        "data": {
            "role_address": role_address,
            "level": level,
            "compartments": list(compartments),
            "nda_signed": nda_signed,
        },
    }


@router.post("/revoke")
@limiter.limit(RATE_POST)
async def revoke_clearance(request: Request, body: dict[str, Any]) -> dict:
    """Revoke a knowledge clearance from a role.

    Body:
        {"role_address": "D1-R1-T1-R1"}
    """
    role_address = body.get("role_address", "")

    if not role_address or not isinstance(role_address, str):
        raise HTTPException(400, detail="role_address is required and must be a non-empty string")

    # Validate D/T/R grammar
    try:
        from pact.governance import Address

        Address.parse(role_address)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    if _engine is None:
        raise HTTPException(503, detail="No governance engine configured")

    # Governance gate — mutation requires approval
    held = await governance_gate(role_address, "revoke_clearance")
    if held is not None:
        return held

    try:
        _engine.revoke_clearance(role_address)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to revoke clearance for %s: %s", role_address, exc)
        raise HTTPException(400, detail="Failed to revoke clearance")

    return {
        "status": "ok",
        "data": {
            "role_address": role_address,
            "message": "Clearance revoked",
        },
    }


@router.get("/{role_address}")
@limiter.limit(RATE_GET)
async def get_clearance(request: Request, role_address: str) -> dict:
    """Get the clearance for a role.

    Returns the governance context's clearance information for the
    given role address.
    """
    # Validate D/T/R grammar
    try:
        from pact.governance import Address

        Address.parse(role_address)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    if _engine is None:
        raise HTTPException(503, detail="No governance engine configured")

    try:
        ctx = _engine.get_context(role_address)
    except Exception as exc:
        logger.warning("Failed to get context for %s: %s", role_address, exc)
        raise HTTPException(404, detail=f"No clearance found for role address: {role_address}")

    clearance = getattr(ctx, "clearance", None)
    if clearance is None:
        raise HTTPException(404, detail=f"No clearance found for role address: {role_address}")

    return {
        "status": "ok",
        "data": {
            "role_address": clearance.role_address,
            "max_clearance": (
                clearance.max_clearance.value
                if hasattr(clearance.max_clearance, "value")
                else str(clearance.max_clearance)
            ),
            "compartments": list(clearance.compartments),
            "vetting_status": (
                clearance.vetting_status.value
                if hasattr(clearance.vetting_status, "value")
                else str(clearance.vetting_status)
            ),
            "nda_signed": clearance.nda_signed,
        },
    }
