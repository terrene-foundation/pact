# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Constraint Envelope Template Library — predefined team templates.

Provides TeamTemplate and TemplateRegistry for creating teams from
pre-configured templates. Templates cover common organizational team types:
media, governance, standards, partnerships, engineering, and executive.

Each template includes:
- AgentConfig definitions for all team members
- ConstraintEnvelopeConfig for each agent
- TeamConfig wiring agents to a workspace

Override support: apply(template, overrides) returns a copy with
org-specific customizations (team name, ID, workspace).

YAML loading: TemplateRegistry.load_from_yaml(path) loads a TeamTemplate
from a YAML file for custom team definitions.

Registration validation (M20/5040): register() validates the template via
OrgDefinition.validate_org_detailed() — invalid templates are rejected with
clear error details.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from pact_platform.build.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TeamConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    WorkspaceConfig,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TeamTemplate model
# ---------------------------------------------------------------------------


class TeamTemplate(BaseModel):
    """A complete team template with agents, envelopes, and team config."""

    name: str = Field(description="Template name (e.g., 'media', 'governance')")
    description: str = Field(default="", description="Template description")
    agents: list[AgentConfig] = Field(default_factory=list)
    envelopes: list[ConstraintEnvelopeConfig] = Field(default_factory=list)
    team: TeamConfig = Field(description="Team configuration")
    department: str | None = Field(
        default=None,
        description=(
            "Optional department name this template's team belongs to. "
            "Used when composing multiple templates to group teams by department."
        ),
    )


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------


