# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for post-execution TOCTOU comparison audit.

Tests audit_toctou_check — a batch audit function that compares envelope
snapshots recorded during verify_action with the current org state, detecting
cases where the governance envelope changed after a verdict was issued.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_verdict(
    role_address: str,
    level: str = "auto_approved",
    envelope_version: str = "abc123",
    action: str = "read_data",
) -> MagicMock:
    """Create a mock GovernanceVerdict with the given fields."""
    verdict = MagicMock()
    verdict.role_address = role_address
    verdict.level = level
    verdict.envelope_version = envelope_version
    verdict.action = action
    verdict.timestamp = datetime.now(timezone.utc)
    verdict.effective_envelope_snapshot = {"id": "env-1"}
    return verdict


@pytest.fixture()
def mock_engine():
    """Create a mock GovernanceEngine."""
    engine = MagicMock()
    engine.org_name = "Test Org"
    return engine


# ---------------------------------------------------------------------------
# Tests: audit_toctou_check — no divergences
# ---------------------------------------------------------------------------


class TestToctouNoDivergence:
    """Test cases where envelope has not changed since verdict."""

    def test_no_verdicts_returns_empty(self, mock_engine):
        from pact_platform.use.audit.toctou import audit_toctou_check

        result = audit_toctou_check(mock_engine, [])
        assert result == []

    def test_matching_version_returns_no_divergence(self, mock_engine):
        from pact_platform.use.audit.toctou import audit_toctou_check

        # Engine returns an envelope whose hash matches the recorded version
        mock_envelope = MagicMock()
        mock_envelope.model_dump.return_value = {"id": "env-1", "max_cost": 100.0}
        mock_engine.compute_envelope.return_value = mock_envelope

        verdict = _make_verdict("D1-R1", envelope_version="match-hash")

        # Patch the version computation to return the same hash
        import hashlib
        import json

        expected_hash = hashlib.sha256(
            json.dumps(mock_envelope.model_dump(), sort_keys=True, default=str).encode()
        ).hexdigest()
        verdict.envelope_version = expected_hash

        result = audit_toctou_check(mock_engine, [verdict])
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests: audit_toctou_check — divergences detected
# ---------------------------------------------------------------------------


class TestToctouDivergence:
    """Test cases where envelope changed after verdict was issued."""

    def test_version_mismatch_returns_divergence(self, mock_engine):
        from pact_platform.use.audit.toctou import audit_toctou_check

        mock_envelope = MagicMock()
        mock_envelope.model_dump.return_value = {"id": "env-1", "max_cost": 200.0}
        mock_engine.compute_envelope.return_value = mock_envelope

        verdict = _make_verdict("D1-R1", envelope_version="old-hash-from-verdict")

        result = audit_toctou_check(mock_engine, [verdict])
        assert len(result) == 1
        div = result[0]
        assert div["role_address"] == "D1-R1"
        assert div["recorded_version"] == "old-hash-from-verdict"
        assert "current_version" in div
        assert div["current_version"] != "old-hash-from-verdict"
        assert "timestamp" in div

    def test_multiple_verdicts_mixed_results(self, mock_engine):
        from pact_platform.use.audit.toctou import audit_toctou_check

        import hashlib
        import json

        # Envelope for D1-R1 matches
        mock_envelope_1 = MagicMock()
        env_data_1 = {"id": "env-1", "max_cost": 100.0}
        mock_envelope_1.model_dump.return_value = env_data_1
        matching_hash = hashlib.sha256(
            json.dumps(env_data_1, sort_keys=True, default=str).encode()
        ).hexdigest()

        # Envelope for D1-R1-T1-R1 does NOT match
        mock_envelope_2 = MagicMock()
        mock_envelope_2.model_dump.return_value = {"id": "env-2", "max_cost": 500.0}

        def compute_side_effect(role_address, task_id=None):
            if role_address == "D1-R1":
                return mock_envelope_1
            return mock_envelope_2

        mock_engine.compute_envelope.side_effect = compute_side_effect

        verdict_ok = _make_verdict("D1-R1", envelope_version=matching_hash)
        verdict_mismatch = _make_verdict("D1-R1-T1-R1", envelope_version="stale-version")

        result = audit_toctou_check(mock_engine, [verdict_ok, verdict_mismatch])
        assert len(result) == 1
        assert result[0]["role_address"] == "D1-R1-T1-R1"


# ---------------------------------------------------------------------------
# Tests: audit_toctou_check — edge cases
# ---------------------------------------------------------------------------


class TestToctouEdgeCases:
    """Test edge cases in TOCTOU comparison."""

    def test_no_envelope_for_role_returns_divergence(self, mock_engine):
        """If compute_envelope returns None, the envelope was removed — that is a divergence."""
        from pact_platform.use.audit.toctou import audit_toctou_check

        mock_engine.compute_envelope.return_value = None

        verdict = _make_verdict("D1-R1", envelope_version="had-an-envelope-before")

        result = audit_toctou_check(mock_engine, [verdict])
        assert len(result) == 1
        assert result[0]["current_version"] is None

    def test_empty_envelope_version_skipped(self, mock_engine):
        """Verdicts with empty envelope_version are skipped (no comparison possible)."""
        from pact_platform.use.audit.toctou import audit_toctou_check

        verdict = _make_verdict("D1-R1", envelope_version="")

        result = audit_toctou_check(mock_engine, [verdict])
        assert len(result) == 0

    def test_compute_envelope_error_returns_divergence(self, mock_engine):
        """If compute_envelope raises, treat as divergence with error info."""
        from pact_platform.use.audit.toctou import audit_toctou_check

        mock_engine.compute_envelope.side_effect = RuntimeError("Engine failure")

        verdict = _make_verdict("D1-R1", envelope_version="some-hash")

        result = audit_toctou_check(mock_engine, [verdict])
        assert len(result) == 1
        assert "error" in result[0]

    def test_divergence_includes_action(self, mock_engine):
        """Divergence records should include the action from the original verdict."""
        from pact_platform.use.audit.toctou import audit_toctou_check

        mock_envelope = MagicMock()
        mock_envelope.model_dump.return_value = {"id": "env-1"}
        mock_engine.compute_envelope.return_value = mock_envelope

        verdict = _make_verdict("D1-R1", envelope_version="old-hash", action="send_email")

        result = audit_toctou_check(mock_engine, [verdict])
        assert len(result) == 1
        assert result[0]["action"] == "send_email"
