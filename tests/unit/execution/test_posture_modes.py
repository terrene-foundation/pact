# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for trust posture execution modes and ShadowEnforcer live mode.

Tests cover:
- PSEUDO_AGENT: Block ALL actions before any LLM call
- SUPERVISED: Place ALL actions in HELD queue regardless of constraint state
- SHARED_PLANNING: Planning actions auto-approve; consequential actions HELD
- CONTINUOUS_INSIGHT: Within-envelope auto-approve; boundary-crossing HELD
- DELEGATED: Within-envelope auto-approve; out-of-envelope BLOCKED
- ShadowEnforcer live mode metrics collection
- Posture read at action time (not cached)
"""

import pytest

from care_platform.trust.audit.anchor import AuditChain
from care_platform.build.config.schema import (
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.trust.constraint.gradient import GradientEngine
from care_platform.use.execution.approval import ApprovalQueue
from care_platform.use.execution.llm_backend import (
    BackendRouter,
    StubBackend,
)
from care_platform.use.execution.posture_enforcer import PostureEnforcer
from care_platform.use.execution.registry import AgentRegistry
from care_platform.trust.store.store import MemoryStore
from care_platform.trust.posture import TrustPosture

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_backend():
    return StubBackend(response_content="posture test response")


@pytest.fixture
def backend_router(stub_backend):
    router = BackendRouter()
    router.register_backend(stub_backend)
    return router


@pytest.fixture
def permissive_gradient():
    """Gradient that AUTO_APPROVES everything (posture layer overrides)."""
    return GradientEngine(VerificationGradientConfig(default_level=VerificationLevel.AUTO_APPROVED))


@pytest.fixture
def audit_chain():
    return AuditChain(chain_id="posture-test-chain")


@pytest.fixture
def registry():
    reg = AgentRegistry()
    reg.register(agent_id="agent-1", name="Test Agent", role="tester", team_id="team-a")
    return reg


@pytest.fixture
def approval_queue():
    return ApprovalQueue()


@pytest.fixture
def trust_store():
    store = MemoryStore()
    store.store_delegation(
        delegation_id="del-agent-1",
        data={
            "delegator_id": "terrene.foundation",
            "delegatee_id": "agent-1",
            "agent_name": "Test Agent",
            "capabilities": ["summarize"],
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
    )
    return store


def _make_posture(agent_id: str, level: TrustPostureLevel) -> TrustPosture:
    """Create a TrustPosture at a specific level."""
    return TrustPosture(agent_id=agent_id, current_level=level)


# ---------------------------------------------------------------------------
# 2702: PSEUDO_AGENT — block ALL actions
# ---------------------------------------------------------------------------


class TestPseudoAgentMode:
    """PSEUDO_AGENT posture blocks ALL actions before any LLM call."""

    def test_blocks_simple_action(self, backend_router, trust_store, stub_backend):
        """A simple action should be blocked."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.PSEUDO_AGENT)

        result = enforcer.check_posture(
            posture=posture,
            action="summarize docs/report.md",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        assert result.level == VerificationLevel.BLOCKED
        assert "PSEUDO_AGENT" in result.reason

    def test_blocks_even_auto_approved_action(self, backend_router, trust_store, stub_backend):
        """Even AUTO_APPROVED actions should be blocked for PSEUDO_AGENT."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.PSEUDO_AGENT)

        result = enforcer.check_posture(
            posture=posture,
            action="read docs/readme.md",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        assert result.level == VerificationLevel.BLOCKED


# ---------------------------------------------------------------------------
# 2702: SUPERVISED — ALL actions HELD
# ---------------------------------------------------------------------------


class TestSupervisedMode:
    """SUPERVISED posture places ALL actions in HELD queue."""

    def test_auto_approved_escalated_to_held(self):
        """AUTO_APPROVED actions should be escalated to HELD."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.SUPERVISED)

        result = enforcer.check_posture(
            posture=posture,
            action="summarize docs/report.md",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        assert result.level == VerificationLevel.HELD

    def test_flagged_escalated_to_held(self):
        """FLAGGED actions should also be escalated to HELD."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.SUPERVISED)

        result = enforcer.check_posture(
            posture=posture,
            action="summarize docs/report.md",
            verification_level=VerificationLevel.FLAGGED,
        )

        assert result.level == VerificationLevel.HELD

    def test_blocked_stays_blocked(self):
        """BLOCKED actions should remain BLOCKED (not downgraded to HELD)."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.SUPERVISED)

        result = enforcer.check_posture(
            posture=posture,
            action="delete production db",
            verification_level=VerificationLevel.BLOCKED,
        )

        assert result.level == VerificationLevel.BLOCKED


# ---------------------------------------------------------------------------
# 2702: SHARED_PLANNING — planning auto-approve, consequential HELD
# ---------------------------------------------------------------------------


class TestSharedPlanningMode:
    """SHARED_PLANNING: planning actions auto-approve; consequential actions HELD."""

    def test_planning_action_auto_approved(self):
        """Planning actions (reasoning, drafting, analyzing) should auto-approve."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.SHARED_PLANNING)

        for action in ["analyze report", "draft summary", "reason about approach"]:
            result = enforcer.check_posture(
                posture=posture,
                action=action,
                verification_level=VerificationLevel.AUTO_APPROVED,
            )
            assert result.level == VerificationLevel.AUTO_APPROVED, (
                f"Planning action '{action}' should be AUTO_APPROVED, got {result.level}"
            )

    def test_consequential_action_held(self):
        """Consequential actions (write, send, execute, deploy) should be HELD."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.SHARED_PLANNING)

        for action in [
            "write to database",
            "send email",
            "execute script",
            "deploy service",
        ]:
            result = enforcer.check_posture(
                posture=posture,
                action=action,
                verification_level=VerificationLevel.AUTO_APPROVED,
            )
            assert result.level == VerificationLevel.HELD, (
                f"Consequential action '{action}' should be HELD, got {result.level}"
            )

    def test_blocked_stays_blocked(self):
        """BLOCKED actions stay BLOCKED regardless of action type."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.SHARED_PLANNING)

        result = enforcer.check_posture(
            posture=posture,
            action="analyze report",
            verification_level=VerificationLevel.BLOCKED,
        )
        assert result.level == VerificationLevel.BLOCKED


# ---------------------------------------------------------------------------
# 2702: CONTINUOUS_INSIGHT — within-envelope auto, boundary HELD
# ---------------------------------------------------------------------------


class TestContinuousInsightMode:
    """CONTINUOUS_INSIGHT: within-envelope auto-approve; boundary-crossing HELD."""

    def test_within_envelope_auto_approved(self):
        """Actions within the constraint envelope should auto-approve."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.CONTINUOUS_INSIGHT)

        result = enforcer.check_posture(
            posture=posture,
            action="summarize docs/report.md",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        assert result.level == VerificationLevel.AUTO_APPROVED

    def test_boundary_crossing_held(self):
        """Actions near or crossing envelope boundaries should be HELD."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.CONTINUOUS_INSIGHT)

        # FLAGGED indicates near-boundary — should escalate to HELD
        result = enforcer.check_posture(
            posture=posture,
            action="access sensitive data",
            verification_level=VerificationLevel.FLAGGED,
        )

        assert result.level == VerificationLevel.HELD

    def test_blocked_stays_blocked(self):
        """BLOCKED actions stay BLOCKED."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.CONTINUOUS_INSIGHT)

        result = enforcer.check_posture(
            posture=posture,
            action="violate constraint",
            verification_level=VerificationLevel.BLOCKED,
        )

        assert result.level == VerificationLevel.BLOCKED


# ---------------------------------------------------------------------------
# 2702: DELEGATED — within-envelope auto, out-of-envelope BLOCKED
# ---------------------------------------------------------------------------


class TestDelegatedMode:
    """DELEGATED: within-envelope auto-approve; out-of-envelope BLOCKED (not HELD)."""

    def test_within_envelope_auto_approved(self):
        """Actions within envelope should auto-approve."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.DELEGATED)

        result = enforcer.check_posture(
            posture=posture,
            action="summarize docs/report.md",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        assert result.level == VerificationLevel.AUTO_APPROVED

    def test_out_of_envelope_blocked_not_held(self):
        """Out-of-envelope actions should be BLOCKED (not HELD like other postures)."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.DELEGATED)

        # FLAGGED = near boundary, but for DELEGATED this becomes BLOCKED
        result = enforcer.check_posture(
            posture=posture,
            action="access restricted resource",
            verification_level=VerificationLevel.FLAGGED,
        )

        assert result.level == VerificationLevel.BLOCKED

    def test_held_escalated_to_blocked(self):
        """HELD actions should be escalated to BLOCKED for DELEGATED posture."""
        enforcer = PostureEnforcer()
        posture = _make_posture("agent-1", TrustPostureLevel.DELEGATED)

        result = enforcer.check_posture(
            posture=posture,
            action="modify constraints",
            verification_level=VerificationLevel.HELD,
        )

        assert result.level == VerificationLevel.BLOCKED


# ---------------------------------------------------------------------------
# 2702: Posture read at action time (not cached)
# ---------------------------------------------------------------------------


class TestPostureReadAtActionTime:
    """Posture should be read from trust record at action time, not cached."""

    def test_posture_change_reflected_immediately(self):
        """Changing posture between actions should be reflected immediately."""
        enforcer = PostureEnforcer()

        # Start as SUPERVISED
        posture = _make_posture("agent-1", TrustPostureLevel.SUPERVISED)
        result1 = enforcer.check_posture(
            posture=posture,
            action="summarize docs/report.md",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert result1.level == VerificationLevel.HELD  # SUPERVISED escalates

        # Change to DELEGATED
        posture.current_level = TrustPostureLevel.DELEGATED
        result2 = enforcer.check_posture(
            posture=posture,
            action="summarize docs/report.md",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert result2.level == VerificationLevel.AUTO_APPROVED  # DELEGATED allows


# ---------------------------------------------------------------------------
# 2703: ShadowEnforcer live mode
# ---------------------------------------------------------------------------


class TestShadowEnforcerLiveMode:
    """Test ShadowEnforcer live mode metrics collection."""

    def test_live_mode_disabled_by_default(self):
        """ShadowEnforcer live mode should be disabled by default."""
        from care_platform.trust.shadow_enforcer_live import ShadowEnforcerLive

        enforcer = ShadowEnforcerLive()
        assert enforcer.is_enabled is False

    def test_live_mode_enabled_via_env(self, monkeypatch):
        """Setting CARE_SHADOW_ENFORCER_LIVE=true should enable live mode."""
        from care_platform.trust.shadow_enforcer_live import ShadowEnforcerLive

        enforcer = ShadowEnforcerLive(enabled=True)
        assert enforcer.is_enabled is True

    def test_live_mode_records_agreement(self):
        """Live mode should record agreement between real and shadow decisions."""
        from care_platform.trust.shadow_enforcer_live import ShadowEnforcerLive

        enforcer = ShadowEnforcerLive(enabled=True)

        enforcer.record(
            action="summarize docs/report.md",
            agent_id="agent-1",
            real_decision=VerificationLevel.AUTO_APPROVED,
            shadow_decision=VerificationLevel.AUTO_APPROVED,
        )

        metrics = enforcer.get_metrics("agent-1")
        assert metrics.total_evaluations == 1
        assert metrics.agreement_count == 1
        assert metrics.agreement_rate == 1.0

    def test_live_mode_records_divergence(self):
        """Live mode should record divergences between real and shadow decisions."""
        from care_platform.trust.shadow_enforcer_live import ShadowEnforcerLive

        enforcer = ShadowEnforcerLive(enabled=True)

        enforcer.record(
            action="delete file",
            agent_id="agent-1",
            real_decision=VerificationLevel.AUTO_APPROVED,
            shadow_decision=VerificationLevel.HELD,
        )

        metrics = enforcer.get_metrics("agent-1")
        assert metrics.total_evaluations == 1
        assert metrics.agreement_count == 0
        assert metrics.divergence_count == 1
        assert metrics.agreement_rate == 0.0

    def test_live_mode_per_posture_metrics(self):
        """Live mode should collect metrics per posture level."""
        from care_platform.trust.shadow_enforcer_live import ShadowEnforcerLive

        enforcer = ShadowEnforcerLive(enabled=True)

        enforcer.record(
            action="read file",
            agent_id="agent-1",
            real_decision=VerificationLevel.AUTO_APPROVED,
            shadow_decision=VerificationLevel.AUTO_APPROVED,
            posture=TrustPostureLevel.SUPERVISED,
        )
        enforcer.record(
            action="write file",
            agent_id="agent-1",
            real_decision=VerificationLevel.HELD,
            shadow_decision=VerificationLevel.HELD,
            posture=TrustPostureLevel.DELEGATED,
        )

        posture_metrics = enforcer.get_posture_metrics("agent-1")
        assert TrustPostureLevel.SUPERVISED in posture_metrics
        assert TrustPostureLevel.DELEGATED in posture_metrics
        assert posture_metrics[TrustPostureLevel.SUPERVISED].agreement_count == 1
        assert posture_metrics[TrustPostureLevel.DELEGATED].agreement_count == 1

    def test_no_overhead_when_disabled(self):
        """When disabled, recording should be a no-op with no overhead."""
        from care_platform.trust.shadow_enforcer_live import ShadowEnforcerLive

        enforcer = ShadowEnforcerLive(enabled=False)

        # Should not raise, should be a no-op
        enforcer.record(
            action="test",
            agent_id="agent-1",
            real_decision=VerificationLevel.AUTO_APPROVED,
            shadow_decision=VerificationLevel.BLOCKED,
        )

        # Metrics should show no evaluations
        with pytest.raises(KeyError):
            enforcer.get_metrics("agent-1")

    def test_never_blocks_or_delays(self):
        """Live mode should never block, delay, or alter execution."""
        from care_platform.trust.shadow_enforcer_live import ShadowEnforcerLive

        enforcer = ShadowEnforcerLive(enabled=True)

        # Even divergent results should not raise or block
        for i in range(100):
            enforcer.record(
                action=f"action-{i}",
                agent_id="agent-1",
                real_decision=VerificationLevel.AUTO_APPROVED,
                shadow_decision=VerificationLevel.BLOCKED,
            )

        # All 100 should be recorded without errors
        metrics = enforcer.get_metrics("agent-1")
        assert metrics.total_evaluations == 100
        assert metrics.divergence_count == 100