def _media_template() -> TeamTemplate:
    """Media/Marketing team template.

    Derived from the DM team specification (tasks 601-605).
    5 agents: team lead, content creator, analytics, community manager, SEO specialist.
    All envelopes: $0 spend, internal-only communication.
    """
    # Lead must be a superset of all subordinate capabilities and allowed_actions
    # (monotonic constraint tightening). Rate limit must be >= all subordinates.
    lead_env = ConstraintEnvelopeConfig(
        id="media-lead-envelope",
        description="Media Team Lead: broadest authority within media, $0 spend, internal-only",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                # Lead-specific
                "review_content",
                "approve_publication",
                "coordinate_team",
                "schedule_content",
                "analyze_metrics",
                "draft_strategy",
                # From content creator
                "draft_post",
                "edit_content",
                "research_topic",
                "suggest_hashtags",
                # From analytics
                "read_metrics",
                "generate_report",
                "track_engagement",
                "analyze_trends",
                # From community manager
                "draft_response",
                "moderate_content",
                "track_community",
                "flag_issues",
                # From SEO specialist
                "analyze_keywords",
                "suggest_structure",
                "audit_seo",
                "research_topics",
            ],
            blocked_actions=["publish_externally", "modify_brand_guidelines", "engage_legal"],
            max_actions_per_day=120,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="06:00", active_hours_end="22:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/media/*", "workspaces/standards/public/*", "analytics/*"],
            write_paths=["workspaces/media/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs", "board_minutes"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
            allowed_channels=["slack", "internal_review"],
        ),
    )

    content_env = ConstraintEnvelopeConfig(
        id="media-content-envelope",
        description="Content Creator: draft-only, no publishing",
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
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/media/content/*", "workspaces/standards/public/*"],
            write_paths=["workspaces/media/content/drafts/*"],
            blocked_data_types=[
                "pii",
                "financial_records",
                "legal_docs",
                "board_minutes",
                "strategy",
            ],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    analytics_env = ConstraintEnvelopeConfig(
        id="media-analytics-envelope",
        description="Analytics: read-heavy, 24/7 monitoring",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "read_metrics",
                "generate_report",
                "track_engagement",
                "analyze_trends",
            ],
            blocked_actions=[
                "publish_externally",
                "modify_brand_guidelines",
                "engage_legal",
                "modify_content",
                "access_pii",
            ],
            max_actions_per_day=120,
        ),
        temporal=TemporalConstraintConfig(),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/media/*", "analytics/*"],
            write_paths=["workspaces/media/reports/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    community_env = ConstraintEnvelopeConfig(
        id="media-community-envelope",
        description="Community Manager: draft responses, moderate",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "draft_response",
                "moderate_content",
                "track_community",
                "flag_issues",
            ],
            blocked_actions=[
                "publish_externally",
                "modify_brand_guidelines",
                "engage_legal",
                "approve_publication",
            ],
            max_actions_per_day=40,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/media/community/*", "workspaces/standards/public/*"],
            write_paths=["workspaces/media/community/drafts/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs", "board_minutes"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    seo_env = ConstraintEnvelopeConfig(
        id="media-seo-envelope",
        description="SEO Specialist: analysis and suggestions",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "analyze_keywords",
                "suggest_structure",
                "audit_seo",
                "research_topics",
            ],
            blocked_actions=[
                "publish_externally",
                "modify_brand_guidelines",
                "engage_legal",
                "approve_publication",
            ],
            max_actions_per_day=30,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=[
                "workspaces/media/content/*",
                "workspaces/standards/public/*",
                "analytics/seo/*",
            ],
            write_paths=["workspaces/media/seo/reports/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    envelopes = [lead_env, content_env, analytics_env, community_env, seo_env]

    agents = [
        AgentConfig(
            id="media-team-lead",
            name="Media Team Lead",
            role="Team coordination, content review, approval routing",
            constraint_envelope="media-lead-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                # Lead-specific
                "review_content",
                "approve_publication",
                "coordinate_team",
                "schedule_content",
                "analyze_metrics",
                "draft_strategy",
                # From content creator
                "draft_post",
                "edit_content",
                "research_topic",
                "suggest_hashtags",
                # From analytics
                "read_metrics",
                "generate_report",
                "track_engagement",
                "analyze_trends",
                # From community manager
                "draft_response",
                "moderate_content",
                "track_community",
                "flag_issues",
                # From SEO specialist
                "analyze_keywords",
                "suggest_structure",
                "audit_seo",
                "research_topics",
            ],
        ),
        AgentConfig(
            id="media-content-creator",
            name="Content Creator",
            role="Draft social media posts, blog articles, and marketing copy",
            constraint_envelope="media-content-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=["draft_post", "edit_content", "research_topic", "suggest_hashtags"],
        ),
        AgentConfig(
            id="media-analytics",
            name="Analytics Agent",
            role="Monitor engagement metrics, generate reports, track KPIs",
            constraint_envelope="media-analytics-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "read_metrics",
                "generate_report",
                "track_engagement",
                "analyze_trends",
            ],
        ),
        AgentConfig(
            id="media-community-manager",
            name="Community Manager",
            role="Community engagement, response drafting, moderation",
            constraint_envelope="media-community-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=["draft_response", "moderate_content", "track_community", "flag_issues"],
        ),
        AgentConfig(
            id="media-seo-specialist",
            name="SEO Specialist",
            role="SEO optimization, keyword research, content structure",
            constraint_envelope="media-seo-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "analyze_keywords",
                "suggest_structure",
                "audit_seo",
                "research_topics",
            ],
        ),
    ]

    team = TeamConfig(
        id="media-team",
        name="Media Team",
        workspace="ws-media",
        team_lead="media-team-lead",
        agents=[a.id for a in agents],
    )

    return TeamTemplate(
        name="media",
        description="Media/Marketing team with 5 specialist agents",
        agents=agents,
        envelopes=envelopes,
        team=team,
    )


def _governance_template() -> TeamTemplate:
    """Governance/Management team template.

    Agents: team lead, compliance monitor, meeting coordinator.
    All envelopes: $0 spend, internal-only.
    """
    # Lead must be a superset of all subordinate capabilities and allowed_actions
    lead_env = ConstraintEnvelopeConfig(
        id="governance-lead-envelope",
        description="Governance Team Lead: governance coordination, internal-only",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                # Lead-specific
                "review_compliance",
                "coordinate_meeting",
                "draft_policy",
                "approve_review",
                "track_governance",
                # From compliance monitor
                "audit_compliance",
                "flag_violation",
                "generate_report",
                # From meeting coordinator
                "schedule_meeting",
                "draft_minutes",
                "send_reminders",
                "track_actions",
            ],
            blocked_actions=["publish_externally", "engage_legal", "modify_constitution"],
            max_actions_per_day=50,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="06:00", active_hours_end="22:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/governance/*", "workspaces/*/public/*"],
            write_paths=["workspaces/governance/*"],
            blocked_data_types=["pii", "financial_records"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
            allowed_channels=["slack", "internal_review"],
        ),
    )

    compliance_env = ConstraintEnvelopeConfig(
        id="governance-compliance-envelope",
        description="Compliance Monitor: audit, flag, report compliance issues",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "audit_compliance",
                "flag_violation",
                "generate_report",
                "track_governance",
            ],
            blocked_actions=[
                "publish_externally",
                "engage_legal",
                "modify_constitution",
                "approve_review",
            ],
            max_actions_per_day=40,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/governance/*", "workspaces/*/public/*"],
            write_paths=["workspaces/governance/reports/*"],
            blocked_data_types=["pii", "financial_records"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    meeting_env = ConstraintEnvelopeConfig(
        id="governance-meeting-envelope",
        description="Meeting Coordinator: schedule, minutes, follow-up",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "schedule_meeting",
                "draft_minutes",
                "send_reminders",
                "track_actions",
            ],
            blocked_actions=[
                "publish_externally",
                "engage_legal",
                "modify_constitution",
                "approve_review",
            ],
            max_actions_per_day=30,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/governance/meetings/*"],
            write_paths=["workspaces/governance/meetings/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    envelopes = [lead_env, compliance_env, meeting_env]

    agents = [
        AgentConfig(
            id="governance-team-lead",
            name="Governance Team Lead",
            role="Governance coordination and policy oversight",
            constraint_envelope="governance-lead-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                # Lead-specific
                "review_compliance",
                "coordinate_meeting",
                "draft_policy",
                "approve_review",
                "track_governance",
                # From compliance monitor
                "audit_compliance",
                "flag_violation",
                "generate_report",
                # From meeting coordinator
                "schedule_meeting",
                "draft_minutes",
                "send_reminders",
                "track_actions",
            ],
        ),
        AgentConfig(
            id="governance-compliance-monitor",
            name="Compliance Monitor",
            role="Audit compliance, flag violations, generate reports",
            constraint_envelope="governance-compliance-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "audit_compliance",
                "flag_violation",
                "generate_report",
                "track_governance",
            ],
        ),
        AgentConfig(
            id="governance-meeting-coordinator",
            name="Meeting Coordinator",
            role="Schedule meetings, draft minutes, track follow-ups",
            constraint_envelope="governance-meeting-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "schedule_meeting",
                "draft_minutes",
                "send_reminders",
                "track_actions",
            ],
        ),
    ]

    team = TeamConfig(
        id="governance-team",
        name="Governance Team",
        workspace="ws-governance",
        team_lead="governance-team-lead",
        agents=[a.id for a in agents],
    )

    return TeamTemplate(
        name="governance",
        description="Governance/Management team with compliance and coordination agents",
        agents=agents,
        envelopes=envelopes,
        team=team,
    )


def _standards_template() -> TeamTemplate:
    """Standards/Research team template.

    Agents: team lead, spec drafter, cross-reference validator.
    All envelopes: $0 spend, internal-only.
    """
    # Lead must be a superset of all subordinate capabilities and allowed_actions
    lead_env = ConstraintEnvelopeConfig(
        id="standards-lead-envelope",
        description="Standards Team Lead: spec review, coordination",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                # Lead-specific
                "review_spec",
                "approve_draft",
                "coordinate_review",
                "assign_task",
                "track_standards",
                # From spec drafter
                "draft_spec",
                "edit_spec",
                "research_standard",
                "suggest_structure",
                # From cross-reference validator
                "validate_references",
                "check_consistency",
                "generate_report",
                "flag_issues",
            ],
            blocked_actions=["publish_externally", "engage_legal"],
            max_actions_per_day=50,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="06:00", active_hours_end="22:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/standards/*", "workspaces/*/public/*"],
            write_paths=["workspaces/standards/*"],
            blocked_data_types=["pii", "financial_records"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
            allowed_channels=["slack", "internal_review"],
        ),
    )

    drafter_env = ConstraintEnvelopeConfig(
        id="standards-drafter-envelope",
        description="Spec Drafter: draft and edit specifications",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "draft_spec",
                "edit_spec",
                "research_standard",
                "suggest_structure",
            ],
            blocked_actions=[
                "publish_externally",
                "engage_legal",
                "approve_draft",
            ],
            max_actions_per_day=30,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/standards/*"],
            write_paths=["workspaces/standards/drafts/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    validator_env = ConstraintEnvelopeConfig(
        id="standards-validator-envelope",
        description="Cross-Reference Validator: validate cross-references in specs",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "validate_references",
                "check_consistency",
                "generate_report",
                "flag_issues",
            ],
            blocked_actions=[
                "publish_externally",
                "engage_legal",
                "approve_draft",
                "edit_spec",
            ],
            max_actions_per_day=40,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/standards/*", "workspaces/*/public/*"],
            write_paths=["workspaces/standards/validation/*"],
            blocked_data_types=["pii", "financial_records"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    envelopes = [lead_env, drafter_env, validator_env]

    agents = [
        AgentConfig(
            id="standards-team-lead",
            name="Standards Team Lead",
            role="Standards review, coordination, and approval",
            constraint_envelope="standards-lead-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                # Lead-specific
                "review_spec",
                "approve_draft",
                "coordinate_review",
                "assign_task",
                "track_standards",
                # From spec drafter
                "draft_spec",
                "edit_spec",
                "research_standard",
                "suggest_structure",
                # From cross-reference validator
                "validate_references",
                "check_consistency",
                "generate_report",
                "flag_issues",
            ],
        ),
        AgentConfig(
            id="standards-spec-drafter",
            name="Spec Drafter",
            role="Draft and edit specifications",
            constraint_envelope="standards-drafter-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "draft_spec",
                "edit_spec",
                "research_standard",
                "suggest_structure",
            ],
        ),
        AgentConfig(
            id="standards-cross-ref-validator",
            name="Cross-Reference Validator",
            role="Validate cross-references and consistency in specs",
            constraint_envelope="standards-validator-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "validate_references",
                "check_consistency",
                "generate_report",
                "flag_issues",
            ],
        ),
    ]

    team = TeamConfig(
        id="standards-team",
        name="Standards Team",
        workspace="ws-standards",
        team_lead="standards-team-lead",
        agents=[a.id for a in agents],
    )

    return TeamTemplate(
        name="standards",
        description="Standards/Research team with spec drafting and validation agents",
        agents=agents,
        envelopes=envelopes,
        team=team,
    )


def _partnerships_template() -> TeamTemplate:
    """Partnerships/Outreach team template.

    Agents: team lead, researcher, grant writer.
    All envelopes: $0 spend (stricter financial controls for grant writer).
    """
    # Lead must be a superset of all subordinate capabilities and allowed_actions
    lead_env = ConstraintEnvelopeConfig(
        id="partnerships-lead-envelope",
        description="Partnerships Team Lead: outreach coordination",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                # Lead-specific
                "review_proposal",
                "coordinate_outreach",
                "approve_draft",
                "track_partnerships",
                "draft_strategy",
                # From researcher
                "research_partner",
                "analyze_opportunity",
                "generate_report",
                "track_landscape",
                # From grant writer
                "draft_proposal",
                "edit_proposal",
                "research_grant",
                "track_deadlines",
            ],
            blocked_actions=["publish_externally", "engage_legal", "sign_agreement"],
            max_actions_per_day=40,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="06:00", active_hours_end="22:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/partnerships/*", "workspaces/*/public/*"],
            write_paths=["workspaces/partnerships/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
            allowed_channels=["slack", "internal_review"],
        ),
    )

    researcher_env = ConstraintEnvelopeConfig(
        id="partnerships-researcher-envelope",
        description="Researcher: research potential partners and opportunities",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "research_partner",
                "analyze_opportunity",
                "generate_report",
                "track_landscape",
            ],
            blocked_actions=[
                "publish_externally",
                "engage_legal",
                "sign_agreement",
                "approve_draft",
            ],
            max_actions_per_day=30,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/partnerships/*", "workspaces/*/public/*"],
            write_paths=["workspaces/partnerships/research/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    grant_writer_env = ConstraintEnvelopeConfig(
        id="partnerships-grant-writer-envelope",
        description="Grant Writer: draft grant proposals with strict financial controls",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "draft_proposal",
                "edit_proposal",
                "research_grant",
                "track_deadlines",
            ],
            blocked_actions=[
                "publish_externally",
                "engage_legal",
                "sign_agreement",
                "approve_draft",
                "submit_grant",
            ],
            max_actions_per_day=20,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/partnerships/grants/*"],
            write_paths=["workspaces/partnerships/grants/drafts/*"],
            blocked_data_types=["pii", "legal_docs", "board_minutes"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    envelopes = [lead_env, researcher_env, grant_writer_env]

    agents = [
        AgentConfig(
            id="partnerships-team-lead",
            name="Partnerships Team Lead",
            role="Outreach coordination and partnership strategy",
            constraint_envelope="partnerships-lead-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                # Lead-specific
                "review_proposal",
                "coordinate_outreach",
                "approve_draft",
                "track_partnerships",
                "draft_strategy",
                # From researcher
                "research_partner",
                "analyze_opportunity",
                "generate_report",
                "track_landscape",
                # From grant writer
                "draft_proposal",
                "edit_proposal",
                "research_grant",
                "track_deadlines",
            ],
        ),
        AgentConfig(
            id="partnerships-researcher",
            name="Partnership Researcher",
            role="Research potential partners, analyze opportunities",
            constraint_envelope="partnerships-researcher-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "research_partner",
                "analyze_opportunity",
                "generate_report",
                "track_landscape",
            ],
        ),
        AgentConfig(
            id="partnerships-grant-writer",
            name="Grant Writer",
            role="Draft grant proposals with strict financial controls",
            constraint_envelope="partnerships-grant-writer-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "draft_proposal",
                "edit_proposal",
                "research_grant",
                "track_deadlines",
            ],
        ),
    ]

    team = TeamConfig(
        id="partnerships-team",
        name="Partnerships Team",
        workspace="ws-partnerships",
        team_lead="partnerships-team-lead",
        agents=[a.id for a in agents],
    )

    return TeamTemplate(
        name="partnerships",
        description="Partnerships/Outreach team with research and grant writing agents",
        agents=agents,
        envelopes=envelopes,
        team=team,
    )


def _engineering_template() -> TeamTemplate:
    """Engineering/Development team template (M20/5036).

    4 agents: team lead, code reviewer, testing agent, deployment agent.
    Envelopes: code read/write, CI trigger access, no production deploy
    without approval. All envelopes: $0 spend, internal-only communication.
    """
    # Lead must be a superset of all subordinate capabilities and allowed_actions
    # (monotonic constraint tightening). Lead actions include all subordinate actions.
    lead_env = ConstraintEnvelopeConfig(
        id="engineering-lead-envelope",
        description="Engineering Team Lead: broadest authority within engineering, code R/W, CI access",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                # Lead-specific
                "review_code",
                "approve_merge",
                "coordinate_team",
                "trigger_ci",
                "review_tests",
                "plan_deployment",
                "assign_task",
                # From code reviewer
                "suggest_changes",
                "flag_issues",
                # From testing agent
                "run_tests",
                "generate_report",
                "track_coverage",
                # From deployment agent
                "deploy_staging",
                "monitor_deployment",
                "rollback_staging",
            ],
            blocked_actions=["deploy_production", "modify_infrastructure", "engage_legal"],
            max_actions_per_day=80,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="06:00", active_hours_end="22:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=[
                "workspaces/engineering/*",
                "workspaces/*/public/*",
            ],
            write_paths=[
                "workspaces/engineering/*",
            ],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
            allowed_channels=["slack", "internal_review", "ci_notifications"],
        ),
    )

    reviewer_env = ConstraintEnvelopeConfig(
        id="engineering-reviewer-envelope",
        description="Code Reviewer: review code, suggest changes, approve PRs",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "review_code",
                "suggest_changes",
                "approve_merge",
                "flag_issues",
            ],
            blocked_actions=[
                "deploy_production",
                "modify_infrastructure",
                "engage_legal",
                "trigger_ci",
                "plan_deployment",
            ],
            max_actions_per_day=50,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=[
                "workspaces/engineering/src/*",
                "workspaces/engineering/tests/*",
                "workspaces/*/public/*",
            ],
            write_paths=["workspaces/engineering/reviews/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    testing_env = ConstraintEnvelopeConfig(
        id="engineering-testing-envelope",
        description="Testing Agent: run tests, report results, track coverage",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "run_tests",
                "generate_report",
                "track_coverage",
                "flag_issues",
            ],
            blocked_actions=[
                "deploy_production",
                "modify_infrastructure",
                "engage_legal",
                "approve_merge",
                "trigger_ci",
            ],
            max_actions_per_day=60,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=[
                "workspaces/engineering/src/*",
                "workspaces/engineering/tests/*",
            ],
            write_paths=["workspaces/engineering/tests/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    deployment_env = ConstraintEnvelopeConfig(
        id="engineering-deployment-envelope",
        description="Deployment Agent: staging deploys, CI triggers, NO production deploy",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "deploy_staging",
                "trigger_ci",
                "monitor_deployment",
                "rollback_staging",
            ],
            blocked_actions=[
                "deploy_production",
                "modify_infrastructure",
                "engage_legal",
                "approve_merge",
            ],
            max_actions_per_day=40,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=[
                "workspaces/engineering/src/*",
                "workspaces/engineering/deploy/*",
            ],
            write_paths=["workspaces/engineering/deploy/*"],
            blocked_data_types=["pii", "financial_records", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    envelopes = [lead_env, reviewer_env, testing_env, deployment_env]

    agents = [
        AgentConfig(
            id="engineering-team-lead",
            name="Engineering Team Lead",
            role="Team coordination, code review oversight, CI/CD management",
            constraint_envelope="engineering-lead-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                # Lead-specific
                "review_code",
                "approve_merge",
                "coordinate_team",
                "trigger_ci",
                "review_tests",
                "plan_deployment",
                "assign_task",
                # From code reviewer
                "suggest_changes",
                "flag_issues",
                # From testing agent
                "run_tests",
                "generate_report",
                "track_coverage",
                # From deployment agent
                "deploy_staging",
                "monitor_deployment",
                "rollback_staging",
            ],
        ),
        AgentConfig(
            id="engineering-code-reviewer",
            name="Code Reviewer",
            role="Review code changes, suggest improvements, approve PRs",
            constraint_envelope="engineering-reviewer-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "review_code",
                "suggest_changes",
                "approve_merge",
                "flag_issues",
            ],
        ),
        AgentConfig(
            id="engineering-testing-agent",
            name="Testing Agent",
            role="Run test suites, report results, track code coverage",
            constraint_envelope="engineering-testing-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "run_tests",
                "generate_report",
                "track_coverage",
                "flag_issues",
            ],
        ),
        AgentConfig(
            id="engineering-deployment-agent",
            name="Deployment Agent",
            role="Manage staging deployments, CI triggers, monitor releases",
            constraint_envelope="engineering-deployment-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "deploy_staging",
                "trigger_ci",
                "monitor_deployment",
                "rollback_staging",
            ],
        ),
    ]

    team = TeamConfig(
        id="engineering-team",
        name="Engineering Team",
        workspace="ws-engineering",
        team_lead="engineering-team-lead",
        agents=[a.id for a in agents],
    )

    return TeamTemplate(
        name="engineering",
        description="Engineering/Development team with code review, testing, and deployment agents",
        agents=agents,
        envelopes=envelopes,
        team=team,
    )


def _executive_template() -> TeamTemplate:
    """Executive/Leadership team template (M20/5037).

    3 agents: Chief of Staff, strategy analyst, reporting agent.
    Broader read access (cross-workspace), stricter write access,
    higher action limits for leadership. All envelopes: $0 spend,
    internal-only communication.
    """
    # Lead must be a superset of all subordinate capabilities and allowed_actions
    # (monotonic constraint tightening). Chief actions include all subordinate actions.
    chief_env = ConstraintEnvelopeConfig(
        id="executive-chief-envelope",
        description="Chief of Staff: broadest executive authority, cross-workspace read, restricted write",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                # Chief-specific
                "review_strategy",
                "approve_report",
                "coordinate_teams",
                "set_priorities",
                "review_metrics",
                "draft_directive",
                "escalate_issue",
                # From strategy analyst
                "analyze_strategy",
                "research_market",
                "draft_recommendation",
                "generate_report",
                # From reporting agent
                "aggregate_metrics",
                "track_kpis",
                "visualize_data",
            ],
            blocked_actions=["publish_externally", "engage_legal", "modify_constitution"],
            max_actions_per_day=100,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="06:00", active_hours_end="22:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=[
                "workspaces/*/public/*",
                "workspaces/executive/*",
                "workspaces/governance/*",
                "workspaces/*/reports/*",
                "analytics/*",
            ],
            write_paths=["workspaces/executive/*"],
            blocked_data_types=["pii"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
            allowed_channels=["slack", "internal_review", "leadership_channel"],
        ),
    )

    strategy_env = ConstraintEnvelopeConfig(
        id="executive-strategy-envelope",
        description="Strategy Analyst: research, analysis, strategic recommendations",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "analyze_strategy",
                "research_market",
                "draft_recommendation",
                "generate_report",
            ],
            blocked_actions=[
                "publish_externally",
                "engage_legal",
                "modify_constitution",
                "set_priorities",
                "approve_report",
            ],
            max_actions_per_day=60,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=[
                "workspaces/*/public/*",
                "workspaces/executive/*",
                "workspaces/*/reports/*",
            ],
            write_paths=["workspaces/executive/strategy/*"],
            blocked_data_types=["pii", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    reporting_env = ConstraintEnvelopeConfig(
        id="executive-reporting-envelope",
        description="Reporting Agent: aggregate metrics, generate executive reports",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "aggregate_metrics",
                "generate_report",
                "track_kpis",
                "visualize_data",
            ],
            blocked_actions=[
                "publish_externally",
                "engage_legal",
                "modify_constitution",
                "set_priorities",
                "approve_report",
            ],
            max_actions_per_day=80,
        ),
        temporal=TemporalConstraintConfig(active_hours_start="08:00", active_hours_end="20:00"),
        data_access=DataAccessConstraintConfig(
            read_paths=[
                "workspaces/*/public/*",
                "workspaces/executive/*",
                "workspaces/*/reports/*",
                "analytics/*",
            ],
            write_paths=["workspaces/executive/reports/*"],
            blocked_data_types=["pii", "legal_docs"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    envelopes = [chief_env, strategy_env, reporting_env]

    agents = [
        AgentConfig(
            id="executive-chief-of-staff",
            name="Chief of Staff",
            role="Executive coordination, cross-team oversight, strategic direction",
            constraint_envelope="executive-chief-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                # Chief-specific
                "review_strategy",
                "approve_report",
                "coordinate_teams",
                "set_priorities",
                "review_metrics",
                "draft_directive",
                "escalate_issue",
                # From strategy analyst
                "analyze_strategy",
                "research_market",
                "draft_recommendation",
                "generate_report",
                # From reporting agent
                "aggregate_metrics",
                "track_kpis",
                "visualize_data",
            ],
        ),
        AgentConfig(
            id="executive-strategy-analyst",
            name="Strategy Analyst",
            role="Strategic research, market analysis, recommendations",
            constraint_envelope="executive-strategy-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "analyze_strategy",
                "research_market",
                "draft_recommendation",
                "generate_report",
            ],
        ),
        AgentConfig(
            id="executive-reporting-agent",
            name="Reporting Agent",
            role="Aggregate metrics, generate executive dashboards and reports",
            constraint_envelope="executive-reporting-envelope",
            initial_posture=TrustPostureLevel.SUPERVISED,
            capabilities=[
                "aggregate_metrics",
                "generate_report",
                "track_kpis",
                "visualize_data",
            ],
        ),
    ]

    team = TeamConfig(
        id="executive-team",
        name="Executive Team",
        workspace="ws-executive",
        team_lead="executive-chief-of-staff",
        agents=[a.id for a in agents],
    )

    return TeamTemplate(
        name="executive",
        description="Executive/Leadership team with Chief of Staff, strategy, and reporting agents",
        agents=agents,
        envelopes=envelopes,
        team=team,
    )


# ---------------------------------------------------------------------------
# TemplateRegistry
# ---------------------------------------------------------------------------


class TemplateRegistry:
    """Registry of predefined team templates.

    Loaded with built-in team templates
    on construction. Supports list(), get(), apply() with overrides,
    register() with validation, and load_from_yaml() for custom templates.
    """

    def __init__(self) -> None:
        self._templates: dict[str, TeamTemplate] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        """Load all built-in templates."""
        for factory in [
            _media_template,
            _governance_template,
            _standards_template,
            _partnerships_template,
            _engineering_template,
            _executive_template,
        ]:
            tpl = factory()
            # Built-in templates are trusted — skip validation during load
            self._templates[tpl.name] = tpl

    @staticmethod
    def builtin_yaml_dir() -> Path:
        """Return the path to the built-in YAML template directory.

        The canonical location is ``pact/examples/foundation/templates/``.
        Falls back to the legacy ``pact/build/templates/builtin/`` if the
        canonical directory is not found.

        Returns:
            Absolute Path to the directory containing built-in YAML templates.

        Raises:
            FileNotFoundError: If neither the canonical nor the legacy
                template directory exists.
        """
        # Canonical location: pact/examples/foundation/templates/
        canonical = (
            Path(__file__).resolve().parent.parent.parent / "examples" / "foundation" / "templates"
        )
        if canonical.is_dir():
            return canonical
        # Legacy location: pact/build/templates/builtin/
        legacy = Path(__file__).resolve().parent / "builtin"
        if legacy.is_dir():
            return legacy
        raise FileNotFoundError(
            f"Built-in YAML template directory not found at "
            f"'{canonical}' (canonical) or '{legacy}' (legacy)."
        )

    def list(self) -> list[str]:
        """List all available template names.

        Returns:
            Sorted list of template name strings.
        """
        return sorted(self._templates.keys())

    def get(self, name: str) -> TeamTemplate:
        """Get a template by name.

        Args:
            name: Template name (e.g., 'media', 'governance').

        Returns:
            A deep copy of the TeamTemplate.

        Raises:
            ValueError: If the template name is not found.
        """
        tpl = self._templates.get(name)
        if tpl is None:
            available = sorted(self._templates.keys())
            raise ValueError(f"Template '{name}' not found. Available templates: {available}")
        return tpl.model_copy(deep=True)

    def register(self, template: TeamTemplate) -> None:
        """Register a template after validating it (M20/5040).

        Builds a temporary OrgDefinition from the template and runs
        validate_org_detailed(). If any ERROR-severity findings exist,
        the template is rejected with a ValueError containing all error details.

        Args:
            template: The TeamTemplate to validate and register.

        Raises:
            ValueError: If the template fails validation. The error message
                        includes all validation error details.
        """
        from pact_platform.build.org.builder import OrgDefinition

        # Build a temporary OrgDefinition to validate the template
        org = OrgDefinition(
            org_id=f"validate-{template.name}",
            name=f"Validate {template.name}",
            teams=[template.team],
            agents=list(template.agents),
            envelopes=list(template.envelopes),
            workspaces=[
                WorkspaceConfig(
                    id=template.team.workspace,
                    path=f"workspaces/{template.name}/",
                    description=f"Workspace for {template.name}",
                ),
            ],
        )

        results = org.validate_org_detailed()
        errors = [r for r in results if r.is_error]
        if errors:
            error_details = "; ".join(r.message for r in errors)
            raise ValueError(
                f"Template '{template.name}' failed validation with {len(errors)} error(s): "
                f"{error_details}"
            )

        self._templates[template.name] = template
        logger.info("Registered template '%s' with %d agents", template.name, len(template.agents))

    @classmethod
    def load_from_yaml(cls, path: str | Path) -> TeamTemplate:
        """Load a TeamTemplate from a YAML file (M20/5038).

        The YAML file must define name, agents, envelopes, and team sections
        matching the TeamTemplate schema.

        Args:
            path: Path to the YAML template file (str or Path).

        Returns:
            A validated TeamTemplate parsed from the YAML file.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            ValueError: If the YAML content is invalid or missing required fields.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Template YAML file not found: {path}. "
                f"Provide an absolute path to an existing YAML file."
            )

        raw_text = path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML from '{path}': {e}") from e

        if not isinstance(data, dict):
            raise ValueError(
                f"YAML file '{path}' must contain a mapping (dict) at the top level, "
                f"got {type(data).__name__}"
            )

        try:
            template = TeamTemplate(**data)
        except Exception as e:
            raise ValueError(f"Failed to construct TeamTemplate from '{path}': {e}") from e

        logger.info("Loaded template '%s' from YAML file '%s'", template.name, path)
        return template

    def apply(self, name: str, overrides: dict) -> TeamTemplate:
        """Apply a template with optional overrides.

        Supported overrides:
        - ``team_name``: Override the team display name
        - ``team_id``: Override the team ID
        - ``workspace``: Override the workspace reference

        Args:
            name: Template name to apply.
            overrides: Dict of overrides to apply.

        Returns:
            A new TeamTemplate with overrides applied.

        Raises:
            ValueError: If the template name is not found.
        """
        tpl = self.get(name)  # already a deep copy

        if "team_name" in overrides:
            tpl.team.name = overrides["team_name"]
        if "team_id" in overrides:
            tpl.team.id = overrides["team_id"]
        if "workspace" in overrides:
            tpl.team.workspace = overrides["workspace"]

        return tpl
