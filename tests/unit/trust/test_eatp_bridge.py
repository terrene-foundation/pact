# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for EATP Bridge — connects CARE Platform models to EATP SDK operations."""

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
from care_platform.trust.eatp_bridge import EATPBridge

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def genesis_config():
    """Standard genesis configuration for tests."""
    return GenesisConfig(
        authority="terrene.foundation",
        authority_name="Terrene Foundation",
        policy_reference="https://terrene.foundation/governance",
    )


@pytest.fixture()
def team_lead_config():
    """Standard team lead agent configuration."""
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
    """Standard specialist agent configuration."""
    return AgentConfig(
        id="specialist-001",
        name="Content Specialist",
        role="Writes and edits content",
        constraint_envelope="envelope-specialist",
        capabilities=["draft_content", "edit_content"],
    )


@pytest.fixture()
def lead_envelope_config():
    """Constraint envelope for team lead (broader permissions)."""
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
def specialist_envelope_config():
    """Constraint envelope for specialist (tighter permissions)."""
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
async def bridge():
    """Initialized EATP bridge."""
    b = EATPBridge()
    await b.initialize()
    return b


# ---------------------------------------------------------------------------
# Test: Bridge Initialization
# ---------------------------------------------------------------------------


class TestBridgeInitialization:
    async def test_bridge_creates_with_defaults(self):
        bridge = EATPBridge()
        await bridge.initialize()
        assert bridge.ops is not None
        assert bridge.store is not None
        assert bridge.key_manager is not None
        assert bridge.authority_registry is not None

    async def test_bridge_stores_empty_initially(self, bridge):
        # No agents established yet, retrieving a chain should return None
        chain = await bridge.get_trust_chain("nonexistent-agent")
        assert chain is None


# ---------------------------------------------------------------------------
# Test: Genesis Establishment
# ---------------------------------------------------------------------------


class TestEstablishGenesis:
    async def test_establish_genesis_creates_chain(self, bridge, genesis_config):
        genesis = await bridge.establish_genesis(genesis_config)
        assert genesis is not None
        assert genesis.agent_id is not None
        assert genesis.authority_id == "terrene.foundation"

    async def test_establish_genesis_stores_signing_key(self, bridge, genesis_config):
        await bridge.establish_genesis(genesis_config)
        # The bridge should store the signing key for the authority
        assert bridge.has_signing_key(genesis_config.authority)

    async def test_establish_genesis_returns_genesis_record(self, bridge, genesis_config):
        from eatp.chain import GenesisRecord

        genesis = await bridge.establish_genesis(genesis_config)
        assert isinstance(genesis, GenesisRecord)

    async def test_genesis_authority_id_matches_config(self, bridge, genesis_config):
        genesis = await bridge.establish_genesis(genesis_config)
        assert genesis.authority_id == genesis_config.authority

    async def test_genesis_metadata_includes_authority_name(self, bridge, genesis_config):
        genesis = await bridge.establish_genesis(genesis_config)
        assert genesis.metadata.get("authority_name") == genesis_config.authority_name

    async def test_genesis_metadata_includes_policy_reference(self, bridge, genesis_config):
        genesis = await bridge.establish_genesis(genesis_config)
        assert genesis.metadata.get("policy_reference") == genesis_config.policy_reference


# ---------------------------------------------------------------------------
# Test: Constraint Mapping
# ---------------------------------------------------------------------------


