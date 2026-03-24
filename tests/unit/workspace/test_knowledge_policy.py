# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for KnowledgePolicyEnforcer — workspace knowledge policy enforcement.

M17-1702: KnowledgePolicyEnforcer checks data access against workspace knowledge policies.
- Policies define what data types, paths, and classifications are allowed per workspace.
- Bridge access that violates policy is denied.
- Bridge access that complies with policy is allowed.
"""

from __future__ import annotations

import pytest

from pact_platform.build.workspace.knowledge_policy import (
    KnowledgePolicy,
    KnowledgePolicyEnforcer,
    PolicyDecision,
    PolicyViolation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_policy(
    workspace_id: str = "ws-engineering",
    allowed_read_classifications: list[str] | None = None,
    blocked_read_classifications: list[str] | None = None,
    allowed_write_classifications: list[str] | None = None,
    blocked_write_classifications: list[str] | None = None,
    max_data_sensitivity: str = "internal",
    allowed_data_types: list[str] | None = None,
    blocked_data_types: list[str] | None = None,
) -> KnowledgePolicy:
    return KnowledgePolicy(
        workspace_id=workspace_id,
        allowed_read_classifications=allowed_read_classifications or ["public", "internal"],
        blocked_read_classifications=blocked_read_classifications or ["top_secret"],
        allowed_write_classifications=allowed_write_classifications or ["internal"],
        blocked_write_classifications=blocked_write_classifications
        or ["top_secret", "confidential"],
        max_data_sensitivity=max_data_sensitivity,
        allowed_data_types=allowed_data_types or [],
        blocked_data_types=blocked_data_types or ["credentials", "pii"],
    )


# ---------------------------------------------------------------------------
# KnowledgePolicy model
# ---------------------------------------------------------------------------


class TestKnowledgePolicyModel:
    """KnowledgePolicy model holds workspace-level data access rules."""

    def test_create_policy(self):
        policy = _make_policy()
        assert policy.workspace_id == "ws-engineering"
        assert "public" in policy.allowed_read_classifications
        assert "top_secret" in policy.blocked_read_classifications

    def test_policy_with_blocked_data_types(self):
        policy = _make_policy(blocked_data_types=["credentials", "pii", "financial"])
        assert "financial" in policy.blocked_data_types

    def test_policy_requires_workspace_id(self):
        with pytest.raises(ValueError, match="workspace_id"):
            KnowledgePolicy(
                workspace_id="",
                allowed_read_classifications=["public"],
                blocked_read_classifications=[],
                allowed_write_classifications=[],
                blocked_write_classifications=[],
                max_data_sensitivity="public",
                allowed_data_types=[],
                blocked_data_types=[],
            )


# ---------------------------------------------------------------------------
# KnowledgePolicyEnforcer — read access checks
# ---------------------------------------------------------------------------


class TestKnowledgePolicyEnforcerRead:
    """KnowledgePolicyEnforcer enforces read access policies."""

    def test_allowed_read_classification_passes(self):
        policy = _make_policy()
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="docs/architecture.md",
            access_type="read",
            data_classification="internal",
        )
        assert decision.allowed is True
        assert len(decision.violations) == 0

    def test_blocked_read_classification_denied(self):
        policy = _make_policy()
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="secrets/keys.yaml",
            access_type="read",
            data_classification="top_secret",
        )
        assert decision.allowed is False
        assert len(decision.violations) >= 1
        assert any("classification" in v.reason.lower() for v in decision.violations)

    def test_unknown_classification_denied(self):
        """Classifications not in the allowed list should be denied."""
        policy = _make_policy(allowed_read_classifications=["public"])
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="docs/internal.md",
            access_type="read",
            data_classification="confidential",
        )
        assert decision.allowed is False

    def test_public_classification_allowed(self):
        policy = _make_policy()
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="readme.md",
            access_type="read",
            data_classification="public",
        )
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# KnowledgePolicyEnforcer — write access checks
# ---------------------------------------------------------------------------


class TestKnowledgePolicyEnforcerWrite:
    """KnowledgePolicyEnforcer enforces write access policies."""

    def test_allowed_write_classification_passes(self):
        policy = _make_policy()
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="docs/notes.md",
            access_type="write",
            data_classification="internal",
        )
        assert decision.allowed is True

    def test_blocked_write_classification_denied(self):
        policy = _make_policy()
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="secrets/config.yaml",
            access_type="write",
            data_classification="confidential",
        )
        assert decision.allowed is False
        assert len(decision.violations) >= 1


# ---------------------------------------------------------------------------
# KnowledgePolicyEnforcer — data type checks
# ---------------------------------------------------------------------------


class TestKnowledgePolicyEnforcerDataTypes:
    """KnowledgePolicyEnforcer enforces data type restrictions."""

    def test_blocked_data_type_denied(self):
        policy = _make_policy(blocked_data_types=["credentials", "pii"])
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="config/api_keys.json",
            access_type="read",
            data_classification="internal",
            data_type="credentials",
        )
        assert decision.allowed is False
        assert any("data type" in v.reason.lower() for v in decision.violations)

    def test_allowed_data_type_passes(self):
        policy = _make_policy(blocked_data_types=["credentials"])
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="docs/readme.md",
            access_type="read",
            data_classification="internal",
            data_type="documentation",
        )
        assert decision.allowed is True

    def test_no_data_type_specified_passes(self):
        """When data_type is not specified, only classification is checked."""
        policy = _make_policy(blocked_data_types=["credentials"])
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="docs/readme.md",
            access_type="read",
            data_classification="internal",
        )
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# KnowledgePolicyEnforcer — workspace lookup
# ---------------------------------------------------------------------------


class TestKnowledgePolicyEnforcerWorkspaceLookup:
    """KnowledgePolicyEnforcer handles workspace lookup correctly."""

    def test_unknown_workspace_denied(self):
        """Access to an unregistered workspace should be denied."""
        policy = _make_policy(workspace_id="ws-engineering")
        enforcer = KnowledgePolicyEnforcer(policies=[policy])

        decision = enforcer.check_access(
            workspace_id="ws-unknown",
            path="docs/readme.md",
            access_type="read",
            data_classification="public",
        )
        assert decision.allowed is False
        assert any("no policy" in v.reason.lower() for v in decision.violations)

    def test_multiple_workspaces_independent(self):
        """Each workspace has independent policies."""
        eng_policy = _make_policy(
            workspace_id="ws-engineering",
            allowed_read_classifications=["public", "internal"],
        )
        hr_policy = _make_policy(
            workspace_id="ws-hr",
            allowed_read_classifications=["public"],
            blocked_read_classifications=["internal", "top_secret"],
        )
        enforcer = KnowledgePolicyEnforcer(policies=[eng_policy, hr_policy])

        # Engineering can read internal
        eng_decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="docs/arch.md",
            access_type="read",
            data_classification="internal",
        )
        assert eng_decision.allowed is True

        # HR cannot read internal
        hr_decision = enforcer.check_access(
            workspace_id="ws-hr",
            path="docs/arch.md",
            access_type="read",
            data_classification="internal",
        )
        assert hr_decision.allowed is False

    def test_add_policy_after_init(self):
        enforcer = KnowledgePolicyEnforcer(policies=[])
        policy = _make_policy(workspace_id="ws-new")
        enforcer.add_policy(policy)

        decision = enforcer.check_access(
            workspace_id="ws-new",
            path="readme.md",
            access_type="read",
            data_classification="public",
        )
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# PolicyDecision model
# ---------------------------------------------------------------------------


class TestPolicyDecision:
    """PolicyDecision provides clear allow/deny information."""

    def test_allowed_decision(self):
        decision = PolicyDecision(allowed=True, violations=[])
        assert decision.allowed is True
        assert len(decision.violations) == 0

    def test_denied_decision(self):
        violation = PolicyViolation(
            reason="Classification 'top_secret' is blocked for read access",
            policy_workspace_id="ws-eng",
            dimension="classification",
        )
        decision = PolicyDecision(allowed=False, violations=[violation])
        assert decision.allowed is False
        assert decision.violations[0].dimension == "classification"
