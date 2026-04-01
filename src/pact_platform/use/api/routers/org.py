# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Org management API router -- /api/v1/org.

Provides endpoints for loading and deploying organizational structures
through the GovernanceEngine.  The frontend org-builder page uses these
to load existing orgs and deploy YAML definitions.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from typing import Any

import yaml as yaml_lib
from fastapi import APIRouter, HTTPException, Request

from pact_platform.use.api.governance import set_engine as _set_shared_engine
from pact_platform.use.api.rate_limit import RATE_GET, RATE_POST, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/org", tags=["org"])

# Module-level engine reference — kept in sync with shared governance module.
_engine: Any = None
_deploy_lock = threading.Lock()


def set_engine(engine: Any) -> None:
    """Inject the GovernanceEngine reference into both org router and shared governance module."""
    global _engine
    _engine = engine
    _set_shared_engine(engine)


@router.get("/structure")
@limiter.limit(RATE_GET)
async def get_org_structure(request: Request) -> dict:
    """Return the compiled org tree for the org-builder frontend.

    Returns the org name, departments, teams, and roles in a shape
    the frontend OrgTree component expects.
    """
    if _engine is None:
        raise HTTPException(
            status_code=503,
            detail="Governance engine not initialized — run 'pact quickstart' or 'pact org create' first",
        )

    try:
        compiled = _engine.get_org()
    except Exception:
        logger.warning("Failed to get compiled org from engine — returning 500")
        raise HTTPException(500, detail="Failed to load org structure")

    # compiled.nodes is dict[str, OrgNode]
    nodes = []
    for address, node in compiled.nodes.items():
        nodes.append(
            {
                "address": address,
                "type": getattr(node, "type", "unknown"),
                "name": getattr(node, "name", address),
                "parent_address": getattr(node, "parent_address", None),
                "role_id": getattr(node, "role_id", None),
            }
        )

    return {
        "status": "ok",
        "data": {
            "org_name": compiled.org_id,
            "nodes": nodes,
            "node_count": len(nodes),
        },
    }


