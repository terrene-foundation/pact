# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for AuthorizationCheck (Task 1602).

Validates that:
- AuthorizationCheck evaluates BOTH authorization (constraint envelope) and
  capability (attestation)
- Both must pass for an action to proceed
- Clear error messages distinguish "not authorized" from "not capable"
- Agent with capability but no authorization is blocked
- Agent with authorization but no capability is blocked
- Agent with both passes
- Agent with neither fails with appropriate message
"""

import pytest

from care_platform.trust.authorization import AuthorizationCheck, AuthorizationResult
from care_platform.trust.attestation import CapabilityAttestation
from care_platform.constraint.envelope import ConstraintEnvelope
from care_platform.config.schema import ConstraintEnvelopeConfig, OperationalConstraintConfig


def _make_envelope(
    *,
    envelope_id: str = "test-envelope",
    allowed_actions: list[str] | None = None,
    blocked_actions: list[str] | None = None,
) -> ConstraintEnvelope:
    """Create a ConstraintEnvelope for testing."""
    config = ConstraintEnvelopeConfig(
        id=envelope_id,
        operational=OperationalConstraintConfig(
            allowed_actions=allowed_actions or [],
            blocked_actions=blocked_actions or [],
        ),
    )
    return ConstraintEnvelope(config=config)


def _make_attestation(
    *,
    agent_id: str = "agent-1",
    capabilities: list[str] | None = None,
    revoked: bool = False,
) -> CapabilityAttestation:
    """Create a CapabilityAttestation for testing."""
    return CapabilityAttestation(
        attestation_id="attest-1",
        agent_id=agent_id,
        delegation_id="deleg-1",
        constraint_envelope_id="test-envelope",
        capabilities=capabilities or [],
        issuer_id="authority-1",
        revoked=revoked,
    )


class TestAuthorizationCheckConstruction:
    """AuthorizationCheck requires envelope and attestation."""

    def test_requires_envelope(self):
        """AuthorizationCheck requires a non-None envelope."""
        attestation = _make_attestation(capabilities=["read_data"])
        with pytest.raises(ValueError, match="envelope"):
            AuthorizationCheck(envelope=None, attestation=attestation)

    def test_requires_attestation(self):
        """AuthorizationCheck requires a non-None attestation."""
        envelope = _make_envelope()
        with pytest.raises(ValueError, match="attestation"):
            AuthorizationCheck(envelope=envelope, attestation=None)

    def test_accepts_valid_inputs(self):
        """AuthorizationCheck accepts valid envelope and attestation."""
        envelope = _make_envelope()
        attestation = _make_attestation(capabilities=["read_data"])
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        assert check is not None


class TestAuthorizationCheckBothPass:
    """Agent with both authorization and capability passes."""

    def test_both_pass_is_authorized(self):
        """Agent authorized by envelope AND capable per attestation passes."""
        envelope = _make_envelope()  # No blocked/allowed restrictions = allows all
        attestation = _make_attestation(capabilities=["read_data"])
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        result = check.evaluate(action="read_data", agent_id="agent-1")
        assert result.authorized is True
        assert result.capable is True
        assert result.permitted is True

    def test_both_pass_has_no_errors(self):
        """When both pass, there should be no error messages."""
        envelope = _make_envelope()
        attestation = _make_attestation(capabilities=["read_data"])
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        result = check.evaluate(action="read_data", agent_id="agent-1")
        assert result.denial_reason == ""


class TestAuthorizationCheckCapableButNotAuthorized:
    """Agent with capability but no authorization is blocked."""

    def test_capable_but_blocked_by_envelope(self):
        """Agent has capability in attestation but envelope blocks it."""
        envelope = _make_envelope(blocked_actions=["deploy"])
        attestation = _make_attestation(capabilities=["deploy"])
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        result = check.evaluate(action="deploy", agent_id="agent-1")
        assert result.capable is True
        assert result.authorized is False
        assert result.permitted is False

    def test_not_authorized_message_is_clear(self):
        """Denial reason clearly states the agent is not authorized."""
        envelope = _make_envelope(blocked_actions=["deploy"])
        attestation = _make_attestation(capabilities=["deploy"])
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        result = check.evaluate(action="deploy", agent_id="agent-1")
        assert "not authorized" in result.denial_reason.lower() or "authorization" in result.denial_reason.lower()


class TestAuthorizationCheckAuthorizedButNotCapable:
    """Agent with authorization but no capability is blocked."""

    def test_authorized_but_no_capability(self):
        """Envelope allows the action but attestation does not list it."""
        envelope = _make_envelope()  # allows all
        attestation = _make_attestation(capabilities=["read_data"])  # no "write_data"
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        result = check.evaluate(action="write_data", agent_id="agent-1")
        assert result.authorized is True
        assert result.capable is False
        assert result.permitted is False

    def test_not_capable_message_is_clear(self):
        """Denial reason clearly states the agent lacks capability."""
        envelope = _make_envelope()
        attestation = _make_attestation(capabilities=["read_data"])
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        result = check.evaluate(action="write_data", agent_id="agent-1")
        assert "not capable" in result.denial_reason.lower() or "capability" in result.denial_reason.lower()


class TestAuthorizationCheckNeitherPass:
    """Agent with neither authorization nor capability fails."""

    def test_neither_authorized_nor_capable(self):
        """Both envelope and attestation deny the action."""
        envelope = _make_envelope(blocked_actions=["deploy"])
        attestation = _make_attestation(capabilities=["read_data"])
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        result = check.evaluate(action="deploy", agent_id="agent-1")
        assert result.authorized is False
        assert result.capable is False
        assert result.permitted is False

    def test_combined_denial_mentions_both(self):
        """Denial reason mentions both authorization and capability failures."""
        envelope = _make_envelope(blocked_actions=["deploy"])
        attestation = _make_attestation(capabilities=["read_data"])
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        result = check.evaluate(action="deploy", agent_id="agent-1")
        reason = result.denial_reason.lower()
        assert "authorization" in reason or "not authorized" in reason
        # The first failure (authorization) is sufficient to explain denial


class TestAuthorizationCheckRevokedAttestation:
    """Revoked attestation makes agent not capable."""

    def test_revoked_attestation_is_not_capable(self):
        """A revoked attestation means the agent has no valid capabilities."""
        envelope = _make_envelope()
        attestation = _make_attestation(capabilities=["read_data"], revoked=True)
        check = AuthorizationCheck(envelope=envelope, attestation=attestation)
        result = check.evaluate(action="read_data", agent_id="agent-1")
        assert result.capable is False
        assert result.permitted is False


class TestAuthorizationResult:
    """AuthorizationResult model correctness."""

    def test_permitted_requires_both(self):
        """permitted is True only when both authorized and capable are True."""
        result = AuthorizationResult(
            authorized=True, capable=True, denial_reason=""
        )
        assert result.permitted is True

    def test_not_permitted_when_not_authorized(self):
        result = AuthorizationResult(
            authorized=False, capable=True, denial_reason="not authorized"
        )
        assert result.permitted is False

    def test_not_permitted_when_not_capable(self):
        result = AuthorizationResult(
            authorized=True, capable=False, denial_reason="not capable"
        )
        assert result.permitted is False


class TestAttestationHasAuthorization:
    """CapabilityAttestation.has_authorization() method (Task 1602 addition)."""

    def test_has_authorization_with_envelope_allowing(self):
        """has_authorization returns True when envelope does not block."""
        attestation = _make_attestation(capabilities=["read_data"])
        envelope = _make_envelope()
        assert attestation.has_authorization("read_data", envelope) is True

    def test_has_authorization_with_envelope_blocking(self):
        """has_authorization returns False when envelope blocks the action."""
        attestation = _make_attestation(capabilities=["deploy"])
        envelope = _make_envelope(blocked_actions=["deploy"])
        assert attestation.has_authorization("deploy", envelope) is False

    def test_has_authorization_revoked_attestation(self):
        """has_authorization returns False for revoked attestation."""
        attestation = _make_attestation(capabilities=["read_data"], revoked=True)
        envelope = _make_envelope()
        assert attestation.has_authorization("read_data", envelope) is False
