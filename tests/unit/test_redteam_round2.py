# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Round 2 red team findings (RT2-01 through RT2-36).

Covers all Round 2 fixes across middleware, revocation, attestation, messaging,
bridges, shadow enforcer, hook enforcer, audit pipeline, approval queue,
EATP bridge, circuit breaker, and constraint envelope modules.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from care_platform.audit.anchor import AuditAnchor, AuditChain, _redact_metadata
from care_platform.audit.pipeline import AuditPipeline
from care_platform.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.cache import CachedVerification, VerificationCache
from care_platform.constraint.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from care_platform.constraint.envelope import ConstraintEnvelope, EvaluationResult
from care_platform.constraint.gradient import GradientEngine
from care_platform.constraint.middleware import (
    ActionOutcome,
    ApprovalRequest,
    VerificationMiddleware,
)
from care_platform.execution.approval import ApprovalQueue, PendingAction
from care_platform.execution.hook_enforcer import HookEnforcer, HookVerdict
from care_platform.trust.attestation import CapabilityAttestation
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.trust.messaging import AgentMessage, MessageChannel, MessageType
from care_platform.trust.revocation import RevocationManager
from care_platform.trust.shadow_enforcer import ShadowEnforcer
from care_platform.workspace.bridge import (
    Bridge,
    BridgeManager,
    BridgePermission,
    BridgeStatus,
    BridgeType,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_envelope_config(**kwargs) -> ConstraintEnvelopeConfig:
    """Create a ConstraintEnvelopeConfig with sensible defaults."""
    return ConstraintEnvelopeConfig(
        id=kwargs.pop("id", "test-envelope"),
        description=kwargs.pop("description", "Test envelope"),
        financial=kwargs.get("financial", FinancialConstraintConfig(max_spend_usd=1000.0)),
        operational=kwargs.get("operational", OperationalConstraintConfig()),
        temporal=kwargs.get("temporal", TemporalConstraintConfig()),
        data_access=kwargs.get("data_access", DataAccessConstraintConfig()),
        communication=kwargs.get(
            "communication", CommunicationConstraintConfig(internal_only=False)
        ),
    )


def _make_envelope(*, expires_at: datetime | None = None, **kwargs) -> ConstraintEnvelope:
    """Create a ConstraintEnvelope with sensible defaults."""
    config = _make_envelope_config(**kwargs)
    envelope_kwargs: dict = {"config": config}
    if expires_at is not None:
        envelope_kwargs["expires_at"] = expires_at
    return ConstraintEnvelope(**envelope_kwargs)


def _make_gradient_engine(
    *rules: GradientRuleConfig,
    default: VerificationLevel = VerificationLevel.HELD,
) -> GradientEngine:
    """Create a GradientEngine with the given rules."""
    config = VerificationGradientConfig(rules=list(rules), default_level=default)
    return GradientEngine(config)


def _make_middleware(
    rules: list[GradientRuleConfig] | None = None,
    default_level: VerificationLevel = VerificationLevel.HELD,
    envelope_kwargs: dict | None = None,
    audit_chain: AuditChain | None = None,
    approval_queue: ApprovalQueue | None = None,
    eatp_bridge: EATPBridge | None = None,
    signing_key: bytes | None = None,
    signer_id: str = "test-signer",
    circuit_breaker: CircuitBreaker | None = None,
    envelope: ConstraintEnvelope | None = None,
) -> VerificationMiddleware:
    """Create a fully wired VerificationMiddleware for testing."""
    engine = _make_gradient_engine(*(rules or []), default=default_level)
    if envelope is None:
        envelope = _make_envelope(**(envelope_kwargs or {}))
    return VerificationMiddleware(
        gradient_engine=engine,
        envelope=envelope,
        audit_chain=audit_chain,
        approval_queue=approval_queue,
        eatp_bridge=eatp_bridge,
        signing_key=signing_key,
        signer_id=signer_id,
        circuit_breaker=circuit_breaker,
    )


# ---------------------------------------------------------------------------
# RT2-01: Middleware approve/reject blocked during halt state
# ---------------------------------------------------------------------------


class TestRT2_01_HaltBlocksApprovalAndRejection:
    """RT2-01: Approval and rejection must be blocked when middleware is halted."""

    def test_approve_blocked_during_halt_direct_queue(self):
        """Approving a held action via the direct queue raises during halt."""
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD)],
        )
        held = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held.approval_request.request_id

        mw.halt("security incident")

        with pytest.raises(RuntimeError, match="halted"):
            mw.approve_request(request_id, approver_id="reviewer")

    def test_reject_blocked_during_halt_direct_queue(self):
        """Rejecting a held action via the direct queue raises during halt."""
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD)],
        )
        held = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held.approval_request.request_id

        mw.halt("security incident")

        with pytest.raises(RuntimeError, match="halted"):
            mw.reject_request(request_id, approver_id="reviewer")

    def test_approve_blocked_during_halt_shared_queue(self):
        """Approving via shared queue raises during halt."""
        shared_q = ApprovalQueue()
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD)],
            approval_queue=shared_q,
        )
        held = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held.approval_request.request_id

        mw.halt("emergency")

        with pytest.raises(RuntimeError, match="halted"):
            mw.approve_request(request_id, approver_id="reviewer")

    def test_reject_blocked_during_halt_shared_queue(self):
        """Rejecting via shared queue raises during halt."""
        shared_q = ApprovalQueue()
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD)],
            approval_queue=shared_q,
        )
        held = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held.approval_request.request_id

        mw.halt("emergency")

        with pytest.raises(RuntimeError, match="halted"):
            mw.reject_request(request_id, approver_id="reviewer", reason="denied")

    def test_process_action_blocked_during_halt(self):
        """New actions are BLOCKED when middleware is halted."""
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
        )
        mw.halt("system down")

        result = mw.process_action(agent_id="agent-1", action="read_data")
        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED

    def test_resume_allows_operations_again(self):
        """After resume, approve/reject and actions work again."""
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD)],
        )
        held = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held.approval_request.request_id

        mw.halt("temporary halt")
        mw.resume()

        # Should not raise now
        result = mw.approve_request(request_id, approver_id="reviewer")
        assert result.outcome == ActionOutcome.EXECUTED


# ---------------------------------------------------------------------------
# RT2-02: RevocationManager invalidates verification cache on revoke
# ---------------------------------------------------------------------------


