# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bootstrap mode API router -- /api/v1/org/bootstrap.

Bootstrap mode provides time-limited permissive RoleEnvelopes for all
roles in a new org, allowing initial configuration and testing without
requiring complete envelope setup first.  When bootstrap expires or is
ended early, those envelopes are removed and the org falls back to
whatever is configured (or fail-closed defaults).

This is an L3-only feature -- L1 fail-closed behavior is not modified.
The engine creates standard RoleEnvelopes via the normal L1 API; the
only "permissive" part is that the envelope constraints are generous
(but bounded) defaults rather than operator-specified policy.

Issue #23.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from pact_platform.models import (
    MAX_SHORT_STRING,
    db,
    validate_finite,
    validate_record_id,
    validate_string_length,
)
from pact_platform.use.api.governance import governance_gate
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/org/bootstrap", tags=["bootstrap"])

_engine: Any = None
_activation_lock = asyncio.Lock()


def _is_bootstrap_allowed() -> bool:
    """Check env var at request time so it can be disabled without restart."""
    return os.getenv("PACT_ALLOW_BOOTSTRAP_MODE", "false").lower() in (
        "true",
        "1",
        "yes",
    )


# Keep module-level for test patching compatibility
_BOOTSTRAP_ALLOWED: bool | None = None

# Bootstrap envelope constraints -- generous but bounded defaults.
# These are intentionally below production limits to prevent misuse.
_MAX_DURATION_HOURS = 72
_DEFAULT_DURATION_HOURS = 24
_DEFAULT_MAX_BUDGET = 1000.0
_DEFAULT_MAX_DAILY_ACTIONS = 500
_MAX_SINGLE_ACTION_COST = 100.0
_BOOTSTRAP_MAX_CLASSIFICATION = "confidential"


def set_engine(engine: Any) -> None:
    """Inject the GovernanceEngine reference."""
    global _engine
    _engine = engine


def _require_bootstrap_allowed() -> None:
    """Raise 403 if bootstrap mode is not enabled via environment.

    Checks ``_BOOTSTRAP_ALLOWED`` (set by tests) first, then falls back
    to reading the env var at request time so it can be toggled without
    a server restart.
    """
    allowed = _BOOTSTRAP_ALLOWED if _BOOTSTRAP_ALLOWED is not None else _is_bootstrap_allowed()
    if not allowed:
        raise HTTPException(
            403,
            detail=(
                "Bootstrap mode is not enabled. "
                "Set PACT_ALLOW_BOOTSTRAP_MODE=true in the environment to allow it."
            ),
        )


async def _get_active_bootstrap(org_id: str) -> dict[str, Any] | None:
    """Return the active bootstrap record for an org, or None."""
    records = await db.express.list(
        "BootstrapRecord",
        {"org_id": org_id, "status": "active"},
        limit=1,
    )
    if not records:
        return None

    record = records[0]

    # Auto-expire if past deadline
    expires_at_str = record.get("expires_at", "")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now(UTC) >= expires_at:
                await _expire_bootstrap(record)
                return None
        except (ValueError, TypeError):
            pass

    return record


async def _expire_bootstrap(record: dict[str, Any]) -> None:
    """Mark a bootstrap record as expired and remove engine envelopes."""
    await db.express.update(
        "BootstrapRecord",
        record["id"],
        {
            "status": "expired",
            "ended_at": datetime.now(UTC).isoformat(),
        },
    )

    # Remove bootstrap envelopes from engine if available
    if _engine is not None:
        envelope_ids = record.get("envelope_ids", {})
        id_list = envelope_ids.get("ids", []) if isinstance(envelope_ids, dict) else []
        for env_id in id_list:
            try:
                if hasattr(_engine, "remove_role_envelope"):
                    _engine.remove_role_envelope(env_id)
            except Exception as exc:
                logger.warning("Failed to remove bootstrap envelope %s: %s", env_id, exc)

    logger.info("Bootstrap %s expired for org %s", record["id"], record.get("org_id"))


