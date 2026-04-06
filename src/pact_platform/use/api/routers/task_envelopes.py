# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Task envelope lifecycle API router -- /api/v1/governance/task-envelopes.

Manages the lifecycle of task envelopes: creation with mandatory expiry,
agent acknowledgment/rejection, and active envelope queries.  This is
separate from the envelopes.py router (which handles set_task via PUT) --
this router adds lifecycle operations (acknowledge, reject, list, expire).

L3 TaskEnvelopeRecord persists the envelope across restarts and schedules
auto-expiry.  L1 EnvelopeStore remains the runtime source of truth.

Issue #24.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from pact_platform.models import (
    MAX_LONG_STRING,
    MAX_SHORT_STRING,
    db,
    validate_dtr_address,
    validate_finite,
    validate_record_id,
    validate_string_length,
)
from pact_platform.use.api.governance import governance_gate
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/governance/task-envelopes", tags=["task-envelopes"])

_engine: Any = None

# Maximum allowed expiry window: 30 days from now.
_MAX_EXPIRY_DAYS = 30


def set_engine(engine: Any) -> None:
    """Inject the GovernanceEngine reference."""
    global _engine
    _engine = engine


def _validate_role_address(role_address: str) -> None:
    """Validate a D/T/R address string, raising 400 on failure."""
    validate_dtr_address(role_address, "role_address")


def _validate_expires_at(expires_at_str: str) -> datetime:
    """Parse and validate an ISO 8601 expires_at string.

    Must be in the future and within 30 days.

    Returns:
        Parsed datetime object.

    Raises:
        HTTPException 400: On invalid format or out-of-range value.
    """
    if not expires_at_str or not isinstance(expires_at_str, str):
        raise HTTPException(
            400,
            detail="expires_at is required and must be an ISO 8601 datetime string",
        )

    try:
        expires_at = datetime.fromisoformat(expires_at_str)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            400,
            detail=f"expires_at is not valid ISO 8601: {exc}",
        )

    # Ensure timezone-aware comparison
    now = datetime.now(UTC)
    if expires_at.tzinfo is None:
        # Treat naive datetimes as UTC
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at <= now:
        raise HTTPException(400, detail="expires_at must be in the future")

    max_expiry = now + timedelta(days=_MAX_EXPIRY_DAYS)
    if expires_at > max_expiry:
        raise HTTPException(
            400,
            detail=f"expires_at must be within {_MAX_EXPIRY_DAYS} days from now",
        )

    return expires_at


def _validate_envelope_config_numerics(config: dict[str, Any], _depth: int = 0) -> None:
    """Recursively validate all numeric fields in an envelope config.

    Raises ValueError on NaN/Inf per trust-plane-security.md Rule 3.
    """
    if _depth > 10:
        raise ValueError("Envelope config nesting too deep (max 10 levels)")
    for key, value in config.items():
        if isinstance(value, dict):
            _validate_envelope_config_numerics(value, _depth + 1)
        elif isinstance(value, (int, float)):
            validate_finite(**{key: value})


@router.get("/{role_address}/active")
@limiter.limit(RATE_GET)
async def list_active_task_envelopes(request: Request, role_address: str) -> dict:
    """List active (non-expired) task envelopes for a role.

    Returns envelopes with status "active" or "acknowledged", sorted
    by creation time (most recent first).
    """
    _validate_role_address(role_address)

    # Fetch both active and acknowledged envelopes
    active_records = await db.express.list(
        "TaskEnvelopeRecord",
        {"role_address": role_address, "status": "active"},
        limit=1000,
    )
    acknowledged_records = await db.express.list(
        "TaskEnvelopeRecord",
        {"role_address": role_address, "status": "acknowledged"},
        limit=1000,
    )

    all_records = active_records + acknowledged_records

    # Auto-expire any that are past their deadline
    result_records: list[dict[str, Any]] = []
    now = datetime.now(UTC)
    for record in all_records:
        expires_at_str = record.get("expires_at", "")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if now >= expires_at:
                    await db.express.update(
                        "TaskEnvelopeRecord",
                        record["id"],
                        {"status": "expired"},
                    )
                    logger.info(
                        "Task envelope %s auto-expired for role %s",
                        record["id"],
                        role_address,
                    )
                    continue
            except (ValueError, TypeError):
                pass

        result_records.append(record)

    result_records.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    return {
        "status": "ok",
        "data": result_records,
        "count": len(result_records),
    }


