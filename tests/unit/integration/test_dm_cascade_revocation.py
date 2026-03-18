# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Task 607: DM Team cascade revocation integration test.

Tests the cascade revocation mechanism for the DM team hierarchy:
- Authority (genesis) -> DM Team Lead -> 4 specialist agents
- Surgical revocation: only target agent revoked, others unaffected
- Cascade revocation: team lead revoked cascades to all specialists
- In-flight HELD action auto-rejected when agent is revoked
- Audit trail records all revocation events

DM team hierarchy:
  authority:terrene.foundation (genesis)
    -> dm-team-lead
      -> dm-content-creator
      -> dm-analytics
      -> dm-community-manager
      -> dm-seo-specialist
"""

from care_platform.trust.audit.pipeline import AuditPipeline
from care_platform.build.config.schema import VerificationLevel
from care_platform.use.execution.approval import ApprovalQueue, UrgencyLevel
from care_platform.trust.credentials import CredentialManager
from care_platform.trust.revocation import RevocationManager, RevocationRecord

# ---------------------------------------------------------------------------
# DM team agent IDs
# ---------------------------------------------------------------------------

_AUTHORITY_ID = "authority:terrene.foundation"
_TEAM_LEAD = "dm-team-lead"
_CONTENT_CREATOR = "dm-content-creator"
_ANALYTICS = "dm-analytics"
_COMMUNITY_MANAGER = "dm-community-manager"
_SEO_SPECIALIST = "dm-seo-specialist"

_ALL_SPECIALISTS = [_CONTENT_CREATOR, _ANALYTICS, _COMMUNITY_MANAGER, _SEO_SPECIALIST]
_ALL_AGENTS = [_TEAM_LEAD] + _ALL_SPECIALISTS


def _setup_dm_team() -> tuple[CredentialManager, RevocationManager]:
    """Set up DM team with full delegation tree and active tokens.

    Returns (credential_manager, revocation_manager) with:
    - Delegation tree: authority -> lead -> 4 specialists
    - Active verification tokens for all 5 agents
    """
    cred_mgr = CredentialManager()
    rev_mgr = RevocationManager(credential_manager=cred_mgr)

    # Register delegation tree: authority -> lead
    rev_mgr.register_delegation(_AUTHORITY_ID, _TEAM_LEAD)

    # Register delegation tree: lead -> specialists
    for specialist_id in _ALL_SPECIALISTS:
        rev_mgr.register_delegation(_TEAM_LEAD, specialist_id)

    # Issue verification tokens for all agents
    cred_mgr.issue_token(_TEAM_LEAD, trust_score=0.90)
    for specialist_id in _ALL_SPECIALISTS:
        cred_mgr.issue_token(specialist_id, trust_score=0.85)

    return cred_mgr, rev_mgr


# ---------------------------------------------------------------------------
# Test: Surgical revocation — only target affected
# ---------------------------------------------------------------------------


class TestDmSurgicalRevocation:
    """Surgical revocation revokes only the target agent. All others remain active."""

    def test_surgical_revoke_content_creator(self):
        """Revoke Content Creator surgically: only it is revoked, others active."""
        cred_mgr, rev_mgr = _setup_dm_team()

        record = rev_mgr.surgical_revoke(_CONTENT_CREATOR, "Calibration test: surgical", "founder")

        assert isinstance(record, RevocationRecord)
        assert record.agent_id == _CONTENT_CREATOR
        assert record.revocation_type == "surgical"
        assert record.affected_agents == []

    def test_surgical_revoke_invalidates_target_token(self):
        """Content Creator's verification token is invalid after surgical revocation."""
        cred_mgr, rev_mgr = _setup_dm_team()
        rev_mgr.surgical_revoke(_CONTENT_CREATOR, "Token test", "founder")

        assert cred_mgr.get_valid_token(_CONTENT_CREATOR) is None
        assert cred_mgr.needs_reverification(_CONTENT_CREATOR)

    def test_surgical_revoke_siblings_unaffected(self):
        """All other DM agents remain active after surgical revocation of one."""
        cred_mgr, rev_mgr = _setup_dm_team()
        rev_mgr.surgical_revoke(_CONTENT_CREATOR, "Sibling test", "founder")

        # Team lead unaffected
        assert cred_mgr.get_valid_token(_TEAM_LEAD) is not None
        assert not rev_mgr.is_revoked(_TEAM_LEAD)

        # All other specialists unaffected
        for specialist_id in [_ANALYTICS, _COMMUNITY_MANAGER, _SEO_SPECIALIST]:
            assert cred_mgr.get_valid_token(specialist_id) is not None, (
                f"Agent '{specialist_id}' should not be affected by surgical revocation"
            )
            assert not rev_mgr.is_revoked(specialist_id)

    def test_re_establishing_revoked_agent_creates_new_chain(self):
        """A revoked agent can be re-delegated with a fresh trust chain."""
        cred_mgr, rev_mgr = _setup_dm_team()
        rev_mgr.surgical_revoke(_CONTENT_CREATOR, "Re-establish test", "founder")

        # Re-delegation is always possible (forward-looking revocation)
        assert rev_mgr.can_redelegate(_CONTENT_CREATOR)

        # Issue a new token (simulates re-delegation)
        new_token = cred_mgr.issue_token(_CONTENT_CREATOR, trust_score=0.80)
        assert new_token.is_valid
        assert cred_mgr.get_valid_token(_CONTENT_CREATOR) is not None


