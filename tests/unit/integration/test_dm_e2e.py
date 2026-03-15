# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Task 609: DM Team end-to-end test — content creation to publication.

Implements a simplified version of the 15-step content creation flow
using the existing EATPBridge, DelegationManager, AuditPipeline, and
ApprovalQueue. Validates:

1. Genesis -> delegate to team lead -> delegate to specialist
2. Specialist creates content (auto-approved for internal actions)
3. External publish action is HELD
4. Human approves the held action
5. Audit chain verified for integrity after the full flow
6. Cost tracking records API usage

Flow (simplified from the 15-step scenario in todo 609):
  Step 1:  Establish genesis (Founder authority)
  Step 2:  Delegate to DM Team Lead
  Step 3:  Delegate to Content Creator
  Step 4:  Team Lead reads brief (auto-approved, internal)
  Step 5:  Team Lead delegates research to Content Creator
  Step 6:  Content Creator researches topic (auto-approved, read)
  Step 7:  Content Creator drafts post (auto-approved, draft)
  Step 8:  Analytics Agent reads metrics (auto-approved, read)
  Step 9:  Team Lead reviews and approves internally (flagged, review)
  Step 10: Team Lead submits publish action -> HELD
  Step 11: Founder reviews HELD action
  Step 12: Founder approves
  Step 13: Verify audit chain integrity
  Step 14: Verify cost tracking
  Step 15: Verify no unauthorized external actions
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio

