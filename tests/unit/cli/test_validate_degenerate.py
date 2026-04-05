# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for degenerate envelope warning in `pact validate` CLI (TODO-21).

Validates that the build CLI validate command surfaces degenerate envelope
warnings when constraint envelopes are too restrictive.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pact_platform.build.cli import _check_envelopes_degenerate


class TestCheckEnvelopesDegenerate:
    """Unit tests for _check_envelopes_degenerate helper."""

    def test_no_envelopes_returns_empty(self):
        """Empty envelope list produces no warnings."""
        result = _check_envelopes_degenerate([])
        assert result == []

    def test_permissive_envelope_no_warnings(self):
        """A permissive envelope should produce no degenerate warnings."""
        from pact_platform.build.config.schema import (
            CommunicationConstraintConfig,
            ConstraintEnvelopeConfig,
            FinancialConstraintConfig,
            OperationalConstraintConfig,
        )

        env = ConstraintEnvelopeConfig(
            id="env-good",
            financial=FinancialConstraintConfig(max_spend_usd=10000.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
                max_actions_per_day=500,
            ),
            communication=CommunicationConstraintConfig(
                allowed_channels=["slack", "email"],
            ),
        )
        result = _check_envelopes_degenerate([env])
        assert result == []

    def test_degenerate_envelope_produces_warnings(self):
        """An envelope with $0 budget and no actions should produce warnings."""
        from pact_platform.build.config.schema import (
            ConstraintEnvelopeConfig,
            FinancialConstraintConfig,
            OperationalConstraintConfig,
        )

        env = ConstraintEnvelopeConfig(
            id="env-degenerate",
            financial=FinancialConstraintConfig(max_spend_usd=0.0),
            operational=OperationalConstraintConfig(allowed_actions=[]),
        )
        result = _check_envelopes_degenerate([env])
        assert len(result) > 0
        # Each result should be a (envelope_id, warning_msg) tuple
        for env_id, msg in result:
            assert env_id == "env-degenerate"
            assert isinstance(msg, str)
            assert len(msg) > 0

    def test_mixed_envelopes_only_degenerate_flagged(self):
        """Only degenerate envelopes should be flagged, not permissive ones."""
        from pact_platform.build.config.schema import (
            CommunicationConstraintConfig,
            ConstraintEnvelopeConfig,
            FinancialConstraintConfig,
            OperationalConstraintConfig,
        )

        env_good = ConstraintEnvelopeConfig(
            id="env-good",
            financial=FinancialConstraintConfig(max_spend_usd=5000.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
                max_actions_per_day=500,
            ),
            communication=CommunicationConstraintConfig(
                allowed_channels=["slack", "email"],
            ),
        )
        env_bad = ConstraintEnvelopeConfig(
            id="env-bad",
            financial=FinancialConstraintConfig(max_spend_usd=0.0),
            operational=OperationalConstraintConfig(allowed_actions=[]),
        )
        result = _check_envelopes_degenerate([env_good, env_bad])
        env_ids = {r[0] for r in result}
        assert "env-bad" in env_ids
        assert "env-good" not in env_ids

    def test_import_error_returns_empty(self):
        """When L1 check_degenerate_envelope is unavailable, return empty."""
        with patch.dict("sys.modules", {"pact.governance": None}):
            # The function catches ImportError gracefully
            result = _check_envelopes_degenerate([MagicMock(id="test")])
        # Should return empty, not crash
        assert isinstance(result, list)
