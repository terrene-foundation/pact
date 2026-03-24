# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for verification gradient middleware.

The middleware intercepts every agent action, evaluates it through the constraint
envelope and gradient engine, then routes it appropriately:
- AUTO_APPROVED: execute and log
- FLAGGED: execute but mark for review
- HELD: queue for human approval
- BLOCKED: reject with explanation
"""

import pytest

from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from pact_platform.trust.audit.anchor import AuditChain
from pact_platform.trust.constraint.envelope import ConstraintEnvelope
from pact_platform.trust.constraint.gradient import GradientEngine
from pact_platform.trust.constraint.middleware import (
    ActionOutcome,
    VerificationMiddleware,
)

# --- Fixtures ---


def _make_envelope(**kwargs) -> ConstraintEnvelope:
    """Create a ConstraintEnvelope with sensible defaults for testing."""
    config = ConstraintEnvelopeConfig(
        id="test-envelope",
        financial=kwargs.get("financial", FinancialConstraintConfig(max_spend_usd=1000.0)),
        operational=kwargs.get("operational", OperationalConstraintConfig()),
        communication=kwargs.get(
            "communication", CommunicationConstraintConfig(internal_only=False)
        ),
        **{
            k: v
            for k, v in kwargs.items()
            if k not in ("financial", "operational", "communication")
        },
    )
    return ConstraintEnvelope(config=config)


def _make_engine(*rules, default=VerificationLevel.HELD) -> GradientEngine:
    """Create a GradientEngine with the given rules."""
    config = VerificationGradientConfig(rules=list(rules), default_level=default)
    return GradientEngine(config)


def _make_middleware(
    rules: list[GradientRuleConfig] | None = None,
    default_level: VerificationLevel = VerificationLevel.HELD,
    envelope_kwargs: dict | None = None,
    audit_chain: AuditChain | None = None,
) -> VerificationMiddleware:
    """Create a fully wired VerificationMiddleware for testing."""
    engine = _make_engine(*(rules or []), default=default_level)
    envelope = _make_envelope(**(envelope_kwargs or {}))
    return VerificationMiddleware(
        gradient_engine=engine,
        envelope=envelope,
        audit_chain=audit_chain,
    )


# --- Test Classes ---


class TestAutoApprovedActions:
    """Actions classified AUTO_APPROVED should execute and record audit."""

    def test_auto_approved_action_executes(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read actions are safe",
                ),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="read_metrics")

        assert result.verification_level == VerificationLevel.AUTO_APPROVED
        assert result.outcome == ActionOutcome.EXECUTED
        assert result.approval_request is None

    def test_auto_approved_action_records_audit(self):
        chain = AuditChain(chain_id="test-chain")
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
            ],
            audit_chain=chain,
        )
        result = mw.process_action(agent_id="agent-1", action="read_data")

        assert result.audit_recorded is True
        assert chain.length == 1
        anchor = chain.latest
        assert anchor is not None
        assert anchor.agent_id == "agent-1"
        assert anchor.action == "read_data"
        assert anchor.verification_level == VerificationLevel.AUTO_APPROVED


class TestFlaggedActions:
    """Actions classified FLAGGED should execute but be marked for review."""

    def test_flagged_action_executes(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="draft_*",
                    level=VerificationLevel.FLAGGED,
                    reason="Near content boundary",
                ),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="draft_post")

        assert result.verification_level == VerificationLevel.FLAGGED
        assert result.outcome == ActionOutcome.EXECUTED
        assert result.approval_request is None

    def test_flagged_action_appears_in_flagged_list(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="draft_*", level=VerificationLevel.FLAGGED),
            ],
        )
        mw.process_action(agent_id="agent-1", action="draft_post")

        flagged = mw.get_flagged_actions()
        assert len(flagged) == 1
        assert flagged[0].action == "draft_post"
        assert flagged[0].verification_level == VerificationLevel.FLAGGED

    def test_flagged_action_records_audit(self):
        chain = AuditChain(chain_id="test-chain")
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="draft_*", level=VerificationLevel.FLAGGED),
            ],
            audit_chain=chain,
        )
        mw.process_action(agent_id="agent-1", action="draft_post")

        assert chain.length == 1
        assert chain.latest.verification_level == VerificationLevel.FLAGGED


class TestHeldActions:
    """Actions classified HELD should be queued for human approval, not executed."""

    def test_held_action_is_queued(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="send_*",
                    level=VerificationLevel.HELD,
                    reason="External send requires approval",
                ),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="send_email")

        assert result.verification_level == VerificationLevel.HELD
        assert result.outcome == ActionOutcome.QUEUED
        assert result.approval_request is not None
        assert result.approval_request.status == "pending"
        assert result.approval_request.agent_id == "agent-1"
        assert result.approval_request.action == "send_email"

    def test_held_action_in_pending_approvals(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
        )
        mw.process_action(agent_id="agent-1", action="send_email")

        pending = mw.pending_approvals
        assert len(pending) == 1
        assert pending[0].action == "send_email"
        assert pending[0].status == "pending"

    def test_held_action_records_audit(self):
        chain = AuditChain(chain_id="test-chain")
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
            audit_chain=chain,
        )
        mw.process_action(agent_id="agent-1", action="send_email")

        assert chain.length == 1
        assert chain.latest.verification_level == VerificationLevel.HELD
        assert chain.latest.result == "queued"


class TestBlockedActions:
    """Actions classified BLOCKED should be rejected with explanation."""

    def test_blocked_action_is_rejected(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="delete_*",
                    level=VerificationLevel.BLOCKED,
                    reason="Destructive action forbidden",
                ),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="delete_database")

        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED
        assert result.approval_request is None
        assert result.details != ""  # must provide an explanation

    def test_blocked_action_records_audit(self):
        chain = AuditChain(chain_id="test-chain")
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="delete_*", level=VerificationLevel.BLOCKED),
            ],
            audit_chain=chain,
        )
        mw.process_action(agent_id="agent-1", action="delete_database")

        assert chain.length == 1
        assert chain.latest.verification_level == VerificationLevel.BLOCKED
        assert chain.latest.result == "rejected"

    def test_blocked_action_not_queued(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="delete_*", level=VerificationLevel.BLOCKED),
            ],
        )
        mw.process_action(agent_id="agent-1", action="delete_database")

        assert len(mw.pending_approvals) == 0


class TestApprovalWorkflow:
    """Approve and reject held actions."""

    def test_approve_held_action(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
        )
        held_result = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held_result.approval_request.request_id

        approval_result = mw.approve_request(request_id=request_id, approver_id="human-reviewer")

        assert approval_result.outcome == ActionOutcome.EXECUTED
        assert approval_result.verification_level == VerificationLevel.HELD
        assert approval_result.audit_recorded is True

    def test_approve_updates_request_status(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
        )
        held_result = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held_result.approval_request.request_id

        mw.approve_request(request_id=request_id, approver_id="human-reviewer")

        # No longer in pending approvals
        assert len(mw.pending_approvals) == 0

        # The request itself is updated
        request = held_result.approval_request
        assert request.status == "approved"
        assert request.decided_by == "human-reviewer"
        assert request.decided_at is not None

    def test_reject_held_action(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
        )
        held_result = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held_result.approval_request.request_id

        rejection_result = mw.reject_request(
            request_id=request_id,
            approver_id="human-reviewer",
            reason="Not appropriate at this time",
        )

        assert rejection_result.outcome == ActionOutcome.REJECTED
        assert rejection_result.audit_recorded is True

    def test_reject_updates_request_status(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
        )
        held_result = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held_result.approval_request.request_id

        mw.reject_request(
            request_id=request_id,
            approver_id="human-reviewer",
            reason="Not now",
        )

        assert len(mw.pending_approvals) == 0
        request = held_result.approval_request
        assert request.status == "rejected"
        assert request.decided_by == "human-reviewer"
        assert request.decided_at is not None

    def test_approve_nonexistent_request_raises(self):
        mw = _make_middleware()
        with pytest.raises(ValueError, match="not found"):
            mw.approve_request(request_id="nonexistent-id", approver_id="human-reviewer")

    def test_reject_nonexistent_request_raises(self):
        mw = _make_middleware()
        with pytest.raises(ValueError, match="not found"):
            mw.reject_request(request_id="nonexistent-id", approver_id="human-reviewer")


class TestEnvelopeOverrides:
    """Envelope evaluation results should override gradient classification."""

    def test_envelope_denied_forces_blocked(self):
        """When envelope denies an action, it must be BLOCKED regardless of gradient rules."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
            envelope_kwargs={
                "operational": OperationalConstraintConfig(blocked_actions=["forbidden_action"]),
            },
        )
        result = mw.process_action(agent_id="agent-1", action="forbidden_action")

        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED

    def test_envelope_near_boundary_forces_flagged(self):
        """When envelope is near boundary, result should be FLAGGED at minimum."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
            envelope_kwargs={
                "financial": FinancialConstraintConfig(max_spend_usd=100.0),
            },
        )
        # Spend 85% of budget — triggers near_boundary
        result = mw.process_action(agent_id="agent-1", action="purchase_item", spend_amount=85.0)

        assert result.verification_level == VerificationLevel.FLAGGED
        assert result.outcome == ActionOutcome.EXECUTED

    def test_envelope_allowed_uses_gradient_rules(self):
        """When envelope allows, gradient rules determine the level."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
            envelope_kwargs={
                "financial": FinancialConstraintConfig(max_spend_usd=1000.0),
            },
        )
        result = mw.process_action(agent_id="agent-1", action="send_report", spend_amount=5.0)

        # Envelope allows, but gradient says HELD
        assert result.verification_level == VerificationLevel.HELD
        assert result.outcome == ActionOutcome.QUEUED