@router.get("/{role_address}/{task_id}")
@limiter.limit(RATE_GET)
async def get_task_envelope(request: Request, role_address: str, task_id: str) -> dict:
    """Get a specific task envelope record.

    Looks up by role_address and task_id, excluding expired records.
    """
    _validate_role_address(role_address)
    validate_record_id(task_id)

    records = await db.express.list(
        "TaskEnvelopeRecord",
        {"role_address": role_address, "task_id": task_id},
        limit=10,
    )

    # Filter out expired records
    for record in records:
        status = record.get("status", "")
        if status == "expired":
            continue

        # Auto-expire if past deadline
        expires_at_str = record.get("expires_at", "")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if datetime.now(UTC) >= expires_at:
                    await db.express.update(
                        "TaskEnvelopeRecord",
                        record["id"],
                        {"status": "expired"},
                    )
                    continue
            except (ValueError, TypeError):
                pass

        return {"status": "ok", "data": record}

    raise HTTPException(
        404,
        detail=f"No active task envelope found for role '{role_address}' task '{task_id}'",
    )


@router.post("/{role_address}/{task_id}/acknowledge")
@limiter.limit(RATE_POST)
async def acknowledge_task_envelope(
    request: Request,
    role_address: str,
    task_id: str,
    body: dict[str, Any],
) -> dict:
    """Agent acknowledges a task envelope.

    Transitions the envelope from "active" to "acknowledged", recording
    who acknowledged it and when.

    Body:
        {
            "acknowledged_by": "agent-001"
        }
    """
    _validate_role_address(role_address)
    validate_record_id(task_id)

    acknowledged_by = body.get("acknowledged_by", "")
    if not acknowledged_by or not isinstance(acknowledged_by, str):
        raise HTTPException(
            400,
            detail="acknowledged_by is required and must be a non-empty string",
        )
    validate_string_length(acknowledged_by, "acknowledged_by", MAX_SHORT_STRING)

    # Governance gate — acknowledge is a state mutation
    held = await governance_gate(role_address, "acknowledge_task_envelope", {"task_id": task_id})
    if held is not None:
        return held

    # Find the active record
    records = await db.express.list(
        "TaskEnvelopeRecord",
        {"role_address": role_address, "task_id": task_id, "status": "active"},
        limit=1,
    )
    if not records:
        raise HTTPException(
            404,
            detail=(
                f"No active task envelope found for role '{role_address}' "
                f"task '{task_id}' (may already be acknowledged, rejected, or expired)"
            ),
        )

    record = records[0]

    # Check expiry before acknowledging
    expires_at_str = record.get("expires_at", "")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= expires_at:
                await db.express.update(
                    "TaskEnvelopeRecord",
                    record["id"],
                    {"status": "expired"},
                )
                raise HTTPException(
                    409,
                    detail="Task envelope has expired and cannot be acknowledged",
                )
        except HTTPException:
            raise
        except (ValueError, TypeError):
            pass

    now = datetime.now(UTC)
    await db.express.update(
        "TaskEnvelopeRecord",
        record["id"],
        {
            "status": "acknowledged",
            "acknowledged_at": now.isoformat(),
            "acknowledged_by": acknowledged_by,
        },
    )

    logger.info(
        "Task envelope %s acknowledged by %s for role %s task %s",
        record["id"],
        acknowledged_by,
        role_address,
        task_id,
    )

    return {
        "status": "ok",
        "data": {
            "record_id": record["id"],
            "task_id": task_id,
            "role_address": role_address,
            "status": "acknowledged",
            "acknowledged_at": now.isoformat(),
            "acknowledged_by": acknowledged_by,
        },
    }


@router.post("/{role_address}/{task_id}/reject")
@limiter.limit(RATE_POST)
async def reject_task_envelope(
    request: Request,
    role_address: str,
    task_id: str,
    body: dict[str, Any],
) -> dict:
    """Agent rejects a task envelope.

    Transitions the envelope from "active" to "rejected", recording
    who rejected it and the reason.

    Body:
        {
            "rejected_by": "agent-001",
            "reason": "Constraints too restrictive for this task"
        }
    """
    _validate_role_address(role_address)
    validate_record_id(task_id)

    rejected_by = body.get("rejected_by", "")
    reason = body.get("reason", "")

    if not rejected_by or not isinstance(rejected_by, str):
        raise HTTPException(
            400,
            detail="rejected_by is required and must be a non-empty string",
        )
    validate_string_length(rejected_by, "rejected_by", MAX_SHORT_STRING)
    if not reason or not isinstance(reason, str):
        raise HTTPException(
            400,
            detail="reason is required and must be a non-empty string",
        )
    validate_string_length(reason, "reason", MAX_LONG_STRING)

    # Governance gate — rejection is a state mutation
    held = await governance_gate(role_address, "reject_task_envelope", {"task_id": task_id})
    if held is not None:
        return held

    # Find the active record
    records = await db.express.list(
        "TaskEnvelopeRecord",
        {"role_address": role_address, "task_id": task_id, "status": "active"},
        limit=1,
    )
    if not records:
        raise HTTPException(
            404,
            detail=(
                f"No active task envelope found for role '{role_address}' "
                f"task '{task_id}' (may already be acknowledged, rejected, or expired)"
            ),
        )

    record = records[0]

    # Check expiry before rejecting
    expires_at_str = record.get("expires_at", "")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= expires_at:
                await db.express.update(
                    "TaskEnvelopeRecord",
                    record["id"],
                    {"status": "expired"},
                )
                raise HTTPException(
                    409,
                    detail="Task envelope has expired and cannot be rejected",
                )
        except HTTPException:
            raise
        except (ValueError, TypeError):
            pass

    await db.express.update(
        "TaskEnvelopeRecord",
        record["id"],
        {
            "status": "rejected",
            "rejection_reason": reason,
        },
    )

    logger.info(
        "Task envelope %s rejected by %s for role %s task %s: %s",
        record["id"],
        rejected_by,
        role_address,
        task_id,
        reason,
    )

    return {
        "status": "ok",
        "data": {
            "record_id": record["id"],
            "task_id": task_id,
            "role_address": role_address,
            "status": "rejected",
            "rejected_by": rejected_by,
            "reason": reason,
        },
    }