def _build_bootstrap_envelope_config(
    max_budget: float,
    max_daily_actions: int,
) -> dict[str, Any]:
    """Build the envelope config dict for a bootstrap role envelope.

    Returns a dict matching ConstraintEnvelopeConfig structure with
    generous but bounded defaults. Data access is capped at CONFIDENTIAL
    (never SECRET/TOP_SECRET during bootstrap). All bootstrap envelopes
    carry metadata flagging them as bootstrap-created.
    """
    return {
        "financial": {
            "max_budget": max_budget,
            "max_single_action_cost": _MAX_SINGLE_ACTION_COST,
        },
        "operational": {
            "max_daily_actions": max_daily_actions,
        },
        "data_access": {
            "max_classification": _BOOTSTRAP_MAX_CLASSIFICATION,
        },
        "temporal": {},
        "communication": {},
        "metadata": {
            "bootstrap": True,
            "bootstrap_created": True,
        },
    }


@router.post("/activate")
@limiter.limit(RATE_POST)
async def activate_bootstrap(request: Request, body: dict[str, Any]) -> dict:
    """Activate bootstrap mode for an org.

    Creates time-limited permissive RoleEnvelopes for all roles in the
    org via the L1 engine. Requires PACT_ALLOW_BOOTSTRAP_MODE=true.

    Body:
        {
            "org_id": "org-001",
            "duration_hours": 24,       (optional, default 24, max 72)
            "max_budget": 1000.0,       (optional, default 1000.0)
            "max_daily_actions": 500    (optional, default 500)
        }
    """
    _require_bootstrap_allowed()

    org_id = body.get("org_id", "")
    if not org_id or not isinstance(org_id, str):
        raise HTTPException(400, detail="org_id is required and must be a non-empty string")
    validate_string_length(org_id, "org_id", MAX_SHORT_STRING)
    validate_record_id(org_id)

    # Governance gate — bootstrap activation is a high-trust mutation
    held = await governance_gate(org_id, "activate_bootstrap", {"org_id": org_id})
    if held is not None:
        return JSONResponse(content=held, status_code=202)

    duration_hours = body.get("duration_hours", _DEFAULT_DURATION_HOURS)
    if not isinstance(duration_hours, (int, float)):
        raise HTTPException(400, detail="duration_hours must be a number")
    validate_finite(duration_hours=duration_hours)
    if duration_hours <= 0 or duration_hours > _MAX_DURATION_HOURS:
        raise HTTPException(
            400,
            detail=f"duration_hours must be between 1 and {_MAX_DURATION_HOURS}",
        )

    max_budget = body.get("max_budget", _DEFAULT_MAX_BUDGET)
    if not isinstance(max_budget, (int, float)):
        raise HTTPException(400, detail="max_budget must be a number")
    validate_finite(max_budget=max_budget)
    if max_budget <= 0:
        raise HTTPException(400, detail="max_budget must be positive")
    # Upper bound on bootstrap budget — prevent unlimited permissive envelopes
    _MAX_BOOTSTRAP_BUDGET = 10_000.0
    if max_budget > _MAX_BOOTSTRAP_BUDGET:
        raise HTTPException(
            400,
            detail=f"max_budget cannot exceed {_MAX_BOOTSTRAP_BUDGET} during bootstrap",
        )

    max_daily_actions = body.get("max_daily_actions", _DEFAULT_MAX_DAILY_ACTIONS)
    if not isinstance(max_daily_actions, int):
        raise HTTPException(400, detail="max_daily_actions must be an integer")
    if max_daily_actions <= 0:
        raise HTTPException(400, detail="max_daily_actions must be positive")
    # Upper bound on bootstrap actions
    _MAX_BOOTSTRAP_ACTIONS = 5_000
    if max_daily_actions > _MAX_BOOTSTRAP_ACTIONS:
        raise HTTPException(
            400,
            detail=f"max_daily_actions cannot exceed {_MAX_BOOTSTRAP_ACTIONS} during bootstrap",
        )

    # Serialize activation count check + record creation to prevent TOCTOU
    # where two concurrent requests both pass the limit check.
    async with _activation_lock:
        # Limit bootstrap re-activation: max 3 lifetime activations per org
        _MAX_ACTIVATIONS = 3
        all_bootstraps = await db.express.list("BootstrapRecord", {"org_id": org_id}, limit=100)
        if len(all_bootstraps) >= _MAX_ACTIVATIONS:
            raise HTTPException(
                403,
                detail=f"Bootstrap mode has been activated {len(all_bootstraps)} times for org "
                f"'{org_id}' (maximum {_MAX_ACTIVATIONS}). Configure proper envelopes instead.",
            )

        # Check no active bootstrap already exists for this org
        existing = await _get_active_bootstrap(org_id)
        if existing is not None:
            raise HTTPException(
                409,
                detail=(
                    f"Bootstrap mode is already active for org '{org_id}' "
                    f"(expires at {existing.get('expires_at', 'unknown')})"
                ),
            )

        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=duration_hours)
        bootstrap_id = f"boot-{uuid4().hex[:12]}"

        # Create bootstrap envelopes via engine if available
        envelope_ids: list[str] = []
        if _engine is not None and hasattr(_engine, "list_roles"):
            try:
                roles = _engine.list_roles()
                envelope_config = _build_bootstrap_envelope_config(max_budget, max_daily_actions)

                for role in roles:
                    role_address = (
                        role if isinstance(role, str) else getattr(role, "address", str(role))
                    )
                    env_id = f"env-bootstrap-{role_address}-{uuid4().hex[:8]}"

                    try:
                        from pact.governance import RoleEnvelope
                        from pact_platform.build.config.schema import (
                            CommunicationConstraintConfig,
                            ConstraintEnvelopeConfig,
                            DataAccessConstraintConfig,
                            FinancialConstraintConfig,
                            OperationalConstraintConfig,
                            TemporalConstraintConfig,
                        )

                        env_cfg = ConstraintEnvelopeConfig(
                            id=env_id,
                            financial=FinancialConstraintConfig(
                                **(envelope_config.get("financial") or {})
                            ),
                            operational=OperationalConstraintConfig(
                                **(envelope_config.get("operational") or {})
                            ),
                            temporal=TemporalConstraintConfig(
                                **(envelope_config.get("temporal") or {})
                            ),
                            data_access=DataAccessConstraintConfig(
                                **(envelope_config.get("data_access") or {})
                            ),
                            communication=CommunicationConstraintConfig(
                                **(envelope_config.get("communication") or {})
                            ),
                        )

                        role_env = RoleEnvelope(
                            id=env_id,
                            defining_role_address="BOD-R1",  # System address (Board of Directors)
                            target_role_address=role_address,
                            envelope=env_cfg,
                        )
                        _engine.set_role_envelope(role_env)
                        envelope_ids.append(env_id)
                    except Exception as exc:
                        logger.warning(
                            "Failed to create bootstrap envelope for role %s: %s",
                            role_address,
                            exc,
                        )
            except Exception as exc:
                logger.warning("Failed to enumerate roles for bootstrap: %s", exc)

        # Persist the bootstrap record
        await db.express.create(
            "BootstrapRecord",
            {
                "id": bootstrap_id,
                "org_id": org_id,
                "status": "active",
                "started_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "bootstrap_config": {
                    "max_budget": max_budget,
                    "max_daily_actions": max_daily_actions,
                    "duration_hours": duration_hours,
                },
                "envelope_ids": {"ids": envelope_ids},
                "created_at": now.isoformat(),
            },
        )

    logger.info(
        "Bootstrap activated for org %s (id=%s, expires=%s, envelopes=%d)",
        org_id,
        bootstrap_id,
        expires_at.isoformat(),
        len(envelope_ids),
    )

    return {
        "status": "ok",
        "data": {
            "bootstrap_id": bootstrap_id,
            "org_id": org_id,
            "status": "active",
            "started_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "duration_hours": duration_hours,
            "max_budget": max_budget,
            "max_daily_actions": max_daily_actions,
            "envelope_count": len(envelope_ids),
            "envelope_ids": envelope_ids,
        },
    }


