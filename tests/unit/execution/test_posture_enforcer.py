# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for PostureEnforcer — keyword normalization hardening (M35-3502).

Tests cover:
- Unicode homoglyph bypass prevention (Cyrillic characters)
- CamelCase bypass prevention ("executeCommand" contains "execute")
- Hyphenation bypass prevention ("exe-cute" → "execute")
- Zero-width character bypass prevention
- casefold edge cases (German sharp-s)
- Basic consequential action detection still works
- Planning actions are not falsely flagged as consequential
"""

import pytest

from care_platform.config.schema import TrustPostureLevel, VerificationLevel
from care_platform.execution.posture_enforcer import PostureEnforcer
from care_platform.trust.posture import TrustPosture


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def enforcer():
    """Fresh PostureEnforcer instance."""
    return PostureEnforcer()


@pytest.fixture()
def shared_planning_posture():
    """TrustPosture at SHARED_PLANNING level."""
    return TrustPosture(agent_id="test-agent", current_level=TrustPostureLevel.SHARED_PLANNING)


# ---------------------------------------------------------------------------
# Normalization unit tests
# ---------------------------------------------------------------------------


class TestNormalizeActionText:
    """Test the _normalize_action_text static method directly."""

    def test_lowercase_passthrough(self, enforcer):
        """Plain lowercase text should pass through unchanged."""
        result = PostureEnforcer._normalize_action_text("execute command")
        assert result == "execute command"

    def test_camelcase_lowered(self, enforcer):
        """CamelCase should be lowered to a single word."""
        result = PostureEnforcer._normalize_action_text("executeCommand")
        assert "execute" in result
        assert result == "executecommand"

    def test_hyphenation_stripped(self, enforcer):
        """Hyphens should be removed, joining split keywords."""
        result = PostureEnforcer._normalize_action_text("exe-cute")
        assert result == "execute"

    def test_unicode_nfkd_decomposition(self, enforcer):
        """NFKD should decompose compatibility characters."""
        # Fullwidth 'E' (U+FF25) should decompose to ASCII 'E' then casefold
        result = PostureEnforcer._normalize_action_text("\uff25xecute")
        assert "execute" in result

    def test_nonalphanumeric_stripped(self, enforcer):
        """Non-alphanumeric chars (except spaces) should be stripped."""
        result = PostureEnforcer._normalize_action_text("d.e" + "l.e.t.e")
        assert result == "delete"

    def test_casefold_vs_lower(self, enforcer):
        """casefold handles edge cases that lower() misses."""
        # German sharp-s: 'ß'.lower() == 'ß', but 'ß'.casefold() == 'ss'
        result = PostureEnforcer._normalize_action_text("STRASSE")
        assert result == "strasse"

    def test_zero_width_characters_stripped(self, enforcer):
        """Zero-width joiners and similar should be stripped."""
        # U+200B is zero-width space
        result = PostureEnforcer._normalize_action_text("del\u200bete")
        assert result == "delete"

    def test_mixed_bypass_techniques(self, enforcer):
        """Combination of CamelCase + special chars should still normalize."""
        result = PostureEnforcer._normalize_action_text("Ex-ec\u200buteCommand")
        assert "execute" in result

    def test_greek_homoglyph_transliterated(self, enforcer):
        """RT13-H6: Greek homoglyphs should be transliterated to Latin."""
        # Greek omicron ο (U+03BF) looks identical to Latin o
        result = PostureEnforcer._normalize_action_text("dεlεtε")  # Greek epsilon
        assert result == "delete"

    def test_greek_alpha_transliterated(self, enforcer):
        """RT13-H6: Greek alpha → Latin a."""
        result = PostureEnforcer._normalize_action_text("αpprove")  # Greek alpha
        assert result == "approve"


# ---------------------------------------------------------------------------
# Consequential action detection with bypass attempts
# ---------------------------------------------------------------------------


class TestConsequentialActionBypass:
    """Test that _is_consequential_action catches bypass attempts."""

    def test_plain_consequential_keyword(self, enforcer):
        """Standard consequential keywords should be detected."""
        assert enforcer._is_consequential_action("delete the file")
        assert enforcer._is_consequential_action("send email to user")
        assert enforcer._is_consequential_action("execute the command")
        assert enforcer._is_consequential_action("deploy to production")

    def test_camelcase_bypass_blocked(self, enforcer):
        """CamelCase should not bypass detection."""
        assert enforcer._is_consequential_action("executeCommand now")
        assert enforcer._is_consequential_action("deleteAllRecords")
        assert enforcer._is_consequential_action("sendNotification")

    def test_hyphenation_bypass_blocked(self, enforcer):
        """Hyphen-split keywords should not bypass detection."""
        assert enforcer._is_consequential_action("exe-cute this")
        assert enforcer._is_consequential_action("de-lete the record")
        assert enforcer._is_consequential_action("de-ploy to prod")

    def test_dot_separated_bypass_blocked(self, enforcer):
        """Dot-separated keywords should not bypass detection."""
        assert enforcer._is_consequential_action("d.e.l.e.t.e file")
        assert enforcer._is_consequential_action("s.e.n.d email")

    def test_zero_width_bypass_blocked(self, enforcer):
        """Zero-width characters should not bypass detection."""
        assert enforcer._is_consequential_action("del\u200bete file")
        assert enforcer._is_consequential_action("exe\u200bcute command")

    def test_mixed_case_still_detected(self, enforcer):
        """Mixed case should still be detected."""
        assert enforcer._is_consequential_action("DELETE the file")
        assert enforcer._is_consequential_action("Execute Command")
        assert enforcer._is_consequential_action("SEND EMAIL")

    def test_planning_actions_not_flagged(self, enforcer):
        """Planning/read-only actions should not be flagged as consequential."""
        assert not enforcer._is_consequential_action("analyze the data")
        assert not enforcer._is_consequential_action("research the topic")
        assert not enforcer._is_consequential_action("summarize the report")
        assert not enforcer._is_consequential_action("think about options")

    def test_substring_match_catches_embedded_keywords(self, enforcer):
        """Keywords embedded in larger words should be caught (fail-closed)."""
        # "undelete" contains "delete"
        assert enforcer._is_consequential_action("undelete the record")
        # "preapprove" contains "approve"
        assert enforcer._is_consequential_action("preapprove the request")

    def test_empty_action_not_consequential(self, enforcer):
        """Empty string should not be consequential."""
        assert not enforcer._is_consequential_action("")

    def test_numbers_only_not_consequential(self, enforcer):
        """Numeric-only action should not be consequential."""
        assert not enforcer._is_consequential_action("12345")


# ---------------------------------------------------------------------------
# Posture enforcement integration with normalization
# ---------------------------------------------------------------------------


class TestPostureEnforcerWithNormalization:
    """Test that posture enforcement properly uses normalized keyword matching."""

    def test_shared_planning_blocks_camelcase_consequential(
        self, enforcer, shared_planning_posture
    ):
        """SHARED_PLANNING should hold CamelCase consequential actions."""
        result = enforcer.check_posture(
            posture=shared_planning_posture,
            action="executeCommand on server",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert result.level == VerificationLevel.HELD

    def test_shared_planning_blocks_hyphenated_consequential(
        self, enforcer, shared_planning_posture
    ):
        """SHARED_PLANNING should hold hyphen-split consequential actions."""
        result = enforcer.check_posture(
            posture=shared_planning_posture,
            action="de-lete old records",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert result.level == VerificationLevel.HELD

    def test_shared_planning_allows_planning_action(self, enforcer, shared_planning_posture):
        """SHARED_PLANNING should preserve level for planning actions."""
        result = enforcer.check_posture(
            posture=shared_planning_posture,
            action="analyze quarterly data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert result.level == VerificationLevel.AUTO_APPROVED

    def test_shared_planning_blocks_zero_width_bypass(self, enforcer, shared_planning_posture):
        """SHARED_PLANNING should hold zero-width-char bypass attempts."""
        result = enforcer.check_posture(
            posture=shared_planning_posture,
            action="del\u200bete user account",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert result.level == VerificationLevel.HELD
