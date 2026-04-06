# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Knowledge record CRUD API router -- /api/v1/knowledge.

Provides endpoints for creating, listing, retrieving, updating, and
soft-deleting persistent knowledge records with classification and
compartment assignments.  Knowledge records back the access-check
endpoint by allowing lookups by ``item_id``.

Uses DataFlow Express API for all CRUD operations.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

# Valid classification levels (matches ConfidentialityLevel enum values)
_VALID_CLASSIFICATIONS = ("public", "restricted", "confidential", "secret", "top_secret")

# Valid record statuses
_VALID_STATUSES = ("active", "archived", "deleted")


def _validate_classification(classification: str) -> str:
    """Validate classification against ConfidentialityLevel enum.

    Falls back to a string check against the known valid values if the
    enum import fails (e.g., in tests without the full kailash-pact stack).

    Returns:
        The validated classification string.

    Raises:
        HTTPException 400: On invalid classification.
    """
    try:
        from pact_platform.build.config.schema import ConfidentialityLevel

        ConfidentialityLevel(classification)
    except ImportError:
        # Fallback string check when enum is not available
        if classification not in _VALID_CLASSIFICATIONS:
            raise HTTPException(
                400,
                detail=(
                    f"Invalid classification '{classification}'. "
                    f"Valid: {list(_VALID_CLASSIFICATIONS)}"
                ),
            )
    except (ValueError, KeyError):
        raise HTTPException(
            400,
            detail=(
                f"Invalid classification '{classification}'. "
                f"Valid: {list(_VALID_CLASSIFICATIONS)}"
            ),
        )
    return classification


_validate_dtr_address = validate_dtr_address  # Alias for backward compatibility


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=None)
@limiter.limit(RATE_POST)
async def create_knowledge_record(request: Request, body: dict[str, Any]) -> dict | Response:
    """Create a new knowledge record.

    Body:
        {
            "item_id": "doc-finance-q4",
            "classification": "confidential",
            "owning_unit_address": "D1-R1",
            "compartments": ["alpha", "beta"],   (optional)
            "title": "Q4 Finance Report",        (optional)
            "description": "...",                 (optional)
            "created_by": "D1-R1-T1-R1"          (optional)
        }
    """
    item_id = body.get("item_id", "")
    classification = body.get("classification", "")
    owning_unit_address = body.get("owning_unit_address", "")

    # Required fields
    if not item_id or not isinstance(item_id, str):
        raise HTTPException(400, detail="item_id is required and must be a non-empty string")
    if not classification or not isinstance(classification, str):
        raise HTTPException(400, detail="classification is required and must be a non-empty string")
    if not owning_unit_address or not isinstance(owning_unit_address, str):
        raise HTTPException(
            400, detail="owning_unit_address is required and must be a non-empty string"
        )

    # Input length validation
    validate_string_length(item_id, "item_id", MAX_SHORT_STRING)
    validate_string_length(owning_unit_address, "owning_unit_address", MAX_SHORT_STRING)

    # Validate classification against ConfidentialityLevel enum
    _validate_classification(classification)

    # Validate owning_unit_address as D/T/R
    _validate_dtr_address(owning_unit_address, "owning_unit_address")

    # Optional fields
    compartments = body.get("compartments", [])
    if not isinstance(compartments, list):
        raise HTTPException(400, detail="compartments must be a list of strings")
    if not all(isinstance(c, str) for c in compartments):
        raise HTTPException(400, detail="All compartment values must be strings")
    title = body.get("title", "")
    description = body.get("description", "")
    created_by = body.get("created_by", "")

    if title:
        validate_string_length(title, "title", MAX_SHORT_STRING)
    if description:
        validate_string_length(description, "description", MAX_LONG_STRING)
    if created_by:
        validate_string_length(created_by, "created_by", MAX_SHORT_STRING)

    # Governance gate -- mutation requires approval
    held = await governance_gate(
        owning_unit_address,
        "create_knowledge_record",
        {"resource": "knowledge_record"},
    )
    if held is not None:
        return JSONResponse(content=held, status_code=202)

    # Check for duplicate item_id
    existing = await db.express.list("KnowledgeRecord", {"item_id": item_id}, limit=1)
    if existing:
        raise HTTPException(409, detail=f"Knowledge record with item_id '{item_id}' already exists")

    record_id = f"kr-{uuid4().hex[:12]}"

    return await db.express.create(
        "KnowledgeRecord",
        {
            "id": record_id,
            "item_id": item_id,
            "classification": classification,
            "owning_unit_address": owning_unit_address,
            "compartments": {"values": compartments},
            "title": title,
            "description": description,
            "created_by": created_by,
            "status": "active",
        },
    )


