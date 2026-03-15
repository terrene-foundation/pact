# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for trust posture model."""

import pytest

from care_platform.config.schema import TrustPostureLevel
from care_platform.trust.posture import (
    NEVER_DELEGATED_ACTIONS,
    PostureEvidence,
    TrustPosture,
)


class TestPostureUpgrade:
    def test_upgrade_requires_evidence(self):
        posture = TrustPosture(agent_id="agent-1")
        evidence = PostureEvidence()
        can, reason = posture.can_upgrade(evidence)
        assert not can

    def test_upgrade_with_sufficient_evidence(self):
        posture = TrustPosture(agent_id="agent-1")
        evidence = PostureEvidence(
            successful_operations=100,
            total_operations=100,
            days_at_current_posture=90,
            shadow_enforcer_pass_rate=0.95,
            incidents=0,
        )
        can, reason = posture.can_upgrade(evidence)
        assert can

    def test_upgrade_changes_level(self):
        posture = TrustPosture(agent_id="agent-1")
        evidence = PostureEvidence(
            successful_operations=100,
            total_operations=100,
            days_at_current_posture=90,
            shadow_enforcer_pass_rate=0.95,
        )
        posture.upgrade(evidence)
        assert posture.current_level == TrustPostureLevel.SHARED_PLANNING

    def test_upgrade_blocked_with_incidents(self):
        posture = TrustPosture(agent_id="agent-1")
        evidence = PostureEvidence(
            successful_operations=100,
            total_operations=100,
            days_at_current_posture=90,
            shadow_enforcer_pass_rate=0.95,
            incidents=1,
        )
        can, reason = posture.can_upgrade(evidence)
        assert not can
        assert "incidents" in reason.lower()

    def test_upgrade_blocked_without_shadow_enforcer(self):
        posture = TrustPosture(agent_id="agent-1")
        evidence = PostureEvidence(
            successful_operations=100,
            total_operations=100,
            days_at_current_posture=90,
        )
        can, reason = posture.can_upgrade(evidence)
        assert not can
        assert "ShadowEnforcer" in reason

    def test_cannot_upgrade_beyond_delegated(self):
        posture = TrustPosture(agent_id="agent-1", current_level=TrustPostureLevel.DELEGATED)
        evidence = PostureEvidence(
            successful_operations=1000,
            total_operations=1000,
            days_at_current_posture=365,
            shadow_enforcer_pass_rate=1.0,
        )
        can, reason = posture.can_upgrade(evidence)
        assert not can


class TestPostureDowngrade:
    def test_instant_downgrade(self):
        posture = TrustPosture(
            agent_id="agent-1",
            current_level=TrustPostureLevel.SHARED_PLANNING,
        )
        posture.downgrade("Security incident")
        assert posture.current_level == TrustPostureLevel.SUPERVISED

    def test_downgrade_to_specific_level(self):
        posture = TrustPosture(
            agent_id="agent-1",
            current_level=TrustPostureLevel.DELEGATED,
        )
        posture.downgrade("Incident", to_level=TrustPostureLevel.SUPERVISED)
        assert posture.current_level == TrustPostureLevel.SUPERVISED

    def test_cannot_downgrade_upward(self):
        posture = TrustPosture(agent_id="agent-1")
        with pytest.raises(ValueError, match="must be below"):
            posture.downgrade("Oops", to_level=TrustPostureLevel.DELEGATED)

    def test_history_recorded(self):
        posture = TrustPosture(
            agent_id="agent-1",
            current_level=TrustPostureLevel.SHARED_PLANNING,
        )
        posture.downgrade("Test")
        assert len(posture.history) == 1
        assert posture.history[0].reason == "Test"


class TestNeverDelegated:
    def test_strategy_always_held(self):
        posture = TrustPosture(agent_id="agent-1")
        assert posture.is_action_always_held("content_strategy")

    def test_crisis_always_held(self):
        posture = TrustPosture(agent_id="agent-1")
        assert posture.is_action_always_held("crisis_response")

    def test_normal_action_not_held(self):
        posture = TrustPosture(agent_id="agent-1")
        assert not posture.is_action_always_held("draft_post")

    def test_never_delegated_list_nonempty(self):
        assert len(NEVER_DELEGATED_ACTIONS) > 0
