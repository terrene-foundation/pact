# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Uncertainty Classifier (M14 Task 1405)."""

import pytest

from care_platform.build.config.schema import VerificationLevel
from care_platform.trust.uncertainty import (
    ActionMetadata,
    UncertaintyClassifier,
    UncertaintyLevel,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def classifier():
    return UncertaintyClassifier()


# ---------------------------------------------------------------------------
# Test: UncertaintyLevel Enum
# ---------------------------------------------------------------------------


class TestUncertaintyLevelEnum:
    def test_none_level_exists(self):
        assert UncertaintyLevel.NONE.value == "none"

    def test_informational_level_exists(self):
        assert UncertaintyLevel.INFORMATIONAL.value == "informational"

    def test_interpretive_level_exists(self):
        assert UncertaintyLevel.INTERPRETIVE.value == "interpretive"

    def test_judgmental_level_exists(self):
        assert UncertaintyLevel.JUDGMENTAL.value == "judgmental"

    def test_fundamental_level_exists(self):
        assert UncertaintyLevel.FUNDAMENTAL.value == "fundamental"


# ---------------------------------------------------------------------------
# Test: Uncertainty -> Verification Level Mapping
# ---------------------------------------------------------------------------


class TestUncertaintyMapping:
    def test_none_maps_to_auto_approved(self, classifier):
        result = classifier.map_to_verification(UncertaintyLevel.NONE)
        assert result == VerificationLevel.AUTO_APPROVED

    def test_informational_maps_to_auto_approved(self, classifier):
        result = classifier.map_to_verification(UncertaintyLevel.INFORMATIONAL)
        assert result == VerificationLevel.AUTO_APPROVED

    def test_interpretive_maps_to_flagged(self, classifier):
        result = classifier.map_to_verification(UncertaintyLevel.INTERPRETIVE)
        assert result == VerificationLevel.FLAGGED

    def test_judgmental_maps_to_held(self, classifier):
        result = classifier.map_to_verification(UncertaintyLevel.JUDGMENTAL)
        assert result == VerificationLevel.HELD

    def test_fundamental_maps_to_blocked(self, classifier):
        result = classifier.map_to_verification(UncertaintyLevel.FUNDAMENTAL)
        assert result == VerificationLevel.BLOCKED


# ---------------------------------------------------------------------------
# Test: ActionMetadata Validation
# ---------------------------------------------------------------------------


class TestActionMetadata:
    def test_valid_metadata(self):
        meta = ActionMetadata(
            data_completeness=0.9,
            precedent_available=True,
            reversible=True,
            impact_scope="local",
        )
        assert meta.data_completeness == 0.9
        assert meta.precedent_available is True
        assert meta.reversible is True
        assert meta.impact_scope == "local"

    def test_data_completeness_clamped_0_to_1(self):
        with pytest.raises(ValueError):
            ActionMetadata(
                data_completeness=1.5,
                precedent_available=True,
                reversible=True,
                impact_scope="local",
            )

    def test_data_completeness_negative_rejected(self):
        with pytest.raises(ValueError):
            ActionMetadata(
                data_completeness=-0.1,
                precedent_available=True,
                reversible=True,
                impact_scope="local",
            )


# ---------------------------------------------------------------------------
# Test: Classification
# ---------------------------------------------------------------------------


class TestClassification:
    def test_high_confidence_action_is_none_uncertainty(self, classifier):
        """Complete data, precedent available, reversible, local scope."""
        meta = ActionMetadata(
            data_completeness=1.0,
            precedent_available=True,
            reversible=True,
            impact_scope="local",
        )
        result = classifier.classify(meta)
        assert result.level == UncertaintyLevel.NONE
        assert result.verification_level == VerificationLevel.AUTO_APPROVED

    def test_mostly_complete_data_informational(self, classifier):
        """Moderate completeness, precedent, reversible, local -> informational."""
        meta = ActionMetadata(
            data_completeness=0.70,
            precedent_available=True,
            reversible=True,
            impact_scope="local",
        )
        result = classifier.classify(meta)
        assert result.level == UncertaintyLevel.INFORMATIONAL
        assert result.verification_level == VerificationLevel.AUTO_APPROVED

    def test_no_precedent_increases_uncertainty(self, classifier):
        """Good data but no precedent -> interpretive (score > 0.25)."""
        meta = ActionMetadata(
            data_completeness=0.8,
            precedent_available=False,
            reversible=True,
            impact_scope="local",
        )
        result = classifier.classify(meta)
        assert result.level == UncertaintyLevel.INTERPRETIVE
        assert result.verification_level == VerificationLevel.FLAGGED

    def test_irreversible_wide_scope_is_judgmental(self, classifier):
        """Moderate data, irreversible, wide scope -> judgmental (score > 0.50)."""
        meta = ActionMetadata(
            data_completeness=0.7,
            precedent_available=True,
            reversible=False,
            impact_scope="organization",
        )
        result = classifier.classify(meta)
        assert result.level == UncertaintyLevel.JUDGMENTAL
        assert result.verification_level == VerificationLevel.HELD

    def test_low_data_completeness_is_fundamental(self, classifier):
        """Very incomplete data signals fundamental uncertainty."""
        meta = ActionMetadata(
            data_completeness=0.2,
            precedent_available=False,
            reversible=False,
            impact_scope="organization",
        )
        result = classifier.classify(meta)
        assert result.level == UncertaintyLevel.FUNDAMENTAL
        assert result.verification_level == VerificationLevel.BLOCKED

    def test_irreversible_organization_scope_no_precedent_fundamental(self, classifier):
        """Worst-case scenario: irreversible, wide scope, no precedent, poor data."""
        meta = ActionMetadata(
            data_completeness=0.3,
            precedent_available=False,
            reversible=False,
            impact_scope="organization",
        )
        result = classifier.classify(meta)
        assert result.level == UncertaintyLevel.FUNDAMENTAL
        assert result.verification_level == VerificationLevel.BLOCKED

    def test_classification_result_includes_reasoning(self, classifier):
        """Classification result should include a reason."""
        meta = ActionMetadata(
            data_completeness=0.5,
            precedent_available=False,
            reversible=True,
            impact_scope="team",
        )
        result = classifier.classify(meta)
        assert result.reason is not None
        assert len(result.reason) > 0


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_data_completeness(self, classifier):
        meta = ActionMetadata(
            data_completeness=0.0,
            precedent_available=False,
            reversible=False,
            impact_scope="organization",
        )
        result = classifier.classify(meta)
        assert result.level == UncertaintyLevel.FUNDAMENTAL

    def test_perfect_data_completeness(self, classifier):
        meta = ActionMetadata(
            data_completeness=1.0,
            precedent_available=True,
            reversible=True,
            impact_scope="local",
        )
        result = classifier.classify(meta)
        assert result.level == UncertaintyLevel.NONE

    def test_boundary_data_completeness(self, classifier):
        """At 0.5, with no precedent and irreversible, should be at least JUDGMENTAL."""
        meta = ActionMetadata(
            data_completeness=0.5,
            precedent_available=False,
            reversible=False,
            impact_scope="team",
        )
        result = classifier.classify(meta)
        # Should be at least JUDGMENTAL (HELD) or FUNDAMENTAL (BLOCKED)
        assert result.level in (UncertaintyLevel.JUDGMENTAL, UncertaintyLevel.FUNDAMENTAL)

    def test_monotonic_progression(self, classifier):
        """Increasing risk factors should monotonically increase uncertainty."""
        # Start with low uncertainty
        low_meta = ActionMetadata(
            data_completeness=0.95,
            precedent_available=True,
            reversible=True,
            impact_scope="local",
        )
        # Higher uncertainty
        high_meta = ActionMetadata(
            data_completeness=0.3,
            precedent_available=False,
            reversible=False,
            impact_scope="organization",
        )
        low_result = classifier.classify(low_meta)
        high_result = classifier.classify(high_meta)
        # The ordering of UncertaintyLevel should reflect this
        levels = list(UncertaintyLevel)
        assert levels.index(low_result.level) <= levels.index(high_result.level)