class TestConstraintMapping:
    async def test_financial_constraints_mapped(self, bridge, lead_envelope_config):
        constraints = bridge.map_envelope_to_constraints(lead_envelope_config)
        budget_constraints = [c for c in constraints if "budget:" in c]
        assert len(budget_constraints) > 0
        assert any("1000" in c for c in budget_constraints)

    async def test_operational_constraints_mapped(self, bridge, lead_envelope_config):
        constraints = bridge.map_envelope_to_constraints(lead_envelope_config)
        action_constraints = [c for c in constraints if "allow:" in c]
        assert len(action_constraints) > 0
        assert any("analyze_data" in c for c in action_constraints)

    async def test_temporal_constraints_mapped(self, bridge, lead_envelope_config):
        constraints = bridge.map_envelope_to_constraints(lead_envelope_config)
        time_constraints = [c for c in constraints if "time:" in c]
        assert len(time_constraints) > 0
        assert any("08:00" in c and "20:00" in c for c in time_constraints)

    async def test_data_access_constraints_mapped(self, bridge, lead_envelope_config):
        constraints = bridge.map_envelope_to_constraints(lead_envelope_config)
        data_constraints = [c for c in constraints if "read:" in c or "write:" in c]
        assert len(data_constraints) > 0

    async def test_communication_constraints_mapped(self, bridge, lead_envelope_config):
        constraints = bridge.map_envelope_to_constraints(lead_envelope_config)
        comm_constraints = [c for c in constraints if "channel:" in c or "comm:" in c]
        assert len(comm_constraints) > 0

    async def test_internal_only_communication_mapped(self, bridge, specialist_envelope_config):
        constraints = bridge.map_envelope_to_constraints(specialist_envelope_config)
        assert any("internal_only" in c for c in constraints)

    async def test_empty_envelope_produces_minimal_constraints(self, bridge):
        config = ConstraintEnvelopeConfig(id="empty-envelope")
        constraints = bridge.map_envelope_to_constraints(config)
        # Even an empty envelope should produce at least a financial constraint (budget:0)
        assert isinstance(constraints, list)


# ---------------------------------------------------------------------------
# Test: Delegation
# ---------------------------------------------------------------------------


class TestDelegation:
    async def test_delegate_creates_delegation_record(
        self, bridge, genesis_config, team_lead_config, lead_envelope_config
    ):
        from eatp.chain import DelegationRecord

        genesis = await bridge.establish_genesis(genesis_config)
        delegator_id = genesis.agent_id

        delegation = await bridge.delegate(
            delegator_id=delegator_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )
        assert isinstance(delegation, DelegationRecord)
        assert delegation.delegatee_id == team_lead_config.id

    async def test_delegate_sets_capabilities(
        self, bridge, genesis_config, team_lead_config, lead_envelope_config
    ):
        genesis = await bridge.establish_genesis(genesis_config)
        delegator_id = genesis.agent_id

        delegation = await bridge.delegate(
            delegator_id=delegator_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )
        # At least some of the agent's capabilities should be delegated
        assert len(delegation.capabilities_delegated) > 0

    async def test_delegate_sets_constraints(
        self, bridge, genesis_config, team_lead_config, lead_envelope_config
    ):
        genesis = await bridge.establish_genesis(genesis_config)
        delegator_id = genesis.agent_id

        delegation = await bridge.delegate(
            delegator_id=delegator_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )
        assert len(delegation.constraint_subset) > 0

    async def test_delegate_fails_without_genesis(
        self, bridge, team_lead_config, lead_envelope_config
    ):
        with pytest.raises(ValueError, match="[Nn]o.*signing.*key|[Nn]ot.*established"):
            await bridge.delegate(
                delegator_id="nonexistent-authority",
                delegate_agent_config=team_lead_config,
                envelope_config=lead_envelope_config,
            )


# ---------------------------------------------------------------------------
# Test: Verification
# ---------------------------------------------------------------------------


class TestVerification:
    async def test_verify_established_agent_action(
        self, bridge, genesis_config, team_lead_config, lead_envelope_config
    ):
        genesis = await bridge.establish_genesis(genesis_config)
        await bridge.delegate(
            delegator_id=genesis.agent_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )

        result = await bridge.verify_action(
            agent_id=team_lead_config.id,
            action="analyze_data",
            resource="dataset-1",
        )
        assert result.valid is True

    async def test_verify_returns_verification_result(
        self, bridge, genesis_config, team_lead_config, lead_envelope_config
    ):
        from eatp.chain import VerificationResult

        genesis = await bridge.establish_genesis(genesis_config)
        await bridge.delegate(
            delegator_id=genesis.agent_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )

        result = await bridge.verify_action(
            agent_id=team_lead_config.id,
            action="analyze_data",
        )
        assert isinstance(result, VerificationResult)

    async def test_verify_with_different_levels(
        self, bridge, genesis_config, team_lead_config, lead_envelope_config
    ):
        genesis = await bridge.establish_genesis(genesis_config)
        await bridge.delegate(
            delegator_id=genesis.agent_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )

        for level in ["QUICK", "STANDARD", "FULL"]:
            result = await bridge.verify_action(
                agent_id=team_lead_config.id,
                action="analyze_data",
                level=level,
            )
            assert result is not None

    async def test_verify_unknown_agent_fails(self, bridge):
        result = await bridge.verify_action(
            agent_id="unknown-agent",
            action="some_action",
        )
        assert result.valid is False


