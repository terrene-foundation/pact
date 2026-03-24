# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for constraint envelope evaluation."""

from datetime import UTC, datetime

from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)
from pact_platform.trust.constraint.envelope import (
    ConstraintEnvelope,
    EvaluationResult,
)


def _make_envelope(**kwargs) -> ConstraintEnvelope:
    config = ConstraintEnvelopeConfig(id="test-env", **kwargs)
    return ConstraintEnvelope(config=config)


class TestEnvelopeEvaluation:
    def test_allowed_action(self):
        env = _make_envelope(
            operational=OperationalConstraintConfig(allowed_actions=["read", "write"]),
        )
        result = env.evaluate_action("read", "agent-1")
        assert result.is_allowed

    def test_blocked_action(self):
        env = _make_envelope(
            operational=OperationalConstraintConfig(blocked_actions=["delete"]),
        )
        result = env.evaluate_action("delete", "agent-1")
        assert not result.is_allowed
        assert result.overall_result == EvaluationResult.DENIED

    def test_action_not_in_allowed_list(self):
        env = _make_envelope(
            operational=OperationalConstraintConfig(allowed_actions=["read"]),
        )
        result = env.evaluate_action("write", "agent-1")
        assert not result.is_allowed

    def test_financial_over_budget(self):
        env = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=10.0),
        )
        result = env.evaluate_action("purchase", "agent-1", spend_amount=15.0)
        assert not result.is_allowed

    def test_financial_near_boundary(self):
        env = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        result = env.evaluate_action("purchase", "agent-1", spend_amount=85.0)
        assert result.is_near_boundary

    def test_rate_limit_exceeded(self):
        env = _make_envelope(
            operational=OperationalConstraintConfig(max_actions_per_day=20),
        )
        result = env.evaluate_action("draft", "agent-1", current_action_count=20)
        assert not result.is_allowed

    def test_rate_limit_near_boundary(self):
        env = _make_envelope(
            operational=OperationalConstraintConfig(max_actions_per_day=20),
        )
        result = env.evaluate_action("draft", "agent-1", current_action_count=17)
        assert result.is_near_boundary

    def test_external_blocked_when_internal_only(self):
        env = _make_envelope(
            communication=CommunicationConstraintConfig(internal_only=True),
        )
        result = env.evaluate_action("send_email", "agent-1", is_external=True)
        assert not result.is_allowed

    def test_outside_active_hours(self):
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="18:00",
            ),
        )
        late_time = datetime(2026, 3, 11, 22, 0, tzinfo=UTC)
        result = env.evaluate_action("draft", "agent-1", current_time=late_time)
        assert not result.is_allowed

    def test_within_active_hours(self):
        env = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="18:00",
            ),
        )
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)
        result = env.evaluate_action("draft", "agent-1", current_time=work_time)
        assert result.is_allowed

    def test_blocked_data_access(self):
        env = _make_envelope(
            data_access=DataAccessConstraintConfig(blocked_data_types=["pii"]),
        )
        result = env.evaluate_action("read", "agent-1", data_paths=["users/pii/records"])
        assert not result.is_allowed

    def test_five_dimensions_evaluated(self):
        env = _make_envelope()
        result = env.evaluate_action("read", "agent-1")
        assert len(result.dimensions) == 5

    def test_most_restrictive_wins(self):
        """If any dimension denies, overall is denied."""
        env = _make_envelope(
            operational=OperationalConstraintConfig(blocked_actions=["bad"]),
        )
        result = env.evaluate_action("bad", "agent-1")
        assert result.overall_result == EvaluationResult.DENIED


class TestMonotonicTightening:
    def test_tighter_child_accepted(self):
        parent = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write", "delete"],
                blocked_actions=["admin"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            financial=FinancialConstraintConfig(max_spend_usd=50.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
                blocked_actions=["admin", "delete"],
            ),
        )
        child = ConstraintEnvelope(config=child_config, parent_envelope_id="test-env")
        assert child.is_tighter_than(parent)

    def test_looser_child_rejected(self):
        parent = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=50.0),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_communication_loosening_rejected(self):
        parent = _make_envelope(
            communication=CommunicationConstraintConfig(internal_only=True),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            communication=CommunicationConstraintConfig(internal_only=False),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)


class TestEnvelopeMetadata:
    def test_content_hash_stable(self):
        env = _make_envelope()
        h1 = env.content_hash()
        h2 = env.content_hash()
        assert h1 == h2

    def test_content_hash_changes_with_config(self):
        env1 = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=0),
        )
        env2 = _make_envelope(
            financial=FinancialConstraintConfig(max_spend_usd=100),
        )
        assert env1.content_hash() != env2.content_hash()

    def test_default_expiry_90_days(self):
        env = _make_envelope()
        assert env.expires_at is not None
        delta = env.expires_at - env.created_at
        assert delta.days == 90
