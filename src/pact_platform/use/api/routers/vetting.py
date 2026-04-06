# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Clearance vetting workflow API router -- /api/v1/clearance/vetting.

Implements the clearance vetting FSM with multi-approver quorum,
state transitions, and L1 engine integration for granting or
suspending clearances.

FSM states:
    pending -> active | rejected | expired
    active  -> suspended | revoked | expired
    suspended -> revoked  (reinstate creates a NEW pending vetting)
    rejected, expired, revoked are terminal.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from pact_platform.models import (
    MAX_LONG_STRING,
    MAX_SHORT_STRING,
    db,
    validate_dtr_address,
    validate_record_id,
    validate_string_length,
)
from pact_platform.use.api.governance import governance_gate
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter
from pact_platform.use.services.multi_approver import MultiApproverService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vetting", tags=["clearance-vetting"])

# ---------------------------------------------------------------------------
# FSM transition table
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"active", "rejected", "expired"},
    "active": {"suspended", "revoked", "expired"},
    "suspended": {"revoked"},  # reinstate creates NEW pending vetting
    "rejected": set(),  # terminal
    "expired": set(),  # terminal
    "revoked": set(),  # terminal
}

# All valid vetting statuses (union of all keys)
_VALID_STATUSES = tuple(_VALID_TRANSITIONS.keys())

# Approver count by clearance level
_APPROVERS_BY_LEVEL: dict[str, int] = {
    "public": 1,
    "restricted": 1,
    "confidential": 1,
    "secret": 2,
    "top_secret": 3,
}

# Valid clearance levels
_VALID_LEVELS = tuple(_APPROVERS_BY_LEVEL.keys())

# ---------------------------------------------------------------------------
# Module-level engine and service references
# ---------------------------------------------------------------------------

_engine: Any = None
_approver_service: MultiApproverService | None = None


def set_engine(engine: Any) -> None:
    """Inject the GovernanceEngine reference."""
    global _engine
    _engine = engine


def set_approver_service(service: MultiApproverService) -> None:
    """Inject the MultiApproverService instance."""
    global _approver_service
    _approver_service = service


_validate_dtr_address = validate_dtr_address  # Alias for backward compatibility


def _validate_clearance_level(level: str) -> str:
    """Validate that *level* is a known clearance level.

    Raises:
        HTTPException 400: On invalid level.
    """
    try:
        from pact_platform.build.config.schema import ConfidentialityLevel

        ConfidentialityLevel(level)
    except (ValueError, KeyError):
        raise HTTPException(
            400,
            detail=f"Invalid clearance level '{level}'. Valid: {list(_VALID_LEVELS)}",
        )
    return level


def _validate_transition(current_status: str, target_status: str) -> None:
    """Validate an FSM transition.

    Raises:
        HTTPException 409: If the transition is not allowed.
    """
    allowed = _VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            409,
            detail=(
                f"Cannot transition from '{current_status}' to '{target_status}'. "
                f"Allowed transitions: {sorted(allowed) if allowed else 'none (terminal state)'}"
            ),
        )


async def _read_vetting(vetting_id: str) -> dict[str, Any]:
    """Read and validate a vetting record exists.

    Raises:
        HTTPException 404: If not found.
    """
    validate_record_id(vetting_id)
    result = await db.express.read("ClearanceVetting", vetting_id)
    if not result or result.get("found") is False:
        raise HTTPException(404, detail=f"Vetting request '{vetting_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/submit", status_code=201, response_model=None)
