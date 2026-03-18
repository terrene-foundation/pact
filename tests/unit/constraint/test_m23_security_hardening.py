# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""M23 Security Hardening — tests for tasks 2301-2306.

Tests constraint-level security improvements:
- 2301: Financial constraint optional pattern
- 2302: Missing constraint model parameters
- 2303: Delegation expiry enforcement at runtime
- 2304: Cumulative spend thread lock
- 2305: In-flight action revocation check
- 2306: Per-agent rate limiting in middleware
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest

from care_platform.build.config.schema import (
    ConstraintEnvelopeConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.trust.constraint.envelope import (
    ConstraintEnvelope,
    EvaluationResult,
)
from care_platform.trust.constraint.gradient import GradientEngine
from care_platform.trust.constraint.middleware import (
    ActionOutcome,
    VerificationMiddleware,
)

# ---------------------------------------------------------------------------
# 2301: Financial Constraint Optional Pattern (RT5-19)
# ---------------------------------------------------------------------------


class TestFinancialConstraintOptional:
    """Financial constraint should be Optional — not all agents handle money."""

    def test_constraint_envelope_config_allows_none_financial(self):
        """ConstraintEnvelopeConfig should accept financial=None."""
        config = ConstraintEnvelopeConfig(
            id="no-money-agent",
            financial=None,
        )
        assert config.financial is None

    def test_envelope_skips_financial_evaluation_when_none(self):
        """When financial is None, envelope evaluation should skip financial checks."""
        config = ConstraintEnvelopeConfig(
            id="no-money-agent",
            financial=None,
        )
        envelope = ConstraintEnvelope(config=config)

        result = envelope.evaluate_action(
            action="read_data",
            agent_id="agent-1",
            spend_amount=100.0,
        )
        # Financial check should be skipped — no financial dimension in results
        financial_dims = [d for d in result.dimensions if d.dimension == "financial"]
        assert len(financial_dims) == 0, (
            "Financial dimension should not be evaluated when financial config is None"
        )

    def test_envelope_with_financial_none_allows_non_financial_actions(self):
        """Non-financial actions should still work with financial=None."""
        config = ConstraintEnvelopeConfig(
            id="reader-agent",
            financial=None,
            operational=OperationalConstraintConfig(
                allowed_actions=["read_data"],
            ),
        )
        envelope = ConstraintEnvelope(config=config)

        result = envelope.evaluate_action(
            action="read_data",
            agent_id="agent-1",
        )
        assert result.overall_result == EvaluationResult.ALLOWED

    def test_default_financial_zero_spend_blocks_everything(self):
        """Verify that the default financial (max_spend_usd=0.0) blocks any spend."""
        config = ConstraintEnvelopeConfig(id="default-envelope")
        envelope = ConstraintEnvelope(config=config)

        result = envelope.evaluate_action(
            action="api_call",
            agent_id="agent-1",
            spend_amount=0.01,
        )
        # Default max_spend_usd=0.0 means any spend is denied
        financial_dims = [d for d in result.dimensions if d.dimension == "financial"]
        assert len(financial_dims) == 1
        assert financial_dims[0].result == EvaluationResult.DENIED

    def test_is_tighter_than_handles_none_financial(self):
        """is_tighter_than should handle None financial in child and parent."""
        parent_config = ConstraintEnvelopeConfig(
            id="parent",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            financial=None,
        )
        parent = ConstraintEnvelope(config=parent_config)
        child = ConstraintEnvelope(config=child_config)

        # None financial (no spending capability) is tighter than having a budget
        assert child.is_tighter_than(parent) is True

    def test_is_tighter_than_both_none_financial(self):
        """When both parent and child have None financial, child is tighter (or equal)."""
        parent_config = ConstraintEnvelopeConfig(id="parent", financial=None)
        child_config = ConstraintEnvelopeConfig(id="child", financial=None)
        parent = ConstraintEnvelope(config=parent_config)
        child = ConstraintEnvelope(config=child_config)

        assert child.is_tighter_than(parent) is True

    def test_is_tighter_than_child_has_financial_parent_none(self):
        """When parent has None financial, child with financial is looser."""
        parent_config = ConstraintEnvelopeConfig(id="parent", financial=None)
        child_config = ConstraintEnvelopeConfig(
            id="child",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        parent = ConstraintEnvelope(config=parent_config)
        child = ConstraintEnvelope(config=child_config)

        assert child.is_tighter_than(parent) is False


# ---------------------------------------------------------------------------
# 2302: Missing Constraint Model Parameters (RT5-17/20/28)
# ---------------------------------------------------------------------------


class TestMissingConstraintParameters:
    """Add missing parameters: max_delegation_depth, envelope_expiry, rate_limit_window_type."""

    def test_operational_has_max_actions_per_hour(self):
        """OperationalConstraintConfig should have max_actions_per_hour."""
        config = OperationalConstraintConfig(max_actions_per_hour=60)
        assert config.max_actions_per_hour == 60

    def test_operational_max_actions_per_hour_defaults_to_none(self):
        """max_actions_per_hour should default to None (no per-hour limit)."""
        config = OperationalConstraintConfig()
        assert config.max_actions_per_hour is None

    def test_constraint_envelope_config_has_max_delegation_depth(self):
        """ConstraintEnvelopeConfig should have max_delegation_depth."""
        config = ConstraintEnvelopeConfig(
            id="depth-limited",
            max_delegation_depth=3,
        )
        assert config.max_delegation_depth == 3

    def test_max_delegation_depth_defaults_to_none(self):
        """max_delegation_depth should default to None (unlimited)."""
        config = ConstraintEnvelopeConfig(id="default")
        assert config.max_delegation_depth is None

    def test_constraint_envelope_config_has_expires_at(self):
        """ConstraintEnvelopeConfig should have expires_at field."""
        expiry = datetime.now(UTC) + timedelta(days=30)
        config = ConstraintEnvelopeConfig(
            id="expiring-envelope",
            expires_at=expiry,
        )
        assert config.expires_at == expiry

    def test_expires_at_defaults_to_none(self):
        """expires_at should default to None (no explicit expiry on the config level)."""
        config = ConstraintEnvelopeConfig(id="default")
        assert config.expires_at is None

    def test_operational_has_rate_limit_window_type(self):
        """OperationalConstraintConfig should support rate_limit_window_type."""
        config = OperationalConstraintConfig(rate_limit_window_type="rolling")
        assert config.rate_limit_window_type == "rolling"

    def test_rate_limit_window_type_defaults_to_fixed(self):
        """rate_limit_window_type should default to 'fixed'."""
        config = OperationalConstraintConfig()
        assert config.rate_limit_window_type == "fixed"

    def test_rate_limit_window_type_validates_values(self):
        """rate_limit_window_type should only accept 'fixed' or 'rolling'."""
        with pytest.raises(ValueError):
            OperationalConstraintConfig(rate_limit_window_type="invalid")

    def test_is_tighter_than_enforces_delegation_depth(self):
        """Child with deeper max_delegation_depth than parent should fail tightening check."""
        parent_config = ConstraintEnvelopeConfig(
            id="parent",
            max_delegation_depth=3,
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            max_delegation_depth=5,  # wider than parent
        )
        parent = ConstraintEnvelope(config=parent_config)
        child = ConstraintEnvelope(config=child_config)

        assert child.is_tighter_than(parent) is False

    def test_is_tighter_than_allows_tighter_delegation_depth(self):
        """Child with shallower max_delegation_depth should pass tightening check."""
        parent_config = ConstraintEnvelopeConfig(
            id="parent",
            max_delegation_depth=5,
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            max_delegation_depth=3,
        )
        parent = ConstraintEnvelope(config=parent_config)
        child = ConstraintEnvelope(config=child_config)

        assert child.is_tighter_than(parent) is True


# ---------------------------------------------------------------------------
# 2303: Delegation Expiry Enforcement at Runtime (RT5-24)
# ---------------------------------------------------------------------------


class TestDelegationExpiryEnforcement:
    """Delegation expiry must be checked at action-execution time, not just at bootstrap."""

    def test_middleware_blocks_expired_delegation(self):
        """When delegation has expired, actions should be BLOCKED."""
        config = ConstraintEnvelopeConfig(
            id="test-env",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)

        mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=envelope,
            delegation_expiry=datetime.now(UTC) - timedelta(hours=1),  # expired
        )

        result = mw.process_action(
            agent_id="agent-1",
            action="read_data",
        )
        assert result.outcome == ActionOutcome.REJECTED
        assert "delegation" in result.details.lower() and "expir" in result.details.lower()

    def test_middleware_allows_non_expired_delegation(self):
        """When delegation has not expired, actions should proceed normally."""
        config = ConstraintEnvelopeConfig(
            id="test-env",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)

        mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=envelope,
            delegation_expiry=datetime.now(UTC) + timedelta(hours=24),  # valid
        )

        result = mw.process_action(
            agent_id="agent-1",
            action="read_data",
        )
        assert result.outcome == ActionOutcome.EXECUTED

    def test_middleware_no_delegation_expiry_allows_action(self):
        """When no delegation_expiry is set, actions should proceed normally."""
        config = ConstraintEnvelopeConfig(
            id="test-env",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)

        mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=envelope,
        )

        result = mw.process_action(
            agent_id="agent-1",
            action="read_data",
        )
        assert result.outcome == ActionOutcome.EXECUTED