@router.get("")
@limiter.limit(RATE_GET)
async def list_knowledge_records(
    request: Request,
    classification: Optional[str] = Query(None),
    owning_unit_address: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """List knowledge records with optional filters."""
    filt: dict[str, Any] = {}
    if classification:
        filt["classification"] = classification
    if owning_unit_address:
        filt["owning_unit_address"] = owning_unit_address
    if status:
        if status not in _VALID_STATUSES:
            raise HTTPException(400, detail=f"status must be one of: {', '.join(_VALID_STATUSES)}")
        filt["status"] = status

    records = await db.express.list("KnowledgeRecord", filt, limit=limit, offset=offset)
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}


@router.get("/{item_id}")
@limiter.limit(RATE_GET)
async def get_knowledge_record(request: Request, item_id: str) -> dict:
    """Get a knowledge record by item_id."""
    validate_record_id(item_id)
    records = await db.express.list("KnowledgeRecord", {"item_id": item_id}, limit=1)
    if not records:
        raise HTTPException(404, detail=f"Knowledge record with item_id '{item_id}' not found")
    return records[0]


@router.put("/{item_id}", response_model=None)
@limiter.limit(RATE_POST)
async def update_knowledge_record(
    request: Request, item_id: str, body: dict[str, Any]
) -> dict | Response:
    """Update a knowledge record's classification, compartments, or status.

    Only the following fields may be updated:
    classification, compartments, title, description, status.

    Body:
        {
            "classification": "secret",
            "compartments": ["alpha"],
            "title": "Updated title",
            "description": "Updated description",
            "status": "archived"
        }
    """
    validate_record_id(item_id)

    # Look up by item_id
    records = await db.express.list("KnowledgeRecord", {"item_id": item_id}, limit=1)
    if not records:
        raise HTTPException(404, detail=f"Knowledge record with item_id '{item_id}' not found")
    record = records[0]
    record_id = record["id"]

    # Only allow updates to specific fields
    _UPDATABLE_FIELDS = {"classification", "compartments", "title", "description", "status"}
    fields: dict[str, Any] = {}

    for key, value in body.items():
        if key in _UPDATABLE_FIELDS:
            fields[key] = value

    if not fields:
        raise HTTPException(400, detail="No updatable fields provided")

    # Validate classification if provided
    if "classification" in fields:
        _validate_classification(str(fields["classification"]))

    # Validate compartments format if provided
    if "compartments" in fields:
        compartments = fields["compartments"]
        if not isinstance(compartments, list):
            raise HTTPException(400, detail="compartments must be a list of strings")
        fields["compartments"] = {"values": compartments}

    # Validate title/description lengths
    if "title" in fields:
        validate_string_length(str(fields["title"]), "title", MAX_SHORT_STRING)
    if "description" in fields:
        validate_string_length(str(fields["description"]), "description", MAX_LONG_STRING)

    # Validate status if provided
    if "status" in fields:
        if fields["status"] not in _VALID_STATUSES:
            raise HTTPException(400, detail=f"status must be one of: {', '.join(_VALID_STATUSES)}")

    # Governance gate -- mutation always requires approval (fail-closed: H1 fix)
    owning_unit = record.get("owning_unit_address", "") or "system"
    held = await governance_gate(
        owning_unit,
        "update_knowledge_record",
        {"resource": "knowledge_record"},
    )
    if held is not None:
        return JSONResponse(content=held, status_code=202)

    return await db.express.update("KnowledgeRecord", record_id, fields)


@router.delete("/{item_id}", response_model=None)
@limiter.limit(RATE_POST)
async def delete_knowledge_record(request: Request, item_id: str) -> dict | Response:
    """Soft-delete a knowledge record (sets status to 'deleted').

    The record is not physically removed -- its status is set to
    ``deleted`` so that audit trails remain intact.
    """
    validate_record_id(item_id)

    records = await db.express.list("KnowledgeRecord", {"item_id": item_id}, limit=1)
    if not records:
        raise HTTPException(404, detail=f"Knowledge record with item_id '{item_id}' not found")
    record = records[0]
    record_id = record["id"]

    # Governance gate -- deletion always requires approval (fail-closed: H1 fix)
    owning_unit = record.get("owning_unit_address", "") or "system"
    held = await governance_gate(
        owning_unit,
        "delete_knowledge_record",
        {"resource": "knowledge_record"},
    )
    if held is not None:
        return JSONResponse(content=held, status_code=202)

    return await db.express.update("KnowledgeRecord", record_id, {"status": "deleted"})
