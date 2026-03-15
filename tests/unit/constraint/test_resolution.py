# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Constraint Resolution Algorithm (M14 Task 1404)."""

import pytest

from care_platform.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)
from care_platform.constraint.resolution import (
    ConstraintResolutionError,
    resolve_constraints,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _envelope(
    id: str,
    *,
    max_spend_usd: float = 1000.0,
    allowed_actions: list[str] | None = None,
    blocked_actions: list[str] | None = None,
    active_hours_start: str | None = None,
    active_hours_end: str | None = None,
    read_paths: list[str] | None = None,
    write_paths: list[str] | None = None,
    blocked_data_types: list[str] | None = None,
    internal_only: bool = True,
    external_requires_approval: bool = True,
    max_actions_per_day: int | None = None,
) -> ConstraintEnvelopeConfig:
    return ConstraintEnvelopeConfig(
        id=id,
        financial=FinancialConstraintConfig(max_spend_usd=max_spend_usd),
        operational=OperationalConstraintConfig(
            allowed_actions=allowed_actions or [],
            blocked_actions=blocked_actions or [],
            max_actions_per_day=max_actions_per_day,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start=active_hours_start,
            active_hours_end=active_hours_end,
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=read_paths or [],
            write_paths=write_paths or [],
            blocked_data_types=blocked_data_types or [],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=internal_only,
            external_requires_approval=external_requires_approval,
        ),
    )


# ---------------------------------------------------------------------------
# Test: Empty Input
# ---------------------------------------------------------------------------


class TestEmptyInput:
    def test_empty_list_raises_error(self):
        with pytest.raises(ConstraintResolutionError, match="[Ee]mpty|[Nn]o.*envelope"):
            resolve_constraints([])


# ---------------------------------------------------------------------------
# Test: Single Envelope (Passthrough)
# ---------------------------------------------------------------------------


class TestSingleEnvelope:
    def test_single_envelope_passes_through(self):
        env = _envelope("org-level", max_spend_usd=500.0)
        result = resolve_constraints([env])
        assert result.financial.max_spend_usd == 500.0

    def test_single_envelope_preserves_operational(self):
        env = _envelope(
            "org-level",
            allowed_actions=["read", "write", "draft"],
            blocked_actions=["delete"],
        )
        result = resolve_constraints([env])
        assert set(result.operational.allowed_actions) == {"read", "write", "draft"}
        assert set(result.operational.blocked_actions) == {"delete"}

    def test_single_envelope_preserves_temporal(self):
        env = _envelope("org-level", active_hours_start="09:00", active_hours_end="17:00")
        result = resolve_constraints([env])
        assert result.temporal.active_hours_start == "09:00"
        assert result.temporal.active_hours_end == "17:00"

    def test_single_envelope_preserves_data_access(self):
        env = _envelope(
            "org-level",
            read_paths=["data/*"],
            write_paths=["output/*"],
            blocked_data_types=["pii"],
        )
        result = resolve_constraints([env])
        assert result.data_access.read_paths == ["data/*"]
        assert result.data_access.write_paths == ["output/*"]
        assert result.data_access.blocked_data_types == ["pii"]

    def test_single_envelope_preserves_communication(self):
        env = _envelope("org-level", internal_only=False, external_requires_approval=False)
        result = resolve_constraints([env])
        assert result.communication.internal_only is False
        assert result.communication.external_requires_approval is False


# ---------------------------------------------------------------------------
# Test: Two-Level Hierarchy (Org -> Team)
# ---------------------------------------------------------------------------


class TestTwoLevelHierarchy:
    def test_financial_takes_minimum(self):
        org = _envelope("org", max_spend_usd=1000.0)
        team = _envelope("team", max_spend_usd=500.0)
        result = resolve_constraints([org, team])
        assert result.financial.max_spend_usd == 500.0

    def test_financial_takes_minimum_reversed(self):
        org = _envelope("org", max_spend_usd=500.0)
        team = _envelope("team", max_spend_usd=1000.0)
        result = resolve_constraints([org, team])
        assert result.financial.max_spend_usd == 500.0

    def test_operational_allowed_intersection(self):
        org = _envelope("org", allowed_actions=["read", "write", "draft", "publish"])
        team = _envelope("team", allowed_actions=["read", "write", "draft"])
        result = resolve_constraints([org, team])
        assert set(result.operational.allowed_actions) == {"read", "write", "draft"}

    def test_operational_blocked_union(self):
        org = _envelope("org", blocked_actions=["delete"])
        team = _envelope("team", blocked_actions=["deploy"])
        result = resolve_constraints([org, team])
        assert set(result.operational.blocked_actions) == {"delete", "deploy"}

    def test_temporal_intersection(self):
        org = _envelope("org", active_hours_start="08:00", active_hours_end="20:00")
        team = _envelope("team", active_hours_start="09:00", active_hours_end="17:00")
        result = resolve_constraints([org, team])
        assert result.temporal.active_hours_start == "09:00"
        assert result.temporal.active_hours_end == "17:00"

    def test_temporal_wider_child_narrowed(self):
        org = _envelope("org", active_hours_start="09:00", active_hours_end="17:00")
        team = _envelope("team", active_hours_start="08:00", active_hours_end="20:00")
        result = resolve_constraints([org, team])
        # Intersection should be the narrower window
        assert result.temporal.active_hours_start == "09:00"
        assert result.temporal.active_hours_end == "17:00"

    def test_temporal_one_has_no_window(self):
        """If one envelope has no temporal restriction, the other's window wins."""
        org = _envelope("org", active_hours_start="09:00", active_hours_end="17:00")
        team = _envelope("team")  # no temporal constraint
        result = resolve_constraints([org, team])
        assert result.temporal.active_hours_start == "09:00"
        assert result.temporal.active_hours_end == "17:00"

    def test_data_access_read_intersection(self):
        org = _envelope("org", read_paths=["data/*", "config/*", "logs/*"])
        team = _envelope("team", read_paths=["data/*", "config/*"])
        result = resolve_constraints([org, team])
        assert set(result.data_access.read_paths) == {"data/*", "config/*"}

    def test_data_access_write_intersection(self):
        org = _envelope("org", write_paths=["output/*", "drafts/*"])
        team = _envelope("team", write_paths=["output/*"])
        result = resolve_constraints([org, team])
        assert set(result.data_access.write_paths) == {"output/*"}

    def test_data_access_blocked_union(self):
        org = _envelope("org", blocked_data_types=["pii"])
        team = _envelope("team", blocked_data_types=["financial_records"])
        result = resolve_constraints([org, team])
        assert set(result.data_access.blocked_data_types) == {"pii", "financial_records"}

    def test_communication_most_restrictive_internal_only(self):
        org = _envelope("org", internal_only=True)
        team = _envelope("team", internal_only=False)
        result = resolve_constraints([org, team])
        assert result.communication.internal_only is True

    def test_communication_most_restrictive_external_approval(self):
        org = _envelope("org", external_requires_approval=True)
        team = _envelope("team", external_requires_approval=False)
        result = resolve_constraints([org, team])
        assert result.communication.external_requires_approval is True

    def test_communication_both_permissive(self):
        org = _envelope("org", internal_only=False, external_requires_approval=False)
        team = _envelope("team", internal_only=False, external_requires_approval=False)
        result = resolve_constraints([org, team])
        assert result.communication.internal_only is False
        assert result.communication.external_requires_approval is False


# ---------------------------------------------------------------------------
# Test: Three-Level Hierarchy (Org -> Team -> Agent)
# ---------------------------------------------------------------------------


class TestThreeLevelHierarchy:
    def test_financial_cascading_minimum(self):
        org = _envelope("org", max_spend_usd=1000.0)
        team = _envelope("team", max_spend_usd=500.0)
        agent = _envelope("agent", max_spend_usd=100.0)
        result = resolve_constraints([org, team, agent])
        assert result.financial.max_spend_usd == 100.0

    def test_financial_middle_is_minimum(self):
        org = _envelope("org", max_spend_usd=1000.0)
        team = _envelope("team", max_spend_usd=50.0)
        agent = _envelope("agent", max_spend_usd=100.0)
        result = resolve_constraints([org, team, agent])
        assert result.financial.max_spend_usd == 50.0

    def test_operational_cascading_intersection(self):
        org = _envelope("org", allowed_actions=["read", "write", "draft", "publish", "review"])
        team = _envelope("team", allowed_actions=["read", "write", "draft", "publish"])
        agent = _envelope("agent", allowed_actions=["read", "draft"])
        result = resolve_constraints([org, team, agent])
        assert set(result.operational.allowed_actions) == {"read", "draft"}

    def test_operational_cascading_blocked_union(self):
        org = _envelope("org", blocked_actions=["delete"])
        team = _envelope("team", blocked_actions=["deploy"])
        agent = _envelope("agent", blocked_actions=["configure"])
        result = resolve_constraints([org, team, agent])
        assert set(result.operational.blocked_actions) == {"delete", "deploy", "configure"}

    def test_temporal_three_level_intersection(self):
        org = _envelope("org", active_hours_start="06:00", active_hours_end="22:00")
        team = _envelope("team", active_hours_start="08:00", active_hours_end="20:00")
        agent = _envelope("agent", active_hours_start="09:00", active_hours_end="17:00")
        result = resolve_constraints([org, team, agent])
        assert result.temporal.active_hours_start == "09:00"
        assert result.temporal.active_hours_end == "17:00"

    def test_data_access_three_level_intersection(self):
        org = _envelope("org", read_paths=["data/*", "config/*", "logs/*", "reports/*"])
        team = _envelope("team", read_paths=["data/*", "config/*", "logs/*"])
        agent = _envelope("agent", read_paths=["data/*"])
        result = resolve_constraints([org, team, agent])
        assert set(result.data_access.read_paths) == {"data/*"}

    def test_communication_most_restrictive_three_level(self):
        org = _envelope("org", internal_only=False, external_requires_approval=False)
        team = _envelope("team", internal_only=False, external_requires_approval=True)
        agent = _envelope("agent", internal_only=True, external_requires_approval=True)
        result = resolve_constraints([org, team, agent])
        assert result.communication.internal_only is True
        assert result.communication.external_requires_approval is True

    def test_blocked_types_accumulate_across_levels(self):
        org = _envelope("org", blocked_data_types=["pii"])
        team = _envelope("team", blocked_data_types=["financial_records"])
        agent = _envelope("agent", blocked_data_types=["medical"])
        result = resolve_constraints([org, team, agent])
        assert set(result.data_access.blocked_data_types) == {
            "pii",
            "financial_records",
            "medical",
        }


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_allowed_actions_means_unrestricted(self):
        """Empty allowed_actions means no restriction; intersection with non-empty preserves."""
        org = _envelope("org", allowed_actions=[])  # unrestricted
        team = _envelope("team", allowed_actions=["read", "write"])
        result = resolve_constraints([org, team])
        assert set(result.operational.allowed_actions) == {"read", "write"}

    def test_both_empty_allowed_actions(self):
        org = _envelope("org", allowed_actions=[])
        team = _envelope("team", allowed_actions=[])
        result = resolve_constraints([org, team])
        assert result.operational.allowed_actions == []

    def test_disjoint_allowed_actions_raises_error(self):
        org = _envelope("org", allowed_actions=["read", "write"])
        team = _envelope("team", allowed_actions=["deploy", "configure"])
        with pytest.raises(ConstraintResolutionError, match="no overlap"):
            resolve_constraints([org, team])

    def test_zero_budgets(self):
        org = _envelope("org", max_spend_usd=0.0)
        team = _envelope("team", max_spend_usd=100.0)
        result = resolve_constraints([org, team])
        assert result.financial.max_spend_usd == 0.0

    def test_resolved_id_is_descriptive(self):
        org = _envelope("org-level")
        team = _envelope("team-level")
        result = resolve_constraints([org, team])
        # The resolved envelope should have an ID indicating it's resolved
        assert result.id is not None
        assert len(result.id) > 0

    def test_max_actions_per_day_takes_minimum(self):
        org = _envelope("org", max_actions_per_day=100)
        team = _envelope("team", max_actions_per_day=50)
        result = resolve_constraints([org, team])
        assert result.operational.max_actions_per_day == 50

    def test_max_actions_per_day_one_none(self):
        org = _envelope("org", max_actions_per_day=100)
        team = _envelope("team", max_actions_per_day=None)
        result = resolve_constraints([org, team])
        assert result.operational.max_actions_per_day == 100

    def test_max_actions_per_day_both_none(self):
        org = _envelope("org", max_actions_per_day=None)
        team = _envelope("team", max_actions_per_day=None)
        result = resolve_constraints([org, team])
        assert result.operational.max_actions_per_day is None

    def test_no_temporal_windows_yields_no_restriction(self):
        org = _envelope("org")
        team = _envelope("team")
        result = resolve_constraints([org, team])
        assert result.temporal.active_hours_start is None
        assert result.temporal.active_hours_end is None

    def test_read_paths_empty_means_unrestricted(self):
        org = _envelope("org", read_paths=[])  # unrestricted
        team = _envelope("team", read_paths=["data/*"])
        result = resolve_constraints([org, team])
        assert set(result.data_access.read_paths) == {"data/*"}

    def test_write_paths_empty_means_unrestricted(self):
        org = _envelope("org", write_paths=[])
        team = _envelope("team", write_paths=["output/*"])
        result = resolve_constraints([org, team])
        assert set(result.data_access.write_paths) == {"output/*"}
