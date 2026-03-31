# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for degenerate envelope detection wired into validate_org_detailed().

TODO-21: check_degenerate_envelope() is an L1 function that detects envelopes
so tight that no meaningful action is possible. These tests verify it is
correctly wired into the L3 validation flow.
"""

import pytest

from pact_platform.build.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TeamConfig,
    WorkspaceConfig,
)
from pact_platform.build.org.builder import (
    OrgDefinition,
    ValidationResult,
    ValidationSeverity,
)


def _make_valid_org(
    envelopes: list[ConstraintEnvelopeConfig] | None = None,
) -> OrgDefinition:
    """Create a minimal valid org definition for testing.

    If envelopes is provided, creates agents referencing those envelopes.
    Otherwise creates a single agent with a default permissive envelope.
    """
    ws = WorkspaceConfig(id="ws-1", name="Default", path="/workspace")

    if envelopes is None:
        envelopes = [
            ConstraintEnvelopeConfig(
                id="env-permissive",
                financial=FinancialConstraintConfig(max_spend_usd=10000.0),
                operational=OperationalConstraintConfig(
                    allowed_actions=["read", "write", "execute"],
                    max_actions_per_day=1000,
                ),
                communication=CommunicationConstraintConfig(
                    allowed_channels=["slack", "email"],
                ),
            )
        ]

    agents = []
    for i, env in enumerate(envelopes):
        agents.append(
            AgentConfig(
                id=f"agent-{i}",
                name=f"Agent {i}",
                role=f"role-{i}",
                constraint_envelope=env.id,
            )
        )

    team = TeamConfig(
        id="team-1",
        name="Test Team",
        workspace="ws-1",
        team_lead=agents[0].id if agents else None,
        agents=[a.id for a in agents],
    )

    return OrgDefinition(
        org_id="test-org",
        name="Test Organization",
        teams=[team],
        agents=agents,
        envelopes=envelopes,
        workspaces=[ws],
    )


class TestDegenerateEnvelopeWiring:
    """Validate that validate_org_detailed() surfaces degenerate envelope warnings."""

    def test_permissive_envelope_no_degenerate_warnings(self):
        """A permissive envelope should produce no degenerate warnings."""
        org = _make_valid_org()
        results = org.validate_org_detailed()
        degenerate = [r for r in results if r.code == "DEGENERATE_ENVELOPE"]
        assert degenerate == [], f"Unexpected degenerate warnings: {degenerate}"

    def test_zero_budget_envelope_triggers_degenerate_warning(self):
        """An envelope with $0 budget should be flagged as degenerate."""
        env = ConstraintEnvelopeConfig(
            id="env-zero-budget",
            financial=FinancialConstraintConfig(max_spend_usd=0.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read"],
                max_actions_per_day=100,
            ),
        )
        org = _make_valid_org(envelopes=[env])
        results = org.validate_org_detailed()
        degenerate = [r for r in results if r.code == "DEGENERATE_ENVELOPE"]
        assert len(degenerate) > 0, "Expected degenerate warning for $0 budget envelope"
        # Must be WARNING severity, not ERROR
        for r in degenerate:
            assert r.severity == ValidationSeverity.WARNING

    def test_no_allowed_actions_triggers_degenerate_warning(self):
        """An envelope with no allowed actions should be flagged as degenerate."""
        env = ConstraintEnvelopeConfig(
            id="env-no-actions",
            financial=FinancialConstraintConfig(max_spend_usd=1000.0),
            operational=OperationalConstraintConfig(
                allowed_actions=[],
            ),
        )
        org = _make_valid_org(envelopes=[env])
        results = org.validate_org_detailed()
        degenerate = [r for r in results if r.code == "DEGENERATE_ENVELOPE"]
        assert len(degenerate) > 0, "Expected degenerate warning for empty allowed_actions"
        for r in degenerate:
            assert r.severity == ValidationSeverity.WARNING

    def test_degenerate_warning_message_includes_envelope_id(self):
        """Warning message should identify which envelope is degenerate."""
        env = ConstraintEnvelopeConfig(
            id="env-too-tight",
            financial=FinancialConstraintConfig(max_spend_usd=0.0),
            operational=OperationalConstraintConfig(
                allowed_actions=[],
            ),
        )
        org = _make_valid_org(envelopes=[env])
        results = org.validate_org_detailed()
        degenerate = [r for r in results if r.code == "DEGENERATE_ENVELOPE"]
        assert len(degenerate) > 0
        # Check the message references the envelope ID
        messages = " ".join(r.message for r in degenerate)
        assert "env-too-tight" in messages

    def test_multiple_envelopes_only_degenerate_flagged(self):
        """Only truly degenerate envelopes should be flagged, not permissive ones."""
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
            id="env-degenerate",
            financial=FinancialConstraintConfig(max_spend_usd=0.0),
            operational=OperationalConstraintConfig(
                allowed_actions=[],
            ),
        )
        org = _make_valid_org(envelopes=[env_good, env_bad])
        results = org.validate_org_detailed()
        degenerate = [r for r in results if r.code == "DEGENERATE_ENVELOPE"]
        # Only the bad envelope should be flagged
        messages = " ".join(r.message for r in degenerate)
        assert "env-degenerate" in messages
        assert "env-good" not in messages
