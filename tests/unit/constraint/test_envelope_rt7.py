# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""RT7 red team tests for constraint envelope.

RT7-06: select_active_envelope helper — filters expired, prefers most recent.
RT7-09: is_tighter_than must validate temporal and data_access dimensions.
"""

from datetime import UTC, datetime, timedelta

import pytest

from care_platform.config.schema import (
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)
from care_platform.constraint.envelope import (
    ConstraintEnvelope,
    select_active_envelope,
)


def _make_envelope(**kwargs) -> ConstraintEnvelope:
    config = ConstraintEnvelopeConfig(id="rt7-test-env", **kwargs)
    return ConstraintEnvelope(config=config)


# ===========================================================================
# RT7-06: select_active_envelope helper
# ===========================================================================


class TestSelectActiveEnvelope:
    """RT7-06: select_active_envelope filters expired envelopes and picks most recent."""

    def test_returns_none_for_empty_list(self):
        """Empty input returns None."""
        assert select_active_envelope([]) is None

    def test_returns_single_non_expired_envelope(self):
        """Single valid envelope is returned."""
        env = {"id": "env-1", "created_at": "2026-03-01T00:00:00+00:00"}
        result = select_active_envelope([env])
        assert result is not None
        assert result["id"] == "env-1"

    def test_filters_out_expired_envelope(self):
        """Expired envelope (top-level expires_at in the past) is excluded."""
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        env_expired = {
            "id": "env-old",
            "expires_at": past,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        result = select_active_envelope([env_expired])
        assert result is None

    def test_filters_out_expired_in_config(self):
        """Expired envelope with expires_at nested in config is excluded."""
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        env_expired = {
            "id": "env-old",
            "config": {"expires_at": past, "created_at": "2026-01-01T00:00:00+00:00"},
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        result = select_active_envelope([env_expired])
        assert result is None

    def test_keeps_non_expired_envelope(self):
        """Envelope with future expires_at is kept."""
        future = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        env = {"id": "env-valid", "expires_at": future, "created_at": "2026-03-01T00:00:00+00:00"}
        result = select_active_envelope([env])
        assert result is not None
        assert result["id"] == "env-valid"

    def test_prefers_most_recent_by_created_at(self):
        """Among valid envelopes, the most recently created is selected."""
        env_old = {"id": "env-old", "created_at": "2026-01-01T00:00:00+00:00"}
        env_new = {"id": "env-new", "created_at": "2026-03-10T00:00:00+00:00"}
        result = select_active_envelope([env_old, env_new])
        assert result is not None
        assert result["id"] == "env-new"

    def test_prefers_most_recent_even_when_out_of_order(self):
        """Order of input does not affect selection — most recent wins."""
        env_new = {"id": "env-new", "created_at": "2026-03-10T00:00:00+00:00"}
        env_old = {"id": "env-old", "created_at": "2026-01-01T00:00:00+00:00"}
        result = select_active_envelope([env_new, env_old])
        assert result is not None
        assert result["id"] == "env-new"

    def test_mixed_expired_and_valid(self):
        """Only valid envelopes are considered; most recent valid wins."""
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        env_expired = {
            "id": "env-expired",
            "expires_at": past,
            "created_at": "2026-03-11T00:00:00+00:00",
        }
        env_valid_old = {"id": "env-valid-old", "created_at": "2026-01-01T00:00:00+00:00"}
        env_valid_new = {"id": "env-valid-new", "created_at": "2026-03-05T00:00:00+00:00"}
        result = select_active_envelope([env_expired, env_valid_old, env_valid_new])
        assert result is not None
        assert result["id"] == "env-valid-new"

    def test_all_expired_returns_none(self):
        """If all envelopes are expired, returns None."""
        past1 = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        past2 = (datetime.now(UTC) - timedelta(days=5)).isoformat()
        env1 = {"id": "env-1", "expires_at": past1, "created_at": "2026-01-01T00:00:00+00:00"}
        env2 = {"id": "env-2", "expires_at": past2, "created_at": "2026-02-01T00:00:00+00:00"}
        result = select_active_envelope([env1, env2])
        assert result is None

    def test_no_expires_at_is_treated_as_valid(self):
        """Envelopes without expires_at are not filtered out."""
        env = {"id": "env-no-expiry", "created_at": "2026-03-01T00:00:00+00:00"}
        result = select_active_envelope([env])
        assert result is not None
        assert result["id"] == "env-no-expiry"

    def test_datetime_object_expires_at(self):
        """expires_at can be a datetime object, not just a string."""
        past_dt = datetime.now(UTC) - timedelta(days=1)
        future_dt = datetime.now(UTC) + timedelta(days=30)
        env_expired = {
            "id": "env-expired",
            "expires_at": past_dt,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        env_valid = {
            "id": "env-valid",
            "expires_at": future_dt,
            "created_at": "2026-03-01T00:00:00+00:00",
        }
        result = select_active_envelope([env_expired, env_valid])
        assert result is not None
        assert result["id"] == "env-valid"

    def test_naive_datetime_expires_at_treated_as_utc(self):
        """Naive datetime (no timezone) for expires_at should be treated as UTC."""
        # Naive datetime in the past
        past_naive = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
        env = {
            "id": "env-naive-past",
            "expires_at": past_naive,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        result = select_active_envelope([env])
        assert result is None

    def test_created_at_in_config_fallback(self):
        """created_at inside config dict is used for sorting when top-level is absent."""
        env_old = {"id": "env-old", "config": {"created_at": "2026-01-01T00:00:00+00:00"}}
        env_new = {"id": "env-new", "config": {"created_at": "2026-03-10T00:00:00+00:00"}}
        result = select_active_envelope([env_old, env_new])
        assert result is not None
        assert result["id"] == "env-new"

    def test_unparseable_expires_at_treated_as_expired(self):
        """If expires_at cannot be parsed, the envelope is treated as expired (fail-closed)."""
        env = {
            "id": "env-bad-date",
            "expires_at": "not-a-date",
            "created_at": "2026-03-01T00:00:00+00:00",
        }
        result = select_active_envelope([env])
        # Fail-closed: unparseable dates mean the envelope is not trusted
        assert result is None


# ===========================================================================
# RT7-09: is_tighter_than must validate temporal and data_access dimensions
# ===========================================================================


class TestMonotonicTighteningTemporal:
    """RT7-09: is_tighter_than must check temporal dimension."""

    def test_child_narrower_active_hours_is_tighter(self):
        """Child with smaller active hours window within parent is tighter."""
        parent = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="20:00",
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child = ConstraintEnvelope(config=child_config, parent_envelope_id="rt7-test-env")
        assert child.is_tighter_than(parent)

    def test_child_wider_active_hours_start_is_not_tighter(self):
        """Child with earlier start than parent is NOT tighter (wider window)."""
        parent = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="07:00",
                active_hours_end="17:00",
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_child_wider_active_hours_end_is_not_tighter(self):
        """Child with later end than parent is NOT tighter (wider window)."""
        parent = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="20:00",
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_child_with_no_active_hours_when_parent_has_them_is_not_tighter(self):
        """Child removing active hours restriction when parent has them is NOT tighter."""
        parent = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(),  # no active hours
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_child_adds_active_hours_when_parent_has_none_is_tighter(self):
        """Child adding active hours when parent has none is tighter."""
        parent = _make_envelope(
            temporal=TemporalConstraintConfig(),  # no active hours
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child = ConstraintEnvelope(config=child_config, parent_envelope_id="rt7-test-env")
        assert child.is_tighter_than(parent)

    def test_both_no_active_hours_is_tighter(self):
        """Neither has active hours — child is considered tighter (no loosening)."""
        parent = _make_envelope(temporal=TemporalConstraintConfig())
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_same_active_hours_is_tighter(self):
        """Equal active hours is still tighter (not loosened)."""
        parent = _make_envelope(
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_must_include_all_parent_blackout_periods(self):
        """Child must include all parent blackout periods to be tighter."""
        parent = _make_envelope(
            temporal=TemporalConstraintConfig(
                blackout_periods=["2026-03-15", "12-25"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                blackout_periods=["2026-03-15", "12-25", "01-01"],  # superset
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_missing_parent_blackout_period_is_not_tighter(self):
        """Child that drops a parent blackout period is NOT tighter."""
        parent = _make_envelope(
            temporal=TemporalConstraintConfig(
                blackout_periods=["2026-03-15", "12-25"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                blackout_periods=["2026-03-15"],  # missing 12-25
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_child_no_blackout_when_parent_has_them_is_not_tighter(self):
        """Child removing all blackout periods is NOT tighter."""
        parent = _make_envelope(
            temporal=TemporalConstraintConfig(
                blackout_periods=["2026-03-15"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                blackout_periods=[],
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)


class TestMonotonicTighteningDataAccess:
    """RT7-09: is_tighter_than must check data_access dimension."""

    def test_child_read_paths_subset_of_parent_is_tighter(self):
        """Child with read_paths that are a subset of parent is tighter."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(
                read_paths=["reports/", "metrics/", "logs/"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                read_paths=["reports/", "metrics/"],
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_read_paths_not_subset_is_not_tighter(self):
        """Child with a read_path not in parent is NOT tighter."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(
                read_paths=["reports/", "metrics/"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                read_paths=["reports/", "secrets/"],  # secrets/ not in parent
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_child_write_paths_subset_of_parent_is_tighter(self):
        """Child with write_paths that are a subset of parent is tighter."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(
                write_paths=["drafts/", "output/"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                write_paths=["drafts/"],
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_write_paths_not_subset_is_not_tighter(self):
        """Child with a write_path not in parent is NOT tighter."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(
                write_paths=["drafts/"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                write_paths=["drafts/", "config/"],  # config/ not in parent
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_child_must_include_all_parent_blocked_data_types(self):
        """Child must include all parent blocked_data_types to be tighter."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii", "financial_records"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii", "financial_records", "medical"],  # superset
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_missing_parent_blocked_data_type_is_not_tighter(self):
        """Child that drops a parent blocked_data_type is NOT tighter."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii", "financial_records"],
            ),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii"],  # missing financial_records
            ),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_child_adds_read_paths_when_parent_has_none_is_tighter(self):
        """Child adding read_paths restriction when parent has none is tighter."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(read_paths=[]),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(read_paths=["reports/"]),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_removes_read_paths_when_parent_has_them_is_not_tighter(self):
        """Child removing all read_paths (unrestricted) when parent had them is NOT tighter."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(read_paths=["reports/"]),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(read_paths=[]),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_child_removes_write_paths_when_parent_has_them_is_not_tighter(self):
        """Child removing all write_paths (unrestricted) when parent had them is NOT tighter."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(write_paths=["drafts/"]),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(write_paths=[]),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)

    def test_both_empty_read_paths_is_tighter(self):
        """Neither has read_paths — no loosening, so tighter."""
        parent = _make_envelope(data_access=DataAccessConstraintConfig(read_paths=[]))
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(read_paths=[]),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_same_read_paths_is_tighter(self):
        """Equal read_paths is still tighter (not loosened)."""
        parent = _make_envelope(
            data_access=DataAccessConstraintConfig(read_paths=["reports/", "metrics/"]),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(read_paths=["reports/", "metrics/"]),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)