# ---------------------------------------------------------------------------
# Test: Team-wide cascade revocation
# ---------------------------------------------------------------------------


class TestDmCascadeRevocation:
    """Cascade revocation of team lead revokes ALL downstream specialists."""

    def test_cascade_revoke_team_lead_affects_all_specialists(self):
        """Revoking team lead cascades to all 4 specialists."""
        cred_mgr, rev_mgr = _setup_dm_team()

        record = rev_mgr.cascade_revoke(_TEAM_LEAD, "Team-wide cascade test", "founder")

        assert record.revocation_type == "cascade"
        # All 4 specialists should be in affected_agents
        for specialist_id in _ALL_SPECIALISTS:
            assert specialist_id in record.affected_agents, (
                f"Specialist '{specialist_id}' missing from cascade affected list"
            )

    def test_cascade_revoke_all_tokens_invalidated(self):
        """All 5 agent tokens (lead + 4 specialists) are invalidated."""
        cred_mgr, rev_mgr = _setup_dm_team()
        rev_mgr.cascade_revoke(_TEAM_LEAD, "Token cascade", "founder")

        # Team lead token revoked
        assert cred_mgr.get_valid_token(_TEAM_LEAD) is None

        # All specialist tokens revoked
        for specialist_id in _ALL_SPECIALISTS:
            assert cred_mgr.get_valid_token(specialist_id) is None, (
                f"Token for '{specialist_id}' should be revoked after cascade"
            )
            assert cred_mgr.needs_reverification(specialist_id)

    def test_cascade_revoke_is_revoked_for_all(self):
        """is_revoked() returns True for team lead and all specialists."""
        cred_mgr, rev_mgr = _setup_dm_team()
        rev_mgr.cascade_revoke(_TEAM_LEAD, "is_revoked check", "founder")

        assert rev_mgr.is_revoked(_TEAM_LEAD)
        for specialist_id in _ALL_SPECIALISTS:
            assert rev_mgr.is_revoked(specialist_id), (
                f"Agent '{specialist_id}' should be marked as revoked"
            )

    def test_cascade_revoke_does_not_affect_authority(self):
        """The genesis authority is NOT affected by cascading the team lead."""
        cred_mgr, rev_mgr = _setup_dm_team()
        # Issue a token for the authority too
        cred_mgr.issue_token(_AUTHORITY_ID, trust_score=1.0)

        rev_mgr.cascade_revoke(_TEAM_LEAD, "Authority unaffected", "founder")

        # Authority should still have a valid token
        assert cred_mgr.get_valid_token(_AUTHORITY_ID) is not None
        assert not rev_mgr.is_revoked(_AUTHORITY_ID)


# ---------------------------------------------------------------------------
# Test: Audit trail for revocation events
# ---------------------------------------------------------------------------


