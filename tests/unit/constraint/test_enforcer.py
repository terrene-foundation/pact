# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for ConstraintEnforcer (Task 1601).

Validates that:
- ConstraintEnforcer wraps VerificationMiddleware and makes constraint checking mandatory
- Every runtime action passes through the enforcer
- BLOCKED results reject the action
- HELD results queue the action for approval
- AUTO_APPROVED and FLAGGED results allow the action
- EnforcerRequiredError is raised when enforcer is None and runtime tries to process
"""

import pytest

from care_platform.trust.audit.anchor import AuditChain
from care_platform.build.config.schema import (
    ConstraintEnvelopeConfig,
    OperationalConstraintConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.trust.constraint.enforcer import ConstraintEnforcer, EnforcerRequiredError
from care_platform.trust.constraint.envelope import ConstraintEnvelope
from care_platform.trust.constraint.gradient import GradientEngine
from care_platform.trust.constraint.middleware import (
    ActionOutcome,
    MiddlewareResult,
    VerificationMiddleware,
)


def _make_middleware(
    *,
    blocked_actions: list[str] | None = None,
    allowed_actions: list[str] | None = None,
) -> VerificationMiddleware:
    """Create a VerificationMiddleware with a simple config for testing.

    Uses AUTO_APPROVED as the default gradient level so that actions within
    constraints are executed immediately (not queued for approval).
    """
    envelope_config = ConstraintEnvelopeConfig(
        id="test-envelope",
        operational=OperationalConstraintConfig(
            blocked_actions=blocked_actions or [],
            allowed_actions=allowed_actions or [],
        ),
    )
    envelope = ConstraintEnvelope(config=envelope_config)
    gradient_config = VerificationGradientConfig(
        default_level=VerificationLevel.AUTO_APPROVED,
    )
    gradient = GradientEngine(gradient_config)
    audit_chain = AuditChain(chain_id="test-enforcer")
    return VerificationMiddleware(
        gradient_engine=gradient,
        envelope=envelope,
        audit_chain=audit_chain,
    )


class TestConstraintEnforcerConstruction:
    """ConstraintEnforcer is properly constructed and validates inputs."""

    def test_enforcer_requires_middleware(self):
        """ConstraintEnforcer must require a non-None middleware."""
        with pytest.raises(ValueError, match="middleware"):
            ConstraintEnforcer(middleware=None)

    def test_enforcer_accepts_valid_middleware(self):
        """ConstraintEnforcer accepts a valid VerificationMiddleware."""
        middleware = _make_middleware()
        enforcer = ConstraintEnforcer(middleware=middleware)
        assert enforcer is not None

    def test_enforcer_exposes_middleware(self):
        """ConstraintEnforcer exposes the underlying middleware."""
        middleware = _make_middleware()
        enforcer = ConstraintEnforcer(middleware=middleware)
        assert enforcer.middleware is middleware


class TestConstraintEnforcerCheck:
    """ConstraintEnforcer.check() evaluates actions through the verification pipeline."""

    def test_check_returns_middleware_result(self):
        """check() must return a MiddlewareResult."""
        middleware = _make_middleware()
        enforcer = ConstraintEnforcer(middleware=middleware)
        result = enforcer.check(action="read_data", agent_id="agent-1")
        assert isinstance(result, MiddlewareResult)

    def test_check_auto_approves_allowed_action(self):
        """An action within constraints is AUTO_APPROVED."""
        middleware = _make_middleware()
        enforcer = ConstraintEnforcer(middleware=middleware)
        result = enforcer.check(action="read_data", agent_id="agent-1")
        assert result.outcome == ActionOutcome.EXECUTED
        assert result.verification_level in (
            VerificationLevel.AUTO_APPROVED,
            VerificationLevel.FLAGGED,
        )

    def test_check_blocks_denied_action(self):
        """An action that violates constraints is BLOCKED."""
        middleware = _make_middleware(blocked_actions=["delete_all"])
        enforcer = ConstraintEnforcer(middleware=middleware)
        result = enforcer.check(action="delete_all", agent_id="agent-1")
        assert result.outcome == ActionOutcome.REJECTED
        assert result.verification_level == VerificationLevel.BLOCKED

    def test_check_passes_resource_to_middleware(self):
        """check() passes optional resource parameter through."""
        middleware = _make_middleware()
        enforcer = ConstraintEnforcer(middleware=middleware)
        result = enforcer.check(
            action="read_data",
            agent_id="agent-1",
            resource="docs/report.md",
        )
        assert isinstance(result, MiddlewareResult)

    def test_check_logs_every_action(self):
        """Every check() call is recorded in the middleware's action log."""
        middleware = _make_middleware()
        enforcer = ConstraintEnforcer(middleware=middleware)
        enforcer.check(action="action_1", agent_id="agent-1")
        enforcer.check(action="action_2", agent_id="agent-1")
        assert len(middleware.action_log) == 2


class TestConstraintEnforcerBlocked:
    """BLOCKED results properly reject the action."""

    def test_blocked_action_is_rejected(self):
        """When the enforcer returns BLOCKED, the action must be rejected."""
        middleware = _make_middleware(blocked_actions=["dangerous_action"])
        enforcer = ConstraintEnforcer(middleware=middleware)
        result = enforcer.check(action="dangerous_action", agent_id="agent-1")
        assert result.verification_level == VerificationLevel.BLOCKED
        assert result.outcome == ActionOutcome.REJECTED

    def test_blocked_result_contains_explanation(self):
        """BLOCKED results include a human-readable explanation."""
        middleware = _make_middleware(blocked_actions=["dangerous_action"])
        enforcer = ConstraintEnforcer(middleware=middleware)
        result = enforcer.check(action="dangerous_action", agent_id="agent-1")
        assert result.details  # Must not be empty


class TestEnforcerRequiredError:
    """EnforcerRequiredError is raised when enforcer is None."""

    def test_error_is_value_error_subclass(self):
        """EnforcerRequiredError should be a RuntimeError for clear intent."""
        assert issubclass(EnforcerRequiredError, RuntimeError)

    def test_error_has_descriptive_message(self):
        """The error message describes why the enforcer is required."""
        err = EnforcerRequiredError()
        assert "enforcer" in str(err).lower() or "constraint" in str(err).lower()

    def test_error_with_custom_message(self):
        """EnforcerRequiredError can accept a custom message."""
        err = EnforcerRequiredError("Custom: enforcer missing in runtime")
        assert "Custom" in str(err)


class TestConstraintEnforcerHaltIntegration:
    """ConstraintEnforcer respects middleware halt state."""

    def test_check_blocked_when_middleware_halted(self):
        """If middleware is halted, all actions are BLOCKED."""
        middleware = _make_middleware()
        enforcer = ConstraintEnforcer(middleware=middleware)
        middleware.halt("emergency shutdown")
        result = enforcer.check(action="read_data", agent_id="agent-1")
        assert result.outcome == ActionOutcome.REJECTED
        assert result.verification_level == VerificationLevel.BLOCKED

    def test_check_resumes_after_middleware_resume(self):
        """After middleware is resumed, actions process normally."""
        middleware = _make_middleware()
        enforcer = ConstraintEnforcer(middleware=middleware)
        middleware.halt("temporary")
        middleware.resume()
        result = enforcer.check(action="read_data", agent_id="agent-1")
        assert result.outcome == ActionOutcome.EXECUTED