class TestActionLog:
    """All processed actions should be tracked in the action log."""

    def test_action_log_tracks_all_actions(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
                GradientRuleConfig(pattern="delete_*", level=VerificationLevel.BLOCKED),
            ],
        )
        mw.process_action(agent_id="agent-1", action="read_data")
        mw.process_action(agent_id="agent-2", action="send_email")
        mw.process_action(agent_id="agent-3", action="delete_db")

        log = mw.action_log
        assert len(log) == 3
        assert log[0].action == "read_data"
        assert log[0].outcome == ActionOutcome.EXECUTED
        assert log[1].action == "send_email"
        assert log[1].outcome == ActionOutcome.QUEUED
        assert log[2].action == "delete_db"
        assert log[2].outcome == ActionOutcome.REJECTED

    def test_action_log_includes_agent_ids(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
        )
        mw.process_action(agent_id="agent-alpha", action="read")
        mw.process_action(agent_id="agent-beta", action="write")

        log = mw.action_log
        assert log[0].agent_id == "agent-alpha"
        assert log[1].agent_id == "agent-beta"

    def test_flagged_actions_filter(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
                GradientRuleConfig(pattern="draft_*", level=VerificationLevel.FLAGGED),
            ],
        )
        mw.process_action(agent_id="agent-1", action="read_data")
        mw.process_action(agent_id="agent-1", action="draft_post")
        mw.process_action(agent_id="agent-1", action="draft_email")

        flagged = mw.get_flagged_actions()
        assert len(flagged) == 2
        assert all(r.verification_level == VerificationLevel.FLAGGED for r in flagged)


