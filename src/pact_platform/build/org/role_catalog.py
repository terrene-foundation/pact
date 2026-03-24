# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Role Catalog — predefined and custom role definitions for org generation.

Provides RoleDefinition (the data model for a role) and RoleCatalog (the
registry of built-in and custom roles). The catalog is used by OrgGenerator
to resolve role IDs to agent definitions with appropriate capabilities,
postures, and constraint limits.

Built-in roles are aligned with CARE constraint dimensions:
- Financial: max cost per day
- Operational: capabilities (allowed actions), max actions per day
- Temporal: inherited from team/department
- Data Access: inherited from team/department
- Communication: inherited from team/department
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from pact_platform.build.config.schema import TrustPostureLevel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RoleDefinition model
# ---------------------------------------------------------------------------


class RoleDefinition(BaseModel):
    """Definition of an agent role with default capabilities and constraints.

    Each role provides sensible defaults for the auto-generation engine.
    When an OrgGenerator resolves a role_id from the catalog, it uses
    these defaults to create AgentConfig and ConstraintEnvelopeConfig
    instances.

    Attributes:
        role_id: Unique identifier for this role.
        name: Human-readable role name.
        description: What this role does.
        default_capabilities: Actions this role can perform.
        default_posture: Starting trust posture level.
        default_max_actions_per_day: Daily action rate limit.
        default_max_cost_per_day: Maximum USD spend per day.
    """

    role_id: str = Field(description="Unique identifier for this role")
    name: str = Field(description="Human-readable role name")
    description: str = Field(description="What this role does")
    default_capabilities: list[str] = Field(description="Actions this role can perform")
    default_posture: TrustPostureLevel = Field(description="Starting trust posture level")
    default_max_actions_per_day: int = Field(
        gt=0,
        description="Daily action rate limit",
    )
    default_max_cost_per_day: float = Field(
        ge=0.0,
        description="Maximum USD spend per day",
    )


# ---------------------------------------------------------------------------
# Built-in role definitions
# ---------------------------------------------------------------------------


