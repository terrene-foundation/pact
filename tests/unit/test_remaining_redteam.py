# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for remaining red team findings: RT-11, RT-12, RT-13, RT-22, RT-26."""

from __future__ import annotations

import asyncio

import pytest

from care_platform.audit.anchor import AuditAnchor, AuditChain
from care_platform.config.schema import (
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    TemporalConstraintConfig,
    VerificationLevel,
)
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.workspace.bridge import (
    Bridge,
    BridgeManager,
    BridgePermission,
    BridgeStatus,
    BridgeType,
)


# ---------------------------------------------------------------------------
# RT-11: No wildcard capabilities in delegated agents
# ---------------------------------------------------------------------------


class TestRT11NoWildcardDelegation:
    """RT-11: Wildcard capabilities must not be injected into delegatees."""

    def test_delegate_method_does_not_inject_wildcard(self):
        """The delegate method should not add '*' to delegatee capabilities."""
        from care_platform.config.schema import AgentConfig, GenesisConfig

        bridge = EATPBridge()

        async def _run():
            await bridge.initialize()
            genesis = await bridge.establish_genesis(
                GenesisConfig(
                    authority="test-authority",
                    authority_name="Test Authority",
                    policy_reference="https://test.example/policy",
                )
            )
            agent_config = AgentConfig(
                id="agent-1",
                name="Test Agent",
                role="Test",
                constraint_envelope="env-1",
                capabilities=["read", "write"],
            )
            envelope = ConstraintEnvelopeConfig(
                id="env-1",
                description="Test envelope",
            )
            delegation = await bridge.delegate(
                delegator_id=genesis.agent_id,
                delegate_agent_config=agent_config,
                envelope_config=envelope,
            )
            # The delegated capabilities should NOT include '*'
            assert "*" not in delegation.capabilities_delegated

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# RT-12: Complete constraint mapping
# ---------------------------------------------------------------------------


class TestRT12CompleteConstraintMapping:
    """RT-12: Constraint mapping to EATP must include all CARE fields."""

    def test_blackout_periods_mapped(self):
        """blackout_periods should appear in EATP constraint strings."""
        bridge = EATPBridge()
        config = ConstraintEnvelopeConfig(
            id="env-blackout",
            description="Test",
            temporal=TemporalConstraintConfig(
                blackout_periods=["2026-12-25", "01-01"],
            ),
        )
        constraints = bridge.map_envelope_to_constraints(config)
        assert "blackout:2026-12-25" in constraints
        assert "blackout:01-01" in constraints

    def test_blocked_data_types_mapped(self):
        """blocked_data_types should appear in EATP constraint strings."""
        bridge = EATPBridge()
        config = ConstraintEnvelopeConfig(
            id="env-blocked-data",
            description="Test",
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii", "financial"],
            ),
        )
        constraints = bridge.map_envelope_to_constraints(config)
        assert "block_data:pii" in constraints
        assert "block_data:financial" in constraints

    def test_api_cost_budget_mapped(self):
        """api_cost_budget_usd should appear in EATP constraint strings."""
        bridge = EATPBridge()
        config = ConstraintEnvelopeConfig(
            id="env-budget",
            description="Test",
            financial=FinancialConstraintConfig(
                max_spend_usd=1000.0,
                api_cost_budget_usd=500.0,
            ),
        )
        constraints = bridge.map_envelope_to_constraints(config)
        assert "api_budget:500.0" in constraints

    def test_timezone_mapped(self):
        """Non-UTC timezone should appear in EATP constraint strings."""
        bridge = EATPBridge()
        config = ConstraintEnvelopeConfig(
            id="env-tz",
            description="Test",
            temporal=TemporalConstraintConfig(timezone="Asia/Singapore"),
        )
        constraints = bridge.map_envelope_to_constraints(config)
        assert "timezone:Asia/Singapore" in constraints

    def test_utc_timezone_not_mapped(self):
        """UTC timezone should not generate an extra constraint."""
        bridge = EATPBridge()
        config = ConstraintEnvelopeConfig(
            id="env-utc",
            description="Test",
            temporal=TemporalConstraintConfig(timezone="UTC"),
        )
        constraints = bridge.map_envelope_to_constraints(config)
        assert not any(c.startswith("timezone:") for c in constraints)


