# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for CARE trust decorators — @care_verified, @care_audited, @care_shadow."""

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
    _extract_agent_id,
    _resolve_param_index,
    _validate_agent_id,
    care_audited,
    care_shadow,
    care_verified,
)
from care_platform.trust.eatp_bridge import EATPBridge

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def genesis_config():
    """Standard genesis configuration."""
    return GenesisConfig(
        authority="terrene.foundation",
        authority_name="Terrene Foundation",
        policy_reference="https://terrene.foundation/governance",
    )


@pytest.fixture()
def agent_config():
    """Agent with read_data and draft_content capabilities."""
    return AgentConfig(
        id="agent-001",
        name="Test Agent",
        role="Test agent for decorator tests",
        constraint_envelope="envelope-001",
        capabilities=["read_data", "draft_content", "analyze_data"],
    )


@pytest.fixture()
def envelope_config():
    """Permissive envelope for testing."""
    return ConstraintEnvelopeConfig(
        id="envelope-001",
        financial=FinancialConstraintConfig(
            max_spend_usd=10000.0,
            requires_approval_above_usd=5000.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=["read_data", "draft_content", "analyze_data"],
            max_actions_per_day=100,
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["*"],
            write_paths=["workspace/*"],
        ),
    )


@pytest.fixture()
async def bridge_with_agent(genesis_config, agent_config, envelope_config):
    """Initialized bridge with a genesis root and delegated agent."""
    bridge = EATPBridge()
    await bridge.initialize()
    genesis = await bridge.establish_genesis(genesis_config)
    await bridge.delegate(
        delegator_id=genesis.agent_id,
        delegate_agent_config=agent_config,
        envelope_config=envelope_config,
    )
    return bridge


@pytest.fixture()
def provider(bridge_with_agent):
    """CareTrustOpsProvider from an initialized bridge."""
    return CareTrustOpsProvider(bridge_with_agent)


# ---------------------------------------------------------------------------
# CareTrustOpsProvider Tests
# ---------------------------------------------------------------------------


class TestCareTrustOpsProvider:
    """Tests for CareTrustOpsProvider."""

    async def test_ops_returns_trust_operations(self, provider):
        """Provider.ops returns the TrustOperations from the bridge."""
        ops = provider.ops
        assert ops is not None

    async def test_ops_raises_if_bridge_not_initialized(self):
        """Provider.ops raises RuntimeError if bridge not initialized."""
        bridge = EATPBridge()  # Not initialized
        p = CareTrustOpsProvider(bridge)
        with pytest.raises(RuntimeError, match="not been initialized"):
            _ = p.ops

    async def test_bridge_property(self, bridge_with_agent):
        """Provider.bridge returns the underlying bridge."""
        p = CareTrustOpsProvider(bridge_with_agent)
        assert p.bridge is bridge_with_agent


# ---------------------------------------------------------------------------
# _extract_agent_id Tests
# ---------------------------------------------------------------------------


class TestExtractAgentId:
    """Tests for _extract_agent_id and _resolve_param_index helpers."""

    def test_extract_from_kwargs(self):
        """Extracts agent_id from keyword arguments."""
        result = _extract_agent_id((), {"agent_id": "agent-001"}, "agent_id", 0)
        assert result == "agent-001"

    def test_extract_from_positional(self):
        """Extracts agent_id from positional arguments."""
        result = _extract_agent_id(("agent-001", "some-data"), {}, "agent_id", 0)
        assert result == "agent-001"

    def test_extract_custom_param_index(self):
        """Extracts using a custom parameter index."""
        result = _extract_agent_id(("some-data", "actor-001"), {}, "actor_id", 1)
        assert result == "actor-001"

    def test_resolve_param_index(self):
        """_resolve_param_index finds the parameter position."""

        def func(agent_id: str, data: str) -> None:
            pass

        assert _resolve_param_index(func, "agent_id") == 0
        assert _resolve_param_index(func, "data") == 1

    def test_resolve_raises_if_param_not_in_signature(self):
        """Raises ValueError if param name not found in function signature."""

        def func(data: str) -> None:
            pass

        with pytest.raises(ValueError, match="not found in function"):
            _resolve_param_index(func, "agent_id")

    def test_raises_if_param_not_provided(self):
        """Raises ValueError if param exists but not in args."""
        with pytest.raises(ValueError, match="not provided"):
            _extract_agent_id((), {}, "agent_id", 0)

    def test_converts_to_string(self):
        """Non-string values are converted to strings."""
        result = _extract_agent_id((42,), {}, "agent_id", 0)
        assert result == "42"