class TestRT2_02_RevocationInvalidatesCache:
    """RT2-02: Verification cache must be invalidated when an agent is revoked."""

    def test_surgical_revoke_invalidates_cache(self):
        """Surgical revocation should invalidate the agent's cache entries."""
        cache = VerificationCache(max_size=100)
        cache.put(
            ("agent-1", "v1"),
            CachedVerification(
                trust_score=0.9,
                posture=TrustPostureLevel.SUPERVISED,
                verification_result="AUTO_APPROVED",
            ),
            ttl_seconds=300,
        )
        assert cache.get(("agent-1", "v1")) is not None

        mgr = RevocationManager(verification_cache=cache)
        mgr.surgical_revoke("agent-1", "policy violation", "admin")

        # Cache should be invalidated
        assert cache.get(("agent-1", "v1")) is None

    def test_cascade_revoke_invalidates_cache_for_all_affected(self):
        """Cascade revocation should invalidate cache for root + downstream agents."""
        cache = VerificationCache(max_size=100)
        for agent_id in ["root", "child-1", "child-2"]:
            cache.put(
                (agent_id, "v1"),
                CachedVerification(
                    trust_score=0.9,
                    posture=TrustPostureLevel.SUPERVISED,
                    verification_result="AUTO_APPROVED",
                ),
                ttl_seconds=300,
            )

        mgr = RevocationManager(verification_cache=cache)
        mgr.register_delegation("root", "child-1")
        mgr.register_delegation("root", "child-2")

        mgr.cascade_revoke("root", "compromised", "admin")

        for agent_id in ["root", "child-1", "child-2"]:
            assert cache.get((agent_id, "v1")) is None


# ---------------------------------------------------------------------------
# RT2-03: Re-verify before decision catches expired envelope and revoked agent
# ---------------------------------------------------------------------------


class TestRT2_03_ReVerifyBeforeDecision:
    """RT2-03: Middleware re-verifies envelope/attestation at approval time."""

    def test_approve_raises_when_envelope_expired_after_hold(self):
        """If envelope expires between HOLD and APPROVE, approval should fail."""
        # Create envelope that expires in 1 second so we can let it expire
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD)],
            envelope=_make_envelope(
                expires_at=datetime.now(UTC) + timedelta(seconds=1),
            ),
        )
        held = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held.approval_request.request_id

        # Replace the envelope with an already-expired one via object.__setattr__
        # (ConstraintEnvelope is frozen, but we need to simulate time passing)
        expired_envelope = _make_envelope(
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        object.__setattr__(mw, "_envelope", expired_envelope)

        with pytest.raises(RuntimeError, match="expired"):
            mw.approve_request(request_id, approver_id="reviewer")

    def test_approve_raises_when_agent_revoked_after_hold(self):
        """If agent is revoked between HOLD and APPROVE, approval should fail."""
        bridge = EATPBridge()
        # Manually register an attestation so verify_capability returns True initially
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["send_email"],
            issuer_id="admin",
        )
        bridge._attestations["agent-1"] = att

        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="send_*", level=VerificationLevel.HELD)],
            eatp_bridge=bridge,
        )
        held = mw.process_action(agent_id="agent-1", action="send_email")
        request_id = held.approval_request.request_id

        # Revoke the agent
        bridge.revoke_agent("agent-1")

        with pytest.raises(RuntimeError, match="no longer valid"):
            mw.approve_request(request_id, approver_id="reviewer")


# ---------------------------------------------------------------------------
# RT2-04: Messaging HMAC with channel_secret
# ---------------------------------------------------------------------------


class TestRT2_04_MessagingChannelHMAC:
    """RT2-04: When channel_secret is set, send() computes channel_mac on the message."""

    def test_channel_mac_computed_on_send_with_secret(self):
        """Sending through a channel with a secret should set channel_mac."""
        channel = MessageChannel(
            participant_ids=["alice", "bob"],
            channel_secret="supersecret",
        )
        msg = AgentMessage(
            sender_id="alice",
            recipient_id="bob",
            message_type=MessageType.REQUEST,
            payload={"data": "hello"},
        )
        assert channel.send(msg) is True
        assert msg.channel_mac != ""
        assert msg.verify_channel_mac("supersecret") is True

    def test_channel_mac_not_set_without_secret(self):
        """Sending without a channel_secret should leave channel_mac empty."""
        channel = MessageChannel(
            participant_ids=["alice", "bob"],
            channel_secret="",
        )
        msg = AgentMessage(
            sender_id="alice",
            recipient_id="bob",
            message_type=MessageType.REQUEST,
            payload={"data": "hello"},
        )
        assert channel.send(msg) is True
        assert msg.channel_mac == ""

    def test_channel_mac_fails_with_wrong_secret(self):
        """Verifying channel_mac with wrong secret should return False."""
        channel = MessageChannel(
            participant_ids=["alice", "bob"],
            channel_secret="correct_secret",
        )
        msg = AgentMessage(
            sender_id="alice",
            recipient_id="bob",
            message_type=MessageType.REQUEST,
        )
        channel.send(msg)
        assert msg.verify_channel_mac("wrong_secret") is False


# ---------------------------------------------------------------------------
# RT2-05: Revocation cascade calls bridge_manager.revoke_team_bridges;
#         bridge access_through_bridge rejects revoked agents
# ---------------------------------------------------------------------------


class TestRT2_05_RevocationCascadeBridges:
    """RT2-05: Cascade revocation revokes bridges; revoked agents denied access."""

    def test_cascade_revoke_calls_revoke_team_bridges(self):
        """Cascade revocation should revoke bridges for the affected team."""
        bridge_mgr = BridgeManager()
        bridge = bridge_mgr.create_standing_bridge(
            source_team="team-A",
            target_team="team-B",
            purpose="Data share",
            permissions=BridgePermission(read_paths=["docs/*"]),
            created_by="admin",
        )
        bridge.approve_source("s")
        bridge.approve_target("t")
        assert bridge.is_active

        rev_mgr = RevocationManager(bridge_manager=bridge_mgr)
        rev_mgr.cascade_revoke("team-A", "compromised", "admin")

        assert bridge.status == BridgeStatus.REVOKED

    def test_access_through_bridge_rejects_revoked_agent(self):
        """access_through_bridge should deny access to revoked agents."""
        bridge_mgr = BridgeManager()
        bridge = bridge_mgr.create_standing_bridge(
            source_team="team-A",
            target_team="team-B",
            purpose="Data share",
            permissions=BridgePermission(read_paths=["docs/*"]),
            created_by="admin",
        )
        bridge.approve_source("s")
        bridge.approve_target("t")

        # Access should work for non-revoked agent (with valid team context)
        assert bridge_mgr.access_through_bridge(
            bridge.bridge_id,
            "agent-1",
            "docs/report.pdf",
            revoked_agents=set(),
            agent_team_id="team-A",
        )

        # Access should be denied for revoked agent
        assert not bridge_mgr.access_through_bridge(
            bridge.bridge_id,
            "agent-1",
            "docs/report.pdf",
            revoked_agents={"agent-1"},
            agent_team_id="team-A",
        )


# ---------------------------------------------------------------------------
# RT2-06: Middleware blocks when EATP bridge verify_capability returns False
# ---------------------------------------------------------------------------