@limiter.limit(RATE_POST)
async def submit_vetting(request: Request, body: dict[str, Any]) -> dict | Response:
    """Submit a new clearance vetting request.

    Body:
        {
            "role_address": "D1-R1-T1-R1",
            "level": "secret",
            "compartments": ["alpha"],   (optional)
            "nda_signed": true,          (optional)
            "requested_by": "D1-R1"
        }
    """
    role_address = body.get("role_address", "")
    level = body.get("level", "")
    requested_by = body.get("requested_by", "")

    # Required fields
    if not role_address or not isinstance(role_address, str):
        raise HTTPException(400, detail="role_address is required and must be a non-empty string")
    if not level or not isinstance(level, str):
        raise HTTPException(400, detail="level is required and must be a non-empty string")
    if not requested_by or not isinstance(requested_by, str):
        raise HTTPException(400, detail="requested_by is required and must be a non-empty string")

    # Input length validation
    validate_string_length(role_address, "role_address", MAX_SHORT_STRING)
    validate_string_length(requested_by, "requested_by", MAX_SHORT_STRING)

    # Validate D/T/R grammar
    _validate_dtr_address(role_address, "role_address")

    # Validate clearance level
    _validate_clearance_level(level)

    # Optional fields
    compartments = body.get("compartments", [])
    if not isinstance(compartments, list):
        raise HTTPException(400, detail="compartments must be a list of strings")
    if not all(isinstance(c, str) for c in compartments):
        raise HTTPException(400, detail="All compartment values must be strings")
    nda_signed = bool(body.get("nda_signed", False))

    # Determine required approvals
    required_approvals = _APPROVERS_BY_LEVEL.get(level, 1)

    # Governance gate -- submitting a vetting request is a mutation
    held = await governance_gate(
        role_address,
        "submit_clearance_vetting",
        {"resource": "clearance_vetting", "level": level},
    )
    if held is not None:
        return JSONResponse(content=held, status_code=202)

    vetting_id = f"vet-{uuid4().hex[:12]}"

    await db.express.create(
        "ClearanceVetting",
        {
            "id": vetting_id,
            "role_address": role_address,
            "requested_level": level,
            "requested_compartments": {"values": compartments},
            "current_status": "pending",
            "requested_by": requested_by,
            "nda_signed": nda_signed,
            "required_approvals": required_approvals,
            "current_approvals": 0,
            "approval_record_ids": {"ids": []},
        },
    )

    logger.info(
        "Vetting %s submitted for %s at level %s (requires %d approvals)",
        vetting_id,
        role_address,
        level,
        required_approvals,
    )

    return {
        "status": "ok",
        "data": {
            "vetting_id": vetting_id,
            "role_address": role_address,
            "level": level,
            "current_status": "pending",
            "required_approvals": required_approvals,
        },
    }


@router.post("/{vetting_id}/approve", response_model=None)
@limiter.limit(RATE_POST)
async def approve_vetting(
    request: Request, vetting_id: str, body: dict[str, Any]
) -> dict | Response:
    """Record an approval for a pending vetting request.

    When quorum is met, the vetting transitions to ``active`` and
    the L1 engine grants the clearance.

    Body:
        {
            "approver_address": "D1-R1",
            "approver_identity": "Jane Smith",  (optional)
            "reason": "Background check passed"  (optional)
        }
    """
    record = await _read_vetting(vetting_id)

    current_status = record.get("current_status", "")
    if current_status != "pending":
        raise HTTPException(
            409,
            detail=f"Vetting '{vetting_id}' is not pending (current status: {current_status})",
        )

    approver_address = body.get("approver_address", "")
    if not approver_address or not isinstance(approver_address, str):
        raise HTTPException(
            400, detail="approver_address is required and must be a non-empty string"
        )
    validate_string_length(approver_address, "approver_address", MAX_SHORT_STRING)
    _validate_dtr_address(approver_address, "approver_address")

    approver_identity = body.get("approver_identity", "")
    if approver_identity:
        validate_string_length(approver_identity, "approver_identity", MAX_SHORT_STRING)
    reason = body.get("reason", "")
    if reason:
        validate_string_length(reason, "reason", MAX_LONG_STRING)

    if _approver_service is None:
        raise HTTPException(503, detail="Multi-approver service not configured")

    # Check approver eligibility against ApprovalConfig.eligible_roles
    level = record.get("requested_level", "")
    op_type = f"grant_clearance_{level}" if level else "grant_clearance"
    try:
        configs = await db.express.list("ApprovalConfig", {"operation_type": op_type}, limit=1)
        if configs:
            eligible = configs[0].get("eligible_roles", {})
            patterns = eligible.get("patterns", []) if isinstance(eligible, dict) else []
            if patterns:
                matched = any(
                    approver_address.startswith(p.rstrip("*"))
                    for p in patterns
                    if isinstance(p, str)
                )
                if not matched:
                    raise HTTPException(
                        403,
                        detail=(
                            f"Approver '{approver_address}' is not eligible for "
                            f"operation '{op_type}'"
                        ),
                    )
    except HTTPException:
        raise
    except Exception:
        logger.debug("ApprovalConfig eligibility check failed for %s — allowing", op_type)

    # Record the approval (raises ValueError on duplicate)
    try:
        approval_result = await _approver_service.record_approval(
            decision_id=vetting_id,
            approver_address=approver_address,
            approver_identity=approver_identity,
            reason=reason,
        )
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc))

    current_approvals = approval_result["current_approvals"]
    required_approvals = record.get("required_approvals", 1)

    # Update the vetting record's approval count
    update_fields: dict[str, Any] = {
        "current_approvals": current_approvals,
    }

    # Collect approval record IDs
    existing_ids = record.get("approval_record_ids", {}).get("ids", [])
    existing_ids.append(approval_result["approval_id"])
    update_fields["approval_record_ids"] = {"ids": existing_ids}

    quorum_met = current_approvals >= required_approvals

    if quorum_met:
        # Transition to active
        _validate_transition(current_status, "active")
        update_fields["current_status"] = "active"

        # Grant clearance via L1 engine if available
        if _engine is not None:
            try:
                from pact.governance import RoleClearance
                from pact_platform.build.config.schema import ConfidentialityLevel

                compartment_values = record.get("requested_compartments", {}).get("values", [])
                clr = RoleClearance(
                    role_address=record["role_address"],
                    max_clearance=ConfidentialityLevel(record["requested_level"]),
                    compartments=frozenset(compartment_values),
                    nda_signed=record.get("nda_signed", False),
                )
                _engine.grant_clearance(record["role_address"], clr)
                logger.info(
                    "L1 clearance granted for %s at level %s via vetting %s",
                    record["role_address"],
                    record["requested_level"],
                    vetting_id,
                )
            except Exception as exc:
                logger.warning("Failed to grant L1 clearance for vetting %s: %s", vetting_id, exc)

    await db.express.update("ClearanceVetting", vetting_id, update_fields)

    return {
        "status": "ok",
        "data": {
            "vetting_id": vetting_id,
            "approval_id": approval_result["approval_id"],
            "current_approvals": current_approvals,
            "required_approvals": required_approvals,
            "quorum_met": quorum_met,
            "current_status": "active" if quorum_met else "pending",
        },
    }


