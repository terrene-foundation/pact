# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Red team tests for middleware enforcement gaps.

Covers RT-03, RT-05, RT-08, RT-09 findings:
- RT-03: NEVER_DELEGATED_ACTIONS wired into middleware (is_action_always_held)
- RT-05: Unified approval queues (middleware delegates to shared ApprovalQueue)
- RT-08: Envelope expiry check + signed envelope support in middleware
- RT-09: Trust posture level affects action processing
"""

from datetime import UTC, datetime, timedelta

from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    TrustPostureLevel,
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
from pact_platform.use.execution.approval import ApprovalQueue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    approval_queue: ApprovalQueue | None = None,
    signed_envelope=None,
    envelope: ConstraintEnvelope | None = None,
) -> VerificationMiddleware:
    """Create a fully wired VerificationMiddleware for testing."""
    engine = _make_engine(*(rules or []), default=default_level)
    env = envelope or _make_envelope(**(envelope_kwargs or {}))
    return VerificationMiddleware(
        gradient_engine=engine,
        envelope=env,
        audit_chain=audit_chain,
        approval_queue=approval_queue,
        signed_envelope=signed_envelope,
    )


# ===========================================================================
# RT-03: NEVER_DELEGATED_ACTIONS wired into middleware
# ===========================================================================


class TestNeverDelegatedWiring:
    """RT-03: is_action_always_held() must be consulted BEFORE gradient classification.

    Actions in NEVER_DELEGATED_ACTIONS must always be forced to HELD regardless
    of what the gradient engine would classify them as.
    """

    def test_modify_constraints_forced_to_held(self):
        """modify_constraints is in NEVER_DELEGATED_ACTIONS, must be forced HELD."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Everything auto-approved",
                ),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="modify_constraints")
        assert result.verification_level == VerificationLevel.HELD, (
            f"Expected HELD for modify_constraints (never-delegated), "
            f"got {result.verification_level}"
        )
        assert result.outcome == ActionOutcome.QUEUED

    def test_read_data_not_forced_to_held(self):
        """read_data is NOT in NEVER_DELEGATED_ACTIONS, should follow gradient rules."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Read actions safe",
                ),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="read_data")
        assert result.verification_level == VerificationLevel.AUTO_APPROVED
        assert result.outcome == ActionOutcome.EXECUTED

    def test_financial_decisions_forced_to_held(self):
        """financial_decisions is in NEVER_DELEGATED_ACTIONS, must be forced HELD."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Everything auto-approved",
                ),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="financial_decisions")
        assert result.verification_level == VerificationLevel.HELD, (
            f"Expected HELD for financial_decisions (never-delegated), "
            f"got {result.verification_level}"
        )
        assert result.outcome == ActionOutcome.QUEUED

    def test_never_delegated_overrides_blocked_to_held(self):
        """If gradient says BLOCKED but action is never-delegated, keep BLOCKED
        (BLOCKED is more restrictive than HELD)."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="modify_constraints",
                    level=VerificationLevel.BLOCKED,
                    reason="Explicitly blocked",
                ),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="modify_constraints")
        # BLOCKED is more restrictive than HELD, so BLOCKED should remain
        assert result.verification_level == VerificationLevel.BLOCKED

    def test_novel_outreach_forced_to_held(self):
        """novel_outreach is in NEVER_DELEGATED_ACTIONS."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
        )
        result = mw.process_action(agent_id="agent-1", action="novel_outreach")
        assert result.verification_level == VerificationLevel.HELD


# ===========================================================================
# RT-05: Unified approval queues
# ===========================================================================