# ---------------------------------------------------------------------------
# Test: Audit
# ---------------------------------------------------------------------------


class TestAudit:
    async def test_record_audit_creates_anchor(
        self, bridge, genesis_config, team_lead_config, lead_envelope_config
    ):
        from eatp.chain import AuditAnchor

        genesis = await bridge.establish_genesis(genesis_config)
        await bridge.delegate(
            delegator_id=genesis.agent_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )

        anchor = await bridge.record_audit(
            agent_id=team_lead_config.id,
            action="analyze_data",
            resource="dataset-1",
            result="SUCCESS",
        )
        assert isinstance(anchor, AuditAnchor)
        assert anchor.agent_id == team_lead_config.id
        assert anchor.action == "analyze_data"

    async def test_audit_with_failure_result(
        self, bridge, genesis_config, team_lead_config, lead_envelope_config
    ):
        genesis = await bridge.establish_genesis(genesis_config)
        await bridge.delegate(
            delegator_id=genesis.agent_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )

        anchor = await bridge.record_audit(
            agent_id=team_lead_config.id,
            action="analyze_data",
            resource="dataset-1",
            result="FAILURE",
        )
        assert anchor is not None


# ---------------------------------------------------------------------------
# Test: Trust Chain Retrieval
# ---------------------------------------------------------------------------


class TestTrustChainRetrieval:
    async def test_get_trust_chain_after_establish(self, bridge, genesis_config):
        genesis = await bridge.establish_genesis(genesis_config)
        chain = await bridge.get_trust_chain(genesis.agent_id)
        assert chain is not None
        assert chain.genesis is not None

    async def test_get_trust_chain_after_delegation(
        self, bridge, genesis_config, team_lead_config, lead_envelope_config
    ):
        genesis = await bridge.establish_genesis(genesis_config)
        await bridge.delegate(
            delegator_id=genesis.agent_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )
        chain = await bridge.get_trust_chain(team_lead_config.id)
        assert chain is not None
        assert len(chain.delegations) >= 1

    async def test_get_trust_chain_nonexistent_returns_none(self, bridge):
        chain = await bridge.get_trust_chain("nonexistent")
        assert chain is None


# ---------------------------------------------------------------------------
# Test: End-to-End Bridge Flow
# ---------------------------------------------------------------------------


class TestEndToEndBridgeFlow:
    async def test_full_lifecycle(
        self,
        bridge,
        genesis_config,
        team_lead_config,
        specialist_config,
        lead_envelope_config,
        specialist_envelope_config,
    ):
        """Test the full bridge lifecycle: establish -> delegate -> delegate -> verify -> audit."""
        # 1. Establish genesis
        genesis = await bridge.establish_genesis(genesis_config)
        assert genesis is not None

        # 2. Delegate to team lead
        lead_delegation = await bridge.delegate(
            delegator_id=genesis.agent_id,
            delegate_agent_config=team_lead_config,
            envelope_config=lead_envelope_config,
        )
        assert lead_delegation.delegatee_id == team_lead_config.id

        # 3. Delegate from team lead to specialist (tighter constraints)
        specialist_delegation = await bridge.delegate(
            delegator_id=team_lead_config.id,
            delegate_agent_config=specialist_config,
            envelope_config=specialist_envelope_config,
        )
        assert specialist_delegation.delegatee_id == specialist_config.id

        # 4. Verify specialist's action
        verify_result = await bridge.verify_action(
            agent_id=specialist_config.id,
            action="draft_content",
            resource="content/drafts/post-1",
        )
        assert verify_result.valid is True

        # 5. Record audit anchor
        anchor = await bridge.record_audit(
            agent_id=specialist_config.id,
            action="draft_content",
            resource="content/drafts/post-1",
            result="SUCCESS",
        )
        assert anchor.agent_id == specialist_config.id

        # 6. Chain is retrievable for specialist
        chain = await bridge.get_trust_chain(specialist_config.id)
        assert chain is not None