@router.post("/{vetting_id}/reject", response_model=None)
@limiter.limit(RATE_POST)
async def reject_vetting(
    request: Request, vetting_id: str, body: dict[str, Any]
) -> dict | Response:
    """Reject a pending vetting request.

    Body:
        {
            "rejector_address": "D1-R1",
            "reason": "Insufficient justification"
        }
    """
    record = await _read_vetting(vetting_id)

    current_status = record.get("current_status", "")
    _validate_transition(current_status, "rejected")

    rejector_address = body.get("rejector_address", "")
    rejection_reason = body.get("reason", "")

    # Governance gate — rejection is a governance-significant action
    held = await governance_gate(rejector_address or "system", "reject_clearance_vetting")
    if held is not None:
        return held

    if not rejector_address or not isinstance(rejector_address, str):
        raise HTTPException(
            400, detail="rejector_address is required and must be a non-empty string"
        )
    if not rejection_reason or not isinstance(rejection_reason, str):
        raise HTTPException(400, detail="reason is required and must be a non-empty string")

    validate_string_length(rejector_address, "rejector_address", MAX_SHORT_STRING)
    validate_string_length(rejection_reason, "reason", MAX_LONG_STRING)
    _validate_dtr_address(rejector_address, "rejector_address")

    await db.express.update(
        "ClearanceVetting",
        vetting_id,
        {
            "current_status": "rejected",
            "reason": rejection_reason,
            "rejected_by": rejector_address,
            "rejected_reason": rejection_reason,
        },
    )

    logger.info("Vetting %s rejected by %s: %s", vetting_id, rejector_address, rejection_reason)

    return {
        "status": "ok",
        "data": {
            "vetting_id": vetting_id,
            "current_status": "rejected",
            "rejected_by": rejector_address,
            "reason": rejection_reason,
        },
    }


@router.post("/{vetting_id}/suspend", response_model=None)
@limiter.limit(RATE_POST)
async def suspend_vetting(
    request: Request, vetting_id: str, body: dict[str, Any]
) -> dict | Response:
    """Suspend an active clearance.

    Body:
        {
            "suspended_by": "D1-R1",
            "reason": "Security incident under investigation"
        }
    """
    record = await _read_vetting(vetting_id)

    current_status = record.get("current_status", "")
    _validate_transition(current_status, "suspended")

    suspended_by = body.get("suspended_by", "")
    suspension_reason = body.get("reason", "")

    if not suspended_by or not isinstance(suspended_by, str):
        raise HTTPException(400, detail="suspended_by is required and must be a non-empty string")
    if not suspension_reason or not isinstance(suspension_reason, str):
        raise HTTPException(400, detail="reason is required and must be a non-empty string")

    validate_string_length(suspended_by, "suspended_by", MAX_SHORT_STRING)
    validate_string_length(suspension_reason, "reason", MAX_LONG_STRING)
    _validate_dtr_address(suspended_by, "suspended_by")

    # Governance gate — suspension is a governance-significant action
    held = await governance_gate(suspended_by, "suspend_clearance")
    if held is not None:
        return held

    await db.express.update(
        "ClearanceVetting",
        vetting_id,
        {
            "current_status": "suspended",
            "suspended_by": suspended_by,
            "suspended_reason": suspension_reason,
        },
    )

    # Update L1 clearance vetting_status if engine is available
    if _engine is not None:
        role_address = record.get("role_address", "")
        try:
            ctx = _engine.get_context(role_address)
            clearance = getattr(ctx, "clearance", None)
            if clearance is not None and hasattr(clearance, "vetting_status"):
                from pact.governance import RoleClearance
                from pact_platform.build.config.schema import ConfidentialityLevel

                compartment_values = record.get("requested_compartments", {}).get("values", [])
                updated_clr = RoleClearance(
                    role_address=role_address,
                    max_clearance=ConfidentialityLevel(record.get("requested_level", "public")),
                    compartments=frozenset(compartment_values),
                    nda_signed=record.get("nda_signed", False),
                    vetting_status="suspended",
                )
                _engine.grant_clearance(role_address, updated_clr)
                logger.info("L1 clearance vetting_status set to suspended for %s", role_address)
        except Exception as exc:
            logger.warning(
                "Failed to update L1 clearance vetting_status for %s: %s",
                role_address,
                exc,
            )

    logger.info("Vetting %s suspended by %s: %s", vetting_id, suspended_by, suspension_reason)

    return {
        "status": "ok",
        "data": {
            "vetting_id": vetting_id,
            "current_status": "suspended",
            "suspended_by": suspended_by,
            "reason": suspension_reason,
        },
    }


