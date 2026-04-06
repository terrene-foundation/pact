# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Access check API router -- /api/v1/access.

Provides a read-only endpoint for checking whether a role can access
a knowledge item given the current clearance, KSP, and compartment
configuration.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from pact_platform.models import validate_record_id
from pact_platform.use.api.rate_limit import RATE_POST, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/access", tags=["access"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    """Inject the GovernanceEngine reference."""
    global _engine
    _engine = engine


@router.post("/check")
@limiter.limit(RATE_POST)
async def check_access(request: Request, body: dict[str, Any]) -> dict:
    """Check whether a role can access a knowledge item.

    This is a read-only query (no governance gate needed) that evaluates
    the clearance, KSP, and compartment rules for the given role.

    Body:
        {
            "role_address": "D1-R1-T1-R1",
            "item_id": "doc-finance-q4",
            "classification": "confidential",
            "owning_unit_address": "D2",
            "compartments": [],                 (optional, default [])
            "posture": "supervised"             (optional, default "supervised")
        }
    """
    role_address = body.get("role_address", "")
    item_id = body.get("item_id", "")
    classification = body.get("classification", "")
    owning_unit = body.get("owning_unit_address", "")
    compartments = body.get("compartments", [])
    posture_str = body.get("posture", "supervised")

    if not role_address or not isinstance(role_address, str):
        raise HTTPException(400, detail="role_address is required and must be a non-empty string")
    if not item_id or not isinstance(item_id, str):
        raise HTTPException(400, detail="item_id is required and must be a non-empty string")

    # If classification is not provided but item_id is, look up the
    # persisted KnowledgeRecord to populate classification, owning_unit,
    # and compartments.  This allows access checks with just
    # {"role_address", "item_id"} when the item is in the database.
    if not classification:
        from pact_platform.models import db

        kr_records = await db.express.list("KnowledgeRecord", {"item_id": item_id}, limit=1)
        if kr_records:
            kr = kr_records[0]
            classification = kr.get("classification", "")
            if not owning_unit:
                owning_unit = kr.get("owning_unit_address", "")
            if not compartments:
                compartments = kr.get("compartments", {}).get("values", [])

    if not classification or not isinstance(classification, str):
        raise HTTPException(400, detail="classification is required and must be a non-empty string")
    if not owning_unit or not isinstance(owning_unit, str):
        raise HTTPException(
            400, detail="owning_unit_address is required and must be a non-empty string"
        )

    validate_record_id(item_id)

    # Validate D/T/R grammar on role_address
    try:
        from pact.governance import Address

        Address.parse(role_address)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    # Validate classification
    try:
        from pact_platform.build.config.schema import ConfidentialityLevel

        item_classification = ConfidentialityLevel(classification)
    except (ValueError, KeyError):
        valid = ["public", "restricted", "confidential", "secret", "top_secret"]
        raise HTTPException(
            400, detail=f"Invalid classification '{classification}'. Valid: {valid}"
        )

    # Validate posture
    try:
        from pact import TrustPostureLevel

        posture = TrustPostureLevel(posture_str)
    except (ValueError, KeyError):
        valid = [
            "delegated",
            "continuous_insight",
            "shared_planning",
            "supervised",
            "pseudo_agent",
        ]
        raise HTTPException(400, detail=f"Invalid posture '{posture_str}'. Valid: {valid}")

    if _engine is None:
        raise HTTPException(503, detail="No governance engine configured")

    try:
        from pact.governance import KnowledgeItem

        knowledge_item = KnowledgeItem(
            item_id=item_id,
            classification=item_classification,
            owning_unit_address=owning_unit,
            compartments=frozenset(compartments) if compartments else frozenset(),
        )
        decision = _engine.check_access(role_address, knowledge_item, posture)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Access check failed for %s on %s: %s", role_address, item_id, exc)
        raise HTTPException(500, detail="Access check failed")

    return {
        "status": "ok",
        "data": {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "step_failed": decision.step_failed,
            "role_address": role_address,
            "item_id": item_id,
            "classification": classification,
            "posture": posture_str,
        },
    }
