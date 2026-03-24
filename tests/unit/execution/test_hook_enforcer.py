# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for COC hook enforcer (Task 404)."""

import fnmatch

from pact_platform.build.config.schema import (
    VerificationLevel,
)
from pact_platform.use.execution.hook_enforcer import HookEnforcer, HookResult, HookVerdict


class _MockVerdict:
    """Minimal governance verdict for test mock."""

    def __init__(self, level: str, reason: str = "") -> None:
        self.level = level
        self.reason = reason


class _MockGovernanceEngine:
    """Mock GovernanceEngine for hook enforcer tests.

    Accepts a list of (pattern, level) pairs and a default_level.
    Matches action against patterns using fnmatch.
    """

    def __init__(
        self,
        rules: list[tuple[str, VerificationLevel]] | None = None,
        default_level: VerificationLevel = VerificationLevel.HELD,
    ) -> None:
        self._rules = rules or []
        self._default_level = default_level

    def verify_action(self, role_address: str, action: str, context=None) -> _MockVerdict:
        for pattern, level in self._rules:
            if fnmatch.fnmatch(action, pattern):
                return _MockVerdict(level.value.lower(), f"matched pattern {pattern!r}")
        return _MockVerdict(self._default_level.value.lower(), "default level")


def _make_enforcer(
    rules: list[tuple[str, VerificationLevel]] | None = None,
    default_level: VerificationLevel = VerificationLevel.HELD,
) -> HookEnforcer:
    """Helper to create a HookEnforcer with a mock governance engine."""
    engine = _MockGovernanceEngine(rules=rules, default_level=default_level)
    return HookEnforcer(governance_engine=engine, role_address="D1-R1")


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
        enforcer = _make_enforcer(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
        )

        result = enforcer.enforce(agent_id="agent-1", action="read_file")
        assert result.verdict == HookVerdict.ALLOW
        assert result.verification_level == "auto_approved"
        assert result.agent_id == "agent-1"
        assert result.action == "read_file"

    def test_flagged_maps_to_allow_but_logged(self):
        """FLAGGED verification level should produce ALLOW verdict but be logged."""
        enforcer = _make_enforcer(
            rules=[("write_*", VerificationLevel.FLAGGED)],
        )

        result = enforcer.enforce(agent_id="agent-1", action="write_config")
        assert result.verdict == HookVerdict.ALLOW
        assert result.verification_level == "flagged"
        # Should still be logged in enforcement log
        assert len(enforcer.enforcement_log) == 1

    def test_held_maps_to_hold(self):
        """HELD verification level should produce HOLD verdict."""
        enforcer = _make_enforcer(
            rules=[("deploy_*", VerificationLevel.HELD)],
        )

        result = enforcer.enforce(agent_id="agent-1", action="deploy_production")
        assert result.verdict == HookVerdict.HOLD
        assert result.verification_level == "held"

    def test_blocked_maps_to_block(self):
        """BLOCKED verification level should produce BLOCK verdict."""
        enforcer = _make_enforcer(
            rules=[("delete_*", VerificationLevel.BLOCKED)],
        )

        result = enforcer.enforce(agent_id="agent-1", action="delete_database")
        assert result.verdict == HookVerdict.BLOCK
        assert result.verification_level == "blocked"

    def test_no_governance_engine_blocks_failsafe(self):
        """Missing governance engine should produce BLOCK (fail-safe)."""
        enforcer = HookEnforcer(governance_engine=None, role_address="D1-R1")

        result = enforcer.enforce(agent_id="agent-1", action="any_action")
        assert result.verdict == HookVerdict.BLOCK
        assert "fail-safe" in result.reason.lower() or "not configured" in result.reason.lower()

    def test_no_role_address_blocks_failsafe(self):
        """Missing role_address should produce BLOCK (fail-safe)."""
        engine = _MockGovernanceEngine(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
        )
        enforcer = HookEnforcer(governance_engine=engine, role_address=None)

        result = enforcer.enforce(agent_id="agent-1", action="read_file")
        assert result.verdict == HookVerdict.BLOCK
        assert "fail-safe" in result.reason.lower() or "not configured" in result.reason.lower()

    def test_no_governance_and_no_role_blocks_failsafe(self):
        """Missing both governance engine and role_address should produce BLOCK (fail-safe)."""
        enforcer = HookEnforcer()

        result = enforcer.enforce(agent_id="agent-1", action="any_action")
        assert result.verdict == HookVerdict.BLOCK

    def test_enforcement_log_tracks_all_results(self):
        """All enforcement results should be tracked in the log."""
        enforcer = _make_enforcer(
            rules=[
                ("read_*", VerificationLevel.AUTO_APPROVED),
                ("write_*", VerificationLevel.FLAGGED),
                ("delete_*", VerificationLevel.BLOCKED),
            ],
        )

        enforcer.enforce(agent_id="agent-1", action="read_file")
        enforcer.enforce(agent_id="agent-1", action="write_config")
        enforcer.enforce(agent_id="agent-1", action="delete_db")

        assert len(enforcer.enforcement_log) == 3
        assert enforcer.enforcement_log[0].verdict == HookVerdict.ALLOW
        assert enforcer.enforcement_log[1].verdict == HookVerdict.ALLOW
        assert enforcer.enforcement_log[2].verdict == HookVerdict.BLOCK

    def test_stats_report_correct_counts(self):
        """Stats should accurately count verdicts."""
        enforcer = _make_enforcer(
            rules=[
                ("read_*", VerificationLevel.AUTO_APPROVED),
                ("write_*", VerificationLevel.FLAGGED),
                ("deploy_*", VerificationLevel.HELD),
                ("delete_*", VerificationLevel.BLOCKED),
            ],
        )

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
        """When no governance rule matches, the default level is used."""
        enforcer = _make_enforcer(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
            default_level=VerificationLevel.HELD,
        )

        # "unknown_action" matches no rule, so default HELD -> HOLD
        result = enforcer.enforce(agent_id="agent-1", action="unknown_action")
        assert result.verdict == HookVerdict.HOLD
        assert result.verification_level == "held"

    def test_enforcement_includes_timestamp(self):
        """Each HookResult should have a timestamp."""
        enforcer = _make_enforcer(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
        )

        result = enforcer.enforce(agent_id="agent-1", action="read_file")
        assert result.timestamp is not None

    def test_enforcement_with_resource_kwarg(self):
        """Enforce should accept a resource keyword argument."""
        enforcer = _make_enforcer(
            rules=[("read_*", VerificationLevel.AUTO_APPROVED)],
        )

        # Should not raise
        result = enforcer.enforce(
            agent_id="agent-1",
            action="read_file",
            resource="/path/to/file",
        )
        assert result.verdict == HookVerdict.ALLOW