@router.post("/deploy")
@limiter.limit(RATE_POST)
async def deploy_org(request: Request, body: dict[str, Any]) -> dict:
    """Deploy an org definition from YAML.

    Accepts a YAML string, parses it, compiles via GovernanceEngine,
    and returns the compiled node count.  Governance specs (clearances,
    envelopes, bridges, KSPs) are applied if present in the YAML.

    Body:
        {"yaml": "<yaml-string>"}
    """
    yaml_str = body.get("yaml", "")
    if not yaml_str or not isinstance(yaml_str, str):
        raise HTTPException(400, detail="'yaml' field is required and must be a non-empty string")

    if len(yaml_str) > 1_048_576:
        raise HTTPException(413, detail="YAML payload exceeds 1MB limit")

    try:
        parsed = yaml_lib.safe_load(yaml_str)
    except yaml_lib.YAMLError:
        raise HTTPException(400, detail="Invalid YAML syntax")

    # F6: Check nesting depth to prevent resource exhaustion
    def _max_depth(obj: Any, depth: int = 0) -> int:
        if depth > 50:
            return depth
        if isinstance(obj, dict):
            return max((_max_depth(v, depth + 1) for v in obj.values()), default=depth)
        if isinstance(obj, list):
            return max((_max_depth(v, depth + 1) for v in obj), default=depth)
        return depth

    if parsed is not None and _max_depth(parsed) > 50:
        raise HTTPException(400, detail="YAML nesting depth exceeds limit (max 50)")

    try:
        from pact.governance import GovernanceEngine, load_org_yaml
    except ImportError:
        raise HTTPException(
            501,
            detail="pact.governance not available — ensure kailash-pact is installed",
        )

    # S7: Serialize deploy operations to prevent concurrent engine replacement.
    # S8: Single try/finally covers all temp file paths.
    tmp_path: str | None = None
    try:
        with _deploy_lock:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(yaml_str)
                tmp_path = tmp.name

            loaded = load_org_yaml(tmp_path)

            audit_chain = None
            try:
                from pact_platform.cli import _make_audit_chain

                audit_chain = _make_audit_chain()
            except Exception:
                logger.warning(
                    "Audit chain creation failed — governance mutations will not be audited",
                )

            try:
                from pact_platform.cli import _create_engine

                engine = _create_engine(loaded.org_definition, audit_chain=audit_chain)
            except ImportError:
                engine = GovernanceEngine(loaded.org_definition, audit_chain=audit_chain)
            compiled = engine.get_org()

            _apply_governance_specs(engine, loaded, compiled)

            global _engine
            _engine = engine
            _set_shared_engine(engine)

        return {
            "status": "ok",
            "data": {
                "message": f"Org compiled successfully with {len(compiled.nodes)} nodes",
                "compiled_nodes": len(compiled.nodes),
                "org_id": compiled.org_id,
            },
        }
    except HTTPException:
        raise
    except Exception:
        logger.warning("Org deployment failed for submitted YAML")
        raise HTTPException(400, detail="Org compilation failed")
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _apply_governance_specs(engine: Any, loaded: Any, compiled: Any) -> None:
    """Best-effort application of governance specs from a LoadedOrg.

    Mirrors the CLI's org_create logic. Skips specs that fail to resolve
    rather than aborting the entire deploy.
    """
    for spec in loaded.clearances:
        try:
            from pact.governance import RoleClearance
            from pact_platform.build.config.schema import ConfidentialityLevel

            node = compiled.get_node_by_role_id(spec.role_id)
            if node is None:
                continue
            clr = RoleClearance(
                role_address=node.address,
                max_clearance=ConfidentialityLevel(spec.level),
                compartments=frozenset(spec.compartments),
                nda_signed=spec.nda_signed,
            )
            engine.grant_clearance(node.address, clr)
        except Exception:
            logger.warning("Skipped clearance for role '%s'", spec.role_id, exc_info=False)

    for spec in loaded.envelopes:
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

            target_node = compiled.get_node_by_role_id(spec.target)
            definer_node = compiled.get_node_by_role_id(spec.defined_by)
            if target_node is None or definer_node is None:
                continue
            env_config = ConstraintEnvelopeConfig(
                id=f"env-{spec.target}",
                financial=FinancialConstraintConfig(**(spec.financial or {})),
                operational=OperationalConstraintConfig(**(spec.operational or {})),
                temporal=TemporalConstraintConfig(**(spec.temporal or {})),
                data_access=DataAccessConstraintConfig(**(spec.data_access or {})),
                communication=CommunicationConstraintConfig(**(spec.communication or {})),
            )
            role_env = RoleEnvelope(
                id=f"env-{spec.target}",
                defining_role_address=definer_node.address,
                target_role_address=target_node.address,
                envelope=env_config,
            )
            engine.set_role_envelope(role_env)
        except Exception:
            logger.warning("Skipped envelope for target '%s'", spec.target, exc_info=False)

    for spec in loaded.bridges:
        try:
            from pact.governance import PactBridge
            from pact_platform.build.config.schema import ConfidentialityLevel

            role_a_node = compiled.get_node_by_role_id(spec.role_a)
            role_b_node = compiled.get_node_by_role_id(spec.role_b)
            if role_a_node is None or role_b_node is None:
                continue
            bridge = PactBridge(
                id=spec.id,
                role_a_address=role_a_node.address,
                role_b_address=role_b_node.address,
                bridge_type=spec.bridge_type,
                max_classification=ConfidentialityLevel(spec.max_classification),
                bilateral=spec.bilateral,
            )
            engine.create_bridge(bridge)
        except Exception:
            logger.warning("Skipped bridge '%s'", spec.id, exc_info=False)

    for spec in loaded.ksps:
        try:
            from pact.governance import KnowledgeSharePolicy
            from pact_platform.build.config.schema import ConfidentialityLevel

            ksp = KnowledgeSharePolicy(
                id=spec.id,
                source_unit_address=spec.source,
                target_unit_address=spec.target,
                max_classification=ConfidentialityLevel(spec.max_classification),
            )
            engine.create_ksp(ksp)
        except Exception:
            logger.warning("Skipped KSP '%s'", spec.id, exc_info=False)