class TestRT2_06_MiddlewareEATPBridgeBlock:
    """RT2-06: Middleware blocks action when EATP bridge verify_capability returns False."""

    def test_blocks_when_capability_not_attested(self):
        """Agent without valid attestation should be BLOCKED."""
        bridge = EATPBridge()
        # No attestation registered for this agent
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            eatp_bridge=bridge,
        )
        result = mw.process_action(agent_id="agent-unknown", action="read_data")
        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED
        assert "attestation" in result.details.lower()

    def test_passes_when_capability_is_valid(self):
        """Agent with valid attestation should pass through."""
        bridge = EATPBridge()
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read_data"],
            issuer_id="admin",
        )
        bridge._attestations["agent-1"] = att

        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            eatp_bridge=bridge,
        )
        result = mw.process_action(agent_id="agent-1", action="read_data")
        assert result.verification_level == VerificationLevel.AUTO_APPROVED
        assert result.outcome == ActionOutcome.EXECUTED


# ---------------------------------------------------------------------------
# RT2-07: ShadowEnforcer mirrors halt, PSEUDO_AGENT, never-delegated, SUPERVISED
# ---------------------------------------------------------------------------


class TestRT2_07_ShadowEnforcerMirrorsMiddleware:
    """RT2-07: ShadowEnforcer mirrors the full middleware pipeline."""

    def _make_shadow(self, *, halted_check=None) -> ShadowEnforcer:
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope = _make_envelope()
        return ShadowEnforcer(engine, envelope, halted_check=halted_check)

    def test_halt_check_blocks_everything(self):
        """Shadow should report BLOCKED when halt check returns True."""
        shadow = self._make_shadow(halted_check=lambda: True)
        result = shadow.evaluate("read_data", "agent-1")
        assert result.would_be_blocked
        assert result.verification_level == VerificationLevel.BLOCKED

    def test_pseudo_agent_blocked(self):
        """PSEUDO_AGENT posture should block everything in shadow."""
        shadow = self._make_shadow()
        result = shadow.evaluate(
            "read_data", "agent-1", agent_posture=TrustPostureLevel.PSEUDO_AGENT
        )
        assert result.would_be_blocked
        assert result.verification_level == VerificationLevel.BLOCKED

    def test_never_delegated_action_forced_to_held(self):
        """Never-delegated actions (e.g., content_strategy) should be HELD."""
        shadow = self._make_shadow()
        result = shadow.evaluate("content_strategy", "agent-1")
        assert result.would_be_held
        assert result.verification_level == VerificationLevel.HELD

    def test_supervised_posture_escalates_to_held(self):
        """SUPERVISED posture should escalate AUTO_APPROVED to HELD."""
        shadow = self._make_shadow()
        result = shadow.evaluate("read_data", "agent-1", agent_posture=TrustPostureLevel.SUPERVISED)
        assert result.would_be_held
        assert result.verification_level == VerificationLevel.HELD


# ---------------------------------------------------------------------------
# RT2-08: HookEnforcer mirrors halt, PSEUDO_AGENT, never-delegated, SUPERVISED
# ---------------------------------------------------------------------------


class TestRT2_08_HookEnforcerMirrorsMiddleware:
    """RT2-08: HookEnforcer mirrors the full middleware pipeline."""

    def _make_enforcer(self, *, halted_check=None) -> HookEnforcer:
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope = _make_envelope()
        return HookEnforcer(engine, envelope, halted_check=halted_check)

    def test_halt_check_blocks_everything(self):
        """Hook enforcer should BLOCK when halt check returns True."""
        enforcer = self._make_enforcer(halted_check=lambda: True)
        result = enforcer.enforce("agent-1", "read_data")
        assert result.verdict == HookVerdict.BLOCK
        assert "halt" in result.reason.lower()

    def test_pseudo_agent_blocked(self):
        """PSEUDO_AGENT posture should block everything."""
        enforcer = self._make_enforcer()
        result = enforcer.enforce(
            "agent-1", "read_data", agent_posture=TrustPostureLevel.PSEUDO_AGENT
        )
        assert result.verdict == HookVerdict.BLOCK

    def test_never_delegated_action_forced_to_hold(self):
        """Never-delegated actions should result in HOLD verdict."""
        enforcer = self._make_enforcer()
        result = enforcer.enforce("agent-1", "content_strategy")
        assert result.verdict == HookVerdict.HOLD

    def test_supervised_posture_escalates_to_hold(self):
        """SUPERVISED posture should escalate AUTO_APPROVED to HOLD."""
        enforcer = self._make_enforcer()
        result = enforcer.enforce(
            "agent-1", "read_data", agent_posture=TrustPostureLevel.SUPERVISED
        )
        assert result.verdict == HookVerdict.HOLD


# ---------------------------------------------------------------------------
# RT2-09: Expired envelope returns DENIED in evaluate_action
# ---------------------------------------------------------------------------


class TestRT2_09_ExpiredEnvelopeDenied:
    """RT2-09: Expired envelope should return DENIED from evaluate_action."""

    def test_evaluate_action_returns_denied_when_expired(self):
        """evaluate_action should return DENIED overall if envelope is expired."""
        envelope = _make_envelope(expires_at=datetime.now(UTC) - timedelta(hours=1))

        result = envelope.evaluate_action("read", "agent-1")
        assert result.overall_result == EvaluationResult.DENIED
        assert any("expired" in d.reason.lower() for d in result.dimensions)


# ---------------------------------------------------------------------------
# RT2-10: has_capability returns False when attestation is revoked or expired
# ---------------------------------------------------------------------------


class TestRT2_10_HasCapabilityRespectsValidity:
    """RT2-10: has_capability should return False when attestation is revoked or expired."""

    def test_revoked_attestation_has_capability_false(self):
        """A revoked attestation should not report any capability."""
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read", "write"],
            issuer_id="admin",
        )
        assert att.has_capability("read") is True

        att.revoke("policy violation")
        assert att.has_capability("read") is False

    def test_expired_attestation_has_capability_false(self):
        """An expired attestation should not report any capability."""
        att = CapabilityAttestation(
            attestation_id="att-2",
            agent_id="agent-2",
            delegation_id="del-2",
            constraint_envelope_id="env-2",
            capabilities=["read"],
            issuer_id="admin",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert att.has_capability("read") is False


# ---------------------------------------------------------------------------
# RT2-13: frozen_permissions survives Pydantic serialization
# ---------------------------------------------------------------------------


class TestRT2_13_FrozenPermissionsSerialization:
    """RT2-13: frozen_permissions is a regular Pydantic field that survives round-trip."""

    def test_frozen_permissions_survives_serialization(self):
        """frozen_permissions should be present after model_dump/model_validate."""
        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id="team-a",
            target_team_id="team-b",
            purpose="Test",
            permissions=BridgePermission(read_paths=["docs/*"]),
        )
        bridge.approve_source("s")
        bridge.approve_target("t")

        assert bridge.frozen_permissions is not None

        # Round-trip through Pydantic serialization
        data = bridge.model_dump(mode="json")
        restored = Bridge.model_validate(data)

        assert restored.frozen_permissions is not None
        assert restored.frozen_permissions.read_paths == ["docs/*"]

    def test_frozen_permissions_field_not_underscore_prefixed(self):
        """frozen_permissions should be a public field, not private."""
        # Check the field exists in the model fields (not as PrivateAttr)
        field_names = set(Bridge.model_fields.keys())
        assert "frozen_permissions" in field_names


