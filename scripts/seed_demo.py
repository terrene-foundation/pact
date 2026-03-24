#!/usr/bin/env python3
# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Demo seed script — populates realistic data for all PACT dashboard pages.

Seeds 4 teams, 14 agents, constraint envelopes, 250+ audit anchors, held actions,
cross-functional bridges, posture history, cost tracking data, and shadow enforcer
evaluations.

Usage:
    python scripts/seed_demo.py           # Seed data (idempotent)
    python scripts/seed_demo.py --reset   # Clear existing data, then seed

The script uses PACT Python SDK internals directly (no HTTP calls).
"""

from __future__ import annotations

import argparse
import logging
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4

# ---------------------------------------------------------------------------
# PACT imports
# ---------------------------------------------------------------------------
from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    VerificationLevel,
    WorkspaceConfig,
)
from pact_platform.trust.audit.anchor import AuditAnchor, AuditChain
from pact_platform.use.execution.approval import ApprovalQueue, UrgencyLevel
from pact_platform.use.execution.registry import AgentRegistry
from pact_platform.trust.store.cost_tracking import ApiCostRecord, CostTracker
from pact_platform.trust.store.posture_history import (
    PostureChangeRecord,
    PostureChangeTrigger,
    PostureHistoryStore,
)
from pact_platform.build.workspace.bridge import BridgeManager, BridgePermission
from pact_platform.build.workspace.models import (
    Workspace,
    WorkspacePhase,
    WorkspaceRegistry,
    WorkspaceState,
)

if TYPE_CHECKING:
    from pact_platform.trust.shadow_enforcer import ShadowEnforcer

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Deterministic randomness for reproducible demo data
random.seed(42)

# ---------------------------------------------------------------------------
# Team & Agent definitions
# ---------------------------------------------------------------------------

TEAMS = {
    "dm-team": {
        "name": "Digital Marketing",
        "description": "Content creation, scheduling, and analytics",
        "workspace_path": "workspaces/digital-marketing",
    },
    "governance-team": {
        "name": "Governance & Compliance",
        "description": "Policy review, constitution maintenance, audit monitoring",
        "workspace_path": "workspaces/governance",
    },
    "community-team": {
        "name": "Community Management",
        "description": "Outreach, engagement, and support",
        "workspace_path": "workspaces/community",
    },
    "standards-team": {
        "name": "Standards Development",
        "description": "CARE, EATP, and CO specification development",
        "workspace_path": "workspaces/standards",
    },
}

AGENTS = [
    # dm-team (canonical agents from pact_platform.build.verticals.dm_team)
    {
        "agent_id": "dm-team-lead",
        "name": "DM Team Lead",
        "role": "Team coordination, content review, approval routing",
        "team_id": "dm-team",
        "posture": TrustPostureLevel.SUPERVISED,
        "capabilities": [
            "review_content",
            "approve_publication",
            "coordinate_team",
            "schedule_content",
            "analyze_metrics",
            "draft_strategy",
            "draft_post",
            "edit_content",
            "research_topic",
            "suggest_hashtags",
            "read_metrics",
            "generate_report",
            "track_engagement",
            "analyze_trends",
        ],
    },
    {
        "agent_id": "dm-content-creator",
        "name": "Content Creator",
        "role": "Draft social media posts, blog articles, and marketing copy",
        "team_id": "dm-team",
        "posture": TrustPostureLevel.SUPERVISED,
        "capabilities": [
            "draft_post",
            "edit_content",
            "research_topic",
            "suggest_hashtags",
        ],
    },
    {
        "agent_id": "dm-analytics",
        "name": "Analytics Agent",
        "role": "Monitor engagement metrics, generate reports, track KPIs",
        "team_id": "dm-team",
        "posture": TrustPostureLevel.SUPERVISED,
        "capabilities": [
            "read_metrics",
            "generate_report",
            "track_engagement",
            "analyze_trends",
        ],
    },
    {
        "agent_id": "dm-community-manager",
        "name": "Community Manager",
        "role": "Community engagement, response drafting, moderation",
        "team_id": "dm-team",
        "posture": TrustPostureLevel.SUPERVISED,
        "capabilities": [
            "draft_response",
            "moderate_content",
            "track_community",
            "flag_issues",
        ],
    },
    {
        "agent_id": "dm-seo-specialist",
        "name": "SEO Specialist",
        "role": "SEO optimization, keyword research, content structure",
        "team_id": "dm-team",
        "posture": TrustPostureLevel.SUPERVISED,
        "capabilities": [
            "analyze_keywords",
            "suggest_structure",
            "audit_seo",
            "research_topics",
        ],
    },
    # governance-team
    {
        "agent_id": "policy-reviewer",
        "name": "Policy Reviewer",
        "role": "Reviews and updates governance policies",
        "team_id": "governance-team",
        "posture": TrustPostureLevel.DELEGATED,
        "capabilities": [
            "review_policy",
            "draft_policy",
            "cross_reference_clauses",
            "assess_compliance",
        ],
    },
    {
        "agent_id": "compliance-checker",
        "name": "Compliance Checker",
        "role": "Validates actions against governance constraints",
        "team_id": "governance-team",
        "posture": TrustPostureLevel.SHARED_PLANNING,
        "capabilities": [
            "check_compliance",
            "audit_trail",
            "flag_violation",
        ],
    },
    {
        "agent_id": "audit-monitor",
        "name": "Audit Monitor",
        "role": "Monitors audit logs and flags anomalies",
        "team_id": "governance-team",
        "posture": TrustPostureLevel.SUPERVISED,
        "capabilities": [
            "monitor_logs",
            "detect_anomaly",
            "generate_audit_report",
        ],
    },
    # community-team
    {
        "agent_id": "outreach-agent",
        "name": "Outreach Coordinator",
        "role": "Manages community outreach and partnership communications",
        "team_id": "community-team",
        "posture": TrustPostureLevel.SHARED_PLANNING,
        "capabilities": [
            "send_outreach",
            "manage_contacts",
            "draft_proposal",
            "coordinate_events",
        ],
    },
    {
        "agent_id": "engagement-bot",
        "name": "Engagement Bot",
        "role": "Responds to community questions and moderates discussions",
        "team_id": "community-team",
        "posture": TrustPostureLevel.SUPERVISED,
        "capabilities": [
            "respond_to_query",
            "moderate_discussion",
            "escalate_issue",
        ],
    },
    {
        "agent_id": "support-agent",
        "name": "Support Agent",
        "role": "Handles support tickets and documentation requests",
        "team_id": "community-team",
        "posture": TrustPostureLevel.SUPERVISED,
        "capabilities": [
            "handle_ticket",
            "update_docs",
            "triage_issue",
        ],
    },
    # standards-team
    {
        "agent_id": "spec-writer",
        "name": "Specification Writer",
        "role": "Drafts and maintains CARE, EATP, and CO specifications",
        "team_id": "standards-team",
        "posture": TrustPostureLevel.CONTINUOUS_INSIGHT,
        "capabilities": [
            "draft_spec",
            "update_spec",
            "cross_reference",
            "validate_consistency",
        ],
    },
    {
        "agent_id": "reviewer",
        "name": "Standards Reviewer",
        "role": "Reviews specification changes for correctness and consistency",
        "team_id": "standards-team",
        "posture": TrustPostureLevel.SHARED_PLANNING,
        "capabilities": [
            "review_spec",
            "suggest_changes",
            "verify_references",
        ],
    },
    {
        "agent_id": "validator",
        "name": "Standards Validator",
        "role": "Validates implementations against specifications",
        "team_id": "standards-team",
        "posture": TrustPostureLevel.SUPERVISED,
        "capabilities": [
            "validate_implementation",
            "run_conformance_tests",
            "report_gaps",
        ],
    },
]

# ---------------------------------------------------------------------------
# Constraint envelope definitions (one per agent)
# ---------------------------------------------------------------------------


def _build_envelopes() -> dict[str, ConstraintEnvelopeConfig]:
    """Build constraint envelopes keyed by agent_id."""
    return {
        # --- dm-team (canonical envelopes from pact_platform.build.verticals.dm_team) ---
        "dm-team-lead": ConstraintEnvelopeConfig(
            id="env-dm-team-lead",
            description="DM Team Lead: broadest authority within DM, $0 spend, internal-only",
            financial=FinancialConstraintConfig(
                max_spend_usd=0.0,
                api_cost_budget_usd=200.0,
                requires_approval_above_usd=0.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=[
                    "review_content",
                    "approve_publication",
                    "coordinate_team",
                    "schedule_content",
                    "analyze_metrics",
                    "draft_strategy",
                    "draft_post",
                    "edit_content",
                    "research_topic",
                    "suggest_hashtags",
                    "read_metrics",
                    "generate_report",
                    "track_engagement",
                    "analyze_trends",
                    "draft_response",
                    "moderate_content",
                    "track_community",
                    "flag_issues",
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
                timezone="Asia/Singapore",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/dm/*", "workspaces/standards/public/*", "analytics/*"],
                write_paths=["workspaces/dm/*"],
                blocked_data_types=["pii", "financial_records", "legal_docs", "board_minutes"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                allowed_channels=["slack", "internal_review"],
                external_requires_approval=True,
            ),
        ),
        "dm-content-creator": ConstraintEnvelopeConfig(
            id="env-dm-content-creator",
            description="Content Creator: draft-only, no publishing, no external communication",
            financial=FinancialConstraintConfig(
                max_spend_usd=0.0,
                api_cost_budget_usd=100.0,
                requires_approval_above_usd=0.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=[
                    "draft_post",
                    "edit_content",
                    "research_topic",
                    "suggest_hashtags",
                ],
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
                timezone="Asia/Singapore",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["workspaces/dm/content/*", "workspaces/standards/public/*"],
                write_paths=["workspaces/dm/content/drafts/*"],
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
        ),
        "dm-analytics": ConstraintEnvelopeConfig(
            id="env-dm-analytics",
            description="Analytics: read-heavy monitoring, no external communication",
            financial=FinancialConstraintConfig(
                max_spend_usd=0.0,
                api_cost_budget_usd=150.0,
                requires_approval_above_usd=0.0,
            ),
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
            temporal=TemporalConstraintConfig(
                active_hours_start="06:00",
                active_hours_end="22:00",
                timezone="Asia/Singapore",
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
        ),
        "dm-community-manager": ConstraintEnvelopeConfig(
            id="env-dm-community-manager",
            description="Community Manager: draft responses, moderate, no external sending",
            financial=FinancialConstraintConfig(
                max_spend_usd=0.0,
                api_cost_budget_usd=80.0,
                requires_approval_above_usd=0.0,
            ),
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
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="20:00",
                timezone="Asia/Singapore",
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
        ),
        "dm-seo-specialist": ConstraintEnvelopeConfig(
            id="env-dm-seo-specialist",
            description="SEO Specialist: analysis and suggestions, no publishing",
            financial=FinancialConstraintConfig(
                max_spend_usd=0.0,
                api_cost_budget_usd=80.0,
                requires_approval_above_usd=0.0,
            ),
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
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="20:00",
                timezone="Asia/Singapore",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=[
                    "workspaces/dm/content/*",
                    "workspaces/standards/public/*",
                    "analytics/seo/*",
                ],
                write_paths=["workspaces/dm/seo/reports/*"],
                blocked_data_types=["pii", "financial_records", "legal_docs", "board_minutes"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        ),
        # --- governance-team ---
        "policy-reviewer": ConstraintEnvelopeConfig(
            id="env-policy-reviewer",
            description="Policy Reviewer envelope: high trust, broad policy access",
            financial=FinancialConstraintConfig(
                max_spend_usd=2000.0,
                api_cost_budget_usd=1000.0,
                requires_approval_above_usd=500.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=[
                    "review_policy",
                    "draft_policy",
                    "cross_reference_clauses",
                    "assess_compliance",
                ],
                blocked_actions=["modify_governance", "external_publication"],
                max_actions_per_day=80,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="00:00",
                active_hours_end="23:59",
                timezone="UTC",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["governance/*", "constitution/*", "policies/*", "audit/*"],
                write_paths=["governance/drafts/*", "policies/drafts/*"],
                blocked_data_types=["financial_records"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                allowed_channels=["slack-governance", "board-portal"],
                external_requires_approval=True,
            ),
        ),
        "compliance-checker": ConstraintEnvelopeConfig(
            id="env-compliance-checker",
            description="Compliance Checker envelope: read-heavy audit access",
            financial=FinancialConstraintConfig(
                max_spend_usd=500.0,
                api_cost_budget_usd=250.0,
                requires_approval_above_usd=100.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=["check_compliance", "audit_trail", "flag_violation"],
                blocked_actions=["modify_governance", "draft_policy", "modify_constraints"],
                max_actions_per_day=200,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="00:00",
                active_hours_end="23:59",
                timezone="UTC",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["audit/*", "governance/*", "policies/*", "agents/*"],
                write_paths=["audit/flags/*"],
                blocked_data_types=["pii"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                allowed_channels=["slack-compliance"],
                external_requires_approval=True,
            ),
        ),
        "audit-monitor": ConstraintEnvelopeConfig(
            id="env-audit-monitor",
            description="Audit Monitor envelope: read-only monitoring",
            financial=FinancialConstraintConfig(
                max_spend_usd=200.0,
                api_cost_budget_usd=100.0,
                requires_approval_above_usd=50.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=["monitor_logs", "detect_anomaly", "generate_audit_report"],
                blocked_actions=[
                    "modify_governance",
                    "draft_policy",
                    "delete_content",
                    "modify_constraints",
                ],
                max_actions_per_day=500,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="00:00",
                active_hours_end="23:59",
                timezone="UTC",
                blackout_periods=["2026-12-25", "2026-01-01"],
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["audit/*", "logs/*"],
                write_paths=["audit/reports/*"],
                blocked_data_types=["pii", "financial_records"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                allowed_channels=["slack-audit-alerts"],
                external_requires_approval=True,
            ),
        ),
        # --- community-team ---
        "outreach-agent": ConstraintEnvelopeConfig(
            id="env-outreach-agent",
            description="Outreach Coordinator envelope: external communication allowed",
            financial=FinancialConstraintConfig(
                max_spend_usd=1000.0,
                api_cost_budget_usd=400.0,
                requires_approval_above_usd=150.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=[
                    "send_outreach",
                    "manage_contacts",
                    "draft_proposal",
                    "coordinate_events",
                ],
                blocked_actions=["modify_constraints", "financial_decisions"],
                max_actions_per_day=40,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="18:00",
                timezone="Asia/Singapore",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["community/*", "contacts/*", "events/*"],
                write_paths=["community/outreach/*", "events/planned/*"],
                blocked_data_types=["financial_records"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=False,
                allowed_channels=["slack-community", "email-outreach", "discord"],
                external_requires_approval=True,
            ),
        ),
        "engagement-bot": ConstraintEnvelopeConfig(
            id="env-engagement-bot",
            description="Engagement Bot envelope: limited response capability",
            financial=FinancialConstraintConfig(
                max_spend_usd=200.0,
                api_cost_budget_usd=100.0,
                requires_approval_above_usd=50.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=["respond_to_query", "moderate_discussion", "escalate_issue"],
                blocked_actions=[
                    "send_outreach",
                    "modify_constraints",
                    "delete_content",
                    "financial_decisions",
                ],
                max_actions_per_day=300,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="00:00",
                active_hours_end="23:59",
                timezone="UTC",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["community/faq/*", "docs/*"],
                write_paths=["community/responses/*"],
                blocked_data_types=["pii", "financial_records"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=False,
                allowed_channels=["discord", "github-discussions"],
                external_requires_approval=False,
            ),
        ),
        "support-agent": ConstraintEnvelopeConfig(
            id="env-support-agent",
            description="Support Agent envelope: ticket handling, docs updates",
            financial=FinancialConstraintConfig(
                max_spend_usd=300.0,
                api_cost_budget_usd=150.0,
                requires_approval_above_usd=75.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=["handle_ticket", "update_docs", "triage_issue"],
                blocked_actions=[
                    "send_outreach",
                    "modify_constraints",
                    "financial_decisions",
                ],
                max_actions_per_day=100,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="20:00",
                timezone="Asia/Singapore",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["support/tickets/*", "docs/*", "community/faq/*"],
                write_paths=["support/responses/*", "docs/updates/*"],
                blocked_data_types=["pii", "financial_records"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                allowed_channels=["slack-support", "zendesk"],
                external_requires_approval=True,
            ),
        ),
        # --- standards-team ---
        "spec-writer": ConstraintEnvelopeConfig(
            id="env-spec-writer",
            description="Specification Writer envelope: high trust, spec read/write",
            financial=FinancialConstraintConfig(
                max_spend_usd=5000.0,
                api_cost_budget_usd=2000.0,
                requires_approval_above_usd=1000.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=[
                    "draft_spec",
                    "update_spec",
                    "cross_reference",
                    "validate_consistency",
                ],
                blocked_actions=["external_publication", "modify_governance", "modify_constraints"],
                max_actions_per_day=60,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="00:00",
                active_hours_end="23:59",
                timezone="UTC",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["standards/*", "specs/*", "docs/*", "governance/*"],
                write_paths=["standards/drafts/*", "specs/drafts/*"],
                blocked_data_types=["pii"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                allowed_channels=["slack-standards", "github-specs"],
                external_requires_approval=True,
            ),
        ),
        "reviewer": ConstraintEnvelopeConfig(
            id="env-reviewer",
            description="Standards Reviewer envelope: read-heavy review access",
            financial=FinancialConstraintConfig(
                max_spend_usd=1500.0,
                api_cost_budget_usd=750.0,
                requires_approval_above_usd=300.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=["review_spec", "suggest_changes", "verify_references"],
                blocked_actions=[
                    "update_spec",
                    "external_publication",
                    "modify_constraints",
                ],
                max_actions_per_day=50,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="07:00",
                active_hours_end="21:00",
                timezone="UTC",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["standards/*", "specs/*", "docs/*"],
                write_paths=["standards/reviews/*"],
                blocked_data_types=["pii", "financial_records"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                allowed_channels=["slack-standards", "github-reviews"],
                external_requires_approval=True,
            ),
        ),
        "validator": ConstraintEnvelopeConfig(
            id="env-validator",
            description="Standards Validator envelope: read-only conformance testing",
            financial=FinancialConstraintConfig(
                max_spend_usd=800.0,
                api_cost_budget_usd=400.0,
                requires_approval_above_usd=200.0,
            ),
            operational=OperationalConstraintConfig(
                allowed_actions=[
                    "validate_implementation",
                    "run_conformance_tests",
                    "report_gaps",
                ],
                blocked_actions=[
                    "update_spec",
                    "draft_spec",
                    "external_publication",
                    "modify_constraints",
                ],
                max_actions_per_day=80,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="06:00",
                active_hours_end="22:00",
                timezone="UTC",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["standards/*", "specs/*", "implementations/*"],
                write_paths=["validation/results/*"],
                blocked_data_types=["pii", "financial_records"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                allowed_channels=["slack-validation", "ci-reports"],
                external_requires_approval=True,
            ),
        ),
    }


# ---------------------------------------------------------------------------
# Audit anchor generation
# ---------------------------------------------------------------------------

# Realistic action names per agent for audit data
_AGENT_ACTIONS: dict[str, list[tuple[str, str]]] = {
    # (action, resource) tuples — dm-team (canonical agents)
    "dm-team-lead": [
        ("review_content", "blog/ai-trust-governance.md"),
        ("approve_publication", "social/weekly-update.md"),
        ("coordinate_team", "dm-team/sprint-planning"),
        ("schedule_content", "content-calendar/march"),
        ("analyze_metrics", "engagement/weekly-report"),
        ("draft_strategy", "strategy/q2-content-plan"),
    ],
    "dm-content-creator": [
        ("draft_post", "blog/ai-trust-governance.md"),
        ("draft_post", "social/weekly-update.md"),
        ("edit_content", "newsletter/march-2026.md"),
        ("research_topic", "trends/agent-orchestration"),
        ("suggest_hashtags", "social/eatp-announcement"),
        ("draft_post", "blog/eatp-deep-dive.md"),
        ("edit_content", "blog/care-philosophy.md"),
    ],
    "dm-analytics": [
        ("read_metrics", "engagement/weekly-report"),
        ("generate_report", "campaign/q1-performance"),
        ("track_engagement", "social/reach-by-platform"),
        ("analyze_trends", "growth/q2-projections"),
        ("read_metrics", "content/top-performers"),
        ("generate_report", "audience/demographics-march"),
    ],
    "dm-community-manager": [
        ("draft_response", "community/question-about-eatp"),
        ("moderate_content", "community/discussion-guidelines"),
        ("track_community", "community/engagement-march"),
        ("flag_issues", "community/spam-report-14"),
        ("draft_response", "community/how-to-contribute"),
    ],
    "dm-seo-specialist": [
        ("analyze_keywords", "seo/eatp-keyword-research"),
        ("suggest_structure", "blog/care-philosophy-restructure"),
        ("audit_seo", "site/monthly-seo-audit"),
        ("research_topics", "trends/trust-governance-search-volume"),
        ("analyze_keywords", "seo/co-methodology-terms"),
    ],
    "policy-reviewer": [
        ("review_policy", "governance/data-retention-policy"),
        ("draft_policy", "governance/agent-autonomy-guidelines"),
        ("cross_reference_clauses", "constitution/entrenched-provisions"),
        ("assess_compliance", "operations/q1-compliance-audit"),
        ("review_policy", "governance/contributor-framework"),
        ("draft_policy", "governance/bridge-approval-policy"),
    ],
    "compliance-checker": [
        ("check_compliance", "agent/dm-content-creator/actions-log"),
        ("audit_trail", "team/dm-team/march-operations"),
        ("flag_violation", "agent/dm-team-lead/unapproved-publish"),
        ("check_compliance", "bridge/standing-dm-community"),
        ("audit_trail", "team/standards-team/spec-changes"),
    ],
    "audit-monitor": [
        ("monitor_logs", "platform/api-access-log"),
        ("detect_anomaly", "agent/dm-analytics/unusual-query-volume"),
        ("generate_audit_report", "platform/weekly-audit-summary"),
        ("monitor_logs", "trust/delegation-changes"),
        ("detect_anomaly", "cost/budget-spike-dm-team"),
    ],
    "outreach-agent": [
        ("send_outreach", "partner/open-source-community-invite"),
        ("manage_contacts", "contacts/developer-advocates"),
        ("draft_proposal", "event/care-workshop-proposal"),
        ("coordinate_events", "event/standards-hackathon"),
        ("send_outreach", "partner/university-collaboration"),
    ],
    "engagement-bot": [
        ("respond_to_query", "discord/question-about-eatp"),
        ("moderate_discussion", "github/discussion-123"),
        ("escalate_issue", "discord/security-concern-report"),
        ("respond_to_query", "discord/how-to-contribute"),
        ("respond_to_query", "github/question-about-co"),
        ("moderate_discussion", "discord/off-topic-cleanup"),
    ],
    "support-agent": [
        ("handle_ticket", "zendesk/ticket-4521"),
        ("update_docs", "docs/getting-started-guide"),
        ("triage_issue", "github/issue-287"),
        ("handle_ticket", "zendesk/ticket-4535"),
        ("update_docs", "docs/api-reference"),
    ],
    "spec-writer": [
        ("draft_spec", "standards/care/v1.2-mirror-thesis"),
        ("update_spec", "standards/eatp/trust-lineage-chain"),
        ("cross_reference", "standards/co/methodology-layers"),
        ("validate_consistency", "standards/care-eatp-alignment"),
        ("draft_spec", "standards/cdi/constraint-dimensions"),
        ("update_spec", "standards/co/domain-applications"),
    ],
    "reviewer": [
        ("review_spec", "standards/care/v1.2-draft"),
        ("suggest_changes", "standards/eatp/verification-gradient"),
        ("verify_references", "standards/co/principle-citations"),
        ("review_spec", "standards/cdi/v0.9-draft"),
        ("suggest_changes", "standards/care/mirror-thesis-wording"),
    ],
    "validator": [
        ("validate_implementation", "platform/eatp-bridge-conformance"),
        ("run_conformance_tests", "sdk/kailash-kaizen-care-compliance"),
        ("report_gaps", "platform/constraint-envelope-gaps"),
        ("validate_implementation", "platform/posture-lifecycle"),
        ("run_conformance_tests", "sdk/eatp-sdk-operations"),
    ],
}

# Verification level distribution (realistic: most auto-approved)
_VERIFICATION_WEIGHTS = {
    "AUTO_APPROVED": 0.72,
    "FLAGGED": 0.15,
    "HELD": 0.10,
    "BLOCKED": 0.03,
}

# Action result distribution per verification level
_RESULT_BY_LEVEL = {
    "AUTO_APPROVED": "SUCCESS",
    "FLAGGED": "SUCCESS",  # flagged but still succeeded
    "HELD": "SUCCESS",  # approved and succeeded
    "BLOCKED": "DENIED",
}


def _random_verification_level() -> str:
    """Pick a verification level based on realistic distribution."""
    r = random.random()
    cumulative = 0.0
    for level, weight in _VERIFICATION_WEIGHTS.items():
        cumulative += weight
        if r <= cumulative:
            return level
    return "AUTO_APPROVED"


# ---------------------------------------------------------------------------
# LLM cost data
# ---------------------------------------------------------------------------

_LLM_MODELS = [
    ("anthropic", "claude-sonnet-4-20250514", Decimal("0.003"), Decimal("0.015")),
    ("anthropic", "claude-opus-4-20250514", Decimal("0.015"), Decimal("0.075")),
    ("anthropic", "claude-haiku-3-20250307", Decimal("0.00025"), Decimal("0.00125")),
]


# ---------------------------------------------------------------------------
# Seeding functions
# ---------------------------------------------------------------------------


def seed_agents(registry: AgentRegistry) -> None:
    """Register all 14 agents across 4 teams."""
    for agent_def in AGENTS:
        # Check if already registered (idempotent)
        if registry.get(agent_def["agent_id"]) is not None:
            continue
        record = registry.register(
            agent_id=agent_def["agent_id"],
            name=agent_def["name"],
            role=agent_def["role"],
            team_id=agent_def["team_id"],
            capabilities=agent_def["capabilities"],
            posture=agent_def["posture"].value,
        )
        record.envelope_id = f"env-{agent_def['agent_id']}"
        # Set a recent last_active_at so they don't appear stale
        record.last_active_at = datetime.now(UTC) - timedelta(hours=random.randint(1, 12))


def seed_workspaces(workspace_registry: WorkspaceRegistry) -> None:
    """Register workspaces for each team."""
    for team_id, team_info in TEAMS.items():
        ws_id = f"ws-{team_id}"
        if workspace_registry.get(ws_id) is not None:
            continue

        config = WorkspaceConfig(
            id=ws_id,
            path=team_info["workspace_path"],
            description=team_info["description"],
        )
        workspace = Workspace(
            config=config,
            team_id=team_id,
            workspace_state=WorkspaceState.PROVISIONING,
            current_phase=WorkspacePhase.ANALYZE,
        )
        # Activate the workspace
        workspace.activate(reason="Initial provisioning complete")

        # Progress each workspace to a different phase for visual variety
        phase_targets = {
            "dm-team": WorkspacePhase.IMPLEMENT,
            "governance-team": WorkspacePhase.VALIDATE,
            "community-team": WorkspacePhase.PLAN,
            "standards-team": WorkspacePhase.CODIFY,
        }
        target = phase_targets.get(team_id, WorkspacePhase.ANALYZE)

        # Walk through phases to reach target
        phase_path = {
            WorkspacePhase.PLAN: [WorkspacePhase.PLAN],
            WorkspacePhase.IMPLEMENT: [WorkspacePhase.PLAN, WorkspacePhase.IMPLEMENT],
            WorkspacePhase.VALIDATE: [
                WorkspacePhase.PLAN,
                WorkspacePhase.IMPLEMENT,
                WorkspacePhase.VALIDATE,
            ],
            WorkspacePhase.CODIFY: [
                WorkspacePhase.PLAN,
                WorkspacePhase.IMPLEMENT,
                WorkspacePhase.VALIDATE,
                WorkspacePhase.CODIFY,
            ],
        }
        for phase in phase_path.get(target, []):
            workspace.transition_to(phase, reason=f"Progressing to {phase.value}")

        workspace_registry.register(workspace)


def seed_envelopes() -> dict[str, ConstraintEnvelopeConfig]:
    """Build and return the envelope registry."""
    return _build_envelopes()


def seed_audit_anchors() -> tuple[dict[str, int], list[dict]]:
    """Generate 250+ audit anchor records spread across agents and time.

    Returns:
        Tuple of (verification_stats dict, list of audit record dicts).
    """
    now = datetime.now(UTC)
    stats: dict[str, int] = {
        "AUTO_APPROVED": 0,
        "FLAGGED": 0,
        "HELD": 0,
        "BLOCKED": 0,
    }
    records: list[dict] = []

    for agent_def in AGENTS:
        agent_id = agent_def["agent_id"]
        actions = _AGENT_ACTIONS.get(agent_id, [])
        if not actions:
            continue

        # Each agent gets 20-25 audit records over the last 30 days
        num_records = random.randint(20, 25)
        for _ in range(num_records):
            action, resource = random.choice(actions)
            level = _random_verification_level()
            result = _RESULT_BY_LEVEL[level]
            # Occasionally a HELD action is rejected
            if level == "HELD" and random.random() < 0.2:
                result = "DENIED"
            timestamp = now - timedelta(
                days=random.randint(0, 29),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            records.append(
                {
                    "anchor_id": f"aa-{uuid4().hex[:8]}",
                    "agent_id": agent_id,
                    "team_id": agent_def["team_id"],
                    "action": action,
                    "resource": resource,
                    "verification_level": level,
                    "result": result,
                    "timestamp": timestamp.isoformat(),
                }
            )
            stats[level] += 1

    return stats, records


def seed_held_actions(approval_queue: ApprovalQueue) -> None:
    """Submit 5 held actions at varying urgency levels."""
    # Skip if queue already has pending items (idempotent)
    if approval_queue.queue_depth > 0:
        return

    held_actions = [
        {
            "agent_id": "dm-team-lead",
            "action": "approve_publication",
            "reason": "Publication approval has governance implications — requires human review",
            "team_id": "dm-team",
            "resource": "blog/controversial-ai-opinion",
            "urgency": UrgencyLevel.IMMEDIATE,
            "constraint_details": {
                "dimension": "operational",
                "rule": "approval_actions_held",
                "channel": "blog-public",
            },
        },
        {
            "agent_id": "dm-content-creator",
            "action": "draft_post",
            "reason": "Draft volume approaching daily action limit (18 of 20 used)",
            "team_id": "dm-team",
            "resource": "campaign/hero-content-batch",
            "urgency": UrgencyLevel.STANDARD,
            "constraint_details": {
                "dimension": "operational",
                "rule": "approaching_daily_limit",
                "current_count": 18,
                "limit": 20,
            },
        },
        {
            "agent_id": "outreach-agent",
            "action": "send_outreach",
            "reason": "External email to new partner requires approval",
            "team_id": "community-team",
            "resource": "partner/university-collaboration-proposal",
            "urgency": UrgencyLevel.STANDARD,
            "constraint_details": {
                "dimension": "communication",
                "rule": "external_requires_approval",
                "channel": "email-outreach",
                "recipient": "partner-university",
            },
        },
        {
            "agent_id": "spec-writer",
            "action": "update_spec",
            "reason": "Modifying entrenched EATP provision requires governance review",
            "team_id": "standards-team",
            "resource": "standards/eatp/trust-lineage-chain/section-3",
            "urgency": UrgencyLevel.IMMEDIATE,
            "constraint_details": {
                "dimension": "operational",
                "rule": "governance_review_required",
                "affected_section": "Trust Lineage Chain core definition",
            },
        },
        {
            "agent_id": "engagement-bot",
            "action": "escalate_issue",
            "reason": "Potential security concern reported — requires human triage",
            "team_id": "community-team",
            "resource": "discord/security-vulnerability-report",
            "urgency": UrgencyLevel.BATCH,
            "constraint_details": {
                "dimension": "operational",
                "rule": "security_escalation",
                "severity": "medium",
            },
        },
    ]

    for ha in held_actions:
        approval_queue.submit(
            agent_id=ha["agent_id"],
            action=ha["action"],
            reason=ha["reason"],
            team_id=ha["team_id"],
            resource=ha["resource"],
            urgency=ha["urgency"],
            constraint_details=ha["constraint_details"],
        )


def seed_bridges(bridge_manager: BridgeManager) -> None:
    """Create 4 cross-functional bridges with varying types and statuses."""
    # Skip if bridges already exist (idempotent)
    if bridge_manager.list_all_bridges():
        return

    # 1. Standing bridge: dm-team <-> community-team (content sharing)
    standing = bridge_manager.create_standing_bridge(
        source_team="dm-team",
        target_team="community-team",
        purpose="Shared content pipeline: DM creates, Community distributes",
        permissions=BridgePermission(
            read_paths=["content/approved/*", "content/published/*"],
            write_paths=["content/community-feedback/*"],
            message_types=["content_ready", "feedback", "schedule_update"],
            requires_attribution=True,
        ),
        created_by="dm-team-lead",
    )
    # Approve both sides to make it ACTIVE
    bridge_manager.approve_bridge_source(standing.bridge_id, "dm-team-lead")
    bridge_manager.approve_bridge_target(standing.bridge_id, "outreach-agent")

    # 2. Scoped bridge: governance-team <-> standards-team (spec review, 30 days)
    scoped = bridge_manager.create_scoped_bridge(
        source_team="governance-team",
        target_team="standards-team",
        purpose="EATP v1.2 governance review — time-bounded access for spec review cycle",
        permissions=BridgePermission(
            read_paths=["standards/eatp/v1.2-draft/*", "standards/care/v1.2-draft/*"],
            write_paths=["standards/reviews/governance/*"],
            message_types=["review_comment", "approval", "change_request"],
            requires_attribution=True,
        ),
        created_by="policy-reviewer",
        valid_days=30,
        one_time=False,
    )
    # Approve both sides to make it ACTIVE
    bridge_manager.approve_bridge_source(scoped.bridge_id, "policy-reviewer")
    bridge_manager.approve_bridge_target(scoped.bridge_id, "spec-writer")

    # 3. Ad-hoc bridge: dm-team -> governance-team (compliance check)
    adhoc = bridge_manager.create_adhoc_bridge(
        source_team="dm-team",
        target_team="governance-team",
        purpose="One-time compliance check for new AI content policy blog post",
        request_payload={
            "content_type": "blog_post",
            "title": "AI Agents in Enterprise: A Trust-First Approach",
            "concerns": [
                "References Foundation governance model",
                "Mentions specific EATP constraint dimensions",
                "Needs compliance review before external publication",
            ],
        },
        created_by="dm-content-creator",
    )
    # Approve both sides — still pending response
    bridge_manager.approve_bridge_source(adhoc.bridge_id, "dm-content-creator")
    bridge_manager.approve_bridge_target(adhoc.bridge_id, "compliance-checker")

    # 4. Standing bridge: standards-team <-> community-team (spec feedback)
    standing2 = bridge_manager.create_standing_bridge(
        source_team="standards-team",
        target_team="community-team",
        purpose="Community feedback channel for specification drafts",
        permissions=BridgePermission(
            read_paths=["standards/drafts/public/*"],
            write_paths=[],
            message_types=["feedback_request", "community_input"],
            requires_attribution=False,
        ),
        created_by="spec-writer",
    )
    # Only source approved — target still pending
    bridge_manager.approve_bridge_source(standing2.bridge_id, "spec-writer")


def seed_posture_history(posture_store: PostureHistoryStore) -> None:
    """Create realistic posture history for agents showing progression over time."""
    # Skip if history already exists (idempotent)
    try:
        posture_store.current_posture("dm-team-lead")
        return  # Already seeded
    except KeyError:
        pass  # Expected — no history yet

    now = datetime.now(UTC)

    # Each agent's posture history: list of (from, to, direction, trigger, days_ago, reason)
    histories: dict[str, list[tuple[str, str, str, PostureChangeTrigger, int, str]]] = {
        "dm-team-lead": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                180,
                "Initial activation after onboarding period",
            ),
        ],
        "dm-content-creator": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                120,
                "Completed supervised onboarding with zero incidents",
            ),
        ],
        "dm-analytics": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                90,
                "Initial activation for analytics monitoring",
            ),
        ],
        "dm-community-manager": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                60,
                "Initial activation for community management",
            ),
        ],
        "dm-seo-specialist": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                45,
                "Initial activation for SEO analysis",
            ),
        ],
        "policy-reviewer": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                500,
                "Initial activation",
            ),
            (
                "supervised",
                "shared_planning",
                "upgrade",
                PostureChangeTrigger.REVIEW,
                400,
                "Demonstrated governance expertise across 200+ policy reviews",
            ),
            (
                "shared_planning",
                "continuous_insight",
                "upgrade",
                PostureChangeTrigger.TRUST_SCORE,
                250,
                "Consistent 99% success rate, 600+ operations",
            ),
            (
                "continuous_insight",
                "delegated",
                "upgrade",
                PostureChangeTrigger.APPROVAL,
                30,
                "Board-approved delegation: 1000+ ops, 99.5% success, 98% shadow pass rate",
            ),
        ],
        "compliance-checker": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                200,
                "Initial activation",
            ),
            (
                "supervised",
                "shared_planning",
                "upgrade",
                PostureChangeTrigger.REVIEW,
                90,
                "Achieved 96% success rate over 150 compliance checks",
            ),
        ],
        "audit-monitor": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                90,
                "Initial activation after configuration review",
            ),
        ],
        "outreach-agent": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                150,
                "Initial activation",
            ),
            (
                "supervised",
                "shared_planning",
                "upgrade",
                PostureChangeTrigger.REVIEW,
                45,
                "Demonstrated appropriate judgment in external communications",
            ),
        ],
        "engagement-bot": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                60,
                "Bot activated in supervised mode after testing",
            ),
        ],
        "support-agent": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                100,
                "Initial activation",
            ),
            (
                "supervised",
                "shared_planning",
                "upgrade",
                PostureChangeTrigger.REVIEW,
                40,
                "Promoted after successful ticket handling period",
            ),
            (
                "shared_planning",
                "supervised",
                "downgrade",
                PostureChangeTrigger.INCIDENT,
                20,
                "Incorrect documentation update caused user confusion — reverted to supervised",
            ),
        ],
        "spec-writer": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                300,
                "Initial activation",
            ),
            (
                "supervised",
                "shared_planning",
                "upgrade",
                PostureChangeTrigger.REVIEW,
                200,
                "Demonstrated deep specification knowledge across 300+ operations",
            ),
            (
                "shared_planning",
                "continuous_insight",
                "upgrade",
                PostureChangeTrigger.TRUST_SCORE,
                60,
                "Exceeded thresholds: 99% success, 550 ops, 96% shadow pass rate",
            ),
        ],
        "reviewer": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                180,
                "Initial activation",
            ),
            (
                "supervised",
                "shared_planning",
                "upgrade",
                PostureChangeTrigger.REVIEW,
                60,
                "Reliable review quality: 97% success rate across 120 reviews",
            ),
        ],
        "validator": [
            (
                "pseudo_agent",
                "supervised",
                "upgrade",
                PostureChangeTrigger.SCHEDULED,
                90,
                "Initial activation in supervised mode",
            ),
        ],
    }

    for agent_id, changes in histories.items():
        for from_p, to_p, direction, trigger, days_ago, reason in changes:
            record = PostureChangeRecord(
                agent_id=agent_id,
                from_posture=from_p,
                to_posture=to_p,
                direction=direction,
                trigger=trigger,
                changed_by=(
                    "governance-lead" if trigger != PostureChangeTrigger.TRUST_SCORE else "system"
                ),
                changed_at=now - timedelta(days=days_ago),
                reason=reason,
            )
            posture_store.record_change(record)


def seed_cost_tracking(cost_tracker: CostTracker) -> None:
    """Generate realistic API cost records over the last 30 days."""
    # Skip if records already exist (idempotent) — check via report
    report = cost_tracker.spend_report(days=30)
    if report.total_calls > 0:
        return

    now = datetime.now(UTC)

    # Set team monthly budgets
    team_budgets = {
        "dm-team": Decimal("3000"),
        "governance-team": Decimal("5000"),
        "community-team": Decimal("2000"),
        "standards-team": Decimal("8000"),
    }
    for team_id, budget in team_budgets.items():
        cost_tracker.set_team_monthly_budget(team_id, budget)

    # Set per-agent daily budgets
    agent_daily_budgets = {
        "dm-team-lead": Decimal("80"),
        "dm-content-creator": Decimal("50"),
        "dm-analytics": Decimal("60"),
        "dm-community-manager": Decimal("30"),
        "dm-seo-specialist": Decimal("30"),
        "policy-reviewer": Decimal("80"),
        "compliance-checker": Decimal("40"),
        "audit-monitor": Decimal("20"),
        "outreach-agent": Decimal("60"),
        "engagement-bot": Decimal("30"),
        "support-agent": Decimal("25"),
        "spec-writer": Decimal("150"),
        "reviewer": Decimal("70"),
        "validator": Decimal("50"),
    }
    for agent_id, budget in agent_daily_budgets.items():
        cost_tracker.set_daily_budget(agent_id, budget)

    # Generate cost records for each agent over 30 days
    for agent_def in AGENTS:
        agent_id = agent_def["agent_id"]
        team_id = agent_def["team_id"]

        # Higher-posture agents tend to use more expensive models
        posture = agent_def["posture"]
        if posture in (TrustPostureLevel.CONTINUOUS_INSIGHT, TrustPostureLevel.DELEGATED):
            model_weights = [0.2, 0.6, 0.2]  # more opus
        elif posture == TrustPostureLevel.SHARED_PLANNING:
            model_weights = [0.5, 0.3, 0.2]  # balanced
        else:
            model_weights = [0.6, 0.1, 0.3]  # more haiku/sonnet

        # 3-8 calls per day, spread across 30 days
        calls_per_day = random.randint(3, 8)
        for day_offset in range(30):
            day_calls = random.randint(max(1, calls_per_day - 2), calls_per_day + 2)
            for _ in range(day_calls):
                provider, model, input_rate, output_rate = random.choices(
                    _LLM_MODELS, weights=model_weights, k=1
                )[0]

                input_tokens = random.randint(500, 8000)
                output_tokens = random.randint(200, 4000)
                cost = input_rate * Decimal(str(input_tokens)) / Decimal(
                    "1000"
                ) + output_rate * Decimal(str(output_tokens)) / Decimal("1000")

                timestamp = now - timedelta(
                    days=day_offset,
                    hours=random.randint(6, 22),
                    minutes=random.randint(0, 59),
                )

                record = ApiCostRecord(
                    agent_id=agent_id,
                    team_id=team_id,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost.quantize(Decimal("0.0001")),
                    timestamp=timestamp,
                )
                cost_tracker.record(record)


def seed_verification_stats(audit_records: list[dict]) -> dict[str, int]:
    """Aggregate verification stats from audit records.

    Args:
        audit_records: List of audit record dicts with verification_level keys.

    Returns:
        Dict mapping VerificationLevel string to count.
    """
    stats: dict[str, int] = {
        "AUTO_APPROVED": 0,
        "FLAGGED": 0,
        "HELD": 0,
        "BLOCKED": 0,
    }
    for rec in audit_records:
        level = rec.get("verification_level", "AUTO_APPROVED")
        stats[level] = stats.get(level, 0) + 1
    return stats


def convert_verification_stats_to_enum_keys(
    string_stats: dict[str, int],
) -> dict[VerificationLevel, int]:
    """Convert string-keyed verification stats to VerificationLevel enum keys.

    The seed_verification_stats function returns string keys for simplicity
    during aggregation. This function converts those to VerificationLevel
    enum keys for type-safe consumption by PactAPI.

    Args:
        string_stats: Dict mapping verification level strings to counts.

    Returns:
        Dict mapping VerificationLevel enum values to counts.

    Raises:
        KeyError: If a required verification level key is missing from the input.
    """
    level_map = {
        "AUTO_APPROVED": VerificationLevel.AUTO_APPROVED,
        "FLAGGED": VerificationLevel.FLAGGED,
        "HELD": VerificationLevel.HELD,
        "BLOCKED": VerificationLevel.BLOCKED,
    }
    result: dict[VerificationLevel, int] = {}
    for string_key, enum_key in level_map.items():
        if string_key not in string_stats:
            raise KeyError(
                f"Missing required verification level key '{string_key}' in stats dict. "
                f"Available keys: {sorted(string_stats.keys())}"
            )
        result[enum_key] = string_stats[string_key]
    return result


# ---------------------------------------------------------------------------
# AuditChain construction from seed records
# ---------------------------------------------------------------------------


def build_audit_chain(audit_records: list[dict]) -> AuditChain:
    """Construct an AuditChain from the seed audit records.

    Creates a proper AuditChain with sealed anchors for each audit record,
    preserving timestamps and verification levels. This chain can be passed
    to PactAPI for dashboard_trends() to produce non-zero trend data.

    Args:
        audit_records: List of audit record dicts from seed_audit_anchors().

    Returns:
        An AuditChain populated with sealed anchors from the records.

    Raises:
        ValueError: If audit_records is empty.
    """
    if not audit_records:
        raise ValueError(
            "Cannot build AuditChain from empty audit_records list. "
            "Run seed_audit_anchors() first to generate records."
        )

    chain = AuditChain(chain_id="pact-main")

    # Sort records by timestamp to ensure chronological ordering
    sorted_records = sorted(
        audit_records,
        key=lambda r: r.get("timestamp", ""),
    )

    for record in sorted_records:
        # Parse the ISO timestamp string back to datetime
        timestamp_str = record.get("timestamp", "")
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            logger.warning(
                "build_audit_chain: skipping record with invalid timestamp: %r",
                timestamp_str,
            )
            continue

        # Map string verification level to enum
        level_str = record.get("verification_level", "AUTO_APPROVED")
        try:
            level = VerificationLevel(level_str)
        except ValueError:
            logger.warning(
                "build_audit_chain: skipping record with invalid verification_level: %r",
                level_str,
            )
            continue

        # Build the anchor with proper chaining
        sequence = len(chain.anchors)
        previous_hash = chain.anchors[-1].content_hash if chain.anchors else None

        anchor = AuditAnchor(
            anchor_id=record.get("anchor_id", f"aa-{sequence}"),
            sequence=sequence,
            previous_hash=previous_hash,
            agent_id=record.get("agent_id", "unknown"),
            action=record.get("action", "unknown"),
            verification_level=level,
            result=record.get("result", ""),
            timestamp=timestamp,
            metadata={
                "team_id": record.get("team_id", ""),
                "resource": record.get("resource", ""),
            },
        )
        anchor.seal()
        chain.anchors.append(anchor)

    return chain


# ---------------------------------------------------------------------------
# Shadow enforcer seed data
# ---------------------------------------------------------------------------


def seed_shadow_evaluations() -> ShadowEnforcer:
    """Create a ShadowEnforcer and populate it with realistic evaluation data.

    Generates 20-50 evaluations per agent with a mix of AUTO_APPROVED, FLAGGED,
    HELD, and BLOCKED results to create realistic dashboard metrics.

    Returns:
        A fully populated ShadowEnforcer instance.
    """
    import fnmatch
    from dataclasses import dataclass

    from pact_platform.trust.shadow_enforcer import ShadowEnforcer

    # Seed governance rules: pattern → level
    _RULES: list[tuple[str, str]] = [
        ("emergency_*", "blocked"),
        ("delete_*", "blocked"),
        ("modify_constraints", "blocked"),
        ("publish_*", "held"),
        ("send_*", "held"),
        ("approve_*", "held"),
        ("flag_*", "flagged"),
        ("escalate_*", "flagged"),
    ]

    @dataclass(frozen=True)
    class _SeedVerdict:
        level: str
        reason: str
        role_address: str
        action: str
        audit_details: dict

    class _SeedGovernanceEngine:
        """Minimal mock governance engine for seeding shadow data."""

        def verify_action(
            self, role_address: str, action: str, context: dict | None = None
        ) -> _SeedVerdict:
            for pattern, level in _RULES:
                if fnmatch.fnmatch(action, pattern):
                    return _SeedVerdict(
                        level=level,
                        reason=f"Matched rule: {pattern}",
                        role_address=role_address,
                        action=action,
                        audit_details={},
                    )
            return _SeedVerdict(
                level="auto_approved",
                reason="No matching rule; using default level",
                role_address=role_address,
                action=action,
                audit_details={},
            )

    shadow_enforcer = ShadowEnforcer(
        governance_engine=_SeedGovernanceEngine(),  # type: ignore[arg-type]
        role_address="D1-R1",
    )

    # Synthetic actions with varying verification outcomes
    # These are deliberately chosen to trigger different gradient rules
    _shadow_actions: dict[str, list[str]] = {
        "dm-team-lead": [
            "review_content",
            "approve_publication",  # triggers HELD (approve_*)
            "coordinate_team",
            "schedule_content",
            "analyze_metrics",
            "draft_strategy",
            "flag_quality_issue",  # triggers FLAGGED (flag_*)
        ],
        "dm-content-creator": [
            "draft_post",
            "edit_content",
            "research_topic",
            "suggest_hashtags",
            "publish_draft",  # triggers HELD (publish_*)
            "flag_quality_issue",  # triggers FLAGGED (flag_*)
        ],
        "dm-analytics": [
            "read_metrics",
            "generate_report",
            "track_engagement",
            "analyze_trends",
            "flag_anomaly",  # triggers FLAGGED (flag_*)
        ],
        "dm-community-manager": [
            "draft_response",
            "moderate_content",
            "track_community",
            "flag_issues",  # triggers FLAGGED (flag_*)
            "send_response",  # triggers HELD (send_*)
        ],
        "dm-seo-specialist": [
            "analyze_keywords",
            "suggest_structure",
            "audit_seo",
            "research_topics",
            "flag_seo_issue",  # triggers FLAGGED (flag_*)
        ],
        "policy-reviewer": [
            "review_policy",
            "draft_policy",
            "cross_reference_clauses",
            "assess_compliance",
            "approve_policy",  # triggers HELD (approve_*)
            "flag_violation",  # triggers FLAGGED (flag_*)
        ],
        "compliance-checker": [
            "check_compliance",
            "audit_trail",
            "flag_violation",  # triggers FLAGGED (flag_*)
            "escalate_issue",  # triggers FLAGGED (escalate_*)
            "generate_report",
        ],
        "audit-monitor": [
            "monitor_logs",
            "detect_anomaly",
            "generate_audit_report",
            "flag_suspicious_activity",  # triggers FLAGGED (flag_*)
            "escalate_incident",  # triggers FLAGGED (escalate_*)
        ],
        "outreach-agent": [
            "send_outreach",  # triggers HELD (send_*)
            "manage_contacts",
            "draft_proposal",
            "coordinate_events",
            "send_invitation",  # triggers HELD (send_*)
            "publish_announcement",  # triggers HELD (publish_*)
        ],
        "engagement-bot": [
            "respond_to_query",
            "moderate_discussion",
            "escalate_issue",  # triggers FLAGGED (escalate_*)
            "flag_inappropriate",  # triggers FLAGGED (flag_*)
            "send_welcome",  # triggers HELD (send_*)
        ],
        "support-agent": [
            "handle_ticket",
            "update_docs",
            "triage_issue",
            "send_response",  # triggers HELD (send_*)
            "escalate_ticket",  # triggers FLAGGED (escalate_*)
        ],
        "spec-writer": [
            "draft_spec",
            "update_spec",
            "cross_reference",
            "validate_consistency",
            "publish_draft",  # triggers HELD (publish_*)
            "flag_inconsistency",  # triggers FLAGGED (flag_*)
        ],
        "reviewer": [
            "review_spec",
            "suggest_changes",
            "verify_references",
            "approve_changes",  # triggers HELD (approve_*)
            "flag_issue",  # triggers FLAGGED (flag_*)
        ],
        "validator": [
            "validate_implementation",
            "run_conformance_tests",
            "report_gaps",
            "flag_nonconformance",  # triggers FLAGGED (flag_*)
            "escalate_failure",  # triggers FLAGGED (escalate_*)
        ],
    }

    for agent_def in AGENTS:
        agent_id = agent_def["agent_id"]
        actions = _shadow_actions.get(agent_id, agent_def.get("capabilities", []))
        if not actions:
            continue

        # Each agent gets 20-50 evaluations
        num_evaluations = random.randint(20, 50)
        for _ in range(num_evaluations):
            action = random.choice(actions)
            # Occasionally try a blocked action for variety
            if random.random() < 0.03:
                action = random.choice(
                    ["emergency_shutdown", "delete_all_data", "modify_constraints"]
                )
            shadow_enforcer.evaluate(action, agent_id)

    return shadow_enforcer


# ---------------------------------------------------------------------------
# Reset function
# ---------------------------------------------------------------------------


def reset_all(
    registry: AgentRegistry,
    approval_queue: ApprovalQueue,
    cost_tracker: CostTracker,
    workspace_registry: WorkspaceRegistry,
    bridge_manager: BridgeManager,
    posture_store: PostureHistoryStore,
) -> None:
    """Clear all existing data for a fresh seed.

    Note: In-memory stores are cleared by re-creating them. For the objects
    passed in, we clear their internal state directly.
    """
    # Clear agent registry
    agent_ids = [a.agent_id for a in registry.active_agents()]
    for agent_id in agent_ids:
        try:
            registry.deregister(agent_id)
        except ValueError:
            pass

    # Clear approval queue (expire and consume all pending)
    for pa in list(approval_queue.pending):
        try:
            approval_queue.reject(pa.action_id, "system-reset", reason="Data reset")
        except (ValueError, PermissionError):
            pass

    # Clear cost tracker (replace internal lists)
    cost_tracker._records.clear()
    cost_tracker._alerts.clear()
    cost_tracker._budgets.clear()
    cost_tracker._team_budgets.clear()

    # Clear workspace registry
    workspace_registry.workspaces.clear()

    # Clear bridge manager (access internal dict)
    bridge_manager._bridges.clear()
    bridge_manager._state_machines.clear()

    # PostureHistoryStore: clear records via internal dict
    # Use object.__setattr__ to bypass the append-only guard
    object.__setattr__(posture_store, "_records", {})
    object.__setattr__(posture_store, "_sequence_counter", 0)

    print("  All existing data cleared.")


# ---------------------------------------------------------------------------
# DM Team Runner seed data (Task 5058)
# ---------------------------------------------------------------------------

_DM_SAMPLE_TASKS = [
    {
        "description": "Draft a LinkedIn post about the EATP SDK v0.1 release",
        "target_agent": "dm-content-creator",
    },
    {
        "description": "Draft a blog article about open governance principles",
        "target_agent": "dm-content-creator",
    },
    {
        "description": "Draft a tweet about the Foundation's new constitution",
        "target_agent": "dm-content-creator",
    },
    {"description": "Read engagement metrics for the last 30 days", "target_agent": "dm-analytics"},
    {"description": "Analyze trends in social media engagement", "target_agent": "dm-analytics"},
    {"description": "Generate a weekly performance report", "target_agent": "dm-analytics"},
    {
        "description": "Draft a response to the community question about CARE",
        "target_agent": "dm-community-manager",
    },
    {
        "description": "Moderate the forum discussion on agent trust",
        "target_agent": "dm-community-manager",
    },
    {
        "description": "Analyze keywords for our open governance content",
        "target_agent": "dm-seo-specialist",
    },
    {"description": "Audit SEO for the Foundation website", "target_agent": "dm-seo-specialist"},
    {"description": "Review the content strategy for Q2", "target_agent": "dm-team-lead"},
    {
        "description": "Draft a strategy for the upcoming standards release",
        "target_agent": "dm-team-lead",
    },
]


def seed_dm_runner_tasks():
    """Seed sample DM tasks through the DMTeamRunner.

    Creates a DMTeamRunner, runs shadow calibration, and submits
    sample tasks to demonstrate the full execution pipeline.

    Returns:
        The DMTeamRunner instance with completed tasks and calibration data.
    """
    from pact_platform.examples.foundation.dm_runner import DMTeamRunner

    runner = DMTeamRunner()

    # Run shadow calibration first
    runner.run_shadow_calibration()

    # Submit sample tasks
    results = []
    for task in _DM_SAMPLE_TASKS:
        result = runner.submit_task(
            description=task["description"],
            target_agent=task.get("target_agent"),
        )
        results.append(result)

    return runner, results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> dict[str, Any] | None:
    parser = argparse.ArgumentParser(description="Seed demo data for the PACT dashboard")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear all existing data before seeding",
    )
    args = parser.parse_args()

    print("PACT Demo Seed")
    print("=" * 50)

    # Create platform components
    registry = AgentRegistry()
    approval_queue = ApprovalQueue()
    cost_tracker = CostTracker()
    workspace_registry = WorkspaceRegistry()
    bridge_manager = BridgeManager()
    posture_store = PostureHistoryStore()

    if args.reset:
        print("\nResetting existing data...")
        reset_all(
            registry,
            approval_queue,
            cost_tracker,
            workspace_registry,
            bridge_manager,
            posture_store,
        )

    # Seed agents
    print("\n[1/10] Seeding agents...")
    seed_agents(registry)
    teams = sorted({a.team_id for a in registry.active_agents()})
    total_agents = len(registry.active_agents())
    print(f"  {total_agents} agents across {len(teams)} teams: {', '.join(teams)}")

    # Seed workspaces
    print("\n[2/10] Seeding workspaces...")
    seed_workspaces(workspace_registry)
    ws_count = len(workspace_registry.list_active())
    print(f"  {ws_count} workspaces created and activated")
    for ws in workspace_registry.list_active():
        print(f"    {ws.id}: state={ws.workspace_state.value}, phase={ws.current_phase.value}")

    # Seed constraint envelopes
    print("\n[3/10] Seeding constraint envelopes...")
    envelope_registry = seed_envelopes()
    print(f"  {len(envelope_registry)} constraint envelopes configured")

    # Seed audit anchors, verification stats, and AuditChain
    print("\n[4/10] Seeding audit anchors and building AuditChain...")
    verification_stats_raw, audit_records = seed_audit_anchors()
    verification_stats_str = seed_verification_stats(audit_records)
    verification_stats = convert_verification_stats_to_enum_keys(verification_stats_str)
    audit_chain = build_audit_chain(audit_records)
    print(f"  {len(audit_records)} audit anchors generated (last 30 days)")
    print(f"  AuditChain built with {audit_chain.length} sealed anchors")
    for level, count in verification_stats_str.items():
        print(f"    {level}: {count}")

    # Seed held actions
    print("\n[5/10] Seeding held actions...")
    seed_held_actions(approval_queue)
    print(f"  {approval_queue.queue_depth} actions pending approval")
    for pa in approval_queue.pending:
        print(f"    [{pa.urgency.value.upper()}] {pa.agent_id}: {pa.action} — {pa.reason[:60]}...")

    # Seed bridges
    print("\n[6/10] Seeding cross-functional bridges...")
    seed_bridges(bridge_manager)
    all_bridges = bridge_manager.list_all_bridges()
    print(f"  {len(all_bridges)} bridges created")
    for br in all_bridges:
        print(
            f"    {br.bridge_id}: {br.bridge_type.value} "
            f"{br.source_team_id} -> {br.target_team_id} "
            f"[{br.status.value}] — {br.purpose[:50]}..."
        )

    # Seed posture history
    print("\n[7/10] Seeding posture history...")
    seed_posture_history(posture_store)
    total_records = sum(len(posture_store.get_history(a["agent_id"])) for a in AGENTS)
    print(f"  {total_records} posture change records across {len(AGENTS)} agents")

    # Seed cost tracking
    print("\n[8/10] Seeding cost tracking data...")
    seed_cost_tracking(cost_tracker)
    report = cost_tracker.spend_report(days=30)
    print(f"  {report.total_calls} API cost records over 30 days")
    print(f"  Total spend: ${report.total_cost:.2f}")
    print("  By model:")
    for model, cost in sorted(report.by_model.items(), key=lambda x: x[1], reverse=True):
        print(f"    {model}: ${cost:.2f}")

    # Seed shadow enforcer evaluations
    print("\n[9/10] Seeding shadow enforcer evaluations...")
    shadow_enforcer = seed_shadow_evaluations()
    shadow_agents = 0
    shadow_total = 0
    for agent_def in AGENTS:
        try:
            m = shadow_enforcer.get_metrics(agent_def["agent_id"])
            shadow_agents += 1
            shadow_total += m.total_evaluations
        except KeyError:
            pass
    print(f"  {shadow_total} shadow evaluations across {shadow_agents} agents")

    # Seed DM Team Runner tasks (Task 5058)
    print("\n[10/10] Seeding DM Team Runner tasks...")
    dm_runner, dm_results = seed_dm_runner_tasks()
    dm_completed = sum(1 for r in dm_results if r.error is None)
    dm_held = sum(1 for r in dm_results if r.metadata.get("held"))
    dm_blocked = sum(1 for r in dm_results if r.error and "BLOCKED" in (r.error or ""))
    print(
        f"  {len(dm_results)} DM tasks submitted ({dm_completed} completed, {dm_held} held, {dm_blocked} blocked)"
    )
    dm_stats = dm_runner.get_agent_stats()
    for agent_id, stats in sorted(dm_stats.items()):
        if stats["tasks_submitted"] > 0:
            print(f"    {agent_id}: {stats['tasks_submitted']} tasks")

    # Summary
    print("\n" + "=" * 50)
    print("Seed complete. Summary:")
    print(f"  Teams:              {len(teams)}")
    print(f"  Agents:             {total_agents}")
    print(f"  Workspaces:         {ws_count}")
    print(f"  Envelopes:          {len(envelope_registry)}")
    print(f"  Audit anchors:      {len(audit_records)}")
    print(f"  Held actions:       {approval_queue.queue_depth}")
    print(f"  Bridges:            {len(all_bridges)}")
    print(f"  Posture records:    {total_records}")
    print(f"  Cost records:       {report.total_calls}")
    print(f"  Total API spend:    ${report.total_cost:.2f}")
    print(f"  Shadow evaluations: {shadow_total}")
    print(f"  DM tasks:           {len(dm_results)}")
    print("=" * 50)

    # Return components for programmatic use
    return {
        "registry": registry,
        "approval_queue": approval_queue,
        "cost_tracker": cost_tracker,
        "workspace_registry": workspace_registry,
        "bridge_manager": bridge_manager,
        "posture_store": posture_store,
        "envelope_registry": envelope_registry,
        "verification_stats": verification_stats,
        "audit_records": audit_records,
        "audit_chain": audit_chain,
        "shadow_enforcer": shadow_enforcer,
        "dm_runner": dm_runner,
    }


if __name__ == "__main__":
    main()
