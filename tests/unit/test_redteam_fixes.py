# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for red team findings RT-14, RT-25, RT-29, RT-30, RT-31, RT-34.

Each test class corresponds to a specific red team finding and validates
the behavioral change introduced by the fix.
"""

import pytest

from care_platform.audit.anchor import AuditChain
from care_platform.config.schema import (
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.envelope import ConstraintEnvelope
from care_platform.constraint.gradient import GradientEngine
from care_platform.constraint.middleware import ActionOutcome, VerificationMiddleware
from care_platform.constraint.verification_level import (
    VerificationThoroughness,
    select_verification_level,
)
from care_platform.trust.credentials import CredentialManager
from care_platform.trust.posture import (
    UPGRADE_REQUIREMENTS,
    PostureEvidence,
    TrustPosture,
)
from care_platform.trust.revocation import RevocationManager
from care_platform.trust.shadow_enforcer import ShadowEnforcer


# ---------------------------------------------------------------------------
# RT-14: Wire cascade revocation into EATP bridge
# ---------------------------------------------------------------------------


class _FakeBridge:
    """Minimal stand-in for EATPBridge to track revoke_agent calls."""

    def __init__(self):
        self._revoked_agents: set[str] = set()

    def revoke_agent(self, agent_id: str) -> None:
        self._revoked_agents.add(agent_id)


class TestRT14RevocationBridgeWiring:
    """RT-14: RevocationManager must propagate revocations to EATP bridge."""

    def test_surgical_revoke_calls_bridge(self):
        bridge = _FakeBridge()
        mgr = RevocationManager(eatp_bridge=bridge)
        mgr.surgical_revoke("agent-a", "test reason", "admin-1")
        assert "agent-a" in bridge._revoked_agents

    def test_cascade_revoke_calls_bridge_for_all(self):
        bridge = _FakeBridge()
        mgr = RevocationManager(eatp_bridge=bridge)
        mgr.register_delegation("agent-a", "agent-b")
        mgr.register_delegation("agent-b", "agent-c")
        mgr.cascade_revoke("agent-a", "cascade test", "admin-1")
        assert "agent-a" in bridge._revoked_agents
        assert "agent-b" in bridge._revoked_agents
        assert "agent-c" in bridge._revoked_agents

    def test_no_bridge_does_not_error(self):
        """When no bridge is configured, revocation still works."""
        mgr = RevocationManager()
        record = mgr.surgical_revoke("agent-a", "no bridge", "admin-1")
        assert record.agent_id == "agent-a"

    def test_cascade_siblings_not_revoked_in_bridge(self):
        bridge = _FakeBridge()
        mgr = RevocationManager(eatp_bridge=bridge)
        mgr.register_delegation("root", "agent-a")
        mgr.register_delegation("root", "agent-b")
        mgr.cascade_revoke("agent-a", "sibling test", "admin-1")
        assert "agent-a" in bridge._revoked_agents
        assert "agent-b" not in bridge._revoked_agents


# ---------------------------------------------------------------------------
# RT-25: Fix PSEUDO_AGENT dead end
# ---------------------------------------------------------------------------


class TestRT25PseudoAgentUpgrade:
    """RT-25: PSEUDO_AGENT must have a defined upgrade path to SUPERVISED."""

    def test_supervised_upgrade_requirements_exist(self):
        assert TrustPostureLevel.SUPERVISED in UPGRADE_REQUIREMENTS
        reqs = UPGRADE_REQUIREMENTS[TrustPostureLevel.SUPERVISED]
        assert reqs["min_days"] == 7
        assert reqs["min_operations"] == 10
        assert reqs["min_success_rate"] == 0.90
        assert reqs["max_incidents"] == 0

    def test_pseudo_agent_can_upgrade_with_evidence(self):
        posture = TrustPosture(
            agent_id="agent-new",
            current_level=TrustPostureLevel.PSEUDO_AGENT,
        )
        evidence = PostureEvidence(
            successful_operations=15,
            total_operations=15,
            days_at_current_posture=10,
            incidents=0,
        )
        can, reason = posture.can_upgrade(evidence)
        assert can, f"Expected upgrade eligibility but got: {reason}"

    def test_pseudo_agent_upgrade_blocked_insufficient_days(self):
        posture = TrustPosture(
            agent_id="agent-new",
            current_level=TrustPostureLevel.PSEUDO_AGENT,
        )
        evidence = PostureEvidence(
            successful_operations=15,
            total_operations=15,
            days_at_current_posture=3,  # less than 7
            incidents=0,
        )
        can, reason = posture.can_upgrade(evidence)
        assert not can
        assert "days" in reason.lower()

    def test_pseudo_agent_upgrade_blocked_insufficient_ops(self):
        posture = TrustPosture(
            agent_id="agent-new",
            current_level=TrustPostureLevel.PSEUDO_AGENT,
        )
        evidence = PostureEvidence(
            successful_operations=5,
            total_operations=5,
            days_at_current_posture=10,
            incidents=0,
        )
        can, reason = posture.can_upgrade(evidence)
        assert not can
        assert "operations" in reason.lower()

    def test_pseudo_agent_upgrade_changes_to_supervised(self):
        posture = TrustPosture(
            agent_id="agent-new",
            current_level=TrustPostureLevel.PSEUDO_AGENT,
        )
        evidence = PostureEvidence(
            successful_operations=15,
            total_operations=15,
            days_at_current_posture=10,
            incidents=0,
        )
        posture.upgrade(evidence)
        assert posture.current_level == TrustPostureLevel.SUPERVISED


# ---------------------------------------------------------------------------
# RT-29: Fix ShadowEnforcer incident mapping
# ---------------------------------------------------------------------------


def _make_envelope(**kwargs):
    return ConstraintEnvelope(
        config=ConstraintEnvelopeConfig(
            id="test-envelope",
            financial=FinancialConstraintConfig(max_spend_usd=kwargs.get("max_spend", 1000.0)),
            operational=OperationalConstraintConfig(
                blocked_actions=kwargs.get("blocked_actions", []),
            ),
        ),
    )


def _make_gradient(default_level=VerificationLevel.HELD, rules=None):
    return GradientEngine(
        config=VerificationGradientConfig(
            rules=rules or [],
            default_level=default_level,
        ),
    )


class TestRT29ShadowIncidentMapping:
    """RT-29: ShadowEnforcer blocked_count maps to shadow_blocked_count, NOT incidents."""

    def test_blocked_maps_to_shadow_blocked_count(self):
        gradient = _make_gradient(default_level=VerificationLevel.BLOCKED)
        enforcer = ShadowEnforcer(gradient_engine=gradient, envelope=_make_envelope())
        enforcer.evaluate("bad_action", "agent-1")
        enforcer.evaluate("bad_action_2", "agent-1")
        evidence = enforcer.to_posture_evidence("agent-1")
        assert evidence.shadow_blocked_count == 2
        assert evidence.incidents == 0  # NOT blocked_count

    def test_shadow_blocked_does_not_block_upgrade(self):
        """shadow_blocked_count is informational and should not prevent upgrades."""
        posture = TrustPosture(
            agent_id="agent-1",
            current_level=TrustPostureLevel.PSEUDO_AGENT,
        )
        evidence = PostureEvidence(
            successful_operations=15,
            total_operations=15,
            days_at_current_posture=10,
            incidents=0,
            shadow_blocked_count=5,  # informational only
        )
        can, reason = posture.can_upgrade(evidence)
        assert can, f"shadow_blocked_count should not block upgrade: {reason}"

    def test_real_incidents_still_block_upgrade(self):
        """Real incidents (not shadow) must still block upgrades."""
        posture = TrustPosture(
            agent_id="agent-1",
            current_level=TrustPostureLevel.PSEUDO_AGENT,
        )
        evidence = PostureEvidence(
            successful_operations=15,
            total_operations=15,
            days_at_current_posture=10,
            incidents=1,  # real incident
            shadow_blocked_count=0,
        )
        can, reason = posture.can_upgrade(evidence)
        assert not can
        assert "incidents" in reason.lower()


# ---------------------------------------------------------------------------
# RT-30: Emergency halt mechanism
# ---------------------------------------------------------------------------


class TestRT30EmergencyHalt:
    """RT-30: VerificationMiddleware must support emergency halt."""

    def _make_middleware(self):
        gradient = _make_gradient(
            default_level=VerificationLevel.AUTO_APPROVED,
            rules=[GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED)],
        )
        envelope = _make_envelope()
        return VerificationMiddleware(gradient_engine=gradient, envelope=envelope)

    def test_halt_blocks_all_actions(self):
        mw = self._make_middleware()
        mw.halt("Security breach detected")
        result = mw.process_action(agent_id="agent-1", action="read_data")
        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED
        assert "halted" in result.details.lower()

    def test_resume_allows_actions(self):
        mw = self._make_middleware()
        mw.halt("Temporary issue")
        mw.resume()
        result = mw.process_action(agent_id="agent-1", action="read_data")
        assert result.outcome == ActionOutcome.EXECUTED

    def test_halt_requires_reason(self):
        mw = self._make_middleware()
        with pytest.raises(ValueError, match="reason"):
            mw.halt("")

    def test_halt_state_persists_across_actions(self):
        mw = self._make_middleware()
        mw.halt("Lockdown")
        r1 = mw.process_action(agent_id="agent-1", action="action1")
        r2 = mw.process_action(agent_id="agent-2", action="action2")
        assert r1.outcome == ActionOutcome.REJECTED
        assert r2.outcome == ActionOutcome.REJECTED

    def test_resume_when_not_halted_is_noop(self):
        mw = self._make_middleware()
        mw.resume()  # should not raise
        result = mw.process_action(agent_id="agent-1", action="read_data")
        assert result.outcome == ActionOutcome.EXECUTED


# ---------------------------------------------------------------------------
# RT-31: Fix duplicate VerificationLevel enums
# ---------------------------------------------------------------------------


class TestRT31VerificationThoroughness:
    """RT-31: VerificationThoroughness is canonical, no duplicate enums."""

    def test_verification_thoroughness_from_verification_level_module(self):
        """VerificationThoroughness should be importable from verification_level."""
        assert VerificationThoroughness.QUICK.value == "quick"
        assert VerificationThoroughness.STANDARD.value == "standard"
        assert VerificationThoroughness.FULL.value == "full"

    def test_select_verification_level_returns_thoroughness(self):
        result = select_verification_level(
            action_type="test",
            cache_hit=True,
            is_cross_team=False,
            is_first_action=False,
        )
        assert isinstance(result, VerificationThoroughness)
        assert result == VerificationThoroughness.QUICK

    def test_gradient_uses_same_thoroughness(self):
        """GradientEngine must use the same VerificationThoroughness class."""
        from care_platform.constraint.gradient import (
            VerificationThoroughness as GradientVT,
        )

        assert GradientVT is VerificationThoroughness


# ---------------------------------------------------------------------------
# RT-34: Confidentiality-aware audit export
# ---------------------------------------------------------------------------


class TestRT34AuditRedaction:
    """RT-34: AuditChain.export(redact_metadata=True) redacts sensitive keys."""

    def test_redact_reason_key(self):
        chain = AuditChain(chain_id="redact-test")
        chain.append(
            "agent-1",
            "action",
            VerificationLevel.FLAGGED,
            metadata={"reason": "Near financial boundary", "approver_id": "human-1"},
        )
        exported = chain.export(redact_metadata=True)
        assert len(exported) == 1
        assert exported[0]["metadata"]["reason"] == "[REDACTED]"
        assert exported[0]["metadata"]["approver_id"] == "human-1"

    def test_remove_token_key(self):
        chain = AuditChain(chain_id="redact-test")
        chain.append(
            "agent-1",
            "action",
            VerificationLevel.AUTO_APPROVED,
            metadata={"auth_token": "abc123", "agent_name": "worker"},
        )
        exported = chain.export(redact_metadata=True)
        assert "auth_token" not in exported[0]["metadata"]
        assert exported[0]["metadata"]["agent_name"] == "worker"

    def test_remove_secret_key(self):
        chain = AuditChain(chain_id="redact-test")
        chain.append(
            "agent-1",
            "action",
            VerificationLevel.AUTO_APPROVED,
            metadata={"api_secret": "xyz", "status": "ok"},
        )
        exported = chain.export(redact_metadata=True)
        assert "api_secret" not in exported[0]["metadata"]
        assert exported[0]["metadata"]["status"] == "ok"

    def test_no_redaction_by_default(self):
        chain = AuditChain(chain_id="redact-test")
        chain.append(
            "agent-1",
            "action",
            VerificationLevel.FLAGGED,
            metadata={"reason": "test", "auth_token": "abc"},
        )
        exported = chain.export()
        assert exported[0]["metadata"]["reason"] == "test"
        assert exported[0]["metadata"]["auth_token"] == "abc"

    def test_redact_with_rejection_reason(self):
        chain = AuditChain(chain_id="redact-test")
        chain.append(
            "agent-1",
            "action",
            VerificationLevel.HELD,
            metadata={"rejection_reason": "Policy violation", "request_id": "req-1"},
        )
        exported = chain.export(redact_metadata=True)
        assert exported[0]["metadata"]["rejection_reason"] == "[REDACTED]"
        assert exported[0]["metadata"]["request_id"] == "req-1"