@router.post("/bridges/approve")
@limiter.limit(RATE_POST)
async def approve_bridge_lca(request: Request, body: dict[str, Any]) -> dict:
    """Pre-approve a bridge via lowest-common-ancestor (LCA) check.

    The approver must be the LCA of both roles in the org tree.
    Approval is required before create_bridge() will succeed.
    Approvals expire after 24 hours.

    Body:
        {"source_address": "...", "target_address": "...", "approver_address": "..."}
    """
    source = body.get("source_address", "")
    target = body.get("target_address", "")
    approver = body.get("approver_address", "")

    if not source or not target or not approver:
        raise HTTPException(
            400, detail="source_address, target_address, and approver_address are required"
        )

    # C2 fix: validate D/T/R grammar on all address inputs
    try:
        from pact.governance import Address

        Address.parse(source)
        Address.parse(target)
        Address.parse(approver)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    if _engine is None:
        raise HTTPException(503, detail="Governance engine not initialized")

    try:
        approval = _engine.approve_bridge(source, target, approver)
    except Exception:
        logger.warning("Bridge LCA approval failed for source=%s target=%s", source, target)
        raise HTTPException(400, detail="Bridge approval failed — approver may not be the LCA")

    return {
        "status": "ok",
        "data": {
            "source_address": approval.source_address,
            "target_address": approval.target_address,
            "approved_by": approval.approved_by,
            "approved_at": str(approval.approved_at),
            "expires_at": str(approval.expires_at),
        },
    }


@router.post("/roles/{role_address}/designate-acting")
@limiter.limit(RATE_POST)
async def designate_acting_occupant(
    request: Request, role_address: str, body: dict[str, Any]
) -> dict:
    """Designate an acting occupant for a vacant role.

    When a role becomes vacant, the parent role must designate an acting
    occupant within 24 hours. If no designation, all downstream agents
    are auto-suspended.

    Body:
        {"acting_role_address": "...", "designated_by": "..."}
    """
    acting = body.get("acting_role_address", "")
    designated_by = body.get("designated_by", "")

    if not acting or not designated_by:
        raise HTTPException(400, detail="acting_role_address and designated_by are required")

    # C2 fix: validate D/T/R grammar on all address inputs
    try:
        from pact.governance import Address

        Address.parse(role_address)
        Address.parse(acting)
        Address.parse(designated_by)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    if _engine is None:
        raise HTTPException(503, detail="Governance engine not initialized")

    try:
        designation = _engine.designate_acting_occupant(role_address, acting, designated_by)
    except Exception:
        logger.warning("Vacancy designation failed for role %s", role_address)
        raise HTTPException(400, detail="Vacancy designation failed")

    return {
        "status": "ok",
        "data": {
            "vacant_role_address": designation.vacant_role_address,
            "acting_role_address": designation.acting_role_address,
            "designated_by": designation.designated_by,
            "designated_at": str(designation.designated_at),
            "expires_at": str(designation.expires_at),
        },
    }


@router.get("/roles/{role_address}/vacancy")
@limiter.limit(RATE_GET)
async def get_vacancy_status(request: Request, role_address: str) -> dict:
    """Get vacancy designation status for a role.

    Returns the current acting occupant designation, or 404 if no
    designation exists.
    """
    # C2 fix: validate D/T/R grammar on path parameter
    try:
        from pact.governance import Address

        Address.parse(role_address)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid D/T/R address: {exc}")

    if _engine is None:
        raise HTTPException(503, detail="Governance engine not initialized")

    designation = _engine.get_vacancy_designation(role_address)
    if designation is None:
        raise HTTPException(404, detail="No vacancy designation found")

    return {
        "status": "ok",
        "data": {
            "vacant_role_address": designation.vacant_role_address,
            "acting_role_address": designation.acting_role_address,
            "designated_by": designation.designated_by,
            "designated_at": str(designation.designated_at),
            "expires_at": str(designation.expires_at),
        },
    }
