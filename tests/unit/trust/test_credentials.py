# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for credential lifecycle management (Task 206)."""

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from care_platform.trust.credentials import CredentialManager, VerificationToken


class TestVerificationTokenIssue:
    """Test VerificationToken.issue() class method."""

    def test_issue_token_with_default_ttl(self):
        """Issue a token with the default 5-minute TTL."""
        token = VerificationToken.issue(
            agent_id="agent-1",
            trust_score=0.85,
            verification_level="STANDARD",
        )
        assert token.agent_id == "agent-1"
        assert token.trust_score == 0.85
        assert token.verification_level == "STANDARD"
        assert not token.revoked
        assert token.token_id.startswith("vt-")
        # Default TTL is 300 seconds (5 minutes)
        expected_delta = timedelta(seconds=300)
        actual_delta = token.expires_at - token.issued_at
        assert actual_delta == expected_delta

    def test_issue_token_with_custom_ttl(self):
        """Issue a token with a custom TTL."""
        token = VerificationToken.issue(
            agent_id="agent-2",
            trust_score=0.90,
            verification_level="FULL",
            ttl_seconds=600,
        )
        expected_delta = timedelta(seconds=600)
        actual_delta = token.expires_at - token.issued_at
        assert actual_delta == expected_delta

    def test_issue_token_unique_ids(self):
        """Each issued token gets a unique token_id."""
        token_a = VerificationToken.issue("agent-1", 0.5)
        token_b = VerificationToken.issue("agent-1", 0.5)
        assert token_a.token_id != token_b.token_id


class TestVerificationTokenValidity:
    """Test VerificationToken.is_valid property."""

    def test_valid_token_within_ttl(self):
        """Token is valid when within its TTL and not revoked."""
        token = VerificationToken.issue("agent-1", 0.85)
        assert token.is_valid

    @freeze_time("2026-01-01 12:00:00", tz_offset=0)
    def test_expired_token_is_invalid(self):
        """Token is invalid after its TTL expires."""
        token = VerificationToken.issue(
            agent_id="agent-1",
            trust_score=0.85,
            ttl_seconds=300,
        )
        # Token issued at 12:00, expires at 12:05
        assert token.is_valid

        # Now manually check with a time after expiry
        token.expires_at = datetime(2026, 1, 1, 11, 59, 0, tzinfo=UTC)
        assert not token.is_valid

    def test_revoked_token_is_invalid(self):
        """Token is invalid after revocation, even if within TTL."""
        token = VerificationToken.issue("agent-1", 0.85)
        assert token.is_valid
        token.revoke()
        assert not token.is_valid

    def test_revoke_sets_revoked_flag(self):
        """revoke() sets the revoked flag to True."""
        token = VerificationToken.issue("agent-1", 0.85)
        assert not token.revoked
        token.revoke()
        assert token.revoked


class TestCredentialManagerIssueToken:
    """Test CredentialManager.issue_token()."""

    def test_issue_token_stores_and_returns(self):
        """Issuing a token stores it and returns the token."""
        mgr = CredentialManager(default_ttl_seconds=300)
        token = mgr.issue_token("agent-1", 0.85, "STANDARD")
        assert token.agent_id == "agent-1"
        assert token.trust_score == 0.85
        assert token.verification_level == "STANDARD"

    def test_issue_token_replaces_previous(self):
        """Issuing a new token for the same agent replaces the old one."""
        mgr = CredentialManager(default_ttl_seconds=300)
        token_old = mgr.issue_token("agent-1", 0.70)
        token_new = mgr.issue_token("agent-1", 0.90)
        current = mgr.get_valid_token("agent-1")
        assert current is not None
        assert current.token_id == token_new.token_id
        assert current.token_id != token_old.token_id

    def test_issue_token_tracks_history(self):
        """Old tokens are moved to history when replaced."""
        mgr = CredentialManager(default_ttl_seconds=300)
        mgr.issue_token("agent-1", 0.70)
        mgr.issue_token("agent-1", 0.90)
        # History should contain the old token
        assert len(mgr._token_history) >= 1
        assert mgr._token_history[0].trust_score == 0.70


