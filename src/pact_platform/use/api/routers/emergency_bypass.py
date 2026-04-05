# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Emergency bypass API router -- /api/v1/emergency-bypass.

Provides endpoints for creating, checking, expiring, and reviewing
emergency bypass records (PACT spec Section 9).

Emergency bypass is a high-trust operation.  All mutation endpoints
pass through the governance gate.  Rate limiting is applied per-role
by the EmergencyBypass engine (MAX_BYPASSES_PER_WEEK with cooldown).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from pact_platform.use.api.governance import governance_gate
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/emergency-bypass", tags=["emergency-bypass"])

_bypass: Any = None


def set_bypass(bypass: Any) -> None:
    """Inject the EmergencyBypass instance."""
    global _bypass
    _bypass = bypass


def _require_bypass() -> Any:
    """Return the bypass engine or raise 503."""
    if _bypass is None:
        raise HTTPException(503, detail="Emergency bypass engine not configured")
    return _bypass


def _record_to_dict(record: Any) -> dict[str, Any]:
    """Convert a BypassRecord to a JSON-safe dict."""
    return {
        "bypass_id": record.bypass_id,
        "role_address": record.role_address,
        "tier": record.tier.value,
        "reason": record.reason,
        "approved_by": record.approved_by,
        "expanded_envelope": record.expanded_envelope,
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "expired_manually": record.expired_manually,
        "review_due_by": record.review_due_by.isoformat() if record.review_due_by else None,
        "audit_anchor_id": record.audit_anchor_id,
    }


@router.post("")
@limiter.limit(RATE_POST)
async def create_bypass(request: Request, body: dict[str, Any]) -> dict:
    """Create an emergency bypass for a role.

    Body:
        {
            "role_address": "D1-R1",
            "tier": "tier_1",
            "reason": "Production incident requires elevated access",
            "approved_by": "admin@example.com",
            "authority_level": "supervisor",        (optional)
            "expanded_envelope": {...},              (optional)
            "approver_envelope": {...},              (optional, for scope validation)
            "approver_address": "D1-R1-T1-R1",     (optional, for structural validation)
            "target_address": "D1-R1-T2-R1"        (optional, for structural validation)
        }
    """
    bp = _require_bypass()

    role_address = body.get("role_address", "")
    tier_str = body.get("tier", "")
    reason = body.get("reason", "")
    approved_by = body.get("approved_by", "")

    if not role_address or not isinstance(role_address, str):
        raise HTTPException(400, detail="role_address is required and must be a non-empty string")
    if not tier_str or not isinstance(tier_str, str):
        raise HTTPException(400, detail="tier is required and must be a non-empty string")
    if not reason or not isinstance(reason, str):
        raise HTTPException(400, detail="reason is required and must be a non-empty string")
    if not approved_by or not isinstance(approved_by, str):
        raise HTTPException(400, detail="approved_by is required and must be a non-empty string")

    # Validate D/T/R grammar
    try:
        from pact.governance import Address

        Address.parse(role_address)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    # Validate tier
    from pact_platform.engine.emergency_bypass import AuthorityLevel, BypassTier

    try:
        tier = BypassTier(tier_str.lower())
    except (ValueError, KeyError):
        valid = [t.value for t in BypassTier if t != BypassTier.TIER_4]
        raise HTTPException(400, detail=f"Invalid tier '{tier_str}'. Valid: {valid}")

    # Parse optional authority level
    authority_level = None
    authority_str = body.get("authority_level")
    if authority_str:
        try:
            authority_level = AuthorityLevel(authority_str.lower())
        except (ValueError, KeyError):
            valid = [a.value for a in AuthorityLevel]
            raise HTTPException(
                400, detail=f"Invalid authority_level '{authority_str}'. Valid: {valid}"
            )

    # Governance gate — bypass creation is a high-trust mutation
    held = await governance_gate(
        role_address, "create_emergency_bypass", {"tier": tier_str, "reason": reason}
    )
    if held is not None:
        return held

    try:
        record = bp.create_bypass(
            role_address=role_address,
            tier=tier,
            reason=reason,
            approved_by=approved_by,
            expanded_envelope=body.get("expanded_envelope"),
            authority_level=authority_level,
            approver_envelope=body.get("approver_envelope"),
            approver_address=body.get("approver_address"),
            target_address=body.get("target_address"),
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(403, detail=str(exc))

    return {"status": "ok", "data": _record_to_dict(record)}


@router.get("/check/{role_address:path}")
@limiter.limit(RATE_GET)
async def check_bypass(request: Request, role_address: str) -> dict:
    """Check if a role has an active emergency bypass.

    Returns the active bypass record or null.
    """
    bp = _require_bypass()
    record = bp.check_bypass(role_address)
    return {
        "status": "ok",
        "data": _record_to_dict(record) if record else None,
    }


@router.post("/expire/{bypass_id}")
@limiter.limit(RATE_POST)
async def expire_bypass(request: Request, bypass_id: str) -> dict:
    """Manually expire an active bypass."""
    bp = _require_bypass()

    if not bypass_id:
        raise HTTPException(400, detail="bypass_id is required")

    record = bp.expire_bypass(bypass_id)
    if record is None:
        raise HTTPException(404, detail=f"Bypass '{bypass_id}' not found")

    return {"status": "ok", "data": _record_to_dict(record)}


@router.get("/active")
@limiter.limit(RATE_GET)
async def list_active_bypasses(request: Request) -> dict:
    """List all currently active (non-expired) bypass records."""
    bp = _require_bypass()
    records = bp.list_active_bypasses()
    return {
        "status": "ok",
        "data": [_record_to_dict(r) for r in records],
        "count": len(records),
    }


@router.get("/reviews/due")
@limiter.limit(RATE_GET)
async def list_reviews_due(request: Request) -> dict:
    """List bypass records whose post-incident review is due."""
    bp = _require_bypass()
    records = bp.list_reviews_due()
    return {
        "status": "ok",
        "data": [_record_to_dict(r) for r in records],
        "count": len(records),
    }


@router.get("/reviews/overdue")
@limiter.limit(RATE_GET)
async def list_overdue_reviews(request: Request) -> dict:
    """List bypass records whose review deadline has passed."""
    bp = _require_bypass()
    records = bp.check_overdue_reviews()
    return {
        "status": "ok",
        "data": [_record_to_dict(r) for r in records],
        "count": len(records),
    }