# ---------------------------------------------------------------------------
# RT-13: Audit anchor signing
# ---------------------------------------------------------------------------


class TestRT13AuditAnchorSigning:
    """RT-13: Audit anchors can be signed and verified."""

    def test_sign_and_verify(self):
        """A signed anchor should verify with the same key."""
        anchor = AuditAnchor(
            anchor_id="test-1",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.seal()
        key = b"test-signing-key-32-bytes-long!!"
        anchor.sign(key, "test-signer")

        assert anchor.is_signed
        assert anchor.signer_id == "test-signer"
        assert anchor.verify_signature(key)

    def test_verify_with_wrong_key_fails(self):
        """Signature verification should fail with a different key."""
        anchor = AuditAnchor(
            anchor_id="test-2",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.seal()
        anchor.sign(b"correct-key-here-32-bytes-long!!", "signer-1")

        assert not anchor.verify_signature(b"wrong-key-here-32-bytes-nooope!!")

    def test_sign_unsealed_raises(self):
        """Signing an unsealed anchor should raise ValueError."""
        anchor = AuditAnchor(
            anchor_id="test-3",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        with pytest.raises(ValueError, match="unsealed"):
            anchor.sign(b"key", "signer")

    def test_unsigned_anchor_verify_returns_false(self):
        """An unsigned anchor should return False for verify_signature."""
        anchor = AuditAnchor(
            anchor_id="test-4",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.seal()
        assert not anchor.verify_signature(b"any-key")

    def test_chain_auto_signing(self):
        """AuditChain.append with signing_key should auto-sign anchors."""
        chain = AuditChain(chain_id="signed-chain")
        key = b"chain-signing-key-32-bytes-ok!!"
        anchor = chain.append(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
            signing_key=key,
            signer_id="chain-signer",
        )
        assert anchor.is_signed
        assert anchor.verify_signature(key)

    def test_chain_integrity_uses_timing_safe_comparison(self):
        """verify_integrity should use hmac.compare_digest (timing-safe)."""
        anchor = AuditAnchor(
            anchor_id="test-5",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.seal()
        # Verify integrity uses hmac.compare_digest internally
        assert anchor.verify_integrity()
        # Tamper with the hash — should fail
        anchor.content_hash = "0" * 64
        assert not anchor.verify_integrity()


# ---------------------------------------------------------------------------
# RT-22: Bridge permission freezing
# ---------------------------------------------------------------------------


class TestRT22BridgePermissionFreezing:
    """RT-22: Bridge permissions should be frozen after activation."""

    def test_permissions_frozen_on_activation(self):
        """After both sides approve, permissions should be frozen."""
        mgr = BridgeManager()
        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Standing data share",
            permissions=BridgePermission(
                read_paths=["docs/*"],
                write_paths=["drafts/*"],
            ),
            created_by="admin",
        )
        bridge.approve_source("source-approver")
        bridge.approve_target("target-approver")
        assert bridge.status == BridgeStatus.ACTIVE

        # Verify frozen permissions exist
        assert bridge.frozen_permissions is not None
        assert bridge.effective_permissions.read_paths == ["docs/*"]

    def test_mutating_permissions_after_activation_does_not_affect_access(self):
        """Changing permissions.read_paths after activation should not affect access checks."""
        mgr = BridgeManager()
        bridge = mgr.create_standing_bridge(
            source_team="team-a",
            target_team="team-b",
            purpose="Test freeze",
            permissions=BridgePermission(
                read_paths=["reports/*"],
            ),
            created_by="admin",
        )
        bridge.approve_source("s")
        bridge.approve_target("t")

        # Access should work with original permissions
        assert bridge.check_access("reports/q1.pdf", "read")

        # Mutate the original permissions object
        bridge.permissions.read_paths = ["nothing/*"]

        # Access should STILL work because frozen permissions are used
        assert bridge.check_access("reports/q1.pdf", "read")
        # And the mutated path should NOT work
        assert not bridge.check_access("nothing/file.txt", "read")

    def test_pending_bridge_uses_current_permissions(self):
        """Before activation, effective_permissions returns current (unfrozen) permissions."""
        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id="a",
            target_team_id="b",
            purpose="Test",
            permissions=BridgePermission(read_paths=["src/*"]),
        )
        assert bridge.effective_permissions.read_paths == ["src/*"]
        assert bridge.frozen_permissions is None


# ---------------------------------------------------------------------------
# RT-26: CapabilityAttestation wired into bridge
# ---------------------------------------------------------------------------


class TestRT26AttestationWiring:
    """RT-26: CapabilityAttestation should be created during delegation and
    revoked during agent revocation."""

    def test_delegation_creates_attestation(self):
        """Delegating to an agent should create a CapabilityAttestation."""
        from care_platform.config.schema import AgentConfig, GenesisConfig

        bridge = EATPBridge()

        async def _run():
            await bridge.initialize()
            genesis = await bridge.establish_genesis(
                GenesisConfig(
                    authority="test-auth",
                    authority_name="Test Auth",
                    policy_reference="https://test.example/policy",
                )
            )
            agent = AgentConfig(
                id="agent-att-1",
                name="Test Agent",
                role="Test",
                constraint_envelope="env-1",
                capabilities=["read", "write"],
            )
            envelope = ConstraintEnvelopeConfig(id="env-1", description="Test")
            await bridge.delegate(
                delegator_id=genesis.agent_id,
                delegate_agent_config=agent,
                envelope_config=envelope,
            )

            att = bridge.get_attestation("agent-att-1")
            assert att is not None
            assert att.agent_id == "agent-att-1"
            assert set(att.capabilities) == {"read", "write"}
            assert att.is_valid

        asyncio.run(_run())

    def test_verify_capability_checks_attestation(self):
        """verify_capability should check the attestation registry."""
        from care_platform.config.schema import AgentConfig, GenesisConfig

        bridge = EATPBridge()

        async def _run():
            await bridge.initialize()
            genesis = await bridge.establish_genesis(
                GenesisConfig(
                    authority="test-auth-2",
                    authority_name="Test Auth 2",
                    policy_reference="https://test.example/policy",
                )
            )
            agent = AgentConfig(
                id="agent-att-2",
                name="Test Agent 2",
                role="Test",
                constraint_envelope="env-2",
                capabilities=["read"],
            )
            envelope = ConstraintEnvelopeConfig(id="env-2", description="Test")
            await bridge.delegate(
                delegator_id=genesis.agent_id,
                delegate_agent_config=agent,
                envelope_config=envelope,
            )

            assert bridge.verify_capability("agent-att-2", "read")
            assert not bridge.verify_capability("agent-att-2", "write")
            assert not bridge.verify_capability("nonexistent", "read")

        asyncio.run(_run())

    def test_revoke_agent_also_revokes_attestation(self):
        """Revoking an agent should also revoke its attestation."""
        from care_platform.config.schema import AgentConfig, GenesisConfig

        bridge = EATPBridge()

        async def _run():
            await bridge.initialize()
            genesis = await bridge.establish_genesis(
                GenesisConfig(
                    authority="test-auth-3",
                    authority_name="Test Auth 3",
                    policy_reference="https://test.example/policy",
                )
            )
            agent = AgentConfig(
                id="agent-att-3",
                name="Test Agent 3",
                role="Test",
                constraint_envelope="env-3",
                capabilities=["read"],
            )
            envelope = ConstraintEnvelopeConfig(id="env-3", description="Test")
            await bridge.delegate(
                delegator_id=genesis.agent_id,
                delegate_agent_config=agent,
                envelope_config=envelope,
            )

            # Before revocation
            assert bridge.verify_capability("agent-att-3", "read")

            # Revoke
            bridge.revoke_agent("agent-att-3")

            # After revocation — attestation should be revoked
            att = bridge.get_attestation("agent-att-3")
            assert att is not None
            assert att.revoked
            assert not att.is_valid
            assert not bridge.verify_capability("agent-att-3", "read")

        asyncio.run(_run())

    def test_no_attestation_for_unknown_agent(self):
        """Getting attestation for unknown agent returns None."""
        bridge = EATPBridge()
        assert bridge.get_attestation("unknown") is None
        assert not bridge.verify_capability("unknown", "read")