class TestCredentialManagerGetValidToken:
    """Test CredentialManager.get_valid_token()."""

    def test_get_valid_token_returns_token(self):
        """Returns the current valid token for an agent."""
        mgr = CredentialManager()
        mgr.issue_token("agent-1", 0.85)
        token = mgr.get_valid_token("agent-1")
        assert token is not None
        assert token.agent_id == "agent-1"

    def test_get_valid_token_returns_none_for_unknown_agent(self):
        """Returns None when no token exists for the agent."""
        mgr = CredentialManager()
        assert mgr.get_valid_token("unknown-agent") is None

    def test_get_valid_token_returns_none_for_expired(self):
        """Returns None when the agent's token has expired."""
        mgr = CredentialManager()
        token = mgr.issue_token("agent-1", 0.85)
        # Manually expire the token
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        assert mgr.get_valid_token("agent-1") is None

    def test_get_valid_token_returns_none_for_revoked(self):
        """Returns None when the agent's token has been revoked."""
        mgr = CredentialManager()
        mgr.issue_token("agent-1", 0.85)
        mgr.revoke_agent_tokens("agent-1")
        assert mgr.get_valid_token("agent-1") is None


class TestCredentialManagerNeedsReverification:
    """Test CredentialManager.needs_reverification()."""

    def test_needs_reverification_no_token(self):
        """Agent needs re-verification when they have no token at all."""
        mgr = CredentialManager()
        assert mgr.needs_reverification("agent-1")

    def test_needs_reverification_expired_token(self):
        """Agent needs re-verification when their token is expired."""
        mgr = CredentialManager()
        token = mgr.issue_token("agent-1", 0.85)
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        assert mgr.needs_reverification("agent-1")

    def test_no_reverification_with_valid_token(self):
        """Agent does NOT need re-verification when they have a valid token."""
        mgr = CredentialManager()
        mgr.issue_token("agent-1", 0.85)
        assert not mgr.needs_reverification("agent-1")


class TestCredentialManagerRevokeAgentTokens:
    """Test CredentialManager.revoke_agent_tokens()."""

    def test_revoke_agent_tokens(self):
        """Revoking agent tokens invalidates their current token."""
        mgr = CredentialManager()
        mgr.issue_token("agent-1", 0.85)
        mgr.revoke_agent_tokens("agent-1")
        assert mgr.get_valid_token("agent-1") is None

    def test_revoke_nonexistent_agent_no_error(self):
        """Revoking tokens for an agent with no token does not raise."""
        mgr = CredentialManager()
        # Should not raise
        mgr.revoke_agent_tokens("nonexistent-agent")


class TestCredentialManagerCleanupExpired:
    """Test CredentialManager.cleanup_expired()."""

    def test_cleanup_removes_expired_tokens(self):
        """cleanup_expired removes tokens that have passed their expiry."""
        mgr = CredentialManager()
        token = mgr.issue_token("agent-1", 0.85)
        # Manually expire the token
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        removed = mgr.cleanup_expired()
        assert removed >= 1
        assert "agent-1" not in mgr._tokens

    def test_cleanup_keeps_valid_tokens(self):
        """cleanup_expired does not remove valid tokens."""
        mgr = CredentialManager()
        mgr.issue_token("agent-1", 0.85)
        removed = mgr.cleanup_expired()
        assert removed == 0
        assert mgr.get_valid_token("agent-1") is not None

    def test_cleanup_returns_count(self):
        """cleanup_expired returns the number of removed tokens."""
        mgr = CredentialManager()
        t1 = mgr.issue_token("agent-1", 0.85)
        t2 = mgr.issue_token("agent-2", 0.90)
        t1.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        t2.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        removed = mgr.cleanup_expired()
        assert removed == 2


class TestCredentialManagerMultipleAgents:
    """Test that multiple agents are tracked independently."""

    def test_independent_agent_tracking(self):
        """Each agent's token is independent of others."""
        mgr = CredentialManager()
        mgr.issue_token("agent-1", 0.85, "STANDARD")
        mgr.issue_token("agent-2", 0.90, "FULL")

        t1 = mgr.get_valid_token("agent-1")
        t2 = mgr.get_valid_token("agent-2")
        assert t1 is not None
        assert t2 is not None
        assert t1.agent_id == "agent-1"
        assert t2.agent_id == "agent-2"
        assert t1.trust_score == 0.85
        assert t2.trust_score == 0.90

    def test_revoking_one_agent_does_not_affect_others(self):
        """Revoking one agent's tokens does not affect another agent."""
        mgr = CredentialManager()
        mgr.issue_token("agent-1", 0.85)
        mgr.issue_token("agent-2", 0.90)
        mgr.revoke_agent_tokens("agent-1")
        assert mgr.get_valid_token("agent-1") is None
        assert mgr.get_valid_token("agent-2") is not None
