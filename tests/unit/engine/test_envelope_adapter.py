# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for PlatformEnvelopeAdapter.

Covers:
- Envelope resolution and conversion to supervisor params
- NaN/Inf guard on financial, delegation, and rate-limit fields
- Confidentiality level -> data_clearance mapping
- Maximally restrictive defaults when no envelope exists
- Financial field priority (max_spend_usd over api_cost_budget_usd)
- Tool list pass-through
"""

from __future__ import annotations

import math

import pytest

from pact.governance import (
    CompiledOrg,
    GovernanceEngine,
    NodeType,
    OrgNode,
)
from pact_platform.engine.envelope_adapter import (
    PlatformEnvelopeAdapter,
    _DEFAULT_MAX_CHILDREN,
    _DEFAULT_MAX_DEPTH,
    _DEFAULT_TIMEOUT_SECONDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine() -> GovernanceEngine:
    """Create a minimal GovernanceEngine with one department and role."""
    dept = OrgNode(
        address="D1",
        node_type=NodeType.DEPARTMENT,
        name="Department 1",
        node_id="D1",
    )
    role = OrgNode(
        address="D1-R1",
        node_type=NodeType.ROLE,
        name="Role 1",
        node_id="R1",
        parent_address="D1",
    )
    compiled = CompiledOrg(org_id="test-org", nodes={"D1": dept, "D1-R1": role})
    return GovernanceEngine(compiled)


# ---------------------------------------------------------------------------
# Tests: Maximally restrictive defaults
# ---------------------------------------------------------------------------


class TestMaximallyRestrictiveDefaults:
    """When engine.compute_envelope returns None, adapter must return
    maximally restrictive defaults (budget 0, empty tools, public clearance)."""

    def test_no_envelope_returns_zero_budget(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        result = adapter.adapt(envelope=None, role_address="D1-R1")
        assert result["budget_usd"] == 0.0

    def test_no_envelope_returns_empty_tools(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        result = adapter.adapt(envelope=None, role_address="D1-R1")
        assert result["tools"] == []

    def test_no_envelope_returns_public_clearance(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        result = adapter.adapt(envelope=None, role_address="D1-R1")
        assert result["data_clearance"] == "public"

    def test_no_envelope_returns_default_timeout(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        result = adapter.adapt(envelope=None, role_address="D1-R1")
        assert result["timeout_seconds"] == _DEFAULT_TIMEOUT_SECONDS

    def test_no_envelope_returns_default_max_children(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        result = adapter.adapt(envelope=None, role_address="D1-R1")
        assert result["max_children"] == _DEFAULT_MAX_CHILDREN

    def test_no_envelope_returns_default_max_depth(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        result = adapter.adapt(envelope=None, role_address="D1-R1")
        assert result["max_depth"] == _DEFAULT_MAX_DEPTH


# ---------------------------------------------------------------------------
# Tests: Direct envelope conversion
# ---------------------------------------------------------------------------


class TestDirectEnvelopeConversion:
    """Test adapt() with a pre-resolved envelope dict."""

    def test_max_spend_usd_sets_budget(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"financial": {"max_spend_usd": 100.0}}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["budget_usd"] == 100.0

    def test_api_cost_budget_used_as_fallback(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"financial": {"api_cost_budget_usd": 50.0}}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["budget_usd"] == 50.0

    def test_max_spend_usd_takes_priority_over_api_cost_budget(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"financial": {"max_spend_usd": 200.0, "api_cost_budget_usd": 50.0}}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["budget_usd"] == 200.0

    def test_no_financial_field_means_zero_budget(self):
        """Explicit: no financial config -> budget 0, NOT a fallback default."""
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"financial": {}}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["budget_usd"] == 0.0

    def test_allowed_actions_passed_as_tools(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"operational": {"allowed_actions": ["web_search", "code_execute"]}}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["tools"] == ["web_search", "code_execute"]

    def test_empty_allowed_actions_returns_empty_tools(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"operational": {"allowed_actions": []}}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["tools"] == []

    def test_max_delegation_depth_overrides_default(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"max_delegation_depth": 3}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["max_depth"] == 3


# ---------------------------------------------------------------------------
# Tests: Confidentiality clearance mapping
# ---------------------------------------------------------------------------


class TestClearanceMapping:
    """Test confidentiality_clearance -> data_clearance string mapping."""

    @pytest.mark.parametrize(
        "clearance_in,expected",
        [
            ("public", "public"),
            ("restricted", "restricted"),
            ("confidential", "confidential"),
            ("secret", "secret"),
            ("top_secret", "top_secret"),
            ("PUBLIC", "public"),
            ("Restricted", "restricted"),
        ],
    )
    def test_clearance_string_mapping(self, clearance_in, expected):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"confidentiality_clearance": clearance_in}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["data_clearance"] == expected

    def test_unknown_clearance_defaults_to_public(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"confidentiality_clearance": "cosmic_top_secret"}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["data_clearance"] == "public"

    def test_enum_like_clearance_with_value_attribute(self):
        """The adapter handles enum objects with a .value attribute."""

        class FakeEnum:
            value = "confidential"

        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"confidentiality_clearance": FakeEnum()}
        result = adapter.adapt(envelope=envelope, role_address="D1-R1")
        assert result["data_clearance"] == "confidential"


# ---------------------------------------------------------------------------
# Tests: NaN/Inf guards
# ---------------------------------------------------------------------------


class TestNaNInfGuards:
    """All numeric fields must reject NaN and Inf per trust-plane-security rules."""

    def test_nan_max_spend_usd_raises(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"financial": {"max_spend_usd": float("nan")}}
        with pytest.raises(ValueError, match="finite"):
            adapter.adapt(envelope=envelope, role_address="D1-R1")

    def test_inf_max_spend_usd_raises(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"financial": {"max_spend_usd": float("inf")}}
        with pytest.raises(ValueError, match="finite"):
            adapter.adapt(envelope=envelope, role_address="D1-R1")

    def test_neg_inf_api_cost_budget_raises(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"financial": {"api_cost_budget_usd": float("-inf")}}
        with pytest.raises(ValueError, match="finite"):
            adapter.adapt(envelope=envelope, role_address="D1-R1")

    def test_nan_max_delegation_depth_raises(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"max_delegation_depth": float("nan")}
        with pytest.raises(ValueError, match="finite"):
            adapter.adapt(envelope=envelope, role_address="D1-R1")

    def test_nan_max_actions_per_day_raises(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"operational": {"max_actions_per_day": float("nan")}}
        with pytest.raises(ValueError, match="finite"):
            adapter.adapt(envelope=envelope, role_address="D1-R1")

    def test_inf_max_actions_per_hour_raises(self):
        engine = _make_engine()
        adapter = PlatformEnvelopeAdapter(engine)
        envelope = {"operational": {"max_actions_per_hour": float("inf")}}
        with pytest.raises(ValueError, match="finite"):
            adapter.adapt(envelope=envelope, role_address="D1-R1")