@router.get("/status/{org_id}")
@limiter.limit(RATE_GET)
async def get_bootstrap_status(request: Request, org_id: str) -> dict:
    """Get bootstrap status for an org.

    Returns the active bootstrap record or null if no active bootstrap
    exists (either never activated, expired, or ended early).
    """
    validate_record_id(org_id)

    record = await _get_active_bootstrap(org_id)
    if record is None:
        return {
            "status": "ok",
            "data": None,
            "message": f"No active bootstrap for org '{org_id}'",
        }

    return {
        "status": "ok",
        "data": {
            "bootstrap_id": record["id"],
            "org_id": record.get("org_id", ""),
            "status": record.get("status", ""),
            "started_at": record.get("started_at", ""),
            "expires_at": record.get("expires_at", ""),
            "bootstrap_config": record.get("bootstrap_config", {}),
            "envelope_ids": record.get("envelope_ids", {}),
        },
    }


@router.post("/end")
@limiter.limit(RATE_POST)
async def end_bootstrap(request: Request, body: dict[str, Any]) -> dict:
    """End bootstrap mode early for an org.

    Removes all bootstrap envelopes from the engine and marks the
    bootstrap record as ended_early.

    Body:
        {
            "org_id": "org-001",
            "ended_by": "admin@example.com"
        }
    """
    org_id = body.get("org_id", "")
    ended_by = body.get("ended_by", "")

    if not org_id or not isinstance(org_id, str):
        raise HTTPException(400, detail="org_id is required and must be a non-empty string")
    if not ended_by or not isinstance(ended_by, str):
        raise HTTPException(400, detail="ended_by is required and must be a non-empty string")
    validate_record_id(org_id)
    validate_string_length(ended_by, "ended_by", MAX_SHORT_STRING)

    # Governance gate — ending bootstrap is a governance-significant action
    held = await governance_gate(ended_by, "end_bootstrap", {"org_id": org_id})
    if held is not None:
        return JSONResponse(content=held, status_code=202)

    record = await _get_active_bootstrap(org_id)
    if record is None:
        raise HTTPException(
            404,
            detail=f"No active bootstrap found for org '{org_id}'",
        )

    now = datetime.now(UTC)

    # Remove bootstrap envelopes from engine if available
    if _engine is not None:
        envelope_ids = record.get("envelope_ids", {})
        id_list = envelope_ids.get("ids", []) if isinstance(envelope_ids, dict) else []
        for env_id in id_list:
            try:
                if hasattr(_engine, "remove_role_envelope"):
                    _engine.remove_role_envelope(env_id)
            except Exception as exc:
                logger.warning("Failed to remove bootstrap envelope %s: %s", env_id, exc)

    await db.express.update(
        "BootstrapRecord",
        record["id"],
        {
            "status": "ended_early",
            "ended_by": ended_by,
            "ended_at": now.isoformat(),
        },
    )

    logger.info(
        "Bootstrap %s ended early for org %s by %s",
        record["id"],
        org_id,
        ended_by,
    )

    return {
        "status": "ok",
        "data": {
            "bootstrap_id": record["id"],
            "org_id": org_id,
            "status": "ended_early",
            "ended_by": ended_by,
            "ended_at": now.isoformat(),
        },
    }


