# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Foundation example vertical — Terrene Foundation organization.

This package contains the domain-specific Terrene Foundation organization
definition including the DM (Digital Media) team, agent prompts, runner,
and organization configuration. It demonstrates how the PACT framework
is used to structure a real organization with governed AI agents.

Modules:
    dm_team     — DM team agent and envelope definitions
    dm_prompts  — Agent-specific system prompts for the DM team
    dm_runner   — DMTeamRunner orchestrator
    org         — Full Foundation organization (11 teams, 3 departments)
"""

from pact_platform.examples.foundation.dm_prompts import DM_AGENT_PROMPTS, get_system_prompt
from pact_platform.examples.foundation.dm_runner import DMTeamRunner
from pact_platform.examples.foundation.dm_team import (
    DM_ANALYTICS,
    DM_ANALYTICS_ENVELOPE,
    DM_COMMUNITY_ENVELOPE,
    DM_COMMUNITY_MANAGER,
    DM_CONTENT_CREATOR,
    DM_CONTENT_ENVELOPE,
    DM_LEAD_ENVELOPE,
    DM_SEO_ENVELOPE,
    DM_SEO_SPECIALIST,
    DM_TEAM,
    DM_TEAM_LEAD,
    DM_VERIFICATION_GRADIENT,
    get_dm_team_config,
    validate_dm_team,
)
from pact_platform.examples.foundation.org import (
    FOUNDATION_BRIDGES,
    FOUNDATION_ORG_CONFIG,
    generate_foundation_org,
)

__all__ = [
    # DM Team
    "DM_TEAM_LEAD",
    "DM_CONTENT_CREATOR",
    "DM_ANALYTICS",
    "DM_COMMUNITY_MANAGER",
    "DM_SEO_SPECIALIST",
    "DM_LEAD_ENVELOPE",
    "DM_CONTENT_ENVELOPE",
    "DM_ANALYTICS_ENVELOPE",
    "DM_COMMUNITY_ENVELOPE",
    "DM_SEO_ENVELOPE",
    "DM_TEAM",
    "DM_VERIFICATION_GRADIENT",
    "get_dm_team_config",
    "validate_dm_team",
    # DM Prompts
    "DM_AGENT_PROMPTS",
    "get_system_prompt",
    # DM Runner
    "DMTeamRunner",
    # Foundation Org
    "FOUNDATION_ORG_CONFIG",
    "FOUNDATION_BRIDGES",
    "generate_foundation_org",
]
