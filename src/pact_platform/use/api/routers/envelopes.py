# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Envelope management API router -- /api/v1/envelopes.

Provides endpoints for querying and setting role/task envelopes
through the GovernanceEngine.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from pact_platform.models import validate_finite, validate_record_id
from pact_platform.use.api.governance import governance_gate
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/governance/envelopes", tags=["envelopes"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    """Inject the GovernanceEngine reference."""
    global _engine
    _engine = engine


def _validate_envelope_numerics(config: dict[str, Any]) -> None:
    """Validate all numeric fields in an envelope config dict.

    Recursively checks nested dicts (financial, operational, temporal,
    data_access, communication) for NaN/Inf values.
    """
    for key, value in config.items():
        if isinstance(value, dict):
            _validate_envelope_numerics(value)
        elif isinstance(value, (int, float)):
            validate_finite(**{key: value})


@router.get("/{role_address}")
@limiter.limit(RATE_GET)
async def get_envelope(request: Request, role_address: str) -> dict:
    """Get the effective (computed) envelope for a role.

    Returns the merged envelope that accounts for the full hierarchy
    of role and task envelopes via monotonic tightening.
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
        envelope_config = _engine.compute_envelope(role_address)
    except Exception as exc:
        logger.warning("Failed to compute envelope for %s: %s", role_address, exc)
        raise HTTPException(500, detail="Failed to compute envelope")

    if envelope_config is None:
        return {
            "status": "ok",
            "data": {
                "role_address": role_address,
                "envelope": None,
                "message": "No envelope configured — role operates under default (maximally restrictive) constraints",
            },
        }

    # Serialize the envelope config to a dict
    envelope_data: dict[str, Any] = {}
    if hasattr(envelope_config, "to_dict"):
        envelope_data = envelope_config.to_dict()
    elif hasattr(envelope_config, "__dict__"):
        envelope_data = {k: v for k, v in envelope_config.__dict__.items() if not k.startswith("_")}
    else:
        envelope_data = {"raw": str(envelope_config)}

    return {
        "status": "ok",
        "data": {
            "role_address": role_address,
            "envelope": envelope_data,
        },
    }


@router.put("/{role_address}/role")
@limiter.limit(RATE_POST)
async def set_role_envelope(request: Request, role_address: str, body: dict[str, Any]) -> dict:
    """Set the role envelope for a role.

    Body:
        {
            "defining_role_address": "D1-R1",
            "envelope": {
                "id": "env-analyst",
                "financial": {"max_budget": 1000.0},
                "operational": {"max_daily_actions": 100},
                ...
            }
        }
    """
    defining_role = body.get("defining_role_address", "")
    envelope_dict = body.get("envelope", {})

    if not defining_role or not isinstance(defining_role, str):
        raise HTTPException(
            400, detail="defining_role_address is required and must be a non-empty string"
        )
    if not envelope_dict or not isinstance(envelope_dict, dict):
        raise HTTPException(400, detail="envelope is required and must be a non-empty dict")

    # Validate D/T/R grammar for both addresses
    try:
        from pact.governance import Address

        Address.parse(role_address)
        Address.parse(defining_role)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    # Validate numeric fields
    try:
        _validate_envelope_numerics(envelope_dict)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    if _engine is None:
        raise HTTPException(503, detail="No governance engine configured")

    # Governance gate — mutation requires approval
    held = await governance_gate(defining_role, "set_role_envelope", {"target": role_address})
    if held is not None:
        return held

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

        env_id = envelope_dict.get("id", f"env-{role_address}")
        env_config = ConstraintEnvelopeConfig(
            id=env_id,
            financial=FinancialConstraintConfig(**(envelope_dict.get("financial") or {})),
            operational=OperationalConstraintConfig(**(envelope_dict.get("operational") or {})),
            temporal=TemporalConstraintConfig(**(envelope_dict.get("temporal") or {})),
            data_access=DataAccessConstraintConfig(**(envelope_dict.get("data_access") or {})),
            communication=CommunicationConstraintConfig(
                **(envelope_dict.get("communication") or {})
            ),
        )
        role_env = RoleEnvelope(
            id=env_id,
            defining_role_address=defining_role,
            target_role_address=role_address,
            envelope=env_config,
        )
        _engine.set_role_envelope(role_env)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to set role envelope for %s: %s", role_address, exc)
        raise HTTPException(400, detail="Failed to set role envelope")

    return {
        "status": "ok",
        "data": {
            "role_address": role_address,
            "defining_role_address": defining_role,
            "message": "Role envelope set successfully",
        },
    }


@router.put("/{role_address}/task")
@limiter.limit(RATE_POST)
async def set_task_envelope(request: Request, role_address: str, body: dict[str, Any]) -> dict:
    """Set the task envelope for a role.

    Body:
        {
            "task_id": "task-001",
            "parent_envelope_id": "env-analyst",
            "envelope": {
                "id": "task-env-001",
                "financial": {"max_budget": 500.0},
                ...
            }
        }
    """
    task_id = body.get("task_id", "")
    parent_envelope_id = body.get("parent_envelope_id", "")
    envelope_dict = body.get("envelope", {})

    if not task_id or not isinstance(task_id, str):
        raise HTTPException(400, detail="task_id is required and must be a non-empty string")
    if not envelope_dict or not isinstance(envelope_dict, dict):
        raise HTTPException(400, detail="envelope is required and must be a non-empty dict")

    validate_record_id(task_id)
    if parent_envelope_id:
        validate_record_id(parent_envelope_id)

    # Validate D/T/R grammar
    try:
        from pact.governance import Address

        Address.parse(role_address)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    # Validate numeric fields
    try:
        _validate_envelope_numerics(envelope_dict)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    if _engine is None:
        raise HTTPException(503, detail="No governance engine configured")

    # Governance gate — mutation requires approval
    held = await governance_gate(role_address, "set_task_envelope", {"task_id": task_id})
    if held is not None:
        return held

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

        env_id = envelope_dict.get("id", f"task-env-{task_id}")
        env_config = ConstraintEnvelopeConfig(
            id=env_id,
            financial=FinancialConstraintConfig(**(envelope_dict.get("financial") or {})),
            operational=OperationalConstraintConfig(**(envelope_dict.get("operational") or {})),
            temporal=TemporalConstraintConfig(**(envelope_dict.get("temporal") or {})),
            data_access=DataAccessConstraintConfig(**(envelope_dict.get("data_access") or {})),
            communication=CommunicationConstraintConfig(
                **(envelope_dict.get("communication") or {})
            ),
        )
        task_env = TaskEnvelope(
            id=env_id,
            task_id=task_id,
            parent_envelope_id=parent_envelope_id or "",
            envelope=env_config,
        )
        _engine.set_task_envelope(task_env)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to set task envelope for %s: %s", role_address, exc)
        raise HTTPException(400, detail="Failed to set task envelope")

    return {
        "status": "ok",
        "data": {
            "role_address": role_address,
            "task_id": task_id,
            "message": "Task envelope set successfully",
        },
    }
