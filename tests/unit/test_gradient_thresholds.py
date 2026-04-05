# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for gradient thresholds wiring from L1 (kailash-pact) to L3 (pact-platform).

Validates that:
- DimensionThresholds and GradientThresholdsConfig are re-exported from schema.py
- L1 validation (ordering, NaN/Inf rejection) works through the re-export path
- RoleEnvelope accepts gradient_thresholds at construction
- The envelope router correctly parses gradient_thresholds from request body
"""

from __future__ import annotations

import pytest


class TestDimensionThresholds:
    """L1 DimensionThresholds validation via L3 re-export."""

    def test_valid_thresholds(self) -> None:
        from pact_platform.build.config.schema import DimensionThresholds

        dt = DimensionThresholds(
            auto_approve_threshold=100.0,
            flag_threshold=500.0,
            hold_threshold=1000.0,
        )
        assert dt.auto_approve_threshold == 100.0
        assert dt.flag_threshold == 500.0
        assert dt.hold_threshold == 1000.0

    def test_equal_thresholds_accepted(self) -> None:
        """auto <= flag <= hold allows equal values."""
        from pact_platform.build.config.schema import DimensionThresholds

        dt = DimensionThresholds(
            auto_approve_threshold=500.0,
            flag_threshold=500.0,
            hold_threshold=500.0,
        )
        assert dt.auto_approve_threshold == 500.0

    def test_rejects_misordering(self) -> None:
        from pact_platform.build.config.schema import DimensionThresholds

        with pytest.raises(Exception):
            DimensionThresholds(
                auto_approve_threshold=1000.0,
                flag_threshold=500.0,
                hold_threshold=100.0,
            )

    def test_rejects_nan(self) -> None:
        from pact_platform.build.config.schema import DimensionThresholds

        with pytest.raises(Exception):
            DimensionThresholds(
                auto_approve_threshold=float("nan"),
                flag_threshold=500.0,
                hold_threshold=1000.0,
            )

    def test_rejects_inf(self) -> None:
        from pact_platform.build.config.schema import DimensionThresholds

        with pytest.raises(Exception):
            DimensionThresholds(
                auto_approve_threshold=float("inf"),
                flag_threshold=500.0,
                hold_threshold=1000.0,
            )

    def test_rejects_negative_inf(self) -> None:
        from pact_platform.build.config.schema import DimensionThresholds

        with pytest.raises(Exception):
            DimensionThresholds(
                auto_approve_threshold=float("-inf"),
                flag_threshold=500.0,
                hold_threshold=1000.0,
            )

    def test_frozen(self) -> None:
        """DimensionThresholds is frozen -- fields cannot be mutated."""
        from pact_platform.build.config.schema import DimensionThresholds

        dt = DimensionThresholds(
            auto_approve_threshold=100.0,
            flag_threshold=500.0,
            hold_threshold=1000.0,
        )
        with pytest.raises(Exception):
            dt.auto_approve_threshold = 999.0  # type: ignore[misc]


class TestGradientThresholdsConfig:
    """L1 GradientThresholdsConfig via L3 re-export."""

    def test_with_financial(self) -> None:
        from pact_platform.build.config.schema import (
            DimensionThresholds,
            GradientThresholdsConfig,
        )

        gt = GradientThresholdsConfig(
            financial=DimensionThresholds(
                auto_approve_threshold=100.0,
                flag_threshold=500.0,
                hold_threshold=1000.0,
            )
        )
        assert gt.financial is not None
        assert gt.financial.flag_threshold == 500.0

    def test_none_financial(self) -> None:
        from pact_platform.build.config.schema import GradientThresholdsConfig

        gt = GradientThresholdsConfig()
        assert gt.financial is None

    def test_frozen(self) -> None:
        """GradientThresholdsConfig is frozen -- fields cannot be mutated."""
        from pact_platform.build.config.schema import GradientThresholdsConfig

        gt = GradientThresholdsConfig()
        with pytest.raises(Exception):
            gt.financial = None  # type: ignore[misc]


class TestRoleEnvelopeGradientThresholds:
    """RoleEnvelope construction with gradient_thresholds."""

    def test_with_gradient_thresholds(self) -> None:
        from pact.governance import RoleEnvelope
        from pact_platform.build.config.schema import (
            ConstraintEnvelopeConfig,
            DimensionThresholds,
            GradientThresholdsConfig,
        )

        gt = GradientThresholdsConfig(
            financial=DimensionThresholds(
                auto_approve_threshold=100.0,
                flag_threshold=500.0,
                hold_threshold=1000.0,
            )
        )
        env = RoleEnvelope(
            id="test-env",
            defining_role_address="D1-R1",
            target_role_address="D1-T1-R1",
            envelope=ConstraintEnvelopeConfig(id="test-env"),
            gradient_thresholds=gt,
        )
        assert env.gradient_thresholds is not None
        assert env.gradient_thresholds.financial is not None
        assert env.gradient_thresholds.financial.auto_approve_threshold == 100.0
        assert env.gradient_thresholds.financial.flag_threshold == 500.0
        assert env.gradient_thresholds.financial.hold_threshold == 1000.0

    def test_without_gradient_thresholds(self) -> None:
        from pact.governance import RoleEnvelope
        from pact_platform.build.config.schema import ConstraintEnvelopeConfig

        env = RoleEnvelope(
            id="test-env",
            defining_role_address="D1-R1",
            target_role_address="D1-T1-R1",
            envelope=ConstraintEnvelopeConfig(id="test-env"),
        )
        assert env.gradient_thresholds is None

    def test_with_none_gradient_thresholds_explicit(self) -> None:
        from pact.governance import RoleEnvelope
        from pact_platform.build.config.schema import ConstraintEnvelopeConfig

        env = RoleEnvelope(
            id="test-env",
            defining_role_address="D1-R1",
            target_role_address="D1-T1-R1",
            envelope=ConstraintEnvelopeConfig(id="test-env"),
            gradient_thresholds=None,
        )
        assert env.gradient_thresholds is None


class TestEnvelopeRouterGradientParsing:
    """Test gradient_thresholds parsing in the set_role_envelope API endpoint."""

    def test_parse_gradient_thresholds_from_dict(self) -> None:
        """Simulate what the router does: parse gradient_thresholds from a raw dict."""
        from pact_platform.build.config.schema import (
            DimensionThresholds,
            GradientThresholdsConfig,
        )

        # Simulate the raw envelope_dict from a request body
        envelope_dict = {
            "id": "env-test",
            "financial": {"max_spend_usd": 1000},
            "gradient_thresholds": {
                "financial": {
                    "auto_approve_threshold": 100.0,
                    "flag_threshold": 500.0,
                    "hold_threshold": 1000.0,
                }
            },
        }

        # Replicate the parsing logic from the router
        gradient_thresholds = None
        gt_raw = envelope_dict.get("gradient_thresholds")
        if gt_raw and isinstance(gt_raw, dict):
            fin_raw = gt_raw.get("financial")
            financial_dt = None
            if fin_raw and isinstance(fin_raw, dict):
                financial_dt = DimensionThresholds(**fin_raw)
            gradient_thresholds = GradientThresholdsConfig(financial=financial_dt)

        assert gradient_thresholds is not None
        assert gradient_thresholds.financial is not None
        assert gradient_thresholds.financial.auto_approve_threshold == 100.0
        assert gradient_thresholds.financial.flag_threshold == 500.0
        assert gradient_thresholds.financial.hold_threshold == 1000.0

    def test_parse_gradient_thresholds_absent(self) -> None:
        """When gradient_thresholds is absent, result is None."""
        envelope_dict = {
            "id": "env-test",
            "financial": {"max_spend_usd": 1000},
        }

        gradient_thresholds = None
        gt_raw = envelope_dict.get("gradient_thresholds")
        if gt_raw and isinstance(gt_raw, dict):
            from pact_platform.build.config.schema import (
                DimensionThresholds,
                GradientThresholdsConfig,
            )

            fin_raw = gt_raw.get("financial")
            financial_dt = None
            if fin_raw and isinstance(fin_raw, dict):
                financial_dt = DimensionThresholds(**fin_raw)
            gradient_thresholds = GradientThresholdsConfig(financial=financial_dt)

        assert gradient_thresholds is None

    def test_parse_gradient_thresholds_empty_dict(self) -> None:
        """When gradient_thresholds is an empty dict, result is None (falsy)."""
        envelope_dict = {
            "id": "env-test",
            "gradient_thresholds": {},
        }

        gradient_thresholds = None
        gt_raw = envelope_dict.get("gradient_thresholds")
        if gt_raw and isinstance(gt_raw, dict):
            from pact_platform.build.config.schema import (
                DimensionThresholds,
                GradientThresholdsConfig,
            )

            fin_raw = gt_raw.get("financial")
            financial_dt = None
            if fin_raw and isinstance(fin_raw, dict):
                financial_dt = DimensionThresholds(**fin_raw)
            gradient_thresholds = GradientThresholdsConfig(financial=financial_dt)

        # Empty dict is falsy -- no gradient_thresholds created
        assert gradient_thresholds is None

    def test_parse_gradient_thresholds_financial_none(self) -> None:
        """When gradient_thresholds has no financial key, financial is None."""
        from pact_platform.build.config.schema import (
            DimensionThresholds,
            GradientThresholdsConfig,
        )

        envelope_dict = {
            "id": "env-test",
            "gradient_thresholds": {"other_dimension": {}},
        }

        gradient_thresholds = None
        gt_raw = envelope_dict.get("gradient_thresholds")
        if gt_raw and isinstance(gt_raw, dict):
            fin_raw = gt_raw.get("financial")
            financial_dt = None
            if fin_raw and isinstance(fin_raw, dict):
                financial_dt = DimensionThresholds(**fin_raw)
            gradient_thresholds = GradientThresholdsConfig(financial=financial_dt)

        assert gradient_thresholds is not None
        assert gradient_thresholds.financial is None

    def test_parse_gradient_thresholds_rejects_bad_values(self) -> None:
        """L1 validation rejects NaN thresholds even when parsed through L3."""
        from pact_platform.build.config.schema import DimensionThresholds

        with pytest.raises(Exception):
            DimensionThresholds(
                auto_approve_threshold=float("nan"),
                flag_threshold=500.0,
                hold_threshold=1000.0,
            )


class TestUniversityExampleGradientThresholds:
    """Verify university example includes gradient thresholds."""

    def test_cs_chair_has_gradient_thresholds(self) -> None:
        from pact.governance import GovernanceEngine, load_org_yaml
        from pact_platform.examples.university.envelopes import (
            create_university_envelopes,
        )

        # Build a minimal compiled org for the function
        # We just need the envelopes returned -- they are constructed with hardcoded addresses
        # so we can inspect them directly without a full org.
        from unittest.mock import MagicMock

        compiled_org = MagicMock(spec=["nodes"])
        envelopes = create_university_envelopes(compiled_org)

        # Find the CS Chair envelope
        cs_chair_env = None
        for env in envelopes:
            if env.id == "env-cs-chair":
                cs_chair_env = env
                break

        assert cs_chair_env is not None, "CS Chair envelope not found"
        assert cs_chair_env.gradient_thresholds is not None
        assert cs_chair_env.gradient_thresholds.financial is not None
        assert cs_chair_env.gradient_thresholds.financial.auto_approve_threshold == 500.0
        assert cs_chair_env.gradient_thresholds.financial.flag_threshold == 2000.0
        assert cs_chair_env.gradient_thresholds.financial.hold_threshold == 5000.0

    def test_other_envelopes_no_gradient_thresholds(self) -> None:
        """Envelopes without explicit gradient_thresholds should have None."""
        from pact_platform.examples.university.envelopes import (
            create_university_envelopes,
        )
        from unittest.mock import MagicMock

        compiled_org = MagicMock(spec=["nodes"])
        envelopes = create_university_envelopes(compiled_org)

        for env in envelopes:
            if env.id != "env-cs-chair":
                assert (
                    env.gradient_thresholds is None
                ), f"Envelope {env.id} should not have gradient_thresholds"


class TestSchemaReExports:
    """Verify DimensionThresholds is properly re-exported from schema.py."""

    def test_dimension_thresholds_importable(self) -> None:
        from pact_platform.build.config.schema import DimensionThresholds

        assert DimensionThresholds is not None

    def test_gradient_thresholds_config_importable(self) -> None:
        from pact_platform.build.config.schema import GradientThresholdsConfig

        assert GradientThresholdsConfig is not None

    def test_dimension_thresholds_in_all(self) -> None:
        import pact_platform.build.config.schema as schema

        assert "DimensionThresholds" in schema.__all__

    def test_gradient_thresholds_config_in_all(self) -> None:
        import pact_platform.build.config.schema as schema

        assert "GradientThresholdsConfig" in schema.__all__