class TestUnifiedApprovalQueues:
    """RT-05: Middleware should submit to shared ApprovalQueue when provided."""

    def test_held_action_submitted_to_shared_queue(self):
        """When ApprovalQueue is provided, HELD actions should be submitted there."""
        shared_queue = ApprovalQueue()
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
            approval_queue=shared_queue,
        )
        result = mw.process_action(agent_id="agent-1", action="send_email")
        assert result.outcome == ActionOutcome.QUEUED
        assert shared_queue.queue_depth == 1

    def test_held_action_details_in_shared_queue(self):
        """Submitted action should have correct details in the shared queue."""
        shared_queue = ApprovalQueue()
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(
                    pattern="send_*",
                    level=VerificationLevel.HELD,
                    reason="External send requires approval",
                ),
            ],
            approval_queue=shared_queue,
        )
        mw.process_action(agent_id="agent-1", action="send_email", resource="email://out")
        pending = shared_queue.pending
        assert len(pending) == 1
        assert pending[0].agent_id == "agent-1"
        assert pending[0].action == "send_email"

    def test_without_shared_queue_still_works(self):
        """When no ApprovalQueue is provided, middleware uses its own internal queue."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
            approval_queue=None,
        )
        result = mw.process_action(agent_id="agent-1", action="send_email")
        assert result.outcome == ActionOutcome.QUEUED
        assert len(mw.pending_approvals) == 1

    def test_approve_delegates_to_shared_queue(self):
        """approve_request should delegate to shared queue when present."""
        shared_queue = ApprovalQueue()
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
            approval_queue=shared_queue,
        )
        result = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = result.approval_request.request_id

        approval_result = mw.approve_request(request_id=request_id, approver_id="human-1")
        assert approval_result.outcome == ActionOutcome.EXECUTED
        # Shared queue should show resolved
        assert shared_queue.queue_depth == 0

    def test_reject_delegates_to_shared_queue(self):
        """reject_request should delegate to shared queue when present."""
        shared_queue = ApprovalQueue()
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
            approval_queue=shared_queue,
        )
        result = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = result.approval_request.request_id

        rejection_result = mw.reject_request(
            request_id=request_id, approver_id="human-1", reason="No"
        )
        assert rejection_result.outcome == ActionOutcome.REJECTED
        assert shared_queue.queue_depth == 0


# ===========================================================================
# RT-08: Envelope expiry check + signed envelope support
# ===========================================================================


class TestEnvelopeExpiryCheck:
    """RT-08: process_action must check envelope expiry at the start."""

    def test_expired_envelope_returns_blocked(self):
        """If the envelope is expired, process_action must return BLOCKED."""
        config = ConstraintEnvelopeConfig(
            id="test-envelope",
            financial=FinancialConstraintConfig(max_spend_usd=1000.0),
            communication=CommunicationConstraintConfig(internal_only=False),
        )
        envelope = ConstraintEnvelope(
            config=config,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )

        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
            envelope=envelope,
        )
        result = mw.process_action(agent_id="agent-1", action="read_data")
        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED
        assert "expired" in result.details.lower()

    def test_non_expired_envelope_proceeds_normally(self):
        """If the envelope is not expired, action should proceed through normal pipeline."""
        envelope = _make_envelope()
        # Ensure not expired (default is 90 days from now)
        assert not envelope.is_expired

        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
            envelope=envelope,
        )
        result = mw.process_action(agent_id="agent-1", action="read_data")
        assert result.verification_level == VerificationLevel.AUTO_APPROVED
        assert result.outcome == ActionOutcome.EXECUTED


class TestSignedEnvelopeSupport:
    """RT-08: Middleware should accept optional signed_envelope parameter."""

    def test_middleware_accepts_signed_envelope_parameter(self):
        """VerificationMiddleware.__init__ should accept signed_envelope kwarg."""
        engine = _make_engine(default=VerificationLevel.HELD)
        envelope = _make_envelope()
        # Should not raise
        mw = VerificationMiddleware(
            gradient_engine=engine,
            envelope=envelope,
            signed_envelope=None,
        )
        assert mw.signed_envelope is None

    def test_signed_envelope_stored_on_instance(self):
        """When signed_envelope is provided, it should be accessible."""

        engine = _make_engine(default=VerificationLevel.HELD)
        envelope = _make_envelope()
        # We just need to test the parameter is stored, not actual signing
        mw = VerificationMiddleware(
            gradient_engine=engine,
            envelope=envelope,
            signed_envelope=None,
        )
        assert hasattr(mw, "signed_envelope")


# ===========================================================================
# RT-09: Trust posture level wired into middleware
# ===========================================================================


class TestPostureLevelInMiddleware:
    """RT-09: Agent trust posture should affect action processing."""

    def test_pseudo_agent_always_blocked(self):
        """PSEUDO_AGENT has no action authority -- always BLOCKED."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
        )
        result = mw.process_action(
            agent_id="agent-1",
            action="read_data",
            agent_posture=TrustPostureLevel.PSEUDO_AGENT,
        )
        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED
        assert "pseudo_agent" in result.details.lower()

    def test_supervised_upgrades_auto_approved_to_held(self):
        """SUPERVISED posture: if gradient says AUTO_APPROVED, upgrade to HELD."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
        )
        result = mw.process_action(
            agent_id="agent-1",
            action="read_data",
            agent_posture=TrustPostureLevel.SUPERVISED,
        )
        assert result.verification_level == VerificationLevel.HELD
        assert result.outcome == ActionOutcome.QUEUED

    def test_supervised_keeps_blocked_as_blocked(self):
        """SUPERVISED posture should not downgrade BLOCKED to HELD."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="delete_*", level=VerificationLevel.BLOCKED),
            ],
        )
        result = mw.process_action(
            agent_id="agent-1",
            action="delete_db",
            agent_posture=TrustPostureLevel.SUPERVISED,
        )
        assert result.verification_level == VerificationLevel.BLOCKED

    def test_supervised_keeps_held_as_held(self):
        """SUPERVISED posture: HELD remains HELD (already at minimum)."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD),
            ],
        )
        result = mw.process_action(
            agent_id="agent-1",
            action="send_email",
            agent_posture=TrustPostureLevel.SUPERVISED,
        )
        assert result.verification_level == VerificationLevel.HELD

    def test_shared_planning_defers_to_gradient(self):
        """SHARED_PLANNING posture: defer to gradient rules."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
        )
        result = mw.process_action(
            agent_id="agent-1",
            action="read_data",
            agent_posture=TrustPostureLevel.SHARED_PLANNING,
        )
        assert result.verification_level == VerificationLevel.AUTO_APPROVED

    def test_delegated_defers_to_gradient(self):
        """DELEGATED posture: defer to gradient rules."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
        )
        result = mw.process_action(
            agent_id="agent-1",
            action="read_data",
            agent_posture=TrustPostureLevel.DELEGATED,
        )
        assert result.verification_level == VerificationLevel.AUTO_APPROVED

    def test_no_posture_defers_to_gradient(self):
        """When no posture is provided, defer to gradient rules (backward compat)."""
        mw = _make_middleware(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
        )
        result = mw.process_action(
            agent_id="agent-1",
            action="read_data",
        )
        assert result.verification_level == VerificationLevel.AUTO_APPROVED
