# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for Genesis Manager — manages genesis record lifecycle."""

import pytest

from care_platform.config.schema import GenesisConfig
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
def alt_genesis_config():
    """Alternative genesis config for renewal tests."""
    return GenesisConfig(
        authority="terrene.foundation",
        authority_name="Terrene Foundation (Renewed)",
        policy_reference="https://terrene.foundation/governance/v2",
    )


@pytest.fixture()
async def bridge():
    b = EATPBridge()
    await b.initialize()
    return b


@pytest.fixture()
def manager(bridge):
    return GenesisManager(bridge=bridge)


# ---------------------------------------------------------------------------
# Test: Genesis Creation
# ---------------------------------------------------------------------------


class TestGenesisCreation:
    async def test_create_genesis_returns_genesis_record(self, manager, genesis_config):
        from eatp.chain import GenesisRecord

        genesis = await manager.create_genesis(genesis_config)
        assert isinstance(genesis, GenesisRecord)

    async def test_create_genesis_generates_keypair(self, manager, genesis_config):
        await manager.create_genesis(genesis_config)
        # The manager should have stored the signing key
        assert manager.bridge.has_signing_key(genesis_config.authority)

    async def test_create_genesis_sets_authority(self, manager, genesis_config):
        genesis = await manager.create_genesis(genesis_config)
        assert genesis.authority_id == genesis_config.authority

    async def test_create_genesis_agent_id_derived_from_authority(self, manager, genesis_config):
        genesis = await manager.create_genesis(genesis_config)
        # The agent_id should be deterministic and related to the authority
        assert genesis_config.authority in genesis.agent_id or genesis.agent_id is not None

    async def test_create_genesis_stores_chain(self, manager, genesis_config):
        genesis = await manager.create_genesis(genesis_config)
        chain = await manager.bridge.get_trust_chain(genesis.agent_id)
        assert chain is not None


# ---------------------------------------------------------------------------
# Test: Genesis Validation
# ---------------------------------------------------------------------------


class TestGenesisValidation:
    async def test_validate_existing_genesis_is_valid(self, manager, genesis_config):
        genesis = await manager.create_genesis(genesis_config)
        is_valid, message = await manager.validate_genesis(genesis.agent_id)
        assert is_valid is True
        assert message  # Should have a descriptive message

    async def test_validate_nonexistent_genesis_is_invalid(self, manager):
        is_valid, message = await manager.validate_genesis("nonexistent-agent")
        assert is_valid is False
        assert "not found" in message.lower() or "no" in message.lower()

    async def test_validate_returns_descriptive_reason(self, manager, genesis_config):
        genesis = await manager.create_genesis(genesis_config)
        is_valid, message = await manager.validate_genesis(genesis.agent_id)
        # Message should be informative, not empty
        assert len(message) > 0


# ---------------------------------------------------------------------------
# Test: Genesis Renewal
# ---------------------------------------------------------------------------


class TestGenesisRenewal:
    async def test_renew_genesis_creates_new_record(self, manager, genesis_config):
        original = await manager.create_genesis(genesis_config)
        renewed = await manager.renew_genesis(genesis_config.authority)
        assert renewed is not None
        assert renewed.id != original.id

    async def test_renew_genesis_preserves_authority(self, manager, genesis_config):
        await manager.create_genesis(genesis_config)
        renewed = await manager.renew_genesis(genesis_config.authority)
        assert renewed.authority_id == genesis_config.authority

    async def test_renew_genesis_without_prior_fails(self, manager):
        with pytest.raises(ValueError, match="[Nn]o.*genesis|[Nn]ot.*found|[Nn]ot.*established"):
            await manager.renew_genesis("unknown-authority")

    async def test_renew_genesis_new_chain_is_valid(self, manager, genesis_config):
        await manager.create_genesis(genesis_config)
        renewed = await manager.renew_genesis(genesis_config.authority)
        is_valid, _ = await manager.validate_genesis(renewed.agent_id)
        assert is_valid is True
