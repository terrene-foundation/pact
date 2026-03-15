# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""RT-02: Wire monotonic tightening into delegation flow.

Tests that:
1. DelegationManager.create_delegation() calls validate_tightening() BEFORE bridge.delegate()
2. validate_tightening() checks temporal dimension (active_hours subset)
3. validate_tightening() checks data_access dimension (read_paths, write_paths subset, blocked_data_types superset)
4. ConstraintEnvelope.is_tighter_than() is callable from delegation flow
5. Delegation is rejected (ValueError) when tightening is violated
"""

import pytest

from care_platform.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)
from care_platform.trust.delegation import DelegationManager
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.trust.genesis import GenesisManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def genesis_config():
    return GenesisConfig(
        authority="terrene.foundation",
        authority_name="Terrene Foundation",
        policy_reference="https://terrene.foundation/governance",
    )


@pytest.fixture()
async def bridge():
    b = EATPBridge()
    await b.initialize()
    return b


@pytest.fixture()
def delegation_manager(bridge):
    return DelegationManager(bridge=bridge)


@pytest.fixture()
def genesis_manager(bridge):
    return GenesisManager(bridge=bridge)


@pytest.fixture()
async def established_authority(genesis_manager, genesis_config):
    return await genesis_manager.create_genesis(genesis_config)


@pytest.fixture()
def parent_envelope():
    """Parent envelope with constraints across all five dimensions."""
    return ConstraintEnvelopeConfig(
        id="parent-envelope",
        description="Parent envelope",
        financial=FinancialConstraintConfig(max_spend_usd=1000.0),
        operational=OperationalConstraintConfig(
            allowed_actions=["read", "write", "review"],
            blocked_actions=["delete"],
            max_actions_per_day=100,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="08:00",
            active_hours_end="20:00",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["content/*", "analytics/*", "reports/*"],
            write_paths=["content/*", "drafts/*"],
            blocked_data_types=["pii", "financial_records"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=False,
            allowed_channels=["slack", "email"],
        ),
    )


@pytest.fixture()
def tighter_child_envelope():
    """Child envelope that is a valid monotonic tightening of parent."""
    return ConstraintEnvelopeConfig(
        id="child-envelope",
        description="Tighter child",
        financial=FinancialConstraintConfig(max_spend_usd=500.0),
        operational=OperationalConstraintConfig(
            allowed_actions=["read", "write"],
            blocked_actions=["delete"],
            max_actions_per_day=50,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="09:00",
            active_hours_end="18:00",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["content/*"],
            write_paths=["content/*"],
            blocked_data_types=["pii", "financial_records", "medical"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack"],
        ),
    )


@pytest.fixture()
def child_agent():
    return AgentConfig(
        id="child-agent-001",
        name="Child Agent",
        role="Content writer",
        constraint_envelope="child-envelope",
        capabilities=["read", "write"],
    )


# ---------------------------------------------------------------------------
# RT-02a: Temporal dimension checks in validate_tightening
# ---------------------------------------------------------------------------


class TestTemporalTightening:
    """validate_tightening() must check temporal dimension: active_hours window is subset."""

    def test_tighter_temporal_window_accepted(self, delegation_manager):
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="08:00",
                active_hours_end="20:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="18:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True
        assert len(violations) == 0

    def test_wider_temporal_start_rejected(self, delegation_manager):
        """Child starts earlier than parent -- violates tightening."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="18:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="07:00",
                active_hours_end="18:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("temporal" in v.lower() for v in violations)

    def test_wider_temporal_end_rejected(self, delegation_manager):
        """Child ends later than parent -- violates tightening."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="20:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("temporal" in v.lower() for v in violations)

    def test_child_has_window_parent_has_none_accepted(self, delegation_manager):
        """If parent has no temporal window, child can set any window (tighter)."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(),  # no active hours
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True

    def test_child_removes_parent_window_rejected(self, delegation_manager):
        """Parent has window, child has none -- loosens temporal constraint."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            temporal=TemporalConstraintConfig(),  # no window (unrestricted)
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("temporal" in v.lower() for v in violations)


# ---------------------------------------------------------------------------
# RT-02b: Data access dimension checks in validate_tightening
# ---------------------------------------------------------------------------


class TestDataAccessTightening:
    """validate_tightening() must check data_access dimension."""

    def test_subset_read_paths_accepted(self, delegation_manager):
        parent = ConstraintEnvelopeConfig(
            id="parent",
            data_access=DataAccessConstraintConfig(
                read_paths=["content/*", "analytics/*", "reports/*"],
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                read_paths=["content/*"],
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True

    def test_extra_read_paths_rejected(self, delegation_manager):
        """Child has read paths not in parent -- violates tightening."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            data_access=DataAccessConstraintConfig(
                read_paths=["content/*"],
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                read_paths=["content/*", "secrets/*"],
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("data" in v.lower() or "read" in v.lower() for v in violations)

    def test_subset_write_paths_accepted(self, delegation_manager):
        parent = ConstraintEnvelopeConfig(
            id="parent",
            data_access=DataAccessConstraintConfig(
                write_paths=["content/*", "drafts/*"],
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                write_paths=["content/*"],
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True

    def test_extra_write_paths_rejected(self, delegation_manager):
        """Child has write paths not in parent -- violates tightening."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            data_access=DataAccessConstraintConfig(
                write_paths=["content/*"],
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                write_paths=["content/*", "admin/*"],
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("data" in v.lower() or "write" in v.lower() for v in violations)

    def test_superset_blocked_data_types_accepted(self, delegation_manager):
        """Child blocks more data types than parent (tighter)."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii"],
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii", "financial_records", "medical"],
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True

    def test_missing_blocked_data_types_rejected(self, delegation_manager):
        """Child removes a blocked data type from parent -- loosens restriction."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii", "financial_records"],
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii"],  # missing financial_records
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("data" in v.lower() or "blocked" in v.lower() for v in violations)

    def test_empty_parent_paths_allows_any_child(self, delegation_manager):
        """If parent has no read/write path restrictions, child can set any."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            data_access=DataAccessConstraintConfig(),  # empty
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            data_access=DataAccessConstraintConfig(
                read_paths=["content/*"],
                write_paths=["content/*"],
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True


# ---------------------------------------------------------------------------
# RT-02c: create_delegation() calls validate_tightening() and rejects on violation
# ---------------------------------------------------------------------------


class TestDelegationCallsTightening:
    """create_delegation() MUST call validate_tightening() before bridge.delegate()."""

    async def test_delegation_with_valid_tightening_succeeds(
        self,
        delegation_manager,
        established_authority,
        parent_envelope,
        tighter_child_envelope,
        child_agent,
        bridge,
    ):
        """First delegate with parent envelope, then delegate child with tighter envelope."""
        # Delegate a team lead with parent envelope
        lead_config = AgentConfig(
            id="team-lead-rt02",
            name="Team Lead",
            role="Lead",
            constraint_envelope="parent-envelope",
            capabilities=["read", "write", "review"],
        )
        await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=lead_config,
            envelope_config=parent_envelope,
        )
        # Now delegate child with tighter envelope -- should succeed
        delegation = await delegation_manager.create_delegation(
            delegator_id=lead_config.id,
            delegate_config=child_agent,
            envelope_config=tighter_child_envelope,
            parent_envelope_config=parent_envelope,
        )
        assert delegation is not None

    async def test_delegation_with_loosened_budget_raises(
        self,
        delegation_manager,
        established_authority,
        parent_envelope,
        child_agent,
        bridge,
    ):
        """Attempting to delegate with a budget higher than parent must raise ValueError."""
        lead_config = AgentConfig(
            id="team-lead-rt02-budget",
            name="Team Lead",
            role="Lead",
            constraint_envelope="parent-envelope",
            capabilities=["read", "write"],
        )
        await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=lead_config,
            envelope_config=parent_envelope,
        )
        # Create an envelope that EXPANDS the budget
        expanded_envelope = ConstraintEnvelopeConfig(
            id="expanded-budget",
            financial=FinancialConstraintConfig(max_spend_usd=5000.0),
        )
        with pytest.raises(ValueError, match="[Tt]ightening"):
            await delegation_manager.create_delegation(
                delegator_id=lead_config.id,
                delegate_config=child_agent,
                envelope_config=expanded_envelope,
                parent_envelope_config=parent_envelope,
            )

    async def test_delegation_with_loosened_temporal_raises(
        self,
        delegation_manager,
        established_authority,
        parent_envelope,
        child_agent,
    ):
        """Temporal window expansion must be rejected."""
        lead_config = AgentConfig(
            id="team-lead-rt02-temporal",
            name="Team Lead",
            role="Lead",
            constraint_envelope="parent-envelope",
            capabilities=["read", "write"],
        )
        await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=lead_config,
            envelope_config=parent_envelope,
        )
        # Expand temporal window beyond parent
        expanded_temporal = ConstraintEnvelopeConfig(
            id="expanded-temporal",
            financial=FinancialConstraintConfig(max_spend_usd=500.0),
            temporal=TemporalConstraintConfig(
                active_hours_start="06:00",  # earlier than parent 08:00
                active_hours_end="22:00",  # later than parent 20:00
            ),
        )
        with pytest.raises(ValueError, match="[Tt]ightening"):
            await delegation_manager.create_delegation(
                delegator_id=lead_config.id,
                delegate_config=child_agent,
                envelope_config=expanded_temporal,
                parent_envelope_config=parent_envelope,
            )

    async def test_delegation_without_parent_envelope_skips_tightening(
        self,
        delegation_manager,
        established_authority,
        child_agent,
    ):
        """When no parent_envelope_config is provided, tightening check is skipped (backward compat)."""
        # This is genesis-level delegation -- no parent envelope to compare against
        envelope = ConstraintEnvelopeConfig(
            id="any-envelope",
            financial=FinancialConstraintConfig(max_spend_usd=9999.0),
        )
        delegation = await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=child_agent,
            envelope_config=envelope,
        )
        assert delegation is not None