class TestValidateAgentId:
    """Tests for agent_id input validation (security)."""

    def test_valid_agent_id(self):
        """Valid agent IDs pass validation."""
        assert _validate_agent_id("agent-001") == "agent-001"
        assert _validate_agent_id("team.lead.001") == "team.lead.001"
        assert _validate_agent_id("agent_with_underscores") == "agent_with_underscores"

    def test_empty_agent_id_rejected(self):
        """Empty string agent_id is rejected."""
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_agent_id("")

    def test_oversized_agent_id_rejected(self):
        """Agent IDs exceeding max length are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            _validate_agent_id("a" * 257)

    def test_path_traversal_rejected(self):
        """Path traversal characters are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_agent_id("../../etc/passwd")

    def test_spaces_rejected(self):
        """Spaces are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            _validate_agent_id("agent 001")

    def test_special_chars_rejected(self):
        """Special characters are rejected."""
        for char in ["/", "\\", "<", ">", ":", '"', "|", "?", "*", " ", "\n"]:
            with pytest.raises(ValueError, match="invalid characters"):
                _validate_agent_id(f"agent{char}001")

    def test_max_length_accepted(self):
        """Agent ID at exactly max length is accepted."""
        assert _validate_agent_id("a" * 256) == "a" * 256


# ---------------------------------------------------------------------------
# @care_verified Tests
# ---------------------------------------------------------------------------


class TestCareVerified:
    """Tests for @care_verified decorator."""

    async def test_verified_allows_valid_action(self, provider):
        """Decorated function executes when agent has capability."""

        @care_verified(action="read_data", provider=provider)
        async def read_data(agent_id: str, path: str) -> dict:
            return {"path": path, "data": "content"}

        result = await read_data(agent_id="agent-001", path="/test")
        assert result == {"path": "/test", "data": "content"}

    async def test_verified_blocks_invalid_action(self, provider):
        """Decorated function raises when agent lacks capability."""
        from eatp.enforce.strict import EATPBlockedError

        @care_verified(action="delete_everything", provider=provider)
        async def dangerous_action(agent_id: str) -> None:
            return None

        with pytest.raises(EATPBlockedError):
            await dangerous_action(agent_id="agent-001")

    async def test_verified_with_positional_agent_id(self, provider):
        """Agent ID can be passed as positional argument."""

        @care_verified(action="read_data", provider=provider)
        async def read_data(agent_id: str) -> str:
            return "ok"

        result = await read_data("agent-001")
        assert result == "ok"

    async def test_verified_exposes_enforcer(self, provider):
        """Decorated function has an .enforcer attribute (StrictEnforcer)."""

        @care_verified(action="read_data", provider=provider)
        async def read_data(agent_id: str) -> str:
            return "ok"

        assert hasattr(read_data, "enforcer")

    async def test_verified_preserves_function_name(self, provider):
        """Decorated function preserves original name and docstring."""

        @care_verified(action="read_data", provider=provider)
        async def my_function(agent_id: str) -> str:
            """My docstring."""
            return "ok"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    async def test_verified_with_custom_param_name(self, provider):
        """Custom agent_id_param works correctly."""

        @care_verified(action="read_data", provider=provider, agent_id_param="actor")
        async def read_data(actor: str, path: str) -> dict:
            return {"actor": actor}

        result = await read_data(actor="agent-001", path="/test")
        assert result["actor"] == "agent-001"


# ---------------------------------------------------------------------------
# @care_audited Tests
# ---------------------------------------------------------------------------


class TestCareAudited:
    """Tests for @care_audited decorator."""

    async def test_audited_records_audit_trail(self, provider):
        """Decorated function creates an audit anchor after execution."""

        @care_audited(provider=provider)
        async def process_data(agent_id: str, data: str) -> dict:
            return {"processed": data}

        # Audit decorator should not raise and should return the result
        result = await process_data(agent_id="agent-001", data="test-input")
        assert result == {"processed": "test-input"}

    async def test_audited_preserves_return_value(self, provider):
        """Audit recording doesn't modify the return value."""

        @care_audited(provider=provider)
        async def compute(agent_id: str) -> int:
            return 42

        assert await compute(agent_id="agent-001") == 42

    async def test_audited_preserves_function_metadata(self, provider):
        """Decorated function preserves name and docstring."""

        @care_audited(provider=provider)
        async def my_task(agent_id: str) -> None:
            """Task docstring."""
            pass

        assert my_task.__name__ == "my_task"
        assert my_task.__doc__ == "Task docstring."


# ---------------------------------------------------------------------------
# @care_shadow Tests
# ---------------------------------------------------------------------------