from care_platform.audit.pipeline import AuditPipeline
from care_platform.config.schema import (
    GenesisConfig,
    VerificationLevel,
)
from care_platform.constraint.envelope import ConstraintEnvelope
from care_platform.constraint.gradient import GradientEngine
from care_platform.execution.approval import ApprovalQueue, UrgencyLevel
from care_platform.persistence.cost_tracking import ApiCostRecord, CostTracker
from care_platform.trust.credentials import CredentialManager
from care_platform.trust.delegation import DelegationManager
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.trust.genesis import GenesisManager
from care_platform.trust.revocation import RevocationManager
from care_platform.trust.shadow_enforcer import ShadowEnforcer
from care_platform.verticals.dm_team import (
    DM_CONTENT_CREATOR,
    DM_CONTENT_ENVELOPE,
    DM_LEAD_ENVELOPE,
    DM_TEAM_LEAD,
    DM_ANALYTICS,
    DM_ANALYTICS_ENVELOPE,
    DM_VERIFICATION_GRADIENT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GENESIS_CONFIG = GenesisConfig(
    authority="terrene.foundation",
    authority_name="Terrene Foundation",
    policy_reference="docs/06-operations/constitution/terrene-foundation-constitution.md",
)

_AUTHORITY_AGENT_ID = "authority:terrene.foundation"

# Fixed midday UTC time — within all DM team active hour windows
# (lead: 06:00-22:00, content: 08:00-20:00) to avoid time-of-day CI sensitivity.
_FIXED_TIME = datetime(2026, 3, 14, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# E2E Test
# ---------------------------------------------------------------------------


class TestDmTeamE2E:
    """End-to-end content creation flow: brief to publication."""

    @pytest.fixture
    async def bridge(self):
        """Initialize an EATPBridge for the test."""
        bridge = EATPBridge()
        await bridge.initialize()
        return bridge

    @pytest.fixture
    def gradient_engine(self):
        """Create a GradientEngine with DM team rules."""
        return GradientEngine(config=DM_VERIFICATION_GRADIENT)

    @pytest.fixture
    def audit_pipeline(self):
        """Create an AuditPipeline for the test."""
        return AuditPipeline()

    @pytest.fixture
    def approval_queue(self):
        """Create an ApprovalQueue."""
        return ApprovalQueue()

    @pytest.fixture
    def cost_tracker(self):
        """Create a CostTracker."""
        tracker = CostTracker()
        # Set daily budgets for DM agents
        tracker.set_daily_budget("dm-team-lead", Decimal("5.00"))
        tracker.set_daily_budget("dm-content-creator", Decimal("5.00"))
        tracker.set_daily_budget("dm-analytics", Decimal("5.00"))
        tracker.set_team_monthly_budget("dm-team", Decimal("50.00"))
        return tracker

    async def test_full_content_creation_flow(
        self,
        bridge,
        gradient_engine,
        audit_pipeline,
        approval_queue,
        cost_tracker,
    ):
        """Complete 15-step content creation flow with trust, audit, and approval."""
        genesis_mgr = GenesisManager(bridge)
        delegation_mgr = DelegationManager(bridge)
        lead_envelope = ConstraintEnvelope(config=DM_LEAD_ENVELOPE)
        content_envelope = ConstraintEnvelope(config=DM_CONTENT_ENVELOPE)
        analytics_envelope = ConstraintEnvelope(config=DM_ANALYTICS_ENVELOPE)

        # ---- Step 1: Establish genesis ----
        genesis = await genesis_mgr.create_genesis(_GENESIS_CONFIG)
        assert genesis is not None
        assert genesis.agent_id == _AUTHORITY_AGENT_ID

        # Record genesis in audit
        audit_pipeline.record_action(
            agent_id=_AUTHORITY_AGENT_ID,
            action="establish_genesis",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="SUCCESS",
            reasoning="Root of trust established",
        )

        # ---- Step 2: Delegate to DM Team Lead ----
        lead_delegation = await delegation_mgr.create_delegation(
            delegator_id=_AUTHORITY_AGENT_ID,
            delegate_config=DM_TEAM_LEAD,
            envelope_config=DM_LEAD_ENVELOPE,
        )
        assert lead_delegation is not None

        audit_pipeline.record_action(
            agent_id=_AUTHORITY_AGENT_ID,
            action="delegate_to_lead",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="SUCCESS",
            resource="dm-team-lead",
            reasoning="Delegate authority to DM team lead",
        )

        # ---- Step 3: Delegate to Content Creator ----
        creator_delegation = await delegation_mgr.create_delegation(
            delegator_id="dm-team-lead",
            delegate_config=DM_CONTENT_CREATOR,
            envelope_config=DM_CONTENT_ENVELOPE,
        )
        assert creator_delegation is not None

        audit_pipeline.record_action(
            agent_id="dm-team-lead",
            action="delegate_to_creator",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="SUCCESS",
            resource="dm-content-creator",
        )

        # Also delegate to Analytics
        analytics_delegation = await delegation_mgr.create_delegation(
            delegator_id="dm-team-lead",
            delegate_config=DM_ANALYTICS,
            envelope_config=DM_ANALYTICS_ENVELOPE,
        )
        assert analytics_delegation is not None

        # ---- Step 4: Team Lead reads brief (auto-approved, analyze_metrics) ----
        eval_read = lead_envelope.evaluate_action(
            "analyze_metrics", "dm-team-lead", current_time=_FIXED_TIME
        )
        grad_read = gradient_engine.classify(
            "analyze_metrics", "dm-team-lead", envelope_evaluation=eval_read
        )
        assert (
            grad_read.is_auto_approved
        ), f"Team Lead analyze_metrics should be auto-approved, got {grad_read.level}"

        audit_pipeline.record_action(
            agent_id="dm-team-lead",
            action="analyze_metrics",
            verification_level=grad_read.level,
            result="SUCCESS",
            resource="workspaces/media/briefs/eatp-sdk-release.md",
        )

        # Record cost for the LLM call
        cost_tracker.record(
            ApiCostRecord(
                agent_id="dm-team-lead",
                team_id="dm-team",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                input_tokens=500,
                output_tokens=200,
                cost_usd=Decimal("0.01"),
            )
        )

        # ---- Step 5: Team Lead creates editorial plan (flagged, coordinate_team) ----
        eval_plan = lead_envelope.evaluate_action(
            "coordinate_team", "dm-team-lead", current_time=_FIXED_TIME
        )
        grad_plan = gradient_engine.classify(
            "coordinate_team", "dm-team-lead", envelope_evaluation=eval_plan
        )
        # coordinate_team does not match any gradient pattern -> default FLAGGED
        assert grad_plan.level == VerificationLevel.FLAGGED

        audit_pipeline.record_action(
            agent_id="dm-team-lead",
            action="coordinate_team",
            verification_level=grad_plan.level,
            result="SUCCESS",
            reasoning="Editorial plan created",
        )

        # ---- Step 6: Content Creator researches topic (auto-approved, research_topic) ----
        # research_topic matches no gradient pattern -> FLAGGED (it's not read_*/draft_*/analyze_*)
        # But that's the correct behavior: the gradient default is FLAGGED
        eval_research = content_envelope.evaluate_action(
            "research_topic", "dm-content-creator", current_time=_FIXED_TIME
        )
        grad_research = gradient_engine.classify(
            "research_topic", "dm-content-creator", envelope_evaluation=eval_research
        )

        audit_pipeline.record_action(
            agent_id="dm-content-creator",
            action="research_topic",
            verification_level=grad_research.level,
            result="SUCCESS",
        )

        cost_tracker.record(
            ApiCostRecord(
                agent_id="dm-content-creator",
                team_id="dm-team",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=Decimal("0.02"),
            )
        )

        # ---- Step 7: Content Creator drafts post (auto-approved) ----
        eval_draft = content_envelope.evaluate_action(
            "draft_post", "dm-content-creator", current_time=_FIXED_TIME
        )
        grad_draft = gradient_engine.classify(
            "draft_post", "dm-content-creator", envelope_evaluation=eval_draft
        )
        assert (
            grad_draft.is_auto_approved
        ), f"draft_post should be auto-approved, got {grad_draft.level}"

        audit_pipeline.record_action(
            agent_id="dm-content-creator",
            action="draft_post",
            verification_level=grad_draft.level,
            result="SUCCESS",
            resource="workspaces/dm/content/drafts/eatp-sdk-linkedin.md",
        )

        cost_tracker.record(
            ApiCostRecord(
                agent_id="dm-content-creator",
                team_id="dm-team",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                input_tokens=2000,
                output_tokens=800,
                cost_usd=Decimal("0.04"),
            )
        )

        # ---- Step 8: Analytics Agent reads engagement metrics (auto-approved) ----
        eval_analytics = analytics_envelope.evaluate_action(
            "read_metrics", "dm-analytics", current_time=_FIXED_TIME
        )
        grad_analytics = gradient_engine.classify(
            "read_metrics", "dm-analytics", envelope_evaluation=eval_analytics
        )
        assert grad_analytics.is_auto_approved

        audit_pipeline.record_action(
            agent_id="dm-analytics",
            action="read_metrics",
            verification_level=grad_analytics.level,
            result="SUCCESS",
        )

        # ---- Step 9: Team Lead reviews draft internally (flagged, review_content) ----
        eval_review = lead_envelope.evaluate_action(
            "review_content", "dm-team-lead", current_time=_FIXED_TIME
        )
        grad_review = gradient_engine.classify(
            "review_content", "dm-team-lead", envelope_evaluation=eval_review
        )
        # review_content matches no gradient pattern -> FLAGGED (default)

        audit_pipeline.record_action(
            agent_id="dm-team-lead",
            action="review_content",
            verification_level=grad_review.level,
            result="SUCCESS",
            reasoning="Team lead approved content internally",
        )

        # ---- Step 10: Team Lead submits publish action -> HELD ----
        eval_approve = lead_envelope.evaluate_action(
            "approve_publication", "dm-team-lead", current_time=_FIXED_TIME
        )
        grad_approve = gradient_engine.classify(
            "approve_publication", "dm-team-lead", envelope_evaluation=eval_approve
        )
        assert (
            grad_approve.level == VerificationLevel.HELD
        ), f"approve_publication should be HELD, got {grad_approve.level}"

        # Submit to approval queue
        pending_action = approval_queue.submit(
            agent_id="dm-team-lead",
            action="approve_publication",
            reason="External publication always requires human approval",
            team_id="dm-team",
            resource="workspaces/dm/content/drafts/eatp-sdk-linkedin.md",
            urgency=UrgencyLevel.STANDARD,
        )

        audit_pipeline.record_action(
            agent_id="dm-team-lead",
            action="approve_publication",
            verification_level=VerificationLevel.HELD,
            result="HELD",
            resource="workspaces/dm/content/drafts/eatp-sdk-linkedin.md",
            reasoning="Queued for human approval",
        )

        # ---- Step 11: Verify action is pending ----
        assert approval_queue.queue_depth == 1
        assert pending_action.status == "pending"
        assert pending_action.agent_id == "dm-team-lead"

        # ---- Step 12: Founder approves ----
        approved = approval_queue.approve(
            pending_action.action_id,
            approver_id="founder",
            reason="Content reviewed and approved for publication",
        )
        assert approved.status == "approved"
        assert approved.decided_by == "founder"

        audit_pipeline.record_action(
            agent_id="founder",
            action="approve_held_action",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="SUCCESS",
            resource=pending_action.action_id,
            reasoning="Founder approved publication",
        )

        # ---- Step 13: Verify audit chain integrity ----
        # Verify each agent's chain
        for agent_id in [
            _AUTHORITY_AGENT_ID,
            "dm-team-lead",
            "dm-content-creator",
            "dm-analytics",
            "founder",
        ]:
            is_valid, errors = audit_pipeline.verify_agent_integrity(agent_id)
            assert is_valid, f"Audit chain for '{agent_id}' failed integrity check: {errors}"

        # Verify the team timeline has all the expected actions
        team_timeline = audit_pipeline.get_team_timeline(
            [
                _AUTHORITY_AGENT_ID,
                "dm-team-lead",
                "dm-content-creator",
                "dm-analytics",
                "founder",
            ]
        )
        # We recorded actions for multiple agents
        assert (
            len(team_timeline) >= 10
        ), f"Expected at least 10 audit anchors, got {len(team_timeline)}"

        # ---- Step 14: Verify cost tracking ----
        report = cost_tracker.spend_report(team_id="dm-team", days=1)
        assert report.total_cost > Decimal("0"), "No costs recorded"
        assert (
            report.total_calls >= 3
        ), f"Expected at least 3 API calls recorded, got {report.total_calls}"

        # Verify per-agent costs
        assert "dm-team-lead" in report.by_agent
        assert "dm-content-creator" in report.by_agent

        # ---- Step 15: Verify no unauthorized external actions ----
        # Check that no AUTO_APPROVED action was an external action
        all_records = audit_pipeline.export_for_review()
        for record in all_records:
            if record["verification_level"] == VerificationLevel.AUTO_APPROVED.value:
                action = record["action"]
                # External/publish actions must never be auto-approved
                assert not action.startswith(
                    "publish_"
                ), f"External action '{action}' was auto-approved -- policy violation"
                assert not action.startswith(
                    "external_"
                ), f"External action '{action}' was auto-approved -- policy violation"

        # Check that the HELD action was properly approved before proceeding
        assert approval_queue.queue_depth == 0, "Queue should be empty after approval"

    async def test_delegation_chain_depth_correct(self, bridge):
        """Delegation depth: genesis=0, lead=1, creator=2."""
        genesis_mgr = GenesisManager(bridge)
        delegation_mgr = DelegationManager(bridge)

        await genesis_mgr.create_genesis(_GENESIS_CONFIG)

        await delegation_mgr.create_delegation(
            delegator_id=_AUTHORITY_AGENT_ID,
            delegate_config=DM_TEAM_LEAD,
            envelope_config=DM_LEAD_ENVELOPE,
        )

        await delegation_mgr.create_delegation(
            delegator_id="dm-team-lead",
            delegate_config=DM_CONTENT_CREATOR,
            envelope_config=DM_CONTENT_ENVELOPE,
        )

        # Check delegation depths
        depth_authority = await delegation_mgr.get_delegation_depth(_AUTHORITY_AGENT_ID)
        depth_lead = await delegation_mgr.get_delegation_depth("dm-team-lead")
        depth_creator = await delegation_mgr.get_delegation_depth("dm-content-creator")

        assert depth_authority == 0, f"Authority depth should be 0, got {depth_authority}"
        assert depth_lead == 1, f"Lead depth should be 1, got {depth_lead}"
        assert depth_creator == 2, f"Creator depth should be 2, got {depth_creator}"

    async def test_held_action_blocks_until_approved(self, bridge, approval_queue):
        """HELD actions do not proceed until a human explicitly approves."""
        pending = approval_queue.submit(
            agent_id="dm-team-lead",
            action="approve_publication",
            reason="External publication requires approval",
            team_id="dm-team",
        )

        # Queue has one pending item
        assert approval_queue.queue_depth == 1
        assert pending.status == "pending"

        # Approve it
        approved = approval_queue.approve(pending.action_id, "founder")
        assert approved.status == "approved"
        assert approval_queue.queue_depth == 0

    async def test_audit_chain_records_held_approval(self, bridge, audit_pipeline, approval_queue):
        """The audit trail records both the HELD action and its approval."""
        # Record HELD action
        audit_pipeline.record_action(
            agent_id="dm-team-lead",
            action="approve_publication",
            verification_level=VerificationLevel.HELD,
            result="HELD",
        )

        # Submit and approve
        pending = approval_queue.submit(
            agent_id="dm-team-lead",
            action="approve_publication",
            reason="External publication",
            team_id="dm-team",
        )
        approval_queue.approve(pending.action_id, "founder")

        # Record approval
        audit_pipeline.record_action(
            agent_id="founder",
            action="approve_held_action",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="SUCCESS",
            resource=pending.action_id,
        )

        # Verify both are in the timeline
        timeline = audit_pipeline.get_team_timeline(["dm-team-lead", "founder"])
        assert len(timeline) == 2
        assert timeline[0].action == "approve_publication"
        assert timeline[0].verification_level == VerificationLevel.HELD
        assert timeline[1].action == "approve_held_action"
        assert timeline[1].verification_level == VerificationLevel.AUTO_APPROVED

    async def test_cost_tracking_within_budget(self, bridge, cost_tracker):
        """All LLM calls are within the configured budget."""
        # Record several API calls
        for i in range(5):
            cost_tracker.record(
                ApiCostRecord(
                    agent_id="dm-content-creator",
                    team_id="dm-team",
                    provider="anthropic",
                    model="claude-sonnet-4-20250514",
                    input_tokens=1000,
                    output_tokens=500,
                    cost_usd=Decimal("0.02"),
                )
            )

        # Check budget
        can_spend, reason = cost_tracker.can_spend("dm-content-creator", Decimal("0.02"))
        assert can_spend, f"Should be within budget: {reason}"

        # Total should be $0.10
        report = cost_tracker.spend_report(agent_id="dm-content-creator", days=1)
        assert report.total_cost == Decimal("0.10")
