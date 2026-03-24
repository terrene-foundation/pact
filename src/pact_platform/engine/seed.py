# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Auto-seeding module — populates demo data on first boot."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def seed_demo_data(db: Any) -> dict[str, Any]:
    """Seed demo data if none exists.

    Creates:
    - 2 objectives (admissions review, course catalog update)
    - 5 requests decomposed from objectives
    - 1 HELD decision for the evaluator
    - 3 run records with sample costs
    - 1 agent pool with researcher as member

    Returns:
        dict with seeded=True/False and counts of seeded items.
    """
    # Check if data already exists
    wf = db.create_workflow()
    wf.add_node("AgenticObjectiveListNode", "list", {"filter": {}, "limit": 1})
    results, _ = db.execute_workflow(wf)
    existing = results["list"].get("records", [])
    if existing:
        logger.info("Data already exists (%d objectives), skipping seed", len(existing))
        return {"seeded": False}

    logger.info("Seeding demo data...")

    # --- Objectives ---
    _create(
        db,
        "AgenticObjectiveCreateNode",
        {
            "id": "obj-admissions",
            "org_address": "university/research-dept",
            "title": "Review Graduate Admissions",
            "description": "Screen and evaluate graduate school applications for Fall 2027.",
            "submitted_by": "department-head",
            "status": "active",
            "priority": "high",
            "budget_usd": 50.0,
        },
    )
    _create(
        db,
        "AgenticObjectiveCreateNode",
        {
            "id": "obj-catalog",
            "org_address": "university/admin-dept",
            "title": "Update Course Catalog",
            "description": "Audit current course listings and publish updated catalog.",
            "submitted_by": "registrar",
            "status": "active",
            "priority": "normal",
            "budget_usd": 25.0,
        },
    )

    # --- Requests ---
    for rid, oid, title, assigned, seq in [
        (
            "req-transcripts",
            "obj-admissions",
            "Screen applicant transcripts",
            "research-dept/research-team/senior-researcher",
            1,
        ),
        (
            "req-eligibility",
            "obj-admissions",
            "Verify enrollment eligibility",
            "admin-dept/admin-team/registrar",
            2,
        ),
        (
            "req-resources",
            "obj-admissions",
            "Cross-reference library resources",
            "library-dept/collections-team/head-librarian",
            3,
        ),
        (
            "req-audit",
            "obj-catalog",
            "Audit current course listings",
            "research-dept/research-team/senior-researcher",
            1,
        ),
        (
            "req-publish",
            "obj-catalog",
            "Publish updated catalog",
            "admin-dept/admin-team/registrar",
            2,
        ),
    ]:
        _create(
            db,
            "AgenticRequestCreateNode",
            {
                "id": rid,
                "objective_id": oid,
                "title": title,
                "assigned_to": assigned,
                "assigned_type": "agent",
                "status": "pending",
                "sequence_order": seq,
            },
        )

    # --- HELD decision ---
    _create(
        db,
        "AgenticDecisionCreateNode",
        {
            "id": "dec-restricted",
            "request_id": "req-transcripts",
            "agent_address": "research-dept/research-team/senior-researcher",
            "action": "access_restricted_records",
            "decision_type": "governance_hold",
            "status": "pending",
            "reason_held": "Agent requires CONFIDENTIAL clearance to access restricted student records",
            "constraint_dimension": "data_access",
            "urgency": "high",
            "envelope_version": 1,
        },
    )

    # --- Sample runs ---
    for run_id, req_id, agent, cost, inp, out in [
        (
            "run-researcher",
            "req-transcripts",
            "research-dept/research-team/senior-researcher",
            0.05,
            1200,
            800,
        ),
        ("run-admin", "req-eligibility", "admin-dept/admin-team/registrar", 0.03, 800, 400),
        (
            "run-librarian",
            "req-resources",
            "library-dept/collections-team/head-librarian",
            0.02,
            600,
            300,
        ),
    ]:
        _create(
            db,
            "RunCreateNode",
            {
                "id": run_id,
                "request_id": req_id,
                "agent_address": agent,
                "run_type": "llm",
                "status": "completed",
                "cost_usd": cost,
                "input_tokens": inp,
                "output_tokens": out,
                "verification_level": "auto_approved",
            },
        )

    # --- Pool ---
    _create(
        db,
        "AgenticPoolCreateNode",
        {
            "id": "pool-research",
            "org_id": "university",
            "name": "University Research Pool",
            "pool_type": "agent",
            "routing_strategy": "capability_match",
            "max_concurrent": 3,
        },
    )
    _create(
        db,
        "AgenticPoolMembershipCreateNode",
        {
            "id": "mem-researcher",
            "pool_id": "pool-research",
            "member_address": "research-dept/research-team/senior-researcher",
            "member_type": "agent",
            "capabilities": {"skills": ["transcript_review", "data_analysis", "research"]},
            "max_concurrent": 2,
        },
    )

    summary = {
        "seeded": True,
        "objectives": 2,
        "requests": 5,
        "decisions": 1,
        "runs": 3,
        "pools": 1,
        "pool_members": 1,
    }
    logger.info("Demo data seeded: %s", summary)
    return summary


def seed_if_empty(db: Any) -> None:
    """Seed demo data if the database is empty. Called during server startup."""
    try:
        result = seed_demo_data(db)
        if result["seeded"]:
            logger.info("Auto-seeded demo data on first boot")
    except Exception:
        logger.exception("Failed to seed demo data — continuing without seed")


def _create(db: Any, node_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Helper to create a single record via DataFlow."""
    wf = db.create_workflow()
    wf.add_node(node_type, "create", data)
    results, _ = db.execute_workflow(wf)
    return results["create"]