# ---------------------------------------------------------------------------
# 2304: Cumulative Spend Thread Lock (RT10-A2)
# ---------------------------------------------------------------------------


class TestCumulativeSpendThreadLock:
    """Cumulative spend updates must be protected by a threading lock."""

    def test_cumulative_spend_lock_exists(self):
        """VerificationMiddleware should have a lock for spend tracking."""
        config = ConstraintEnvelopeConfig(
            id="test-env",
            financial=FinancialConstraintConfig(
                max_spend_usd=1000.0,
                api_cost_budget_usd=10000.0,
            ),
        )
        envelope = ConstraintEnvelope(config=config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)

        mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=envelope,
        )
        assert hasattr(mw, "_spend_lock")
        assert isinstance(mw._spend_lock, type(threading.Lock()))

    def test_concurrent_spend_updates_are_consistent(self):
        """Multiple threads updating spend should produce consistent totals."""
        config = ConstraintEnvelopeConfig(
            id="test-env",
            financial=FinancialConstraintConfig(
                max_spend_usd=1000.0,
                api_cost_budget_usd=100000.0,
            ),
        )
        envelope = ConstraintEnvelope(config=config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)

        mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=envelope,
        )

        num_threads = 10
        spend_per_thread = 1.0
        barrier = threading.Barrier(num_threads)

        def spend_action(agent_id: str):
            barrier.wait()
            mw.process_action(
                agent_id=agent_id,
                action="api_call",
                spend_amount=spend_per_thread,
            )

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=spend_action, args=(f"agent-{i % 2}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Total spend across all agents should be exactly num_threads * spend_per_thread
        total = sum(mw._cumulative_spend.values())
        assert total == pytest.approx(num_threads * spend_per_thread, abs=0.01), (
            f"Expected total spend {num_threads * spend_per_thread}, got {total}. "
            "Race condition in spend tracking."
        )


# ---------------------------------------------------------------------------
# 2305: In-flight Action Revocation Check (RT10-A5)
# ---------------------------------------------------------------------------


class TestInflightRevocationCheck:
    """When an agent is revoked while an action is in-flight, it should be blocked."""

    def test_runtime_checks_revocation_at_execution_time(self):
        """ExecutionRuntime should re-check revocation before executing a task."""
        from care_platform.trust.audit.anchor import AuditChain
        from care_platform.use.execution.registry import AgentRegistry
        from care_platform.use.execution.runtime import ExecutionRuntime, TaskStatus
        from care_platform.trust.revocation import RevocationManager

        registry = AgentRegistry()
        registry.register(agent_id="agent-1", name="Agent 1", role="worker")

        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)
        audit_chain = AuditChain(chain_id="test")
        revocation_mgr = RevocationManager()

        runtime = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            revocation_manager=revocation_mgr,
        )

        # Submit a task
        task_id = runtime.submit("read_data", agent_id="agent-1")

        # Revoke the agent before processing
        revocation_mgr.surgical_revoke("agent-1", "security breach", "admin")

        # Process should fail because agent is revoked
        task = runtime.process_next()
        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert task.result is not None
        assert "revoked" in task.result.error.lower()