@router.post("/create")
@limiter.limit(RATE_POST)
async def create_task_envelope(request: Request, body: dict[str, Any]) -> dict:
    """Create a task envelope with required expiry.

    Creates a TaskEnvelopeRecord at L3 for persistence and lifecycle,
    and if the governance engine is available, constructs an L1
    TaskEnvelope and registers it with the engine.

    Body:
        {
            "task_id": "task-001",
            "role_address": "D1-R1",
            "parent_envelope_id": "env-analyst",    (optional)
            "envelope_config": {
                "financial": {"max_budget": 500.0},
                "operational": {"max_daily_actions": 50},
                ...
            },
            "expires_at": "2026-04-07T12:00:00+00:00"
        }
    """
    task_id = body.get("task_id", "")
    role_address = body.get("role_address", "")
    parent_envelope_id = body.get("parent_envelope_id", "")
    envelope_config = body.get("envelope_config", {})
    expires_at_str = body.get("expires_at", "")

    # Validate required fields
    if not task_id or not isinstance(task_id, str):
        raise HTTPException(400, detail="task_id is required and must be a non-empty string")
    validate_record_id(task_id)
    validate_string_length(task_id, "task_id", MAX_SHORT_STRING)

    _validate_role_address(role_address)

    if parent_envelope_id:
        validate_record_id(parent_envelope_id)

    if not envelope_config or not isinstance(envelope_config, dict):
        raise HTTPException(
            400,
            detail="envelope_config is required and must be a non-empty dict",
        )

    # Validate envelope config numerics (NaN/Inf guard)
    try:
        _validate_envelope_config_numerics(envelope_config)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    # Validate and parse expires_at
    expires_at = _validate_expires_at(expires_at_str)

    # Governance gate — task envelope creation is a mutation that affects constraints
    held = await governance_gate(role_address, "create_task_envelope", {"task_id": task_id})
    if held is not None:
        return held

    now = datetime.now(UTC)
    record_id = f"tenv-{uuid4().hex[:12]}"
    env_id = f"task-env-{task_id}-{uuid4().hex[:8]}"

    # Register with L1 engine if available
    if _engine is not None:
        try:
            from pact.governance import TaskEnvelope
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
                financial=FinancialConstraintConfig(**(envelope_config.get("financial") or {})),
                operational=OperationalConstraintConfig(
                    **(envelope_config.get("operational") or {})
                ),
                temporal=TemporalConstraintConfig(**(envelope_config.get("temporal") or {})),
                data_access=DataAccessConstraintConfig(
                    **(envelope_config.get("data_access") or {})
                ),
                communication=CommunicationConstraintConfig(
                    **(envelope_config.get("communication") or {})
                ),
            )
            task_env = TaskEnvelope(
                id=env_id,
                task_id=task_id,
                parent_envelope_id=parent_envelope_id or "",
                envelope=env_cfg,
            )
            _engine.set_task_envelope(task_env)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(
                "Failed to register task envelope with L1 engine for role %s task %s: %s",
                role_address,
                task_id,
                exc,
            )
            raise HTTPException(400, detail="Failed to register task envelope with engine")

    # Persist the L3 record
    await db.express.create(
        "TaskEnvelopeRecord",
        {
            "id": record_id,
            "task_id": task_id,
            "role_address": role_address,
            "parent_envelope_id": parent_envelope_id,
            "envelope_config": envelope_config,
            "status": "active",
            "expires_at": expires_at.isoformat(),
            "created_at": now.isoformat(),
        },
    )

    logger.info(
        "Task envelope %s created for role %s task %s (expires %s)",
        record_id,
        role_address,
        task_id,
        expires_at.isoformat(),
    )

    return {
        "status": "ok",
        "data": {
            "record_id": record_id,
            "task_id": task_id,
            "role_address": role_address,
            "parent_envelope_id": parent_envelope_id,
            "envelope_id": env_id,
            "status": "active",
            "expires_at": expires_at.isoformat(),
            "created_at": now.isoformat(),
        },
    }