@router.get("/history/{org_id}")
@limiter.limit(RATE_GET)
async def get_bootstrap_history(request: Request, org_id: str) -> dict:
    """List all bootstrap records for an org.

    Returns active, expired, and ended_early records sorted by
    creation time (most recent first).
    """
    validate_record_id(org_id)

    records = await db.express.list(
        "BootstrapRecord",
        {"org_id": org_id},
        limit=1000,
    )

    # Auto-expire any that are past their deadline
    result_records: list[dict[str, Any]] = []
    for record in records:
        if record.get("status") == "active":
            expires_at_str = record.get("expires_at", "")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if datetime.now(UTC) >= expires_at:
                        await _expire_bootstrap(record)
                        record = await db.express.read("BootstrapRecord", record["id"])
                        if not record or record.get("found") is False:
                            continue
                except (ValueError, TypeError):
                    pass

        result_records.append(
            {
                "bootstrap_id": record.get("id", ""),
                "org_id": record.get("org_id", ""),
                "status": record.get("status", ""),
                "started_at": record.get("started_at", ""),
                "expires_at": record.get("expires_at", ""),
                "bootstrap_config": record.get("bootstrap_config", {}),
                "envelope_ids": record.get("envelope_ids", {}),
                "ended_by": record.get("ended_by", ""),
                "ended_at": record.get("ended_at", ""),
                "created_at": record.get("created_at", ""),
            }
        )

    result_records.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    return {
        "status": "ok",
        "data": result_records,
        "count": len(result_records),
    }
