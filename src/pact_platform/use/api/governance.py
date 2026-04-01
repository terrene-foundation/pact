# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared governance gate for API routers.

Provides a module-level GovernanceEngine reference and a ``governance_gate()``
function that mutation endpoints call before persisting state changes.

Architecture:
    - The engine is set once at startup or org deploy (via ``set_engine()``).
    - ``org.py`` also calls ``set_engine()`` on deploy.
    - Mutation endpoints call ``governance_gate()`` which maps verdicts to
      HTTP responses: BLOCKED→403, HELD→202+decision record, APPROVED→None.
    - Read-only endpoints do NOT need governance gates.
    - When no engine is configured: dev mode allows, production blocks (fail-closed).

See rules/governance.md Rule 11: All governance decisions must route through
GovernanceEngine.verify_action().
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from pact_platform.models import db, validate_finite

logger = logging.getLogger(__name__)

__all__ = ["set_engine", "get_engine", "governance_gate", "is_governance_active"]

# Module-level engine reference — set by server.py startup or org deploy.
_engine: Any = None
_dev_mode: bool = False
_dev_mode_frozen: bool = False


def set_engine(engine: Any) -> None:
    """Inject the GovernanceEngine reference."""
    global _engine
    _engine = engine


def get_engine() -> Any:
    """Return the current engine (or None)."""
    return _engine


def is_governance_active() -> bool:
    """Return True if a governance engine is configured (not in dev-mode passthrough)."""
    return _engine is not None


def set_dev_mode(enabled: bool) -> None:
    """Set dev-mode flag (allows operations without governance engine).

    Frozen after first call — subsequent calls are silently ignored.
    """
    global _dev_mode, _dev_mode_frozen
    if _dev_mode_frozen:
        logger.warning("set_dev_mode called after freeze — ignoring")
        return
    _dev_mode = enabled
    _dev_mode_frozen = True


async def governance_gate(
    org_address: str,
    action: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Verify an action through the GovernanceEngine.

    Args:
        org_address: D/T/R address of the acting role.
        action: The action being performed (e.g. ``"create_objective"``).
        context: Optional context dict (cost, resource, etc.).

    Returns:
        ``None`` if the action is approved (caller should proceed).
        A dict response if the action was HELD (caller should return this
        as a 202 response instead of proceeding).

    Raises:
        HTTPException 403: If the action is BLOCKED by governance.
        HTTPException 503: If no engine is configured and not in dev mode.
    """
    if _engine is None:
        if _dev_mode:
            logger.debug(
                "Governance engine not configured (dev mode) — allowing %s for %s",
                action,
                org_address,
            )
            return None
        raise HTTPException(
            503,
            detail="Governance engine not initialized — deploy an org first",
        )

    ctx = context or {}

    # NaN-guard any cost value
    cost_val = ctx.get("cost")
    if cost_val is not None:
        validate_finite(cost=cost_val)

    try:
        verdict = _engine.verify_action(
            role_address=org_address,
            action=action,
            context=ctx if ctx else None,
        )
    except Exception:
        # Fail-closed: treat engine errors as BLOCKED
        logger.warning(
            "Governance engine error for action %s by %s — fail-closed", action, org_address
        )
        raise HTTPException(403, detail="Governance verification failed — action blocked")

    level = verdict.level

    if level == "blocked":
        logger.info("Action %s BLOCKED for %s: %s", action, org_address, verdict.reason)
        raise HTTPException(
            403,
            detail="Action blocked by governance",
        )

    if level == "held":
        # Create a decision record for human review
        decision_id = f"dec-{uuid4().hex[:12]}"
        await db.express.create(
            "AgenticDecision",
            {
                "id": decision_id,
                "agent_address": org_address,
                "action": action,
                "decision_type": "governance_hold",
                "status": "pending",
                "reason_held": verdict.reason,
                "urgency": "normal",
                "envelope_version": (
                    int(verdict.envelope_version)
                    if hasattr(verdict, "envelope_version") and verdict.envelope_version
                    else 0
                ),
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        logger.info(
            "Action %s HELD for %s (decision %s): %s",
            action,
            org_address,
            decision_id,
            verdict.reason,
        )
        return {
            "status": "held",
            "decision_id": decision_id,
            "reason": "Action held for review",
        }

    # auto_approved or flagged — proceed
    if level == "flagged":
        logger.warning("Action %s FLAGGED for %s: %s", action, org_address, verdict.reason)
    elif level not in ("auto_approved",):
        # Unknown verdict level — fail-closed
        logger.warning("Unknown governance verdict level %r for %s — fail-closed", level, action)
        raise HTTPException(403, detail="Governance verification failed — action blocked")

    return None