@router.post("/{vetting_id}/reinstate", status_code=201, response_model=None)
@limiter.limit(RATE_POST)
async def reinstate_vetting(
    request: Request, vetting_id: str, body: dict[str, Any]
) -> dict | Response:
    """Reinstate a suspended clearance.

    The suspended vetting is transitioned to ``revoked`` and a NEW
    pending vetting request is created that goes through fresh
    approval.

    Body:
        {
            "requested_by": "D1-R1"
        }
    """
    record = await _read_vetting(vetting_id)

    current_status = record.get("current_status", "")
    if current_status != "suspended":
        raise HTTPException(
            409,
            detail=(
                f"Only suspended vettings can be reinstated " f"(current status: {current_status})"
            ),
        )

    requested_by = body.get("requested_by", "")
    if not requested_by or not isinstance(requested_by, str):
        raise HTTPException(400, detail="requested_by is required and must be a non-empty string")
    validate_string_length(requested_by, "requested_by", MAX_SHORT_STRING)
    _validate_dtr_address(requested_by, "requested_by")

    # Governance gate — reinstatement creates a new vetting
    held = await governance_gate(requested_by, "reinstate_clearance")
    if held is not None:
        return held

    # Transition the suspended vetting to revoked
    _validate_transition(current_status, "revoked")
    await db.express.update(
        "ClearanceVetting",
        vetting_id,
        {
            "current_status": "revoked",
            "revoked_by": requested_by,
            "revoked_reason": "Revoked for reinstatement -- new vetting created",
        },
    )

    # Create a NEW pending vetting with the same parameters
    role_address = record.get("role_address", "")
    level = record.get("requested_level", "")
    compartments = record.get("requested_compartments", {}).get("values", [])
    nda_signed = record.get("nda_signed", False)
    required_approvals = _APPROVERS_BY_LEVEL.get(level, 1)

    new_vetting_id = f"vet-{uuid4().hex[:12]}"

    await db.express.create(
        "ClearanceVetting",
        {
            "id": new_vetting_id,
            "role_address": role_address,
            "requested_level": level,
            "requested_compartments": {"values": compartments},
            "current_status": "pending",
            "requested_by": requested_by,
            "nda_signed": nda_signed,
            "required_approvals": required_approvals,
            "current_approvals": 0,
            "approval_record_ids": {"ids": []},
            "reason": f"Reinstatement of suspended vetting {vetting_id}",
        },
    )

    logger.info(
        "Vetting %s revoked for reinstatement; new vetting %s created",
        vetting_id,
        new_vetting_id,
    )

    return {
        "status": "ok",
        "data": {
            "original_vetting_id": vetting_id,
            "original_status": "revoked",
            "new_vetting_id": new_vetting_id,
            "new_status": "pending",
            "role_address": role_address,
            "level": level,
            "required_approvals": required_approvals,
        },
    }


@router.get("")
@limiter.limit(RATE_GET)
async def list_vettings(
    request: Request,
    status: Optional[str] = Query(None),
    role_address: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """List vetting requests with optional filters."""
    filt: dict[str, Any] = {}
    if status:
        if status not in _VALID_STATUSES:
            raise HTTPException(400, detail=f"status must be one of: {', '.join(_VALID_STATUSES)}")
        filt["current_status"] = status
    if role_address:
        filt["role_address"] = role_address

    records = await db.express.list("ClearanceVetting", filt, limit=limit, offset=offset)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}


@router.get("/{vetting_id}")
@limiter.limit(RATE_GET)
async def get_vetting(request: Request, vetting_id: str) -> dict:
    """Get vetting detail."""
    record = await _read_vetting(vetting_id)
    return record