# ---------------------------------------------------------------------------
# 2306: Per-Agent Rate Limiting in Middleware (I7)
# ---------------------------------------------------------------------------


class TestPerAgentRateLimiting:
    """Per-agent rate limiting tracks action counts within a sliding window."""

    def test_rate_limit_blocks_when_exceeded(self):
        """When max_actions_per_hour is exceeded, actions should be BLOCKED."""
        config = ConstraintEnvelopeConfig(
            id="rate-limited",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                max_actions_per_hour=5,
            ),
        )
        envelope = ConstraintEnvelope(config=config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)

        mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=envelope,
        )

        # Exhaust rate limit
        for i in range(5):
            result = mw.process_action(
                agent_id="agent-1",
                action=f"action_{i}",
            )
            assert result.outcome == ActionOutcome.EXECUTED, f"Action {i} should be executed"

        # 6th action should be blocked
        result = mw.process_action(
            agent_id="agent-1",
            action="action_6",
        )
        assert result.outcome == ActionOutcome.REJECTED
        assert "rate limit" in result.details.lower()

    def test_rate_limit_is_per_agent(self):
        """Rate limiting should be tracked per-agent, not globally."""
        config = ConstraintEnvelopeConfig(
            id="rate-limited",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                max_actions_per_hour=3,
            ),
        )
        envelope = ConstraintEnvelope(config=config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)

        mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=envelope,
        )

        # agent-1 uses 3 actions
        for i in range(3):
            mw.process_action(agent_id="agent-1", action=f"action_{i}")

        # agent-2 should still be allowed
        result = mw.process_action(agent_id="agent-2", action="action_0")
        assert result.outcome == ActionOutcome.EXECUTED

        # agent-1 should be blocked
        result = mw.process_action(agent_id="agent-1", action="action_4")
        assert result.outcome == ActionOutcome.REJECTED

    def test_rate_limit_window_allows_after_expiry(self):
        """Actions should be allowed again after the rate limit window expires."""
        config = ConstraintEnvelopeConfig(
            id="rate-limited",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                max_actions_per_hour=2,
            ),
        )
        envelope = ConstraintEnvelope(config=config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)

        mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=envelope,
        )

        # Use 2 actions
        mw.process_action(agent_id="agent-1", action="action_0")
        mw.process_action(agent_id="agent-1", action="action_1")

        # Should be blocked now
        result = mw.process_action(agent_id="agent-1", action="action_2")
        assert result.outcome == ActionOutcome.REJECTED

        # Manually expire the old actions by clearing the internal window
        # (simulating passage of time)
        mw._rate_limit_windows["agent-1"].clear()

        # Should be allowed again
        result = mw.process_action(agent_id="agent-1", action="action_3")
        assert result.outcome == ActionOutcome.EXECUTED

    def test_no_rate_limit_when_not_configured(self):
        """When max_actions_per_hour is None, no rate limiting should apply."""
        config = ConstraintEnvelopeConfig(
            id="no-rate-limit",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                max_actions_per_hour=None,
            ),
        )
        envelope = ConstraintEnvelope(config=config)
        gradient_config = VerificationGradientConfig(
            default_level=VerificationLevel.AUTO_APPROVED,
        )
        gradient = GradientEngine(gradient_config)

        mw = VerificationMiddleware(
            gradient_engine=gradient,
            envelope=envelope,
        )

        # Should be able to do many actions without being rate limited
        for i in range(100):
            result = mw.process_action(
                agent_id="agent-1",
                action=f"action_{i}",
            )
            assert result.outcome == ActionOutcome.EXECUTED