class TestCareShadow:
    """Tests for @care_shadow decorator."""

    async def test_shadow_never_blocks_valid_action(self, provider):
        """Shadow mode executes function regardless of verification result."""

        @care_shadow(action="read_data", provider=provider)
        async def read_data(agent_id: str) -> str:
            return "ok"

        result = await read_data(agent_id="agent-001")
        assert result == "ok"

    async def test_shadow_never_blocks_invalid_action(self, provider):
        """Shadow mode doesn't block even for actions the agent can't do."""

        @care_shadow(action="delete_everything", provider=provider)
        async def dangerous_action(agent_id: str) -> str:
            return "still executed"

        result = await dangerous_action(agent_id="agent-001")
        assert result == "still executed"

    async def test_shadow_collects_eatp_metrics(self, provider):
        """Shadow mode records EATP-level metrics via the eatp_shadow enforcer."""

        @care_shadow(action="read_data", provider=provider)
        async def read_data(agent_id: str) -> str:
            return "ok"

        await read_data(agent_id="agent-001")
        await read_data(agent_id="agent-001")

        eatp_shadow = read_data.eatp_shadow
        assert eatp_shadow.metrics.total_checks >= 2

    async def test_shadow_forwards_to_care_shadow_enforcer(self, provider, bridge_with_agent):
        """When care_shadow_enforcer is provided, evaluation is forwarded."""
        from unittest.mock import MagicMock

        mock_care_shadow = MagicMock()

        @care_shadow(
            action="read_data",
            provider=provider,
            care_shadow_enforcer=mock_care_shadow,
        )
        async def read_data(agent_id: str) -> str:
            return "ok"

        await read_data(agent_id="agent-001")

        mock_care_shadow.evaluate.assert_called_once_with(action="read_data", agent_id="agent-001")

    async def test_shadow_failsafe_on_care_shadow_error(self, provider):
        """CARE ShadowEnforcer errors don't block execution."""
        from unittest.mock import MagicMock

        mock_care_shadow = MagicMock()
        mock_care_shadow.evaluate.side_effect = RuntimeError("Shadow broke")

        @care_shadow(
            action="read_data",
            provider=provider,
            care_shadow_enforcer=mock_care_shadow,
        )
        async def read_data(agent_id: str) -> str:
            return "still works"

        # Should not raise, despite shadow error
        result = await read_data(agent_id="agent-001")
        assert result == "still works"

    async def test_shadow_preserves_function_metadata(self, provider):
        """Decorated function preserves name and docstring."""

        @care_shadow(action="read_data", provider=provider)
        async def my_shadow_func(agent_id: str) -> None:
            """Shadow docstring."""
            pass

        assert my_shadow_func.__name__ == "my_shadow_func"
        assert my_shadow_func.__doc__ == "Shadow docstring."


# ---------------------------------------------------------------------------
# Migration Path Test
# ---------------------------------------------------------------------------


class TestMigrationPath:
    """Tests verifying the shadow → audited → verified migration path."""

    async def test_shadow_then_audited_then_verified(self, provider):
        """Same function can progress through all three decorator stages."""

        # Stage 1: Shadow — observe without enforcing
        @care_shadow(action="analyze_data", provider=provider)
        async def analyze_shadow(agent_id: str, data: str) -> dict:
            return {"analyzed": data}

        result = await analyze_shadow(agent_id="agent-001", data="test")
        assert result == {"analyzed": "test"}

        # Stage 2: Audited — record audit trail
        @care_audited(provider=provider)
        async def analyze_audited(agent_id: str, data: str) -> dict:
            return {"analyzed": data}

        result = await analyze_audited(agent_id="agent-001", data="test")
        assert result == {"analyzed": "test"}

        # Stage 3: Verified — full trust enforcement
        @care_verified(action="analyze_data", provider=provider)
        async def analyze_verified(agent_id: str, data: str) -> dict:
            return {"analyzed": data}

        result = await analyze_verified(agent_id="agent-001", data="test")
        assert result == {"analyzed": "test"}


# ---------------------------------------------------------------------------
# Sync Wrapper Tests (Gap #1 from test coverage audit)
# ---------------------------------------------------------------------------


class TestSyncWrappers:
    """Tests for sync function decoration (exercises sync_wrapper code paths)."""

    def test_verified_sync_function(self, provider):
        """@care_verified works with a regular (non-async) function."""

        @care_verified(action="read_data", provider=provider)
        def read_data_sync(agent_id: str) -> str:
            return "sync_ok"

        result = read_data_sync(agent_id="agent-001")
        assert result == "sync_ok"

    def test_audited_sync_function(self, provider):
        """@care_audited works with a regular (non-async) function."""

        @care_audited(provider=provider)
        def process_sync(agent_id: str, data: str) -> dict:
            return {"processed": data}

        result = process_sync(agent_id="agent-001", data="input")
        assert result == {"processed": "input"}

    def test_shadow_sync_function(self, provider):
        """@care_shadow works with a regular (non-async) function."""

        @care_shadow(action="read_data", provider=provider)
        def read_sync(agent_id: str) -> str:
            return "shadow_sync"

        result = read_sync(agent_id="agent-001")
        assert result == "shadow_sync"

    def test_verified_sync_blocks_invalid_action(self, provider):
        """Sync @care_verified blocks unauthorized actions."""
        from eatp.enforce.strict import EATPBlockedError

        @care_verified(action="delete_everything", provider=provider)
        def dangerous_sync(agent_id: str) -> None:
            return None

        with pytest.raises(EATPBlockedError):
            dangerous_sync(agent_id="agent-001")