# ---------------------------------------------------------------------------
# RT2-14: Middleware tracks cumulative spend per agent
# ---------------------------------------------------------------------------


class TestRT2_14_CumulativeSpendTracking:
    """RT2-14: Middleware tracks cumulative spend and passes it to envelope."""

    def test_cumulative_spend_accumulates_across_actions(self):
        """Each successful spend should increase the cumulative total."""
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            envelope_kwargs={
                "financial": FinancialConstraintConfig(
                    max_spend_usd=1000.0,
                    api_cost_budget_usd=100.0,
                ),
            },
        )
        mw.process_action(agent_id="agent-1", action="call_api", spend_amount=30.0)
        mw.process_action(agent_id="agent-1", action="call_api", spend_amount=30.0)
        mw.process_action(agent_id="agent-1", action="call_api", spend_amount=30.0)

        # Cumulative = 90, next 20 would exceed 100 budget
        result = mw.process_action(agent_id="agent-1", action="call_api", spend_amount=20.0)
        assert result.verification_level == VerificationLevel.BLOCKED

    def test_cumulative_spend_tracked_per_agent(self):
        """Different agents should have independent spend tracking."""
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            envelope_kwargs={
                "financial": FinancialConstraintConfig(
                    max_spend_usd=1000.0,
                    api_cost_budget_usd=50.0,
                ),
            },
        )
        mw.process_action(agent_id="agent-1", action="call_api", spend_amount=40.0)
        # agent-2 should still have zero cumulative spend
        result = mw.process_action(agent_id="agent-2", action="call_api", spend_amount=40.0)
        assert result.outcome == ActionOutcome.EXECUTED


# ---------------------------------------------------------------------------
# RT2-15: AuditPipeline link_chain includes linked anchors in exports
# ---------------------------------------------------------------------------


class TestRT2_15_AuditPipelineLinkChain:
    """RT2-15: Linked chains appear in export_for_review and get_team_timeline."""

    def test_linked_chain_anchors_in_export_for_review(self):
        """Anchors from linked chains should appear in export_for_review."""
        pipeline = AuditPipeline()

        # Record an action via pipeline
        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        # Create a linked chain with its own anchor
        linked = AuditChain(chain_id="middleware-chain")
        linked.append(
            agent_id="agent-1",
            action="write",
            verification_level=VerificationLevel.FLAGGED,
            result="executed_flagged",
        )
        pipeline.link_chain("middleware", linked)

        exported = pipeline.export_for_review(agent_id="agent-1")
        actions = [e["action"] for e in exported]
        assert "read" in actions
        assert "write" in actions

    def test_linked_chain_anchors_in_get_team_timeline(self):
        """Anchors from linked chains should appear in get_team_timeline."""
        pipeline = AuditPipeline()

        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        linked = AuditChain(chain_id="middleware-chain")
        linked.append(
            agent_id="agent-1",
            action="verify",
            verification_level=VerificationLevel.HELD,
            result="queued",
        )
        pipeline.link_chain("middleware", linked)

        timeline = pipeline.get_team_timeline(["agent-1"])
        actions = [a.action for a in timeline]
        assert "read" in actions
        assert "verify" in actions


# ---------------------------------------------------------------------------
# RT2-17: RevocationManager can_redelegate enforces cooling-off period
# ---------------------------------------------------------------------------


class TestRT2_17_CoolingOffPeriod:
    """RT2-17: can_redelegate enforces a minimum cooling-off after revocation."""

    def test_can_redelegate_false_during_cooling_off(self):
        """Recently revoked agent should not be re-delegatable during cooling-off."""
        mgr = RevocationManager(min_cooling_off_hours=24)
        mgr.surgical_revoke("agent-1", "policy violation", "admin")

        assert mgr.can_redelegate("agent-1") is False

    def test_can_redelegate_true_without_cooling_off(self):
        """With no cooling-off period, revoked agent can always be re-delegated."""
        mgr = RevocationManager(min_cooling_off_hours=0)
        mgr.surgical_revoke("agent-1", "policy violation", "admin")

        assert mgr.can_redelegate("agent-1") is True

    def test_can_redelegate_true_for_non_revoked_agent(self):
        """Non-revoked agent can always be delegated."""
        mgr = RevocationManager(min_cooling_off_hours=24)
        assert mgr.can_redelegate("agent-unknown") is True


# ---------------------------------------------------------------------------
# RT2-18: Middleware upgrades FLAGGED to HELD on approval threshold
# ---------------------------------------------------------------------------


class TestRT2_18_FlaggedToHeldOnApprovalThreshold:
    """RT2-18: FLAGGED should be upgraded to HELD when envelope signals approval threshold."""

    def test_flagged_upgraded_to_held_on_approval_threshold(self):
        """Spend above requires_approval_above_usd but below max should become HELD."""
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            envelope_kwargs={
                "financial": FinancialConstraintConfig(
                    max_spend_usd=1000.0,
                    requires_approval_above_usd=50.0,
                ),
            },
        )
        # Spend 60 exceeds approval threshold (50) but not max (1000)
        # Envelope returns NEAR_BOUNDARY with "approval threshold" reason
        # Gradient sees NEAR_BOUNDARY -> FLAGGED
        # Middleware should then upgrade FLAGGED -> HELD
        result = mw.process_action(agent_id="agent-1", action="purchase", spend_amount=60.0)
        assert result.verification_level == VerificationLevel.HELD
        assert result.outcome == ActionOutcome.QUEUED


# ---------------------------------------------------------------------------
# RT2-20: eatp_bridge delegate uses real delegation.id
# ---------------------------------------------------------------------------


class TestRT2_20_RealDelegationId:
    """RT2-20: attestation.delegation_id should match the EATP delegation record's id."""

    def test_attestation_delegation_id_matches_delegation_record(self):
        """The delegation_id on the attestation should be the real delegation record's id."""
        bridge = EATPBridge()

        async def _run():
            await bridge.initialize()
            genesis = await bridge.establish_genesis(
                GenesisConfig(
                    authority="test-auth",
                    authority_name="Test Authority",
                    policy_reference="https://test.example/policy",
                )
            )
            agent_config = AgentConfig(
                id="agent-1",
                name="Test Agent",
                role="tester",
                constraint_envelope="env-1",
                capabilities=["read"],
            )
            envelope_config = ConstraintEnvelopeConfig(id="env-1", description="Test")

            delegation = await bridge.delegate(
                delegator_id=genesis.agent_id,
                delegate_agent_config=agent_config,
                envelope_config=envelope_config,
            )

            att = bridge.get_attestation("agent-1")
            assert att is not None
            # The attestation delegation_id should match the real delegation record id
            assert att.delegation_id == delegation.id

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# RT2-22: Bridge creation_permissions snapshots at creation, _activate freezes from it
# ---------------------------------------------------------------------------


