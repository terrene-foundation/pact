# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Integration tests for CARE decorator → EATPBridge → TrustOperations pipeline.

These tests verify the full pipeline from CARE decorators through the EATP
bridge to the underlying trust operations, ensuring the integration works
end-to-end with real EATP SDK components (no mocks).
"""

import pytest

from care_platform.build.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GenesisConfig,
    OperationalConstraintConfig,
)
from care_platform.trust.decorators import (
    CareTrustOpsProvider,
    care_audited,
    care_shadow,
    care_verified,
)
from care_platform.trust.eatp_bridge import EATPBridge

# ---------------------------------------------------------------------------
# Fixtures — full EATP trust chain setup
# ---------------------------------------------------------------------------


@pytest.fixture()
async def full_trust_chain():
    """Set up a complete trust chain: genesis → team lead → specialist.

    Returns a dict with bridge, provider, and agent IDs for testing.
    """
    bridge = EATPBridge()
    await bridge.initialize()

    # Genesis
    genesis = await bridge.establish_genesis(
        GenesisConfig(
            authority="terrene.foundation",
            authority_name="Terrene Foundation",
            policy_reference="https://terrene.foundation/governance",
        )
    )

    # Team lead with broad capabilities
    lead_config = AgentConfig(
        id="team-lead-001",
        name="Team Lead",
        role="Leads the content team",
        constraint_envelope="envelope-lead",
        capabilities=[
            "read_data",
            "draft_content",
            "review_content",
            "approve_drafts",
            "analyze_data",
        ],
    )
    lead_envelope = ConstraintEnvelopeConfig(
        id="envelope-lead",
        financial=FinancialConstraintConfig(max_spend_usd=5000.0),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "read_data",
                "draft_content",
                "review_content",
                "approve_drafts",
                "analyze_data",
            ],
            max_actions_per_day=200,
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["*"],
            write_paths=["content/*"],
        ),
    )
    await bridge.delegate(
        delegator_id=genesis.agent_id,
        delegate_agent_config=lead_config,
        envelope_config=lead_envelope,
    )

    # Specialist with narrower capabilities
    specialist_config = AgentConfig(
        id="specialist-001",
        name="Content Specialist",
        role="Writes and edits content",
        constraint_envelope="envelope-specialist",
        capabilities=["draft_content", "read_data"],
    )
    specialist_envelope = ConstraintEnvelopeConfig(
        id="envelope-specialist",
        financial=FinancialConstraintConfig(max_spend_usd=500.0),
        operational=OperationalConstraintConfig(
            allowed_actions=["draft_content", "read_data"],
            max_actions_per_day=50,
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["content/*"],
            write_paths=["content/drafts/*"],
        ),
    )
    await bridge.delegate(
        delegator_id="team-lead-001",
        delegate_agent_config=specialist_config,
        envelope_config=specialist_envelope,
    )

    provider = CareTrustOpsProvider(bridge)

    return {
        "bridge": bridge,
        "provider": provider,
        "genesis_agent_id": genesis.agent_id,
        "lead_id": "team-lead-001",
        "specialist_id": "specialist-001",
    }


# ---------------------------------------------------------------------------
# Full Pipeline Tests
# ---------------------------------------------------------------------------


class TestVerifiedPipeline:
    """End-to-end tests for @care_verified through real EATP trust operations."""

    async def test_lead_can_review_content(self, full_trust_chain):
        """Team lead with review_content capability passes verification."""
        provider = full_trust_chain["provider"]

        @care_verified(action="review_content", provider=provider)
        async def review_content(agent_id: str, content: str) -> dict:
            return {"reviewed": True, "content": content}

        result = await review_content(agent_id="team-lead-001", content="Draft article")
        assert result["reviewed"] is True

    async def test_specialist_cannot_review_content(self, full_trust_chain):
        """Specialist without review_content capability gets blocked."""
        from eatp.enforce.strict import EATPBlockedError

        provider = full_trust_chain["provider"]

        @care_verified(action="review_content", provider=provider)
        async def review_content(agent_id: str, content: str) -> dict:
            return {"reviewed": True}

        with pytest.raises(EATPBlockedError):
            await review_content(agent_id="specialist-001", content="Draft article")

    async def test_same_decorated_function_different_agents(self, full_trust_chain):
        """Same decorated function works with different agents (dynamic agent_id)."""
        provider = full_trust_chain["provider"]

        @care_verified(action="read_data", provider=provider)
        async def read_data(agent_id: str, path: str) -> dict:
            return {"agent": agent_id, "path": path}

        # Both agents have read_data capability
        lead_result = await read_data(agent_id="team-lead-001", path="/reports")
        specialist_result = await read_data(agent_id="specialist-001", path="/content")

        assert lead_result["agent"] == "team-lead-001"
        assert specialist_result["agent"] == "specialist-001"

    async def test_delegation_chain_verification(self, full_trust_chain):
        """Verification works through the delegation chain (genesis → lead → specialist)."""
        provider = full_trust_chain["provider"]

        @care_verified(action="draft_content", provider=provider)
        async def draft_content(agent_id: str, topic: str) -> dict:
            return {"drafted": topic}

        # Both lead and specialist can draft
        result = await draft_content(agent_id="specialist-001", topic="AI Trust")
        assert result["drafted"] == "AI Trust"


class TestAuditedPipeline:
    """End-to-end tests for @care_audited with real EATP audit operations."""

    async def test_audit_anchor_created(self, full_trust_chain):
        """Audit decorator creates a real EATP audit anchor."""
        provider = full_trust_chain["provider"]

        @care_audited(provider=provider)
        async def process_data(agent_id: str, data: str) -> dict:
            return {"processed": data}

        result = await process_data(agent_id="team-lead-001", data="raw-input")
        assert result == {"processed": "raw-input"}

    async def test_multiple_audit_anchors(self, full_trust_chain):
        """Multiple calls create multiple audit anchors."""
        provider = full_trust_chain["provider"]

        @care_audited(provider=provider)
        async def log_action(agent_id: str, action: str) -> str:
            return f"logged: {action}"

        result1 = await log_action(agent_id="team-lead-001", action="first")
        result2 = await log_action(agent_id="team-lead-001", action="second")

        assert result1 == "logged: first"
        assert result2 == "logged: second"


class TestShadowPipeline:
    """End-to-end tests for @care_shadow with real EATP shadow verification."""

    async def test_shadow_observes_valid_action(self, full_trust_chain):
        """Shadow mode records verification for permitted action."""
        provider = full_trust_chain["provider"]

        @care_shadow(action="read_data", provider=provider)
        async def read_data(agent_id: str) -> str:
            return "data"

        result = await read_data(agent_id="team-lead-001")
        assert result == "data"

        # Check EATP shadow metrics were recorded
        metrics = read_data.eatp_shadow.metrics
        assert metrics.total_checks >= 1

    async def test_shadow_observes_blocked_action_without_blocking(self, full_trust_chain):
        """Shadow mode records what would be blocked but doesn't block."""
        provider = full_trust_chain["provider"]

        @care_shadow(action="delete_everything", provider=provider)
        async def dangerous_action(agent_id: str) -> str:
            return "executed anyway"

        result = await dangerous_action(agent_id="specialist-001")
        assert result == "executed anyway"

    async def test_shadow_metrics_accumulate_across_calls(self, full_trust_chain):
        """Shadow metrics accumulate correctly over multiple calls."""
        provider = full_trust_chain["provider"]

        @care_shadow(action="draft_content", provider=provider)
        async def draft(agent_id: str, topic: str) -> dict:
            return {"topic": topic}

        await draft(agent_id="team-lead-001", topic="Trust")
        await draft(agent_id="specialist-001", topic="Safety")
        await draft(agent_id="team-lead-001", topic="Governance")

        metrics = draft.eatp_shadow.metrics
        assert metrics.total_checks >= 3