class TestMiddlewarePassesEnvelopeParams:
    """Middleware should forward action parameters to the envelope for evaluation."""

    def test_spend_amount_forwarded(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
            envelope_kwargs={
                "financial": FinancialConstraintConfig(max_spend_usd=50.0),
            },
        )
        # Exceeds budget — should be blocked
        result = mw.process_action(agent_id="agent-1", action="purchase", spend_amount=100.0)
        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED

    def test_external_flag_forwarded(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
            envelope_kwargs={
                "communication": CommunicationConstraintConfig(internal_only=True),
            },
        )
        result = mw.process_action(agent_id="agent-1", action="send_external", is_external=True)
        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED

    def test_data_paths_forwarded(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
        )
        # Default envelope has no blocked data types, so this should pass
        result = mw.process_action(
            agent_id="agent-1",
            action="read_file",
            data_paths=["public/reports"],
        )
        assert result.outcome == ActionOutcome.EXECUTED

    def test_action_count_forwarded(self):
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
            envelope_kwargs={
                "operational": OperationalConstraintConfig(max_actions_per_day=10),
            },
        )
        # Exceed daily limit
        result = mw.process_action(agent_id="agent-1", action="do_thing", current_action_count=10)
        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED


class TestAuditChainIntegrity:
    """Verify that the audit chain maintains integrity across operations."""

    def test_multiple_actions_chain_correctly(self):
        chain = AuditChain(chain_id="integrity-test")
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="read_*", level=VerificationLevel.AUTO_APPROVED),
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
            audit_chain=chain,
        )

        mw.process_action(agent_id="agent-1", action="read_data")
        mw.process_action(agent_id="agent-2", action="send_email")

        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"
        assert chain.length == 2

    def test_approval_adds_to_chain(self):
        chain = AuditChain(chain_id="approval-test")
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
            audit_chain=chain,
        )

        held = mw.process_action(agent_id="agent-1", action="send_email")
        mw.approve_request(
            request_id=held.approval_request.request_id,
            approver_id="reviewer",
        )

        # Should have 2 anchors: the hold + the approval
        assert chain.length == 2
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"

    def test_rejection_adds_to_chain(self):
        chain = AuditChain(chain_id="rejection-test")
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
            audit_chain=chain,
        )

        held = mw.process_action(agent_id="agent-1", action="send_email")
        mw.reject_request(
            request_id=held.approval_request.request_id,
            approver_id="reviewer",
            reason="Not approved",
        )

        assert chain.length == 2
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"
