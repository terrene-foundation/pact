# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Foundation Full Org — complete Terrene Foundation organization (M41: Tasks 6040-6046).

Defines the full 11-team, 3-department Terrene Foundation organization using
OrgGenerator. This is the dog-food test: the PACT's own organizational
structure run through the same machinery it provides to external users.

Organization structure:
    Tier 1 (Core Operations):
        1. Media/DM — Digital marketing team
        2. Standards — CARE, EATP, CO specifications
        3. Governance — Constitutional governance, compliance
        4. Partnerships — External relationships, contributor framework
        5. Website — terrene.dev and terrene.foundation sites

    Tier 2 (Growth):
        6. Community — Open-source community, GitHub, forums
        7. Developer Relations — SDK documentation, tutorials
        8. Finance — Budget tracking, grant management, treasury

    Tier 3 (Future):
        9. Certification — Agent certification program
       10. Training — Educational content, workshops
       11. Legal — Legal affairs, IP protection

Department groupings:
    Operations: Media/DM, Website, Community
    Standards & Governance: Standards, Governance, Legal, Certification
    Growth: Partnerships, Developer Relations, Finance, Training

Cross-Functional Bridges:
    Standing bridges for commonly collaborating teams.
"""

from __future__ import annotations

from pact_platform.build.org.generator import (
    DepartmentSpec,
    OrgGeneratorConfig,
    TeamSpec,
)

# ---------------------------------------------------------------------------
# Team Specifications
# ---------------------------------------------------------------------------

# --- Tier 1: Core Operations ---

MEDIA_DM_TEAM = TeamSpec(
    name="Media/DM",
    roles=["content_creator", "analyst"],
)

STANDARDS_TEAM = TeamSpec(
    name="Standards",
    roles=["standards_author", "reviewer"],
)

GOVERNANCE_TEAM = TeamSpec(
    name="Governance",
    roles=["governance_officer", "legal_advisor"],
)

PARTNERSHIPS_TEAM = TeamSpec(
    name="Partnerships",
    roles=["partnership_manager", "analyst"],
)

WEBSITE_TEAM = TeamSpec(
    name="Website",
    roles=["website_manager", "content_creator", "developer"],
)

# --- Tier 2: Growth ---

COMMUNITY_TEAM = TeamSpec(
    name="Community",
    roles=["community_manager", "content_creator"],
)

DEVREL_TEAM = TeamSpec(
    name="Developer Relations",
    roles=["developer", "content_creator"],
)

FINANCE_TEAM = TeamSpec(
    name="Finance",
    roles=["finance_manager", "analyst"],
)

# --- Tier 3: Future ---

CERTIFICATION_TEAM = TeamSpec(
    name="Certification",
    roles=["reviewer", "standards_author"],
)

TRAINING_TEAM = TeamSpec(
    name="Training",
    roles=["trainer", "content_creator"],
)

LEGAL_TEAM = TeamSpec(
    name="Legal",
    roles=["legal_advisor", "reviewer"],
)


# ---------------------------------------------------------------------------
# Department Specifications
# ---------------------------------------------------------------------------

OPERATIONS_DEPARTMENT = DepartmentSpec(
    name="Operations",
    teams=[MEDIA_DM_TEAM, WEBSITE_TEAM, COMMUNITY_TEAM],
)

STANDARDS_GOVERNANCE_DEPARTMENT = DepartmentSpec(
    name="Standards & Governance",
    teams=[STANDARDS_TEAM, GOVERNANCE_TEAM, LEGAL_TEAM, CERTIFICATION_TEAM],
)

GROWTH_DEPARTMENT = DepartmentSpec(
    name="Growth",
    teams=[PARTNERSHIPS_TEAM, DEVREL_TEAM, FINANCE_TEAM, TRAINING_TEAM],
)


# ---------------------------------------------------------------------------
# OrgGeneratorConfig — YAML-serializable
# ---------------------------------------------------------------------------

FOUNDATION_ORG_CONFIG = OrgGeneratorConfig(
    org_id="terrene-foundation",
    org_name="Terrene Foundation",
    authority_id="terrene.foundation",
    org_budget=10000.0,
    org_max_actions_per_day=5000,
    departments=[
        OPERATIONS_DEPARTMENT,
        STANDARDS_GOVERNANCE_DEPARTMENT,
        GROWTH_DEPARTMENT,
    ],
)


# ---------------------------------------------------------------------------
# Cross-Functional Bridge Definitions (Task 6044)
# ---------------------------------------------------------------------------

FOUNDATION_BRIDGES: list[dict] = [
    {
        "source": "Standards",
        "target": "Governance",
        "type": "Standing",
        "purpose": "Standards review process — governance reviews all new and amended standards",
    },
    {
        "source": "Media/DM",
        "target": "Community",
        "type": "Standing",
        "purpose": "Content distribution — media content shared with community channels",
    },
    {
        "source": "Developer Relations",
        "target": "Standards",
        "type": "Standing",
        "purpose": "SDK documentation from specs — devrel documents standards for developers",
    },
    {
        "source": "Partnerships",
        "target": "Governance",
        "type": "Standing",
        "purpose": "Contributor compliance — partnerships route contributors through governance review",
    },
    {
        "source": "Finance",
        "target": "Operations",
        "type": "Standing",
        "purpose": "Budget oversight — finance reviews operations department spend",
    },
    {
        "source": "Finance",
        "target": "Standards & Governance",
        "type": "Standing",
        "purpose": "Budget oversight — finance reviews standards & governance department spend",
    },
    {
        "source": "Finance",
        "target": "Growth",
        "type": "Standing",
        "purpose": "Budget oversight — finance reviews growth department spend",
    },
]


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def generate_foundation_org():
    """Generate the complete Terrene Foundation organization.

    Returns:
        A fully validated OrgDefinition for the Terrene Foundation.

    Raises:
        ValueError: If generation or validation fails (should never happen
                    since FOUNDATION_ORG_CONFIG uses only built-in roles).
    """
    from pact_platform.build.org.generator import OrgGenerator

    generator = OrgGenerator()
    return generator.generate(FOUNDATION_ORG_CONFIG)