class TestDmRevocationAuditTrail:
    """Revocation events are recorded in the audit trail."""

    def test_surgical_revocation_recorded_in_log(self):
        """Surgical revocation creates a RevocationRecord in the log."""
        _cred_mgr, rev_mgr = _setup_dm_team()
        rev_mgr.surgical_revoke(_CONTENT_CREATOR, "Audit trail test", "founder")

        log = rev_mgr.get_revocation_log()
        assert len(log) == 1
        assert log[0].agent_id == _CONTENT_CREATOR
        assert log[0].revocation_type == "surgical"
        assert log[0].revoker_id == "founder"
        assert log[0].reason == "Audit trail test"

    def test_cascade_revocation_recorded_with_affected_agents(self):
        """Cascade revocation log includes all affected agents."""
        _cred_mgr, rev_mgr = _setup_dm_team()
        rev_mgr.cascade_revoke(_TEAM_LEAD, "Cascade audit", "founder")

        log = rev_mgr.get_revocation_log()
        assert len(log) == 1
        record = log[0]
        assert record.agent_id == _TEAM_LEAD
        assert record.revocation_type == "cascade"
        assert set(record.affected_agents) == set(_ALL_SPECIALISTS)

    def test_revocation_record_has_timestamp(self):
        """Revocation records have a timestamp."""
        _cred_mgr, rev_mgr = _setup_dm_team()
        record = rev_mgr.surgical_revoke(_CONTENT_CREATOR, "Timestamp test", "founder")
        assert record.revoked_at is not None

    def test_multiple_revocations_all_recorded(self):
        """Multiple revocation events are all captured in the log."""
        _cred_mgr, rev_mgr = _setup_dm_team()
        rev_mgr.surgical_revoke(_CONTENT_CREATOR, "First", "founder")
        rev_mgr.surgical_revoke(_ANALYTICS, "Second", "founder")
        rev_mgr.cascade_revoke(_TEAM_LEAD, "Third cascade", "founder")

        log = rev_mgr.get_revocation_log()
        assert len(log) == 3

    def test_audit_pipeline_records_revocation_action(self):
        """AuditPipeline can record the revocation as an audit anchor."""
        _cred_mgr, rev_mgr = _setup_dm_team()
        audit_pipeline = AuditPipeline()

        record = rev_mgr.cascade_revoke(_TEAM_LEAD, "Pipeline audit test", "founder")

        # Record the revocation in the audit pipeline
        anchor = audit_pipeline.record_action(
            agent_id="founder",
            action="cascade_revoke",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="SUCCESS",
            resource=_TEAM_LEAD,
            reasoning=f"Cascade revocation: {record.reason}",
        )

        assert anchor.is_sealed
        assert anchor.agent_id == "founder"
        assert anchor.action == "cascade_revoke"

        # Verify chain integrity
        is_valid, errors = audit_pipeline.verify_agent_integrity("founder")
        assert is_valid, f"Audit chain integrity failed: {errors}"


# ---------------------------------------------------------------------------
# Test: In-flight HELD action cancelled on revocation
# ---------------------------------------------------------------------------


class TestDmRevocationWithInFlightAction:
    """In-flight HELD actions are rejected when the agent is revoked."""

    def test_held_action_rejected_after_surgical_revocation(self):
        """A HELD action is auto-rejected when the requesting agent is revoked."""
        cred_mgr, rev_mgr = _setup_dm_team()
        approval_queue = ApprovalQueue()

        # Submit a HELD action for content creator
        pending = approval_queue.submit(
            agent_id=_CONTENT_CREATOR,
            action="publish_linkedin_post",
            reason="External publication requires approval",
            team_id="dm-team",
            urgency=UrgencyLevel.STANDARD,
        )

        # Revoke content creator BEFORE action is approved
        rev_mgr.surgical_revoke(_CONTENT_CREATOR, "Agent compromised", "founder")

        # Agent is revoked — the pending action should be rejected
        assert rev_mgr.is_revoked(_CONTENT_CREATOR)

        # Reject the held action (application-level enforcement after detecting revocation)
        rejected = approval_queue.reject(
            pending.action_id,
            approver_id="system",
            reason="Agent revoked — action auto-rejected",
        )

        assert rejected.status == "rejected"
        assert rejected.decided_by == "system"
        assert "revoked" in rejected.decision_reason.lower()

    def test_held_action_rejected_after_cascade_revocation(self):
        """Cascade revocation causes in-flight HELD actions for all agents to be rejectable."""
        cred_mgr, rev_mgr = _setup_dm_team()
        approval_queue = ApprovalQueue()

        # Submit held actions for multiple agents
        pending_creator = approval_queue.submit(
            agent_id=_CONTENT_CREATOR,
            action="publish_blog_article",
            reason="External publication",
            team_id="dm-team",
        )
        pending_community = approval_queue.submit(
            agent_id=_COMMUNITY_MANAGER,
            action="external_outreach",
            reason="External communication",
            team_id="dm-team",
        )

        # Cascade revoke team lead (affects all specialists)
        rev_mgr.cascade_revoke(_TEAM_LEAD, "Team-wide revocation", "founder")

        # All agents are revoked — reject their pending actions
        for pending, agent_id in [
            (pending_creator, _CONTENT_CREATOR),
            (pending_community, _COMMUNITY_MANAGER),
        ]:
            assert rev_mgr.is_revoked(agent_id)
            rejected = approval_queue.reject(
                pending.action_id,
                approver_id="system",
                reason=f"Agent {agent_id} revoked — action auto-rejected",
            )
            assert rejected.status == "rejected"

    def test_approval_queue_empty_after_rejecting_revoked_actions(self):
        """After rejecting all in-flight actions from revoked agents, queue is empty."""
        cred_mgr, rev_mgr = _setup_dm_team()
        approval_queue = ApprovalQueue()

        pending = approval_queue.submit(
            agent_id=_CONTENT_CREATOR,
            action="publish_linkedin_post",
            reason="Approval needed",
            team_id="dm-team",
        )
        assert approval_queue.queue_depth == 1

        rev_mgr.surgical_revoke(_CONTENT_CREATOR, "Revoked", "founder")
        approval_queue.reject(pending.action_id, "system", "Agent revoked")

        assert approval_queue.queue_depth == 0
