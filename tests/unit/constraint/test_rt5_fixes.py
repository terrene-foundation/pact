# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for RT5 security findings:

- RT5-04 (CRITICAL): Frozen (immutable) constraint config models
- RT5-05 (CRITICAL): Reject future-dated signed_at in freshness check
- RT5-16 (MEDIUM): Nonce eviction for unbounded growth
- RT5-18 (MEDIUM): Monotonic tightening check bypass when child is None
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from care_platform.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)
from care_platform.constraint.envelope import ConstraintEnvelope
from care_platform.execution.approval import ApprovalQueue
from care_platform.execution.approver_auth import (
    ApproverRegistry,
    AuthenticatedApprovalQueue,
    SignedDecision,
    _serialize_decision_for_signing,
    sign_decision,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_keypair() -> tuple[bytes, bytes]:
    """Generate an Ed25519 keypair and return (private_key_bytes, public_key_bytes)."""
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes_raw()
    public_bytes = private_key.public_key().public_bytes_raw()
    return private_bytes, public_bytes


def _make_envelope(**kwargs) -> ConstraintEnvelope:
    config = ConstraintEnvelopeConfig(id="rt5-test-env", **kwargs)
    return ConstraintEnvelope(config=config)


def _sign_with_custom_timestamp(
    priv: bytes, action_id: str, decision: str, reason: str, signed_at: datetime
) -> SignedDecision:
    """Create a properly signed decision with a specific signed_at timestamp."""
    import uuid

    nonce = uuid.uuid4().hex
    payload = _serialize_decision_for_signing(
        action_id, decision, reason, nonce, signed_at.isoformat()
    )
    priv_key = Ed25519PrivateKey.from_private_bytes(priv)
    sig = priv_key.sign(payload).hex()

    return SignedDecision(
        action_id=action_id,
        decision=decision,
        reason=reason,
        signature=sig,
        signed_at=signed_at,
        nonce=nonce,
    )


# ===========================================================================
# RT5-04 (CRITICAL): Frozen (immutable) constraint config models
# ===========================================================================


class TestFrozenConstraintConfigs:
    """RT5-04: Constraint config models must be immutable (frozen).

    Execution-plane code must not be able to modify Trust Plane state.
    All six constraint config classes and ConstraintEnvelopeConfig must
    raise an error when mutation is attempted after construction.
    """

    def test_financial_config_frozen(self):
        """FinancialConstraintConfig should reject attribute mutation."""
        config = FinancialConstraintConfig(max_spend_usd=100.0)
        with pytest.raises(Exception):
            config.max_spend_usd = 999.0

    def test_financial_config_api_cost_frozen(self):
        """FinancialConstraintConfig.api_cost_budget_usd should reject mutation."""
        config = FinancialConstraintConfig(api_cost_budget_usd=50.0)
        with pytest.raises(Exception):
            config.api_cost_budget_usd = 9999.0

    def test_operational_config_frozen(self):
        """OperationalConstraintConfig should reject attribute mutation."""
        config = OperationalConstraintConfig(allowed_actions=["read"])
        with pytest.raises(Exception):
            config.max_actions_per_day = 999

    def test_operational_config_blocked_actions_frozen(self):
        """OperationalConstraintConfig.blocked_actions should reject mutation."""
        config = OperationalConstraintConfig(blocked_actions=["delete"])
        with pytest.raises(Exception):
            config.blocked_actions = ["nothing"]

    def test_temporal_config_frozen(self):
        """TemporalConstraintConfig should reject attribute mutation."""
        config = TemporalConstraintConfig(active_hours_start="09:00", active_hours_end="17:00")
        with pytest.raises(Exception):
            config.active_hours_start = "00:00"

    def test_data_access_config_frozen(self):
        """DataAccessConstraintConfig should reject attribute mutation."""
        config = DataAccessConstraintConfig(read_paths=["reports/"])
        with pytest.raises(Exception):
            config.read_paths = ["everything/"]

    def test_communication_config_frozen(self):
        """CommunicationConstraintConfig should reject attribute mutation."""
        config = CommunicationConstraintConfig(internal_only=True)
        with pytest.raises(Exception):
            config.internal_only = False

    def test_constraint_envelope_config_frozen(self):
        """ConstraintEnvelopeConfig should reject attribute mutation."""
        config = ConstraintEnvelopeConfig(id="test")
        with pytest.raises(Exception):
            config.description = "mutated"

    def test_frozen_config_is_hashable(self):
        """Frozen models should be hashable (a benefit of immutability)."""
        config = FinancialConstraintConfig(max_spend_usd=100.0)
        # Should not raise
        hash(config)

    def test_frozen_config_model_copy_creates_new_instance(self):
        """model_copy(update={...}) should be the way to create modified configs."""
        original = FinancialConstraintConfig(max_spend_usd=100.0)
        modified = original.model_copy(update={"max_spend_usd": 200.0})
        assert original.max_spend_usd == 100.0
        assert modified.max_spend_usd == 200.0

    def test_constraint_envelope_config_nested_frozen(self):
        """Nested config fields within ConstraintEnvelopeConfig should also be frozen."""
        config = ConstraintEnvelopeConfig(
            id="test",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        with pytest.raises(Exception):
            config.financial.max_spend_usd = 999.0

    def test_constraint_envelope_runtime_is_frozen(self):
        """RT10-DP1: ConstraintEnvelope (runtime object) must be frozen to prevent
        post-creation constraint widening."""
        env = _make_envelope()
        with pytest.raises(Exception):
            env.version = 2


# ===========================================================================
# RT5-05 (CRITICAL): Reject future-dated signed_at in freshness check
# ===========================================================================


class TestFutureDatedSignedAtRejection:
    """RT5-05: Future-dated signed_at must be rejected in freshness check.

    If signed_at is in the future, the computed age is negative and would
    always pass the `age > max_decision_age_seconds` check. This is a clock
    skew or tampering scenario that must be explicitly rejected.
    """

    def _setup_queue(
        self, max_decision_age_seconds: int = 300
    ) -> tuple[AuthenticatedApprovalQueue, bytes, str]:
        """Create an authenticated queue with one registered approver."""
        priv, pub = _generate_keypair()
        approver_id = "approver-1"

        registry = ApproverRegistry()
        registry.register(approver_id, pub)

        inner_queue = ApprovalQueue()
        auth_queue = AuthenticatedApprovalQueue(
            queue=inner_queue,
            registry=registry,
            max_decision_age_seconds=max_decision_age_seconds,
        )

        pa = auth_queue.submit(
            agent_id="agent-x",
            action="deploy-production",
            reason="held by gradient",
        )
        return auth_queue, priv, pa.action_id

    def test_future_dated_signed_at_rejected(self):
        """A signed decision with signed_at in the future must be rejected."""
        auth_queue, priv, action_id = self._setup_queue()

        future_time = datetime.now(UTC) + timedelta(hours=1)
        signed = _sign_with_custom_timestamp(priv, action_id, "approved", "looks good", future_time)

        with pytest.raises(PermissionError, match="future"):
            auth_queue.approve(
                action_id=action_id,
                approver_id="approver-1",
                signed_decision=signed,
            )

    def test_future_dated_just_one_second_rejected(self):
        """Even 1 second in the future should be rejected (clock skew or tampering)."""
        auth_queue, priv, action_id = self._setup_queue()

        future_time = datetime.now(UTC) + timedelta(seconds=1)
        signed = _sign_with_custom_timestamp(priv, action_id, "approved", "ok", future_time)

        with pytest.raises(PermissionError, match="future"):
            auth_queue.approve(
                action_id=action_id,
                approver_id="approver-1",
                signed_decision=signed,
            )

    def test_current_time_accepted(self):
        """A decision signed at the current time (not future) should be accepted."""
        auth_queue, priv, action_id = self._setup_queue()

        signed = sign_decision(priv, action_id, "approved", "ok")
        result = auth_queue.approve(
            action_id=action_id,
            approver_id="approver-1",
            signed_decision=signed,
        )
        assert result.status == "approved"


# ===========================================================================
# RT5-16 (MEDIUM): Nonce eviction for unbounded growth
# ===========================================================================


class TestNonceEviction:
    """RT5-16: Used nonces must be evicted after they expire.

    Nonces older than max_decision_age_seconds can never be replayed (the
    freshness check rejects them), so they can safely be removed to prevent
    unbounded memory growth.
    """

    def _setup_queue(
        self, max_decision_age_seconds: int = 60
    ) -> tuple[AuthenticatedApprovalQueue, bytes, str]:
        """Create an authenticated queue with short max age for eviction testing."""
        priv, pub = _generate_keypair()
        approver_id = "approver-1"

        registry = ApproverRegistry()
        registry.register(approver_id, pub)

        inner_queue = ApprovalQueue()
        auth_queue = AuthenticatedApprovalQueue(
            queue=inner_queue,
            registry=registry,
            max_decision_age_seconds=max_decision_age_seconds,
        )

        pa = auth_queue.submit(
            agent_id="agent-x",
            action="deploy-production",
            reason="held by gradient",
        )
        return auth_queue, priv, pa.action_id

    def test_used_nonces_is_dict(self):
        """_used_nonces should be a dict (nonce -> timestamp) for eviction support."""
        auth_queue, _, _ = self._setup_queue()
        assert isinstance(auth_queue._used_nonces, dict)

    def test_nonce_stored_with_timestamp(self):
        """After a successful decision, the nonce should be stored with a datetime value."""
        auth_queue, priv, action_id = self._setup_queue()

        signed = sign_decision(priv, action_id, "approved", "ok")
        auth_queue.approve(
            action_id=action_id,
            approver_id="approver-1",
            signed_decision=signed,
        )

        assert signed.nonce in auth_queue._used_nonces
        assert isinstance(auth_queue._used_nonces[signed.nonce], datetime)

    def test_expired_nonces_evicted(self):
        """Nonces older than max_decision_age_seconds should be evicted."""
        auth_queue, priv, action_id = self._setup_queue(max_decision_age_seconds=60)

        # Manually insert an old nonce (simulating one that was used 120s ago)
        old_nonce = "old-nonce-12345"
        old_time = datetime.now(UTC) - timedelta(seconds=120)
        auth_queue._used_nonces[old_nonce] = old_time

        # Insert a fresh nonce
        fresh_nonce = "fresh-nonce-67890"
        auth_queue._used_nonces[fresh_nonce] = datetime.now(UTC)

        assert old_nonce in auth_queue._used_nonces
        assert fresh_nonce in auth_queue._used_nonces

        # Trigger eviction by submitting a new action and approving it
        pa2 = auth_queue.submit(
            agent_id="agent-x",
            action="read-file",
            reason="another action",
        )
        signed = sign_decision(priv, pa2.action_id, "approved", "ok")
        auth_queue.approve(
            action_id=pa2.action_id,
            approver_id="approver-1",
            signed_decision=signed,
        )

        # Old nonce should be evicted, fresh nonce should remain
        assert old_nonce not in auth_queue._used_nonces
        assert fresh_nonce in auth_queue._used_nonces

    def test_evict_expired_nonces_method_exists(self):
        """The _evict_expired_nonces method should exist on AuthenticatedApprovalQueue."""
        auth_queue, _, _ = self._setup_queue()
        assert hasattr(auth_queue, "_evict_expired_nonces")
        assert callable(auth_queue._evict_expired_nonces)

    def test_eviction_does_not_remove_fresh_nonces(self):
        """Nonces within the max age window should not be evicted."""
        auth_queue, priv, action_id = self._setup_queue(max_decision_age_seconds=300)

        signed = sign_decision(priv, action_id, "approved", "ok")
        auth_queue.approve(
            action_id=action_id,
            approver_id="approver-1",
            signed_decision=signed,
        )

        # Manually call eviction
        auth_queue._evict_expired_nonces()

        # Fresh nonce should still be present
        assert signed.nonce in auth_queue._used_nonces


# ===========================================================================
# RT5-18 (MEDIUM): Monotonic tightening check bypass
# ===========================================================================


class TestMonotonicTighteningBypass:
    """RT5-18: is_tighter_than() must not treat child None as tighter than parent value.

    When the parent has max_actions_per_day set but the child has None,
    the child effectively has unlimited actions, which is less restrictive.
    The tightening check must catch this.
    """

    def test_child_none_rate_limit_with_parent_set_is_not_tighter(self):
        """Child with None max_actions_per_day when parent has a limit is NOT tighter."""
        parent = _make_envelope(
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            operational=OperationalConstraintConfig(max_actions_per_day=None),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent), (
            "Child with unlimited actions (None) should NOT be considered tighter "
            "than parent with max_actions_per_day=100"
        )

    def test_both_none_rate_limit_is_tighter(self):
        """When both parent and child have None max_actions_per_day, child is tighter (equal)."""
        parent = _make_envelope(
            operational=OperationalConstraintConfig(max_actions_per_day=None),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            operational=OperationalConstraintConfig(max_actions_per_day=None),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_set_with_parent_none_is_tighter(self):
        """Child with max_actions_per_day set when parent has None is tighter."""
        parent = _make_envelope(
            operational=OperationalConstraintConfig(max_actions_per_day=None),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            operational=OperationalConstraintConfig(max_actions_per_day=50),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_lower_rate_limit_is_tighter(self):
        """Child with lower max_actions_per_day is tighter (existing behavior preserved)."""
        parent = _make_envelope(
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            operational=OperationalConstraintConfig(max_actions_per_day=50),
        )
        child = ConstraintEnvelope(config=child_config)
        assert child.is_tighter_than(parent)

    def test_child_higher_rate_limit_not_tighter(self):
        """Child with higher max_actions_per_day is NOT tighter (existing behavior preserved)."""
        parent = _make_envelope(
            operational=OperationalConstraintConfig(max_actions_per_day=50),
        )
        child_config = ConstraintEnvelopeConfig(
            id="child",
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        child = ConstraintEnvelope(config=child_config)
        assert not child.is_tighter_than(parent)