class TestRT2_22_CreationPermissionsSnapshot:
    """RT2-22: Permissions are snapshotted at creation and frozen from that snapshot."""

    def test_creation_permissions_snapshotted(self):
        """creation_permissions should exist and match initial permissions."""
        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id="a",
            target_team_id="b",
            purpose="Test",
            permissions=BridgePermission(read_paths=["original/*"]),
        )
        assert bridge.creation_permissions is not None
        assert bridge.creation_permissions.read_paths == ["original/*"]

    def test_activate_freezes_from_creation_snapshot(self):
        """Mutating permissions between creation and activation should not affect frozen."""
        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id="a",
            target_team_id="b",
            purpose="Test",
            permissions=BridgePermission(read_paths=["original/*"]),
        )
        # Mutate permissions AFTER creation but BEFORE activation
        bridge.permissions.read_paths = ["mutated/*"]

        # Activate
        bridge.approve_source("s")
        bridge.approve_target("t")

        # frozen_permissions should come from creation_permissions, not mutated
        assert bridge.frozen_permissions is not None
        assert bridge.frozen_permissions.read_paths == ["original/*"]

        # Access check should use frozen (original) permissions
        assert bridge.check_access("original/file.txt", "read") is True
        assert bridge.check_access("mutated/file.txt", "read") is False


# ---------------------------------------------------------------------------
# RT2-24: AuditAnchor compute_hash includes metadata
# ---------------------------------------------------------------------------


class TestRT2_24_AuditAnchorHashIncludesMetadata:
    """RT2-24: compute_hash should include metadata to prevent post-seal tampering."""

    def test_metadata_changes_hash(self):
        """Changing metadata after computing hash should produce a different hash."""
        anchor = AuditAnchor(
            anchor_id="a-1",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
            metadata={"key": "value"},
        )
        hash_with_metadata = anchor.compute_hash()

        anchor.metadata = {"key": "different_value"}
        hash_with_changed_metadata = anchor.compute_hash()

        assert hash_with_metadata != hash_with_changed_metadata

    def test_empty_metadata_vs_populated_differ(self):
        """Empty metadata and populated metadata should produce different hashes."""
        anchor1 = AuditAnchor(
            anchor_id="a-1",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
            metadata={},
        )
        anchor2 = AuditAnchor(
            anchor_id="a-1",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
            metadata={"extra": "data"},
        )
        assert anchor1.compute_hash() != anchor2.compute_hash()


# ---------------------------------------------------------------------------
# RT2-25: AuditAnchor sign() verifies integrity before signing
# ---------------------------------------------------------------------------