def _builtin_roles() -> list[RoleDefinition]:
    """Create all 14 built-in role definitions.

    These roles are aligned with CARE constraint dimensions and cover
    common organizational functions.
    """
    return [
        RoleDefinition(
            role_id="content_creator",
            name="Content Creator",
            description="Creates and manages content across channels",
            default_capabilities=[
                "content_creation",
                "content_editing",
                "content_scheduling",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=50,
            default_max_cost_per_day=10.0,
        ),
        RoleDefinition(
            role_id="analyst",
            name="Analyst",
            description="Analyzes data and produces reports",
            default_capabilities=[
                "data_analysis",
                "report_generation",
                "data_visualization",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=40,
            default_max_cost_per_day=15.0,
        ),
        RoleDefinition(
            role_id="coordinator",
            name="Coordinator",
            description="Coordinates activities across teams and functions",
            default_capabilities=[
                "task_routing",
                "schedule_management",
                "status_reporting",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=80,
            default_max_cost_per_day=5.0,
        ),
        RoleDefinition(
            role_id="reviewer",
            name="Reviewer",
            description="Reviews work products for quality and compliance",
            default_capabilities=[
                "code_review",
                "content_review",
                "compliance_check",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=30,
            default_max_cost_per_day=8.0,
        ),
        RoleDefinition(
            role_id="executive",
            name="Executive",
            description="Makes strategic decisions and approves high-impact actions",
            default_capabilities=[
                "strategic_planning",
                "budget_approval",
                "policy_review",
            ],
            default_posture=TrustPostureLevel.PSEUDO_AGENT,
            default_max_actions_per_day=20,
            default_max_cost_per_day=100.0,
        ),
        RoleDefinition(
            role_id="developer",
            name="Developer",
            description="Develops software and technical systems",
            default_capabilities=[
                "code_development",
                "code_review",
                "testing",
                "debugging",
                "documentation",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=60,
            default_max_cost_per_day=20.0,
        ),
        RoleDefinition(
            role_id="community_manager",
            name="Community Manager",
            description="Manages community engagement and communications",
            default_capabilities=[
                "community_engagement",
                "content_moderation",
                "event_coordination",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=70,
            default_max_cost_per_day=8.0,
        ),
        RoleDefinition(
            role_id="legal_advisor",
            name="Legal Advisor",
            description="Provides legal guidance and compliance review",
            default_capabilities=[
                "legal_review",
                "compliance_assessment",
                "contract_analysis",
            ],
            default_posture=TrustPostureLevel.PSEUDO_AGENT,
            default_max_actions_per_day=15,
            default_max_cost_per_day=50.0,
        ),
        RoleDefinition(
            role_id="finance_manager",
            name="Finance Manager",
            description="Manages financial operations and reporting",
            default_capabilities=[
                "financial_reporting",
                "budget_tracking",
                "expense_review",
            ],
            default_posture=TrustPostureLevel.PSEUDO_AGENT,
            default_max_actions_per_day=25,
            default_max_cost_per_day=30.0,
        ),
        RoleDefinition(
            role_id="trainer",
            name="Trainer",
            description="Develops and delivers training programs",
            default_capabilities=[
                "training_development",
                "knowledge_transfer",
                "assessment_creation",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=35,
            default_max_cost_per_day=12.0,
        ),
        RoleDefinition(
            role_id="standards_author",
            name="Standards Author",
            description="Authors and maintains organizational standards",
            default_capabilities=[
                "standards_drafting",
                "specification_review",
                "documentation",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=25,
            default_max_cost_per_day=15.0,
        ),
        RoleDefinition(
            role_id="governance_officer",
            name="Governance Officer",
            description="Enforces governance policies and compliance",
            default_capabilities=[
                "governance_enforcement",
                "policy_review",
                "audit_coordination",
            ],
            default_posture=TrustPostureLevel.PSEUDO_AGENT,
            default_max_actions_per_day=20,
            default_max_cost_per_day=25.0,
        ),
        RoleDefinition(
            role_id="partnership_manager",
            name="Partnership Manager",
            description="Manages external partnerships and relationships",
            default_capabilities=[
                "partnership_development",
                "relationship_management",
                "proposal_review",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=30,
            default_max_cost_per_day=20.0,
        ),
        RoleDefinition(
            role_id="website_manager",
            name="Website Manager",
            description="Manages web presence and digital content",
            default_capabilities=[
                "web_content_management",
                "site_maintenance",
                "analytics_review",
            ],
            default_posture=TrustPostureLevel.SUPERVISED,
            default_max_actions_per_day=45,
            default_max_cost_per_day=10.0,
        ),
    ]


# ---------------------------------------------------------------------------
# RoleCatalog
# ---------------------------------------------------------------------------


class RoleCatalog:
    """Registry of role definitions for the auto-generation engine.

    Provides built-in roles and allows registration of custom roles.
    Used by OrgGenerator to resolve role_id strings into full
    RoleDefinition instances.

    Usage:
        catalog = RoleCatalog()
        role = catalog.get("developer")
        all_roles = catalog.list()
        catalog.register(custom_role)
    """

    def __init__(self) -> None:
        self._roles: dict[str, RoleDefinition] = {}
        for role in _builtin_roles():
            self._roles[role.role_id] = role
        logger.debug("RoleCatalog initialized with %d built-in roles", len(self._roles))

    def get(self, role_id: str) -> RoleDefinition:
        """Look up a role by ID.

        Args:
            role_id: The role identifier to look up.

        Returns:
            The RoleDefinition for the given role_id.

        Raises:
            ValueError: If the role_id is not found in the catalog.
        """
        role = self._roles.get(role_id)
        if role is None:
            available = sorted(self._roles.keys())
            raise ValueError(f"Role '{role_id}' not found in catalog. Available roles: {available}")
        return role

    def list(self) -> list[RoleDefinition]:
        """Return all registered RoleDefinitions.

        Returns:
            List of all RoleDefinition instances in the catalog.
        """
        return list(self._roles.values())

    def register(self, role: RoleDefinition) -> None:
        """Register a custom role in the catalog.

        Args:
            role: The RoleDefinition to register.

        Raises:
            ValueError: If a role with the same role_id is already registered.
        """
        if role.role_id in self._roles:
            raise ValueError(
                f"Role '{role.role_id}' is already registered in the catalog. "
                f"Use a different role_id for custom roles."
            )
        self._roles[role.role_id] = role
        logger.info("Registered custom role '%s' in catalog", role.role_id)