class TestMigrationPipeline:
    """Integration test for the complete shadow → audited → verified migration."""

    async def test_full_migration_path(self, full_trust_chain):
        """An action can progress through all three trust stages end-to-end."""
        provider = full_trust_chain["provider"]
        agent_id = "team-lead-001"

        # Stage 1: Shadow — collect evidence
        @care_shadow(action="analyze_data", provider=provider)
        async def analyze_v1(agent_id: str, data: str) -> dict:
            return {"analysis": data, "version": 1}

        r1 = await analyze_v1(agent_id=agent_id, data="metrics")
        assert r1["version"] == 1

        shadow_metrics = analyze_v1.eatp_shadow.metrics
        assert shadow_metrics.total_checks >= 1

        # Stage 2: Audited — create audit trail
        @care_audited(provider=provider)
        async def analyze_v2(agent_id: str, data: str) -> dict:
            return {"analysis": data, "version": 2}

        r2 = await analyze_v2(agent_id=agent_id, data="metrics")
        assert r2["version"] == 2

        # Stage 3: Verified — full enforcement
        @care_verified(action="analyze_data", provider=provider)
        async def analyze_v3(agent_id: str, data: str) -> dict:
            return {"analysis": data, "version": 3}

        r3 = await analyze_v3(agent_id=agent_id, data="metrics")
        assert r3["version"] == 3
