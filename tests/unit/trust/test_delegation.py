# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Delegation Manager — manages delegation chains with monotonic tightening."""

import pytest

from care_platform.build.config.schema import (
    AgentConfig,
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)
from care_platform.trust.delegation import ChainStatus, ChainWalkResult, DelegationManager
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
def team_lead_config():
    return AgentConfig(
        id="team-lead-001",
        name="Team Lead",
        role="Leads the content team",
        constraint_envelope="envelope-lead",
        capabilities=[
            "analyze_data",
            "review_content",
            "approve_drafts",
            "draft_content",
            "edit_content",
        ],
    )


@pytest.fixture()
def specialist_config():
    return AgentConfig(
        id="specialist-001",
        name="Content Specialist",
        role="Writes and edits content",
        constraint_envelope="envelope-specialist",
        capabilities=["draft_content", "edit_content"],
    )


@pytest.fixture()
def lead_envelope():
    return ConstraintEnvelopeConfig(
        id="envelope-lead",
        description="Team lead envelope",
        financial=FinancialConstraintConfig(max_spend_usd=1000.0),
        operational=OperationalConstraintConfig(
            allowed_actions=["analyze_data", "review_content", "approve_drafts", "delegate_work"],
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="08:00",
            active_hours_end="20:00",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["content/*", "analytics/*"],
            write_paths=["content/*"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=False,
            allowed_channels=["slack", "email"],
        ),
    )


@pytest.fixture()
def specialist_envelope():
    """Tighter envelope than lead — valid monotonic tightening."""
    return ConstraintEnvelopeConfig(
        id="envelope-specialist",
        description="Specialist envelope",
        financial=FinancialConstraintConfig(max_spend_usd=200.0),
        operational=OperationalConstraintConfig(
            allowed_actions=["draft_content", "edit_content"],
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="09:00",
            active_hours_end="18:00",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["content/*"],
            write_paths=["content/drafts/*"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack"],
        ),
    )


@pytest.fixture()
def expanded_envelope():
    """Intentionally expanded envelope — violates monotonic tightening in budget."""
    return ConstraintEnvelopeConfig(
        id="envelope-expanded",
        description="Expanded envelope (SHOULD FAIL tightening)",
        financial=FinancialConstraintConfig(max_spend_usd=5000.0),  # higher than lead's 1000
        operational=OperationalConstraintConfig(
            allowed_actions=["analyze_data", "review_content", "approve_drafts", "deploy_code"],
        ),
    )


@pytest.fixture()
async def bridge():
    b = EATPBridge()
    await b.initialize()
    return b


@pytest.fixture()
def genesis_manager(bridge):
    return GenesisManager(bridge=bridge)


@pytest.fixture()
def delegation_manager(bridge):
    return DelegationManager(bridge=bridge)


@pytest.fixture()
async def established_authority(genesis_manager, genesis_config):
    """Returns genesis record after establishing root authority."""
    return await genesis_manager.create_genesis(genesis_config)


# ---------------------------------------------------------------------------
# Test: Delegation Creation
# ---------------------------------------------------------------------------


class TestDelegationCreation:
    async def test_create_delegation_returns_record(
        self,
        delegation_manager,
        established_authority,
        team_lead_config,
        lead_envelope,
        bridge,
    ):
        from eatp.chain import DelegationRecord

        delegation = await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        assert isinstance(delegation, DelegationRecord)

    async def test_delegation_has_correct_delegatee(
        self,
        delegation_manager,
        established_authority,
        team_lead_config,
        lead_envelope,
    ):
        delegation = await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        assert delegation.delegatee_id == team_lead_config.id

    async def test_delegation_has_capabilities(
        self,
        delegation_manager,
        established_authority,
        team_lead_config,
        lead_envelope,
    ):
        delegation = await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        assert len(delegation.capabilities_delegated) > 0

    async def test_delegation_has_constraints(
        self,
        delegation_manager,
        established_authority,
        team_lead_config,
        lead_envelope,
    ):
        delegation = await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        assert len(delegation.constraint_subset) > 0

    async def test_delegation_fails_for_unknown_delegator(
        self,
        delegation_manager,
        team_lead_config,
        lead_envelope,
    ):
        with pytest.raises(ValueError):
            await delegation_manager.create_delegation(
                delegator_id="unknown-delegator",
                delegate_config=team_lead_config,
                envelope_config=lead_envelope,
            )

    async def test_chained_delegation(
        self,
        delegation_manager,
        established_authority,
        team_lead_config,
        specialist_config,
        lead_envelope,
        specialist_envelope,
    ):
        """Delegate authority -> lead -> specialist."""
        await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        specialist_deleg = await delegation_manager.create_delegation(
            delegator_id=team_lead_config.id,
            delegate_config=specialist_config,
            envelope_config=specialist_envelope,
        )
        assert specialist_deleg.delegatee_id == specialist_config.id


# ---------------------------------------------------------------------------
# Test: Monotonic Tightening Validation
# ---------------------------------------------------------------------------


class TestMonotonicTightening:
    def test_tighter_budget_accepted(self, delegation_manager):
        parent = ConstraintEnvelopeConfig(
            id="parent",
            financial=FinancialConstraintConfig(max_spend_usd=1000.0),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            financial=FinancialConstraintConfig(max_spend_usd=500.0),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True
        assert len(violations) == 0

    def test_higher_budget_rejected(self, delegation_manager):
        parent = ConstraintEnvelopeConfig(
            id="parent",
            financial=FinancialConstraintConfig(max_spend_usd=1000.0),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            financial=FinancialConstraintConfig(max_spend_usd=2000.0),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("financial" in v.lower() or "budget" in v.lower() for v in violations)

    def test_fewer_actions_accepted(self, delegation_manager):
        parent = ConstraintEnvelopeConfig(
            id="parent",
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write", "delete"],
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True

    def test_more_actions_rejected(self, delegation_manager):
        parent = ConstraintEnvelopeConfig(
            id="parent",
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write"],
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            operational=OperationalConstraintConfig(
                allowed_actions=["read", "write", "delete", "admin"],
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("operational" in v.lower() or "action" in v.lower() for v in violations)

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

    def test_internal_only_tightened_accepted(self, delegation_manager):
        """Parent allows external, child restricts to internal only."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            communication=CommunicationConstraintConfig(
                internal_only=False,
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            communication=CommunicationConstraintConfig(
                internal_only=True,
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True

    def test_loosening_internal_only_rejected(self, delegation_manager):
        """Parent requires internal only, child tries to allow external."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            communication=CommunicationConstraintConfig(
                internal_only=True,
            ),
        )
        child = ConstraintEnvelopeConfig(
            id="child",
            communication=CommunicationConstraintConfig(
                internal_only=False,
            ),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("communication" in v.lower() for v in violations)

    def test_equal_constraints_accepted(self, delegation_manager, lead_envelope):
        """Equal constraints should be accepted (not loosened)."""
        is_valid, violations = delegation_manager.validate_tightening(lead_envelope, lead_envelope)
        assert is_valid is True

    def test_multiple_violations_reported(
        self, delegation_manager, lead_envelope, expanded_envelope
    ):
        """An envelope that expands multiple dimensions should report all violations."""
        is_valid, violations = delegation_manager.validate_tightening(
            lead_envelope, expanded_envelope
        )
        assert is_valid is False
        assert len(violations) >= 1  # At least financial violation


# ---------------------------------------------------------------------------
# Test: Chain Walking
# ---------------------------------------------------------------------------


class TestChainWalking:
    async def test_walk_chain_from_genesis(
        self, delegation_manager, genesis_manager, genesis_config
    ):
        genesis = await genesis_manager.create_genesis(genesis_config)
        result = await delegation_manager.walk_chain(genesis.agent_id)
        assert isinstance(result, ChainWalkResult)
        assert result.status == ChainStatus.VALID
        assert result.depth == 0

    async def test_walk_chain_from_delegated_agent(
        self,
        delegation_manager,
        established_authority,
        team_lead_config,
        lead_envelope,
    ):
        await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        result = await delegation_manager.walk_chain(team_lead_config.id)
        assert result.status == ChainStatus.VALID
        assert result.depth >= 1
        assert len(result.chain) >= 1  # At least one record in the chain

    async def test_walk_chain_two_levels(
        self,
        delegation_manager,
        established_authority,
        team_lead_config,
        specialist_config,
        lead_envelope,
        specialist_envelope,
    ):
        await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        await delegation_manager.create_delegation(
            delegator_id=team_lead_config.id,
            delegate_config=specialist_config,
            envelope_config=specialist_envelope,
        )
        result = await delegation_manager.walk_chain(specialist_config.id)
        assert result.status == ChainStatus.VALID
        assert result.depth >= 2

    async def test_walk_chain_unknown_agent(self, delegation_manager):
        result = await delegation_manager.walk_chain("unknown-agent")
        assert result.status == ChainStatus.BROKEN
        assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# Test: Delegation Depth
# ---------------------------------------------------------------------------


class TestDelegationDepth:
    async def test_genesis_has_depth_zero(
        self, delegation_manager, genesis_manager, genesis_config
    ):
        genesis = await genesis_manager.create_genesis(genesis_config)
        depth = await delegation_manager.get_delegation_depth(genesis.agent_id)
        assert depth == 0

    async def test_direct_delegate_has_depth_one(
        self,
        delegation_manager,
        established_authority,
        team_lead_config,
        lead_envelope,
    ):
        await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        depth = await delegation_manager.get_delegation_depth(team_lead_config.id)
        assert depth >= 1

    async def test_chained_delegate_has_depth_two(
        self,
        delegation_manager,
        established_authority,
        team_lead_config,
        specialist_config,
        lead_envelope,
        specialist_envelope,
    ):
        await delegation_manager.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        await delegation_manager.create_delegation(
            delegator_id=team_lead_config.id,
            delegate_config=specialist_config,
            envelope_config=specialist_envelope,
        )
        depth = await delegation_manager.get_delegation_depth(specialist_config.id)
        assert depth >= 2

    async def test_unknown_agent_depth_zero(self, delegation_manager):
        depth = await delegation_manager.get_delegation_depth("unknown-agent")
        assert depth == 0


# ---------------------------------------------------------------------------
# Test: ChainWalkResult Model
# ---------------------------------------------------------------------------


class TestChainWalkResultModel:
    def test_chain_status_enum_values(self):
        assert ChainStatus.VALID == "valid"
        assert ChainStatus.BROKEN == "broken"
        assert ChainStatus.EXPIRED == "expired"
        assert ChainStatus.REVOKED == "revoked"

    def test_chain_walk_result_valid(self):
        result = ChainWalkResult(
            status=ChainStatus.VALID,
            chain=["genesis-1", "delegation-1"],
            depth=1,
            errors=[],
        )
        assert result.status == ChainStatus.VALID
        assert result.depth == 1
        assert len(result.errors) == 0

    def test_chain_walk_result_broken(self):
        result = ChainWalkResult(
            status=ChainStatus.BROKEN,
            chain=[],
            depth=0,
            errors=["No trust chain found for agent"],
        )
        assert result.status == ChainStatus.BROKEN
        assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Test: RT10-DP4 — Auto-sync with RevocationManager
# ---------------------------------------------------------------------------


class TestRT10_DP4_RevocationAutoSync:
    """RT10-DP4: DelegationManager auto-registers delegations in RevocationManager."""

    async def test_delegation_auto_registers_in_revocation_manager(
        self,
        established_authority,
        team_lead_config,
        lead_envelope,
        bridge,
    ):
        """When a RevocationManager is provided, create_delegation auto-registers."""
        from care_platform.trust.revocation import RevocationManager

        rev_mgr = RevocationManager()
        dm = DelegationManager(bridge=bridge, revocation_manager=rev_mgr)

        await dm.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )

        # The delegation tree should now contain the relationship
        downstream = rev_mgr.get_downstream_agents(established_authority.agent_id)
        assert team_lead_config.id in downstream

    async def test_delegation_without_revocation_manager_still_works(
        self,
        established_authority,
        team_lead_config,
        lead_envelope,
        bridge,
    ):
        """Without a RevocationManager, create_delegation works normally."""
        dm = DelegationManager(bridge=bridge)
        delegation = await dm.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        assert delegation.delegatee_id == team_lead_config.id

    async def test_chained_delegation_auto_registers_both(
        self,
        established_authority,
        team_lead_config,
        specialist_config,
        lead_envelope,
        specialist_envelope,
        bridge,
    ):
        """Chained delegations register both links in the revocation tree."""
        from care_platform.trust.revocation import RevocationManager

        rev_mgr = RevocationManager()
        dm = DelegationManager(bridge=bridge, revocation_manager=rev_mgr)

        await dm.create_delegation(
            delegator_id=established_authority.agent_id,
            delegate_config=team_lead_config,
            envelope_config=lead_envelope,
        )
        await dm.create_delegation(
            delegator_id=team_lead_config.id,
            delegate_config=specialist_config,
            envelope_config=specialist_envelope,
        )

        # Cascade from authority should reach both lead and specialist
        downstream = rev_mgr.get_downstream_agents(established_authority.agent_id)
        assert team_lead_config.id in downstream
        assert specialist_config.id in downstream


class TestFinancialNoneHandling:
    """RT13-M02: validate_tightening handles financial=None gracefully."""

    def test_both_financial_none_accepted(self, delegation_manager):
        """Both parent and child with no financial capability is valid."""
        parent = ConstraintEnvelopeConfig(id="parent", financial=None)
        child = ConstraintEnvelopeConfig(id="child", financial=None)
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True
        financial_violations = [v for v in violations if "financial" in v.lower()]
        assert len(financial_violations) == 0

    def test_parent_none_child_has_financial_rejected(self, delegation_manager):
        """Parent has no financial capability but child declares budget — violation."""
        parent = ConstraintEnvelopeConfig(id="parent", financial=None)
        child = ConstraintEnvelopeConfig(
            id="child",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is False
        assert any("financial" in v.lower() for v in violations)

    def test_parent_has_financial_child_none_accepted(self, delegation_manager):
        """Parent has financial capability, child has none — tighter (valid)."""
        parent = ConstraintEnvelopeConfig(
            id="parent",
            financial=FinancialConstraintConfig(max_spend_usd=1000.0),
        )
        child = ConstraintEnvelopeConfig(id="child", financial=None)
        is_valid, violations = delegation_manager.validate_tightening(parent, child)
        assert is_valid is True
        financial_violations = [v for v in violations if "financial" in v.lower()]
        assert len(financial_violations) == 0
