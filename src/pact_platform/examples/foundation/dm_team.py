# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""DM Team — Digital Media team definition for Terrene Foundation.

This is the first vertical: 5 specialist agents under a team lead,
each with EATP constraint envelopes tailored to their role.

The trust model is based on the EATP trust model research at:
workspaces/pact/01-analysis/01-research/03-eatp-trust-model-dm-team.md

Key principles:
- Monotonic constraint tightening: sub-agents never exceed lead's authority
- All agents start at SUPERVISED trust posture
- External communication always requires human approval
- Financial constraints are $0 for all DM agents (no spending authority)
- Verification gradient: read/draft auto-approved, publish/approve held, delete blocked
"""

from __future__ import annotations

from pact_platform.build.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    TeamConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)

# ---------------------------------------------------------------------------
# Agent Definitions (5 agents)
# ---------------------------------------------------------------------------

# DM Team Lead -- coordinates the team, reviews all external content
DM_TEAM_LEAD = AgentConfig(
    id="dm-team-lead",
    name="DM Team Lead",
    role="Team coordination, content review, approval routing",
    constraint_envelope="dm-lead-envelope",
    initial_posture=TrustPostureLevel.SUPERVISED,
    capabilities=[
        "review_content",
        "approve_publication",
        "coordinate_team",
        "schedule_content",
        "analyze_metrics",
        "draft_strategy",
        # RT-11: Team lead must hold capabilities it delegates to subordinates
        "draft_post",
        "edit_content",
        "research_topic",
        "suggest_hashtags",
        "read_metrics",
        "generate_report",
        "track_engagement",
        "analyze_trends",
        # Community manager capabilities
        "draft_response",
        "moderate_content",
        "track_community",
        "flag_issues",
        # SEO specialist capabilities
        "analyze_keywords",
        "suggest_structure",
        "audit_seo",
        "research_topics",
    ],
)

# Content Creator -- drafts LinkedIn, Twitter, blog posts
DM_CONTENT_CREATOR = AgentConfig(
    id="dm-content-creator",
    name="Content Creator",
    role="Draft social media posts, blog articles, and marketing copy",
    constraint_envelope="dm-content-envelope",
    initial_posture=TrustPostureLevel.SUPERVISED,
    capabilities=["draft_post", "edit_content", "research_topic", "suggest_hashtags"],
)

# Analytics Agent -- monitors engagement, tracks metrics
DM_ANALYTICS = AgentConfig(
    id="dm-analytics",
    name="Analytics Agent",
    role="Monitor engagement metrics, generate reports, track KPIs",
    constraint_envelope="dm-analytics-envelope",
    initial_posture=TrustPostureLevel.SUPERVISED,
    capabilities=["read_metrics", "generate_report", "track_engagement", "analyze_trends"],
)

# Community Manager -- handles community responses, moderation
DM_COMMUNITY_MANAGER = AgentConfig(
    id="dm-community-manager",
    name="Community Manager",
    role="Community engagement, response drafting, moderation",
    constraint_envelope="dm-community-envelope",
    initial_posture=TrustPostureLevel.SUPERVISED,
    capabilities=["draft_response", "moderate_content", "track_community", "flag_issues"],
)

# SEO Specialist -- optimizes content for search
DM_SEO_SPECIALIST = AgentConfig(
    id="dm-seo-specialist",
    name="SEO Specialist",
    role="SEO optimization, keyword research, content structure",
    constraint_envelope="dm-seo-envelope",
    initial_posture=TrustPostureLevel.SUPERVISED,
    capabilities=["analyze_keywords", "suggest_structure", "audit_seo", "research_topics"],
)

# ---------------------------------------------------------------------------
# Constraint Envelopes
# ---------------------------------------------------------------------------

# DM Team Lead envelope -- broadest authority in the DM team.
# $0 direct spending (per EATP research: "May request budget allocation but cannot approve").
# Internal-only communication (per research: "Cannot send external email, post to social").
DM_LEAD_ENVELOPE = ConstraintEnvelopeConfig(
    id="dm-lead-envelope",
    description="DM Team Lead: broadest authority within DM, still $0 spend, internal-only",
    financial=FinancialConstraintConfig(max_spend_usd=0.0),
    operational=OperationalConstraintConfig(
        allowed_actions=[
            # Lead's own actions
            "review_content",
            "approve_publication",
            "coordinate_team",
            "schedule_content",
            "analyze_metrics",
            "draft_strategy",
            # Content Creator actions (monotonic tightening: lead must encompass sub-agents)
            "draft_post",
            "edit_content",
            "research_topic",
            "suggest_hashtags",
            # Analytics actions
            "read_metrics",
            "generate_report",
            "track_engagement",
            "analyze_trends",
            # Community Manager actions
            "draft_response",
            "moderate_content",
            "track_community",
            "flag_issues",
            # SEO Specialist actions
            "analyze_keywords",
            "suggest_structure",
            "audit_seo",
            "research_topics",
        ],
        blocked_actions=["publish_externally", "modify_brand_guidelines", "engage_legal"],
        max_actions_per_day=200,
    ),
    temporal=TemporalConstraintConfig(
        active_hours_start="06:00",
        active_hours_end="22:00",
    ),
    data_access=DataAccessConstraintConfig(
        read_paths=["workspaces/dm/*", "workspaces/standards/public/*", "analytics/*"],
        write_paths=["workspaces/dm/*"],
        blocked_data_types=["pii", "financial_records", "legal_docs", "board_minutes"],
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
        allowed_channels=["slack", "internal_review"],
    ),
)

# Content Creator -- tighter than lead: fewer actions, write only to drafts.
DM_CONTENT_ENVELOPE = ConstraintEnvelopeConfig(
    id="dm-content-envelope",
    description="Content Creator: draft-only, no publishing, no external communication",
    financial=FinancialConstraintConfig(max_spend_usd=0.0),
    operational=OperationalConstraintConfig(
        allowed_actions=["draft_post", "edit_content", "research_topic", "suggest_hashtags"],
        blocked_actions=[
            "publish_externally",
            "modify_brand_guidelines",
            "engage_legal",
            "schedule_content",
            "approve_publication",
        ],
        max_actions_per_day=20,
    ),
    temporal=TemporalConstraintConfig(
        active_hours_start="08:00",
        active_hours_end="20:00",
    ),
    data_access=DataAccessConstraintConfig(
        read_paths=["workspaces/dm/content/*", "workspaces/standards/public/*"],
        write_paths=["workspaces/dm/content/drafts/*"],
        blocked_data_types=["pii", "financial_records", "legal_docs", "board_minutes", "strategy"],
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
    ),
)

# Analytics -- read-heavy, 24/7 monitoring, no external communication.
DM_ANALYTICS_ENVELOPE = ConstraintEnvelopeConfig(
    id="dm-analytics-envelope",
    description="Analytics: read-heavy, 24/7 monitoring, no external communication",
    financial=FinancialConstraintConfig(max_spend_usd=0.0),
    operational=OperationalConstraintConfig(
        allowed_actions=["read_metrics", "generate_report", "track_engagement", "analyze_trends"],
        blocked_actions=[
            "publish_externally",
            "modify_brand_guidelines",
            "engage_legal",
            "modify_content",
            "access_pii",
        ],
        max_actions_per_day=120,
    ),
    temporal=TemporalConstraintConfig(
        # Inherits lead's temporal window — monotonic tightening requires it.
        # If 24/7 monitoring is needed, the lead envelope must also be 24/7.
        active_hours_start="06:00",
        active_hours_end="22:00",
    ),
    data_access=DataAccessConstraintConfig(
        read_paths=["workspaces/dm/*", "analytics/*"],
        write_paths=["workspaces/dm/reports/*"],
        blocked_data_types=["pii", "financial_records", "legal_docs", "board_minutes"],
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
    ),
)

# Community Manager -- can draft responses, cannot send externally, moderate content.
DM_COMMUNITY_ENVELOPE = ConstraintEnvelopeConfig(
    id="dm-community-envelope",
    description="Community Manager: draft responses, moderate, no external sending",
    financial=FinancialConstraintConfig(max_spend_usd=0.0),
    operational=OperationalConstraintConfig(
        allowed_actions=["draft_response", "moderate_content", "track_community", "flag_issues"],
        blocked_actions=[
            "publish_externally",
            "modify_brand_guidelines",
            "engage_legal",
            "approve_publication",
        ],
        max_actions_per_day=40,
    ),
    temporal=TemporalConstraintConfig(
        active_hours_start="08:00",
        active_hours_end="20:00",
    ),
    data_access=DataAccessConstraintConfig(
        read_paths=["workspaces/dm/community/*", "workspaces/standards/public/*"],
        write_paths=["workspaces/dm/community/drafts/*"],
        blocked_data_types=["pii", "financial_records", "legal_docs", "board_minutes"],
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
    ),
)

# SEO Specialist -- analyze and suggest, no publishing, no external communication.
DM_SEO_ENVELOPE = ConstraintEnvelopeConfig(
    id="dm-seo-envelope",
    description="SEO Specialist: analysis and suggestions, no publishing",
    financial=FinancialConstraintConfig(max_spend_usd=0.0),
    operational=OperationalConstraintConfig(
        allowed_actions=["analyze_keywords", "suggest_structure", "audit_seo", "research_topics"],
        blocked_actions=[
            "publish_externally",
            "modify_brand_guidelines",
            "engage_legal",
            "approve_publication",
        ],
        max_actions_per_day=30,
    ),
    temporal=TemporalConstraintConfig(
        active_hours_start="08:00",
        active_hours_end="20:00",
    ),
    data_access=DataAccessConstraintConfig(
        read_paths=["workspaces/dm/content/*", "workspaces/standards/public/*", "analytics/seo/*"],
        write_paths=["workspaces/dm/seo/reports/*"],
        blocked_data_types=["pii", "financial_records", "legal_docs", "board_minutes"],
    ),
    communication=CommunicationConstraintConfig(
        internal_only=True,
        external_requires_approval=True,
    ),
)

# ---------------------------------------------------------------------------
# Verification Gradient
# ---------------------------------------------------------------------------

DM_VERIFICATION_GRADIENT = VerificationGradientConfig(
    default_level=VerificationLevel.FLAGGED,
    rules=[
        # Auto-approved: read-only, draft, analysis -- low risk, internal operations
        GradientRuleConfig(
            pattern="read_*",
            level=VerificationLevel.AUTO_APPROVED,
            reason="Read operations are safe and internal",
        ),
        GradientRuleConfig(
            pattern="draft_*",
            level=VerificationLevel.AUTO_APPROVED,
            reason="Drafts are internal, cannot be published without approval",
        ),
        GradientRuleConfig(
            pattern="analyze_*",
            level=VerificationLevel.AUTO_APPROVED,
            reason="Analysis operations are internal and non-destructive",
        ),
        # Held: approve, publish, external -- require human review
        GradientRuleConfig(
            pattern="approve_*",
            level=VerificationLevel.HELD,
            reason="Approval actions have governance implications",
        ),
        GradientRuleConfig(
            pattern="publish_*",
            level=VerificationLevel.HELD,
            reason="External publication always requires human approval",
        ),
        GradientRuleConfig(
            pattern="external_*",
            level=VerificationLevel.HELD,
            reason="External communication carries reputational risk",
        ),
        # Blocked: delete, modify constraints -- rejected outright
        GradientRuleConfig(
            pattern="delete_*",
            level=VerificationLevel.BLOCKED,
            reason="Destructive operations are blocked for all DM agents",
        ),
        GradientRuleConfig(
            pattern="modify_constraints",
            level=VerificationLevel.BLOCKED,
            reason="Agents cannot modify their own constraint envelopes",
        ),
    ],
)

# ---------------------------------------------------------------------------
# Team Definition
# ---------------------------------------------------------------------------

DM_TEAM = TeamConfig(
    id="dm-team",
    name="Digital Media Team",
    workspace="ws-dm",
    team_lead="dm-team-lead",
    agents=[
        "dm-team-lead",
        "dm-content-creator",
        "dm-analytics",
        "dm-community-manager",
        "dm-seo-specialist",
    ],
    verification_gradient=DM_VERIFICATION_GRADIENT,
)

# ---------------------------------------------------------------------------
# All agents and envelopes in canonical order
# ---------------------------------------------------------------------------

_ALL_AGENTS = [
    DM_TEAM_LEAD,
    DM_CONTENT_CREATOR,
    DM_ANALYTICS,
    DM_COMMUNITY_MANAGER,
    DM_SEO_SPECIALIST,
]

_ALL_ENVELOPES = [
    DM_LEAD_ENVELOPE,
    DM_CONTENT_ENVELOPE,
    DM_ANALYTICS_ENVELOPE,
    DM_COMMUNITY_ENVELOPE,
    DM_SEO_ENVELOPE,
]


def get_dm_team_config() -> dict:
    """Get the complete DM team configuration as a dict suitable for PactConfig.

    Returns a dict with keys: agents, envelopes, teams, gradient.
    """
    return {
        "agents": list(_ALL_AGENTS),
        "envelopes": list(_ALL_ENVELOPES),
        "teams": [DM_TEAM],
        "gradient": DM_VERIFICATION_GRADIENT,
    }


def validate_dm_team() -> tuple[bool, list[str]]:
    """Validate that the DM team config is internally consistent.

    Checks:
    - All agents reference valid envelopes (envelope IDs match)
    - All agents are listed in the team
    - Envelopes demonstrate monotonic tightening from lead
    - All roles have appropriate constraints (internal-only, $0 spend)
    - Verification gradient covers critical patterns

    Returns:
        (True, []) if valid, (False, [list of error messages]) otherwise.
    """
    errors: list[str] = []
    envelope_ids = {e.id for e in _ALL_ENVELOPES}

    # Check all agents reference valid envelopes
    for agent in _ALL_AGENTS:
        if agent.constraint_envelope not in envelope_ids:
            errors.append(
                f"Agent '{agent.id}' references envelope '{agent.constraint_envelope}' "
                f"which does not exist. Available envelopes: {envelope_ids}"
            )

    # Check all agents are listed in the team
    team_agent_ids = set(DM_TEAM.agents)
    for agent in _ALL_AGENTS:
        if agent.id not in team_agent_ids:
            errors.append(f"Agent '{agent.id}' is defined but not listed in team '{DM_TEAM.id}'")

    # Check monotonic tightening: each sub-agent must have tighter constraints than lead
    lead_envelope = DM_LEAD_ENVELOPE
    sub_envelopes = [
        DM_CONTENT_ENVELOPE,
        DM_ANALYTICS_ENVELOPE,
        DM_COMMUNITY_ENVELOPE,
        DM_SEO_ENVELOPE,
    ]
    for env in sub_envelopes:
        # Financial: sub must be <= lead
        if env.financial.max_spend_usd > lead_envelope.financial.max_spend_usd:
            errors.append(
                f"Envelope '{env.id}' has higher max_spend_usd "
                f"({env.financial.max_spend_usd}) than lead ({lead_envelope.financial.max_spend_usd})"
            )
        # Communication: sub must not be less restrictive than lead
        if lead_envelope.communication.internal_only and not env.communication.internal_only:
            errors.append(
                f"Envelope '{env.id}' allows external communication but lead is internal-only"
            )

    # Check all envelopes enforce $0 spending (per EATP research)
    for env in _ALL_ENVELOPES:
        if env.financial.max_spend_usd > 0:
            errors.append(
                f"Envelope '{env.id}' allows spending (${env.financial.max_spend_usd}), "
                f"but DM team is $0 spend per EATP trust model"
            )

    # Check all envelopes are internal-only
    for env in _ALL_ENVELOPES:
        if not env.communication.internal_only:
            errors.append(
                f"Envelope '{env.id}' allows external communication, "
                f"but DM team must be internal-only"
            )

    # Check verification gradient has essential blocked patterns
    blocked_patterns = {
        r.pattern for r in DM_VERIFICATION_GRADIENT.rules if r.level == VerificationLevel.BLOCKED
    }
    for required_blocked in ["delete_*", "modify_constraints"]:
        if required_blocked not in blocked_patterns:
            errors.append(
                f"Verification gradient missing required BLOCKED pattern: '{required_blocked}'"
            )

    return (len(errors) == 0, errors)