class TestRT2_25_SignVerifiesIntegrity:
    """RT2-25: sign() should refuse to sign a tampered anchor."""

    def test_sign_fails_on_tampered_anchor(self):
        """If content is modified after seal(), sign() should raise ValueError."""
        anchor = AuditAnchor(
            anchor_id="a-1",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.seal()

        # Tamper with a field after sealing
        anchor.result = "tampered"

        with pytest.raises(ValueError, match="tampered"):
            anchor.sign(b"signing-key-32-bytes-of-length!", "signer")

    def test_sign_succeeds_on_untampered_anchor(self):
        """sign() should succeed if anchor is sealed and unmodified."""
        anchor = AuditAnchor(
            anchor_id="a-1",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.seal()
        # Should not raise
        anchor.sign(b"signing-key-32-bytes-of-length!", "signer")
        assert anchor.is_signed


# ---------------------------------------------------------------------------
# RT2-26: Middleware with circuit breaker returns BLOCKED when open
# ---------------------------------------------------------------------------


class TestRT2_26_MiddlewareCircuitBreaker:
    """RT2-26: When circuit breaker is OPEN, middleware should return BLOCKED."""

    def test_circuit_breaker_open_returns_blocked(self):
        """Open circuit breaker should cause fail-safe BLOCK."""
        # Create a circuit breaker that trips after 1 failure
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)

        # Create engine that will raise to trip the circuit breaker
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope = _make_envelope()

        mw = VerificationMiddleware(
            gradient_engine=engine,
            envelope=envelope,
            circuit_breaker=cb,
        )

        # Force the circuit breaker to open by recording failures directly
        # We do this by making the classify call fail
        original_classify = engine.classify

        def failing_classify(*args, **kwargs):
            raise RuntimeError("Simulated gradient engine failure")

        engine.classify = failing_classify

        # This should trip the breaker
        try:
            mw.process_action(agent_id="agent-1", action="test_action")
        except RuntimeError:
            pass  # Expected since classify raises

        # Now the breaker should be open; next call should get BLOCKED
        engine.classify = original_classify  # restore, but breaker is still open
        result = mw.process_action(agent_id="agent-1", action="test_action")
        assert result.verification_level == VerificationLevel.BLOCKED
        assert "circuit breaker" in result.details.lower()


# ---------------------------------------------------------------------------
# RT2-27: AuditAnchor _redact_metadata handles nested dicts
# ---------------------------------------------------------------------------


class TestRT2_27_RedactMetadataNestedDicts:
    """RT2-27: _redact_metadata should recursively process nested dicts."""

    def test_nested_dict_reason_redacted(self):
        """Nested dict containing 'reason' key should have value redacted."""
        metadata = {
            "outer_key": "keep",
            "nested": {
                "reason": "sensitive explanation",
                "safe_key": "keep_this",
            },
        }
        redacted = _redact_metadata(metadata)
        assert redacted["outer_key"] == "keep"
        assert redacted["nested"]["reason"] == "[REDACTED]"
        assert redacted["nested"]["safe_key"] == "keep_this"

    def test_nested_dict_token_removed(self):
        """Nested dict containing 'token' key should be removed."""
        metadata = {
            "nested": {
                "auth_token": "secret_value",
                "safe_key": "keep",
            },
        }
        redacted = _redact_metadata(metadata)
        assert "auth_token" not in redacted["nested"]
        assert redacted["nested"]["safe_key"] == "keep"

    def test_deeply_nested_redaction(self):
        """Redaction should handle multiple levels of nesting."""
        metadata = {
            "level1": {
                "level2": {
                    "reason": "deep_secret",
                },
            },
        }
        redacted = _redact_metadata(metadata)
        assert redacted["level1"]["level2"]["reason"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# RT2-28: CapabilityAttestation model_post_init populates signature_hash
# ---------------------------------------------------------------------------


class TestRT2_28_AttestationSignatureHash:
    """RT2-28: model_post_init should auto-populate signature_hash."""

    def test_signature_hash_populated_on_creation(self):
        """Creating an attestation should auto-populate signature_hash."""
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="admin",
        )
        assert att.signature_hash is not None
        assert att.signature_hash != ""
        assert att.signature_hash == att.content_hash()

    def test_signature_hash_not_overwritten_if_provided(self):
        """If signature_hash is explicitly provided, it should be kept."""
        att = CapabilityAttestation(
            attestation_id="att-2",
            agent_id="agent-2",
            delegation_id="del-2",
            constraint_envelope_id="env-2",
            capabilities=["write"],
            issuer_id="admin",
            signature_hash="custom_hash_value",
        )
        assert att.signature_hash == "custom_hash_value"


# ---------------------------------------------------------------------------
# RT2-33: Middleware rejects invalid signed envelope on init
# ---------------------------------------------------------------------------


class TestRT2_33_MiddlewareRejectsInvalidSignedEnvelope:
    """RT2-33: Middleware should reject signed envelope with invalid signature on init."""

    def test_invalid_signed_envelope_raises_on_init(self):
        """Middleware init with a SignedEnvelope that fails verification should raise."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        envelope = _make_envelope()
        priv_key = Ed25519PrivateKey.generate()
        pub_key_bytes = priv_key.public_key().public_bytes_raw()

        from care_platform.constraint.signing import SignedEnvelope

        signed = SignedEnvelope.sign_envelope(
            envelope=envelope,
            signer_id="admin",
            private_key=priv_key.private_bytes_raw(),
        )

        # Tamper with the signature
        signed.signature = "0" * 128

        engine = _make_gradient_engine()
        with pytest.raises(ValueError, match="signature verification failed"):
            VerificationMiddleware(
                gradient_engine=engine,
                envelope=envelope,
                signed_envelope=signed,
                public_key=pub_key_bytes,
            )


# ---------------------------------------------------------------------------
# RT2-34: Middleware passes signing_key to audit_chain.append
# ---------------------------------------------------------------------------


class TestRT2_34_MiddlewareAuditSigning:
    """RT2-34: When signing_key is provided, audit anchors should be signed."""

    def test_audit_anchors_are_signed_when_key_provided(self):
        """Actions processed with a signing_key should produce signed audit anchors."""
        chain = AuditChain(chain_id="signed-test")
        signing_key = b"test-signing-key-32-bytes-long!!"

        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            audit_chain=chain,
            signing_key=signing_key,
            signer_id="middleware-signer",
        )
        mw.process_action(agent_id="agent-1", action="read_data")

        assert chain.length == 1
        anchor = chain.latest
        assert anchor.is_signed
        assert anchor.signer_id == "middleware-signer"
        assert anchor.verify_signature(signing_key)

    def test_audit_anchors_unsigned_when_no_key(self):
        """Without signing_key, audit anchors should not be signed."""
        chain = AuditChain(chain_id="unsigned-test")

        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            audit_chain=chain,
        )
        mw.process_action(agent_id="agent-1", action="read_data")

        assert chain.length == 1
        anchor = chain.latest
        assert not anchor.is_signed


# ---------------------------------------------------------------------------
# RT2-35: ApprovalQueue on_expire callback called when actions expire
# ---------------------------------------------------------------------------


class TestRT2_35_ApprovalQueueOnExpire:
    """RT2-35: on_expire callback should be invoked for each expired action."""

    def test_on_expire_callback_invoked(self):
        """Expiring an action should invoke the on_expire callback."""
        expired_actions: list[PendingAction] = []

        def on_expire_cb(pa: PendingAction) -> None:
            expired_actions.append(pa)

        queue = ApprovalQueue(on_expire=on_expire_cb)

        # Submit an action with a very old timestamp
        pa = queue.submit(
            agent_id="agent-1",
            action="send_email",
            reason="Requires approval",
        )
        # Manually backdate to force expiry
        pa.submitted_at = datetime.now(UTC) - timedelta(hours=100)

        queue.expire_old(max_age_hours=48)

        assert len(expired_actions) == 1
        assert expired_actions[0].action_id == pa.action_id
        assert expired_actions[0].status == "expired"

    def test_on_expire_not_called_when_not_expired(self):
        """Non-expired actions should not trigger the callback."""
        expired_actions: list[PendingAction] = []
        queue = ApprovalQueue(on_expire=lambda pa: expired_actions.append(pa))

        queue.submit(
            agent_id="agent-1",
            action="send_email",
            reason="Requires approval",
        )
        queue.expire_old(max_age_hours=48)

        assert len(expired_actions) == 0


# ---------------------------------------------------------------------------
# RT2-36: Middleware halt/resume records audit anchors
# ---------------------------------------------------------------------------


class TestRT2_36_HaltResumeAuditAnchors:
    """RT2-36: halt() and resume() should record audit anchors."""

    def test_halt_records_audit_anchor(self):
        """Calling halt() should append an audit anchor."""
        chain = AuditChain(chain_id="halt-test")
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            audit_chain=chain,
        )
        mw.halt("security incident")

        assert chain.length == 1
        anchor = chain.latest
        assert anchor.action == "emergency_halt"
        assert anchor.verification_level == VerificationLevel.BLOCKED
        assert anchor.metadata.get("reason") == "security incident"

    def test_resume_records_audit_anchor(self):
        """Calling resume() after halt() should append an audit anchor."""
        chain = AuditChain(chain_id="resume-test")
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            audit_chain=chain,
        )
        mw.halt("temporary issue")
        mw.resume()

        assert chain.length == 2
        halt_anchor = chain.anchors[0]
        resume_anchor = chain.anchors[1]
        assert halt_anchor.action == "emergency_halt"
        assert resume_anchor.action == "emergency_resume"
        assert resume_anchor.verification_level == VerificationLevel.AUTO_APPROVED

    def test_resume_without_halt_does_not_record(self):
        """Calling resume() when not halted should not record an anchor."""
        chain = AuditChain(chain_id="noop-resume")
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            audit_chain=chain,
        )
        mw.resume()
        assert chain.length == 0

    def test_halt_resume_anchors_are_signed_when_key_provided(self):
        """halt/resume anchors should be signed when signing_key is set."""
        chain = AuditChain(chain_id="signed-halt")
        signing_key = b"halt-signing-key-32-bytes-long!!"

        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            audit_chain=chain,
            signing_key=signing_key,
            signer_id="halt-signer",
        )
        mw.halt("test halt")
        mw.resume()

        for anchor in chain.anchors:
            assert anchor.is_signed
            assert anchor.verify_signature(signing_key)


# ---------------------------------------------------------------------------
# RT2-16: Bridge team membership verification
# ---------------------------------------------------------------------------


class TestRT2_16_BridgeTeamMembership:
    """RT2-16: access_through_bridge rejects agents not in source/target team."""

    @staticmethod
    def _make_active_bridge(mgr: BridgeManager) -> str:
        """Create and activate a standing bridge between team-a and team-b."""
        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="test bridge",
            permissions=BridgePermission(read_paths=["docs/*"]),
            created_by="admin",
        )
        bridge.approve_source("approver-a")
        bridge.approve_target("approver-b")
        return bridge.bridge_id

    def test_agent_from_source_team_allowed(self):
        """Agent from bridge source team should be allowed access."""
        mgr = BridgeManager()
        bridge_id = self._make_active_bridge(mgr)
        assert mgr.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="agent-1",
            path="docs/readme.md",
            access_type="read",
            agent_team_id="team-a",
        )

    def test_agent_from_target_team_denied_by_directionality(self):
        """RT7-07: Agent from bridge target team is denied — permissions flow source->target only."""
        mgr = BridgeManager()
        bridge_id = self._make_active_bridge(mgr)
        assert not mgr.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="agent-2",
            path="docs/readme.md",
            access_type="read",
            agent_team_id="team-b",
        )

    def test_agent_from_outside_team_rejected(self):
        """Agent from a team NOT in source/target should be rejected."""
        mgr = BridgeManager()
        bridge_id = self._make_active_bridge(mgr)
        assert not mgr.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="agent-outsider",
            path="docs/readme.md",
            access_type="read",
            agent_team_id="team-c",
        )

    def test_no_team_id_denied_fail_closed(self):
        """RT8-05: When agent_team_id is None, access is DENIED (fail-closed)."""
        mgr = BridgeManager()
        bridge_id = self._make_active_bridge(mgr)
        assert not mgr.access_through_bridge(
            bridge_id=bridge_id,
            agent_id="agent-anon",
            path="docs/readme.md",
            access_type="read",
        )


# ---------------------------------------------------------------------------
# RT2-19: Resource recorded in audit metadata
# ---------------------------------------------------------------------------


class TestRT2_19_ResourceInAuditMetadata:
    """RT2-19: Resource parameter should appear in audit anchor metadata."""

    def test_blocked_action_includes_resource_in_audit(self):
        """When an action is blocked with a resource, audit metadata includes it."""
        chain = AuditChain(chain_id="res-test")
        mw = _make_middleware(audit_chain=chain)
        mw.process_action(
            agent_id="agent-1",
            action="test-action",
            resource="/data/sensitive.csv",
            agent_posture=TrustPostureLevel.PSEUDO_AGENT,
        )
        assert chain.length > 0
        anchor = chain.anchors[-1]
        assert anchor.metadata is not None
        assert anchor.metadata.get("resource") == "/data/sensitive.csv"

    def test_auto_approved_includes_resource_in_audit(self):
        """Auto-approved action with resource records it in audit metadata."""
        chain = AuditChain(chain_id="res-auto")
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            audit_chain=chain,
        )
        mw.process_action(
            agent_id="agent-1",
            action="read-file",
            resource="/data/report.pdf",
        )
        assert chain.length > 0
        anchor = chain.anchors[-1]
        assert anchor.metadata is not None
        assert anchor.metadata.get("resource") == "/data/report.pdf"

    def test_no_resource_means_no_resource_in_metadata(self):
        """When no resource is provided, metadata should not have resource key."""
        chain = AuditChain(chain_id="res-none")
        mw = _make_middleware(
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
            audit_chain=chain,
        )
        mw.process_action(
            agent_id="agent-1",
            action="simple-action",
        )
        assert chain.length > 0
        anchor = chain.anchors[-1]
        # No resource provided means metadata is None or doesn't have 'resource'
        if anchor.metadata is not None:
            assert "resource" not in anchor.metadata


# ---------------------------------------------------------------------------
# RT2-21: Delegation tree sync
# ---------------------------------------------------------------------------


class TestRT2_21_DelegationTreeSync:
    """RT2-21: get_delegation_tree() inverts _delegation_parents into tree format."""

    def test_single_parent_two_children(self):
        """Parent with two children should produce correct tree."""
        bridge = EATPBridge()
        # Manually set up delegation parents
        bridge._delegation_parents["child-a"] = "parent-1"
        bridge._delegation_parents["child-b"] = "parent-1"
        tree = bridge.get_delegation_tree()
        assert "parent-1" in tree
        assert sorted(tree["parent-1"]) == ["child-a", "child-b"]

    def test_multi_level_tree(self):
        """Multi-level delegation should produce correct tree structure."""
        bridge = EATPBridge()
        bridge._delegation_parents["child-1"] = "root"
        bridge._delegation_parents["child-2"] = "root"
        bridge._delegation_parents["grandchild-1"] = "child-1"
        tree = bridge.get_delegation_tree()
        assert sorted(tree["root"]) == ["child-1", "child-2"]
        assert tree["child-1"] == ["grandchild-1"]

    def test_empty_tree(self):
        """Empty delegation parents should produce empty tree."""
        bridge = EATPBridge()
        tree = bridge.get_delegation_tree()
        assert tree == {}


# ---------------------------------------------------------------------------
# RT3-01: HookEnforcer and ShadowEnforcer envelope expiry checks
# ---------------------------------------------------------------------------


class TestRT3_01_HookEnforcerExpiryCheck:
    """RT3-01: HookEnforcer must BLOCK when envelope is expired."""

    def test_expired_envelope_returns_block(self):
        """Expired envelope should cause BLOCK verdict."""
        expired_envelope = _make_envelope(expires_at=datetime(2020, 12, 31, tzinfo=UTC))
        assert expired_envelope.is_expired

        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        enforcer = HookEnforcer(gradient_engine=engine, envelope=expired_envelope)
        result = enforcer.enforce(agent_id="agent-1", action="read-file")
        assert result.verdict == HookVerdict.BLOCK
        assert "expired" in result.reason.lower()

    def test_valid_envelope_still_allows(self):
        """Non-expired envelope should proceed normally."""
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)
        result = enforcer.enforce(agent_id="agent-1", action="read-file")
        assert result.verdict == HookVerdict.ALLOW


class TestRT3_01_ShadowEnforcerExpiryCheck:
    """RT3-01: ShadowEnforcer must report BLOCKED for expired envelope."""

    def test_expired_envelope_returns_blocked_shadow(self):
        """Expired envelope should produce a BLOCKED shadow result."""
        expired_envelope = _make_envelope(expires_at=datetime(2020, 12, 31, tzinfo=UTC))
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        shadow = ShadowEnforcer(gradient_engine=engine, envelope=expired_envelope)
        result = shadow.evaluate(action="read-file", agent_id="agent-1")
        assert result.would_be_blocked
        assert result.verification_level == VerificationLevel.BLOCKED
        assert "expiry" in result.dimension_results

    def test_expired_envelope_increments_blocked_metrics(self):
        """Expired envelope shadow result should count as blocked in metrics."""
        expired_envelope = _make_envelope(expires_at=datetime(2020, 12, 31, tzinfo=UTC))
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        shadow = ShadowEnforcer(gradient_engine=engine, envelope=expired_envelope)
        shadow.evaluate(action="read-file", agent_id="agent-1")
        metrics = shadow.get_metrics("agent-1")
        assert metrics.blocked_count == 1
        assert metrics.total_evaluations == 1


# ---------------------------------------------------------------------------
# RT3-10: HookEnforcer kwargs forwarding
# ---------------------------------------------------------------------------


class TestRT3_10_HookEnforcerKwargsForwarding:
    """RT3-10: HookEnforcer must forward kwargs to envelope evaluation."""

    def test_spend_amount_is_forwarded(self):
        """spend_amount should be forwarded to envelope.evaluate_action."""
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        # Spend within limit — should ALLOW
        result = enforcer.enforce(
            agent_id="agent-1",
            action="purchase",
            spend_amount=50.0,
        )
        assert result.verdict == HookVerdict.ALLOW

    def test_excessive_spend_triggers_block(self):
        """Spending above the envelope limit should trigger BLOCK or HOLD."""
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        envelope = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        # Spend above limit — should not be AUTO_APPROVED
        result = enforcer.enforce(
            agent_id="agent-1",
            action="purchase",
            spend_amount=5000.0,
        )
        assert result.verdict != HookVerdict.ALLOW


# ---------------------------------------------------------------------------
# RT10-DP1: ConstraintEnvelope is frozen (immutable after construction)
# ---------------------------------------------------------------------------


class TestRT10_DP1_FrozenEnvelope:
    """RT10-DP1: ConstraintEnvelope must be frozen to prevent post-creation
    constraint widening."""

    def test_envelope_config_field_is_immutable(self):
        """Cannot replace the config field on a frozen envelope."""
        envelope = _make_envelope()
        with pytest.raises(Exception):
            envelope.config = _make_envelope_config()

    def test_envelope_version_is_immutable(self):
        """Cannot change version after construction."""
        envelope = _make_envelope()
        with pytest.raises(Exception):
            envelope.version = 99

    def test_envelope_expires_at_is_immutable(self):
        """Cannot change expires_at after construction."""
        envelope = _make_envelope()
        with pytest.raises(Exception):
            envelope.expires_at = datetime(2020, 1, 1, tzinfo=UTC)

    def test_envelope_constructed_with_custom_expires_at(self):
        """Can pass expires_at at construction time."""
        future = datetime(2030, 6, 15, tzinfo=UTC)
        envelope = _make_envelope(expires_at=future)
        assert envelope.expires_at == future

    def test_envelope_default_expires_at_90_days(self):
        """Default expires_at is ~90 days from creation."""
        envelope = _make_envelope()
        assert envelope.expires_at is not None
        delta = envelope.expires_at - envelope.created_at
        assert 89 <= delta.days <= 91


# ---------------------------------------------------------------------------
# RT10-DP2: Cumulative spend persistence
# ---------------------------------------------------------------------------


class TestRT10_DP2_SpendPersistence:
    """RT10-DP2: Cumulative spend must survive restarts via TrustStore."""

    def test_spend_persisted_to_store(self):
        """Spend data is written to the store after an action with spend."""
        from care_platform.persistence.store import MemoryStore

        store = MemoryStore()
        envelope = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=10000.0),
        )
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        mw = VerificationMiddleware(
            gradient_engine=engine,
            envelope=envelope,
            spend_store=store,
        )
        mw.process_action(agent_id="agent-1", action="purchase", spend_amount=42.0)

        # Verify spend was persisted
        data = store.get_delegation("__cumulative_spend__")
        assert data is not None
        assert data["spends"]["agent-1"] == 42.0

    def test_spend_hydrated_on_startup(self):
        """New middleware instance loads persisted spend from store."""
        from care_platform.persistence.store import MemoryStore

        store = MemoryStore()
        # Pre-populate store with spend data
        store.store_delegation(
            "__cumulative_spend__",
            {"delegation_id": "__cumulative_spend__", "spends": {"agent-1": 500.0}},
        )

        envelope = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=10000.0),
        )
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )
        mw = VerificationMiddleware(
            gradient_engine=engine,
            envelope=envelope,
            spend_store=store,
        )
        # Internal spend should reflect persisted value
        assert mw._cumulative_spend.get("agent-1") == 500.0

    def test_spend_accumulates_across_simulated_restarts(self):
        """Spend accumulates correctly across middleware instances (simulated restart)."""
        from care_platform.persistence.store import MemoryStore

        store = MemoryStore()
        envelope = _make_envelope(
            financial=FinancialConstraintConfig(
                max_spend_usd=10000.0,
                api_cost_budget_usd=1000.0,
            ),
        )
        engine = _make_gradient_engine(
            GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
        )

        # First "session": spend 100
        mw1 = VerificationMiddleware(
            gradient_engine=engine,
            envelope=envelope,
            spend_store=store,
        )
        mw1.process_action(agent_id="agent-1", action="buy", spend_amount=100.0)

        # Second "session" (simulated restart): spend 200 more
        mw2 = VerificationMiddleware(
            gradient_engine=engine,
            envelope=envelope,
            spend_store=store,
        )
        mw2.process_action(agent_id="agent-1", action="buy", spend_amount=200.0)

        # Total should be 300
        data = store.get_delegation("__cumulative_spend__")
        assert data["spends"]["agent-1"] == 300.0


# ---------------------------------------------------------------------------
# RT10-DP3: Cache key includes envelope content hash
# ---------------------------------------------------------------------------


class TestRT10_DP3_CacheKeyEnvelopeHash:
    """RT10-DP3: Cache key must include envelope content hash so that
    tightened envelopes invalidate stale cached verdicts."""

    def test_cache_miss_after_envelope_change(self):
        """A cached verdict should not be served after the envelope changes."""
        cache = VerificationCache(max_size=100)
        env1 = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=1000.0),
        )
        env2 = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )

        # Cache a result for env1
        key1 = ("agent-1", "read", env1.content_hash())
        cache.put(
            key1,
            CachedVerification(
                trust_score=0.9,
                posture=TrustPostureLevel.DELEGATED,
                verification_result="AUTO_APPROVED",
            ),
            ttl_seconds=60.0,
        )

        # Look up with env2's hash — should miss
        key2 = ("agent-1", "read", env2.content_hash())
        assert cache.get(key2) is None

    def test_cache_hit_same_envelope(self):
        """A cached verdict should be served for the same envelope hash."""
        cache = VerificationCache(max_size=100)
        env = _make_envelope()

        key = ("agent-1", "read", env.content_hash())
        cached = CachedVerification(
            trust_score=0.9,
            posture=TrustPostureLevel.DELEGATED,
            verification_result="AUTO_APPROVED",
        )
        cache.put(key, cached, ttl_seconds=60.0)

        result = cache.get(key)
        assert result is not None
        assert result.verification_result == "AUTO_APPROVED"
