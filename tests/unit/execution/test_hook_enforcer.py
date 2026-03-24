# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for COC hook enforcer (Task 404)."""

from pact_platform.build.config.schema import (
    ConstraintEnvelopeConfig,
    GradientRuleConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from pact_platform.trust.constraint.envelope import ConstraintEnvelope
from pact_platform.trust.constraint.gradient import GradientEngine
from pact_platform.use.execution.hook_enforcer import HookEnforcer, HookResult, HookVerdict


def _make_gradient_engine(
    rules: list[tuple[str, VerificationLevel]] | None = None,
    default_level: VerificationLevel = VerificationLevel.HELD,
) -> GradientEngine:
    """Helper to create a GradientEngine with given rules."""
    gradient_rules = []
    if rules:
        for pattern, level in rules:
            gradient_rules.append(GradientRuleConfig(pattern=pattern, level=level))
    config = VerificationGradientConfig(rules=gradient_rules, default_level=default_level)
    return GradientEngine(config)


def _make_envelope() -> ConstraintEnvelope:
    """Helper to create a basic constraint envelope."""
    return ConstraintEnvelope(
        config=ConstraintEnvelopeConfig(
            id="test-envelope",
            description="Test envelope for hook enforcer tests",
        )
    )


class TestHookVerdict:
    """Test HookVerdict enum values."""

    def test_verdict_values(self):
        assert HookVerdict.ALLOW == "allow"
        assert HookVerdict.BLOCK == "block"
        assert HookVerdict.HOLD == "hold"


class TestHookResult:
    """Test HookResult model."""

    def test_result_fields(self):
        result = HookResult(
            verdict=HookVerdict.ALLOW,
            reason="Auto-approved",
            verification_level="AUTO_APPROVED",
            agent_id="agent-1",
            action="read_file",
        )
        assert result.verdict == HookVerdict.ALLOW
        assert result.reason == "Auto-approved"
        assert result.verification_level == "AUTO_APPROVED"
        assert result.agent_id == "agent-1"
        assert result.action == "read_file"
        assert result.timestamp is not None

    def test_result_defaults(self):
        result = HookResult(verdict=HookVerdict.BLOCK)
        assert result.reason == ""
        assert result.verification_level == ""
        assert result.agent_id == ""
        assert result.action == ""


class TestHookEnforcer:
    """Test HookEnforcer enforcement logic."""

    def test_auto_approved_maps_to_allow(self):
        """AUTO_APPROVED verification level should produce ALLOW verdict."""
        engine = _make_gradient_engine(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        result = enforcer.enforce(agent_id="agent-1", action="read_file")
        assert result.verdict == HookVerdict.ALLOW
        assert result.verification_level == "AUTO_APPROVED"
        assert result.agent_id == "agent-1"
        assert result.action == "read_file"

    def test_flagged_maps_to_allow_but_logged(self):
        """FLAGGED verification level should produce ALLOW verdict but be logged."""
        engine = _make_gradient_engine(
            rules=[("write_*", VerificationLevel.FLAGGED)],
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        result = enforcer.enforce(agent_id="agent-1", action="write_config")
        assert result.verdict == HookVerdict.ALLOW
        assert result.verification_level == "FLAGGED"
        # Should still be logged in enforcement log
        assert len(enforcer.enforcement_log) == 1

    def test_held_maps_to_hold(self):
        """HELD verification level should produce HOLD verdict."""
        engine = _make_gradient_engine(
            rules=[("deploy_*", VerificationLevel.HELD)],
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        result = enforcer.enforce(agent_id="agent-1", action="deploy_production")
        assert result.verdict == HookVerdict.HOLD
        assert result.verification_level == "HELD"

    def test_blocked_maps_to_block(self):
        """BLOCKED verification level should produce BLOCK verdict."""
        engine = _make_gradient_engine(
            rules=[("delete_*", VerificationLevel.BLOCKED)],
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        result = enforcer.enforce(agent_id="agent-1", action="delete_database")
        assert result.verdict == HookVerdict.BLOCK
        assert result.verification_level == "BLOCKED"

    def test_no_gradient_engine_blocks_failsafe(self):
        """Missing gradient engine should produce BLOCK (fail-safe)."""
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=None, envelope=envelope)

        result = enforcer.enforce(agent_id="agent-1", action="any_action")
        assert result.verdict == HookVerdict.BLOCK
        assert "fail-safe" in result.reason.lower() or "not configured" in result.reason.lower()

    def test_no_envelope_blocks_failsafe(self):
        """Missing envelope should produce BLOCK (fail-safe)."""
        engine = _make_gradient_engine(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
        )
        enforcer = HookEnforcer(gradient_engine=engine, envelope=None)

        result = enforcer.enforce(agent_id="agent-1", action="read_file")
        assert result.verdict == HookVerdict.BLOCK
        assert "fail-safe" in result.reason.lower() or "not configured" in result.reason.lower()

    def test_no_gradient_and_no_envelope_blocks_failsafe(self):
        """Missing both gradient engine and envelope should produce BLOCK (fail-safe)."""
        enforcer = HookEnforcer()

        result = enforcer.enforce(agent_id="agent-1", action="any_action")
        assert result.verdict == HookVerdict.BLOCK

    def test_enforcement_log_tracks_all_results(self):
        """All enforcement results should be tracked in the log."""
        engine = _make_gradient_engine(
            rules=[
                ("read_*", VerificationLevel.AUTO_APPROVED),
                ("write_*", VerificationLevel.FLAGGED),
                ("delete_*", VerificationLevel.BLOCKED),
            ],
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        enforcer.enforce(agent_id="agent-1", action="read_file")
        enforcer.enforce(agent_id="agent-1", action="write_config")
        enforcer.enforce(agent_id="agent-1", action="delete_db")

        assert len(enforcer.enforcement_log) == 3
        assert enforcer.enforcement_log[0].verdict == HookVerdict.ALLOW
        assert enforcer.enforcement_log[1].verdict == HookVerdict.ALLOW
        assert enforcer.enforcement_log[2].verdict == HookVerdict.BLOCK

    def test_stats_report_correct_counts(self):
        """Stats should accurately count verdicts."""
        engine = _make_gradient_engine(
            rules=[
                ("read_*", VerificationLevel.AUTO_APPROVED),
                ("write_*", VerificationLevel.FLAGGED),
                ("deploy_*", VerificationLevel.HELD),
                ("delete_*", VerificationLevel.BLOCKED),
            ],
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        enforcer.enforce(agent_id="agent-1", action="read_file")
        enforcer.enforce(agent_id="agent-1", action="read_config")
        enforcer.enforce(agent_id="agent-1", action="write_log")
        enforcer.enforce(agent_id="agent-1", action="deploy_staging")
        enforcer.enforce(agent_id="agent-1", action="delete_temp")

        stats = enforcer.get_stats()
        assert stats["total"] == 5
        assert stats["allow"] == 3  # 2 auto_approved + 1 flagged
        assert stats["hold"] == 1
        assert stats["block"] == 1

    def test_stats_empty_when_no_enforcements(self):
        """Stats on empty enforcer should show zero counts."""
        enforcer = HookEnforcer()
        stats = enforcer.get_stats()
        assert stats["total"] == 0
        assert stats["allow"] == 0
        assert stats["hold"] == 0
        assert stats["block"] == 0

    def test_default_level_used_when_no_rule_matches(self):
        """When no gradient rule matches, the default level is used."""
        engine = _make_gradient_engine(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
            default_level=VerificationLevel.HELD,
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        # "unknown_action" matches no rule, so default HELD -> HOLD
        result = enforcer.enforce(agent_id="agent-1", action="unknown_action")
        assert result.verdict == HookVerdict.HOLD
        assert result.verification_level == "HELD"

    def test_enforcement_includes_timestamp(self):
        """Each HookResult should have a timestamp."""
        engine = _make_gradient_engine(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        result = enforcer.enforce(agent_id="agent-1", action="read_file")
        assert result.timestamp is not None

    def test_enforcement_with_resource_kwarg(self):
        """Enforce should accept a resource keyword argument."""
        engine = _make_gradient_engine(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
        )
        envelope = _make_envelope()
        enforcer = HookEnforcer(gradient_engine=engine, envelope=envelope)

        # Should not raise
        result = enforcer.enforce(
            agent_id="agent-1",
            action="read_file",
            resource="/path/to/file",
        )
        assert result.verdict == HookVerdict.ALLOW
