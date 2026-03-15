# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Edge case tests for CARE Platform core models.

Covers boundary conditions, minimal/empty configurations, maximum constraints,
expired attestations, revoked agents, and other adversarial inputs.
"""

from datetime import UTC, datetime, timedelta

import pytest

from care_platform.audit.anchor import AuditAnchor, AuditChain
from care_platform.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    GradientRuleConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.envelope import (
    ConstraintEnvelope,
    EnvelopeEvaluation,
    EvaluationResult,
)
from care_platform.constraint.gradient import (
    GradientEngine,
    VerificationThoroughness,
)
from care_platform.trust.attestation import CapabilityAttestation
from care_platform.trust.posture import (
    NEVER_DELEGATED_ACTIONS,
    PostureEvidence,
    TrustPosture,
)
from care_platform.config.schema import TrustPostureLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_envelope(envelope_id: str = "env-minimal") -> ConstraintEnvelope:
    """Envelope with all-default (minimal) configuration."""
    config = ConstraintEnvelopeConfig(id=envelope_id)
    return ConstraintEnvelope(config=config)


def _max_restricted_envelope(envelope_id: str = "env-max") -> ConstraintEnvelope:
    """Envelope with maximum constraints on every dimension.

    Notes on operational constraints:
    - allowed_actions must be non-empty to be enforced (empty list is falsy).
    - blocked_actions uses literal string matching, not glob patterns.
    """
    config = ConstraintEnvelopeConfig(
        id=envelope_id,
        description="Maximum restriction",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=["noop"],  # only "noop" allowed; everything else denied
            blocked_actions=["read", "write", "delete", "send", "admin"],
            max_actions_per_day=1,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="12:00",
            active_hours_end="12:01",  # 1-minute window
        ),
        data_access=DataAccessConstraintConfig(
            blocked_data_types=["pii", "financial_records", "health", "credentials"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )
    return ConstraintEnvelope(config=config)


# ===========================================================================
# 1. Minimal / Empty Configuration Edge Cases
# ===========================================================================


class TestMinimalConfiguration:
    """Edge cases for envelopes, engines, and chains with minimal config."""

    def test_minimal_envelope_allows_any_action(self):
        """Default envelope has no restrictions — everything should be allowed."""
        env = _minimal_envelope()
        result = env.evaluate_action("anything", "agent-1")
        # Financial: max_spend_usd=0, spend_amount=0 -> allowed (0 <= 0)
        # Operational: no allowed_actions list, no blocked_actions -> allowed
        # Temporal: no active hours -> allowed
        # Data access: no blocked types -> allowed
        # Communication: internal_only=True but is_external defaults False -> allowed
        assert result.is_allowed
        assert len(result.dimensions) == 5

    def test_minimal_envelope_still_blocks_external(self):
        """Default CommunicationConstraintConfig has internal_only=True."""
        env = _minimal_envelope()
        result = env.evaluate_action("send", "agent-1", is_external=True)
        assert not result.is_allowed
        comm_dim = next(d for d in result.dimensions if d.dimension == "communication")
        assert comm_dim.result == EvaluationResult.DENIED

    def test_minimal_envelope_financial_zero_budget(self):
        """With max_spend_usd=0.0, any nonzero spend is denied."""
        env = _minimal_envelope()
        result = env.evaluate_action("buy", "agent-1", spend_amount=0.01)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.DENIED

    def test_minimal_envelope_zero_spend_allowed(self):
        """Zero spend with zero budget is allowed."""
        env = _minimal_envelope()
        result = env.evaluate_action("read", "agent-1", spend_amount=0.0)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.ALLOWED

    def test_gradient_engine_no_rules_uses_default(self):
        """Engine with no rules returns the configured default level."""
        config = VerificationGradientConfig(rules=[], default_level=VerificationLevel.HELD)
        engine = GradientEngine(config)
        result = engine.classify("any_action", "agent-1")
        assert result.level == VerificationLevel.HELD
        assert result.matched_rule is None
        assert "default" in result.reason.lower()

    def test_empty_audit_chain_verifies(self):
        """An empty chain should verify as valid (no anchors = no errors)."""
        chain = AuditChain(chain_id="empty-chain")
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid
        assert len(errors) == 0
        assert chain.length == 0
        assert chain.latest is None

    def test_empty_capabilities_attestation(self):
        """An attestation with no capabilities is valid but has_capability returns False."""
        att = CapabilityAttestation(
            attestation_id="att-empty",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=[],
            issuer_id="root",
        )
        assert att.is_valid
        assert not att.has_capability("anything")

    def test_empty_data_paths_always_allowed(self):
        """No data paths checked means data access is allowed even with blocked types."""
        config = ConstraintEnvelopeConfig(
            id="env-data-edge",
            data_access=DataAccessConstraintConfig(
                blocked_data_types=["pii", "credentials"],
            ),
        )
        env = ConstraintEnvelope(config=config)
        result = env.evaluate_action("read", "agent-1", data_paths=[])
        data_dim = next(d for d in result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.ALLOWED


# ===========================================================================
# 2. Maximum Constraint Edge Cases
# ===========================================================================


class TestMaximumConstraints:
    """Edge cases for envelopes with the tightest possible constraints."""

    def test_max_restricted_blocks_any_action(self):
        """An envelope with maximum restrictions should deny almost everything."""
        env = _max_restricted_envelope()
        # "read" is in blocked_actions and not "noop" (the only allowed action)
        narrow_window = datetime(2026, 3, 11, 12, 0, tzinfo=UTC)
        result = env.evaluate_action(
            "read",
            "agent-1",
            current_time=narrow_window,
        )
        assert not result.is_allowed

    def test_max_restricted_denies_on_multiple_dimensions(self):
        """Multiple dimensions should show denied status simultaneously."""
        env = _max_restricted_envelope()
        off_hours = datetime(2026, 3, 11, 8, 0, tzinfo=UTC)
        result = env.evaluate_action(
            "read",
            "agent-1",
            spend_amount=1.0,
            current_action_count=5,
            current_time=off_hours,
            data_paths=["users/pii/records"],
            is_external=True,
        )
        assert not result.is_allowed
        denied_dims = [d for d in result.dimensions if d.result == EvaluationResult.DENIED]
        # Should have denials from financial, operational, temporal, data_access, communication
        assert len(denied_dims) >= 4  # at least financial, operational, temporal, communication

    def test_zero_max_spend_denies_any_positive_amount(self):
        """With max_spend_usd=0.0, even the smallest positive spend is denied."""
        env = _max_restricted_envelope()
        result = env.evaluate_action("action", "agent-1", spend_amount=0.001)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.DENIED

    def test_one_action_per_day_limit(self):
        """Rate limit of 1 per day: first action at count=0 allowed, second denied."""
        config = ConstraintEnvelopeConfig(
            id="env-rate-1",
            operational=OperationalConstraintConfig(max_actions_per_day=1),
        )
        env = ConstraintEnvelope(config=config)

        # First action (count=0) is allowed
        result_first = env.evaluate_action("read", "agent-1", current_action_count=0)
        op_dim_first = next(d for d in result_first.dimensions if d.dimension == "operational")
        assert op_dim_first.result == EvaluationResult.ALLOWED

        # Second action (count=1) is denied
        result_second = env.evaluate_action("read", "agent-1", current_action_count=1)
        op_dim_second = next(d for d in result_second.dimensions if d.dimension == "operational")
        assert op_dim_second.result == EvaluationResult.DENIED


# ===========================================================================
# 3. Boundary Conditions — Rate Limits at Exact Thresholds
# ===========================================================================


class TestBoundaryConditions:
    """Test behavior at exact boundary points (80% threshold, exact limits)."""

    def test_rate_limit_exactly_at_80_percent(self):
        """At exactly 80% utilization: 80/100 = 0.8, this hits the > 0.8 check."""
        config = ConstraintEnvelopeConfig(
            id="env-boundary",
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        env = ConstraintEnvelope(config=config)

        # At exactly 80 of 100 actions: utilization = 0.80, NOT > 0.8 -> ALLOWED
        result = env.evaluate_action("read", "agent-1", current_action_count=80)
        op_dim = next(d for d in result.dimensions if d.dimension == "operational")
        assert op_dim.result == EvaluationResult.ALLOWED
        assert op_dim.utilization == 0.80

    def test_rate_limit_one_above_80_percent(self):
        """At 81/100 = 0.81, this exceeds > 0.8 -> NEAR_BOUNDARY."""
        config = ConstraintEnvelopeConfig(
            id="env-boundary",
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        env = ConstraintEnvelope(config=config)

        result = env.evaluate_action("read", "agent-1", current_action_count=81)
        op_dim = next(d for d in result.dimensions if d.dimension == "operational")
        assert op_dim.result == EvaluationResult.NEAR_BOUNDARY
        assert op_dim.utilization == 0.81

    def test_rate_limit_at_exact_max(self):
        """At exactly max_actions_per_day (100/100): denied."""
        config = ConstraintEnvelopeConfig(
            id="env-boundary",
            operational=OperationalConstraintConfig(max_actions_per_day=100),
        )
        env = ConstraintEnvelope(config=config)

        result = env.evaluate_action("read", "agent-1", current_action_count=100)
        op_dim = next(d for d in result.dimensions if d.dimension == "operational")
        assert op_dim.result == EvaluationResult.DENIED

    def test_financial_exactly_at_80_percent(self):
        """Spend exactly at 80% of budget: 80/100 = 0.80, NOT > 0.8 -> ALLOWED."""
        config = ConstraintEnvelopeConfig(
            id="env-fin-boundary",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        env = ConstraintEnvelope(config=config)

        result = env.evaluate_action("buy", "agent-1", spend_amount=80.0)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.ALLOWED
        assert fin_dim.utilization == 0.80

    def test_financial_just_above_80_percent(self):
        """Spend at 80.01/100 -> near boundary."""
        config = ConstraintEnvelopeConfig(
            id="env-fin-boundary",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        env = ConstraintEnvelope(config=config)

        result = env.evaluate_action("buy", "agent-1", spend_amount=80.01)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.NEAR_BOUNDARY

    def test_financial_exactly_at_max(self):
        """Spend exactly at max budget is not denied (not > max)."""
        config = ConstraintEnvelopeConfig(
            id="env-fin-boundary",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        env = ConstraintEnvelope(config=config)

        result = env.evaluate_action("buy", "agent-1", spend_amount=100.0)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        # spend_amount (100.0) is NOT > max_spend_usd (100.0), so not denied
        # But utilization is 1.0 which IS > 0.8, so NEAR_BOUNDARY
        assert fin_dim.result == EvaluationResult.NEAR_BOUNDARY
        assert fin_dim.utilization == 1.0

    def test_financial_one_cent_over_max(self):
        """Spend $100.01 with $100 budget is denied."""
        config = ConstraintEnvelopeConfig(
            id="env-fin-boundary",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        env = ConstraintEnvelope(config=config)

        result = env.evaluate_action("buy", "agent-1", spend_amount=100.01)
        fin_dim = next(d for d in result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.DENIED

    def test_temporal_at_exact_start_of_window(self):
        """Action at exact start of active hours should be allowed."""
        config = ConstraintEnvelopeConfig(
            id="env-temporal-boundary",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        env = ConstraintEnvelope(config=config)

        start_time = datetime(2026, 3, 11, 9, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=start_time)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED

    def test_temporal_at_exact_end_of_window(self):
        """Action at exact end of active hours should be allowed (inclusive)."""
        config = ConstraintEnvelopeConfig(
            id="env-temporal-boundary",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        env = ConstraintEnvelope(config=config)

        end_time = datetime(2026, 3, 11, 17, 0, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=end_time)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.ALLOWED

    def test_temporal_one_minute_after_window(self):
        """Action one minute after end of active hours should be denied."""
        config = ConstraintEnvelopeConfig(
            id="env-temporal-boundary",
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
        )
        env = ConstraintEnvelope(config=config)

        after_end = datetime(2026, 3, 11, 17, 1, tzinfo=UTC)
        result = env.evaluate_action("read", "agent-1", current_time=after_end)
        temp_dim = next(d for d in result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED


# ===========================================================================
# 4. Expired Attestation Edge Cases
# ===========================================================================


class TestExpiredAttestations:
    """Edge cases around attestation expiry and validity."""

    def test_attestation_expired_just_now(self):
        """An attestation that expired moments ago should be invalid."""
        past = datetime.now(UTC) - timedelta(days=91)
        att = CapabilityAttestation(
            attestation_id="att-expired",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="root",
            issued_at=past,
            # expires_at will be auto-set to past + 90 days = 1 day ago
        )
        assert att.is_expired
        assert not att.is_valid

    def test_attestation_expires_exactly_at_90_days(self):
        """Default expiry is issued_at + 90 days."""
        att = CapabilityAttestation(
            attestation_id="att-90",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="root",
        )
        delta = att.expires_at - att.issued_at
        assert delta.days == 90

    def test_attestation_custom_short_expiry(self):
        """Attestation with 1-second expiry becomes invalid quickly."""
        now = datetime.now(UTC)
        att = CapabilityAttestation(
            attestation_id="att-short",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="root",
            issued_at=now,
            expires_at=now - timedelta(seconds=1),  # already expired
        )
        assert att.is_expired
        assert not att.is_valid

    def test_envelope_expired_check(self):
        """An envelope that has passed its expires_at should report is_expired."""
        config = ConstraintEnvelopeConfig(id="env-expired")
        past = datetime.now(UTC) - timedelta(days=100)
        env = ConstraintEnvelope(
            config=config,
            created_at=past,
            expires_at=past + timedelta(days=90),  # expired 10 days ago
        )
        assert env.is_expired

    def test_envelope_not_yet_expired(self):
        """An envelope created just now should not be expired."""
        env = ConstraintEnvelope(config=ConstraintEnvelopeConfig(id="env-fresh"))
        assert not env.is_expired


# ===========================================================================
# 5. Revoked Agent Edge Cases
# ===========================================================================


class TestRevokedAgentWithAttestations:
    """Tests for agents whose attestations have been revoked."""

    def test_revoked_attestation_has_timestamp(self):
        """Revocation records the time it happened."""
        att = CapabilityAttestation(
            attestation_id="att-rev",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read", "write"],
            issuer_id="root",
        )
        assert att.revoked_at is None
        att.revoke("Compromised credentials")
        assert att.revoked_at is not None
        assert att.revoked_at <= datetime.now(UTC)

    def test_revoked_attestation_still_has_capabilities_listed(self):
        """Revocation flags attestation as invalid; has_capability returns False.

        RT2-10: has_capability() now checks is_valid first, so revoked
        attestations correctly report no valid capabilities. The capabilities
        list itself still exists on the model, but the accessor refuses to
        claim they are available.
        """
        att = CapabilityAttestation(
            attestation_id="att-rev-caps",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read", "write", "delete"],
            issuer_id="root",
        )
        att.revoke("Policy violation")
        assert not att.is_valid
        # RT2-10: has_capability returns False when attestation is invalid
        assert not att.has_capability("read")
        assert not att.has_capability("write")
        # But the capabilities list itself is unchanged
        assert "read" in att.capabilities
        assert "write" in att.capabilities

    def test_revoked_attestation_content_hash_unchanged(self):
        """Content hash is computed from issued fields, not revocation status."""
        att = CapabilityAttestation(
            attestation_id="att-hash",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="root",
        )
        hash_before = att.content_hash()
        att.revoke("Test revocation")
        hash_after = att.content_hash()
        # Content hash uses attestation_id, agent_id, delegation_id, etc.
        # but not revocation status, so hash should not change
        assert hash_before == hash_after

    def test_double_revocation_overwrites_reason(self):
        """Revoking an already-revoked attestation updates the reason and timestamp."""
        att = CapabilityAttestation(
            attestation_id="att-double",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="root",
        )
        att.revoke("First reason")
        first_time = att.revoked_at
        first_reason = att.revocation_reason

        att.revoke("Second reason")
        assert att.revocation_reason == "Second reason"
        assert att.revoked
        # The timestamp may be the same or later
        assert att.revoked_at >= first_time

    def test_consistency_check_on_revoked_attestation(self):
        """Consistency check works independently of revocation status."""
        att = CapabilityAttestation(
            attestation_id="att-cons-rev",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read", "write", "admin"],
            issuer_id="root",
        )
        att.revoke("Test")

        # Consistency check is about capability alignment, not validity
        is_consistent, drift = att.verify_consistency(["read", "write"])
        assert not is_consistent
        assert "admin" in drift


# ===========================================================================
# 6. Audit Chain Edge Cases
# ===========================================================================


class TestAuditChainEdgeCases:
    """Edge cases for audit chain integrity and operations."""

    def test_single_anchor_chain_valid(self):
        """A chain with only the genesis anchor is valid."""
        chain = AuditChain(chain_id="single")
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid
        assert chain.length == 1

    def test_tampered_middle_anchor_detected(self):
        """Tampering with a middle anchor breaks both its hash and the next linkage."""
        chain = AuditChain(chain_id="tamper-mid")
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        chain.append("agent-1", "write", VerificationLevel.FLAGGED)
        chain.append("agent-1", "draft", VerificationLevel.HELD)

        # Tamper with the middle anchor
        chain.anchors[1].action = "tampered_write"

        is_valid, errors = chain.verify_chain_integrity()
        assert not is_valid
        # Should detect hash mismatch on anchor 1 and linkage break on anchor 2
        assert len(errors) >= 1

    def test_genesis_anchor_with_previous_hash_detected(self):
        """A genesis anchor (sequence 0) should not have a previous_hash."""
        chain = AuditChain(chain_id="bad-genesis")
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)

        # Inject a bad previous_hash on genesis
        chain.anchors[0].previous_hash = "some-fake-hash"
        # Re-seal so content_hash matches the tampered data
        chain.anchors[0].seal()

        is_valid, errors = chain.verify_chain_integrity()
        assert not is_valid
        assert any("genesis" in e.lower() for e in errors)

    def test_large_chain_integrity(self):
        """A chain with many anchors should maintain integrity."""
        chain = AuditChain(chain_id="large-chain")
        for i in range(100):
            chain.append(
                agent_id=f"agent-{i % 5}",
                action=f"action_{i}",
                verification_level=VerificationLevel.AUTO_APPROVED,
                result=f"result_{i}",
            )

        assert chain.length == 100
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Large chain failed: {errors}"

    def test_filter_by_level_returns_empty_when_no_match(self):
        """Filtering by a level not present returns an empty list."""
        chain = AuditChain(chain_id="filter-empty")
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        chain.append("agent-1", "write", VerificationLevel.AUTO_APPROVED)
        blocked = chain.filter_by_level(VerificationLevel.BLOCKED)
        assert len(blocked) == 0

    def test_export_with_since_filter(self):
        """Export with a since datetime filters out older anchors."""
        chain = AuditChain(chain_id="export-since")

        # Append 3 anchors (all will have timestamps very close together)
        a0 = chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        a1 = chain.append("agent-1", "write", VerificationLevel.FLAGGED)
        a2 = chain.append("agent-1", "draft", VerificationLevel.HELD)

        # Export since the timestamp of anchor 1 (should include anchors 1 and 2)
        exported = chain.export(since=a1.timestamp)
        # a1 and a2 timestamps >= a1.timestamp
        assert len(exported) >= 2

    def test_anchor_metadata_preserved_in_export(self):
        """Custom metadata attached to anchors survives export."""
        chain = AuditChain(chain_id="meta-export")
        chain.append(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
            metadata={"custom_field": "custom_value", "count": 42},
        )
        exported = chain.export()
        assert len(exported) == 1
        assert exported[0]["metadata"]["custom_field"] == "custom_value"
        assert exported[0]["metadata"]["count"] == 42


# ===========================================================================
# 7. Gradient Engine Edge Cases
# ===========================================================================


class TestGradientEngineEdgeCases:
    """Edge cases for the verification gradient engine."""

    def test_wildcard_rule_matches_everything(self):
        """A '*' pattern matches any action."""
        config = VerificationGradientConfig(
            rules=[
                GradientRuleConfig(
                    pattern="*",
                    level=VerificationLevel.AUTO_APPROVED,
                    reason="Catch-all",
                ),
            ],
            default_level=VerificationLevel.BLOCKED,
        )
        engine = GradientEngine(config)

        result = engine.classify("literally_anything", "agent-1")
        assert result.level == VerificationLevel.AUTO_APPROVED
        assert result.matched_rule == "*"

    def test_empty_action_string(self):
        """An empty action string should still be classified (by default level)."""
        config = VerificationGradientConfig(
            rules=[
                GradientRuleConfig(
                    pattern="read_*",
                    level=VerificationLevel.AUTO_APPROVED,
                ),
            ],
            default_level=VerificationLevel.HELD,
        )
        engine = GradientEngine(config)

        result = engine.classify("", "agent-1")
        assert result.level == VerificationLevel.HELD  # no rule matches ""

    def test_envelope_denied_overrides_wildcard_auto_approve(self):
        """Even if rules say auto-approve everything, envelope denial wins."""
        config = VerificationGradientConfig(
            rules=[
                GradientRuleConfig(pattern="*", level=VerificationLevel.AUTO_APPROVED),
            ],
        )
        engine = GradientEngine(config)

        denied_eval = EnvelopeEvaluation(
            envelope_id="env-1",
            action="dangerous",
            agent_id="agent-1",
            overall_result=EvaluationResult.DENIED,
        )

        result = engine.classify("dangerous", "agent-1", envelope_evaluation=denied_eval)
        assert result.is_blocked
        assert result.envelope_evaluation is not None

    def test_all_thoroughness_levels_produce_results(self):
        """Each thoroughness level produces a valid result."""
        config = VerificationGradientConfig(default_level=VerificationLevel.HELD)
        engine = GradientEngine(config)

        for thoroughness in VerificationThoroughness:
            result = engine.classify("action", "agent-1", thoroughness=thoroughness)
            assert result.thoroughness == thoroughness
            assert result.duration_ms >= 0


# ===========================================================================
# 8. Trust Posture Edge Cases
# ===========================================================================


class TestPostureEdgeCases:
    """Edge cases for trust posture transitions."""

    def test_pseudo_agent_can_upgrade_to_supervised(self):
        """PSEUDO_AGENT can upgrade to SUPERVISED with sufficient evidence (RT-25 fix)."""
        posture = TrustPosture(
            agent_id="agent-1",
            current_level=TrustPostureLevel.PSEUDO_AGENT,
        )
        evidence = PostureEvidence(
            successful_operations=1000,
            total_operations=1000,
            days_at_current_posture=365,
            shadow_enforcer_pass_rate=1.0,
        )
        can, reason = posture.can_upgrade(evidence)
        # PSEUDO_AGENT -> SUPERVISED: upgrade requirements now defined (RT-25)
        assert can

    def test_downgrade_to_pseudo_agent(self):
        """Downgrading to PSEUDO_AGENT (the lowest level) works."""
        posture = TrustPosture(
            agent_id="agent-1",
            current_level=TrustPostureLevel.SHARED_PLANNING,
        )
        posture.downgrade("Critical incident", to_level=TrustPostureLevel.PSEUDO_AGENT)
        assert posture.current_level == TrustPostureLevel.PSEUDO_AGENT

    def test_upgrade_requires_exactly_min_operations(self):
        """Exactly meeting min_operations is sufficient for upgrade."""
        posture = TrustPosture(agent_id="agent-1")
        # SUPERVISED -> SHARED_PLANNING requires min_operations=100
        evidence = PostureEvidence(
            successful_operations=100,
            total_operations=100,
            days_at_current_posture=90,
            shadow_enforcer_pass_rate=0.95,
            incidents=0,
        )
        can, reason = posture.can_upgrade(evidence)
        assert can

    def test_upgrade_fails_at_one_below_min_operations(self):
        """One operation short of the minimum blocks upgrade."""
        posture = TrustPosture(agent_id="agent-1")
        evidence = PostureEvidence(
            successful_operations=99,
            total_operations=99,
            days_at_current_posture=90,
            shadow_enforcer_pass_rate=0.95,
            incidents=0,
        )
        can, reason = posture.can_upgrade(evidence)
        assert not can
        assert "100" in reason  # should mention the required number

    def test_every_never_delegated_action_detected(self):
        """All actions in NEVER_DELEGATED_ACTIONS should be flagged by is_action_always_held."""
        posture = TrustPosture(agent_id="agent-1")
        for action in NEVER_DELEGATED_ACTIONS:
            assert posture.is_action_always_held(
                action
            ), f"Action '{action}' should be never-delegated but was not detected"

    def test_posture_history_accumulates(self):
        """Multiple upgrades and downgrades accumulate in history."""
        posture = TrustPosture(agent_id="agent-1")

        # Upgrade to shared_planning
        evidence = PostureEvidence(
            successful_operations=100,
            total_operations=100,
            days_at_current_posture=90,
            shadow_enforcer_pass_rate=0.95,
        )
        posture.upgrade(evidence, "Earned trust")
        assert posture.current_level == TrustPostureLevel.SHARED_PLANNING

        # Downgrade back
        posture.downgrade("Incident occurred")
        assert posture.current_level == TrustPostureLevel.SUPERVISED

        # History has both events
        assert len(posture.history) == 2
        assert posture.history[0].change_type.value == 1  # UPGRADE
        assert posture.history[1].change_type.value == -1  # DOWNGRADE

    def test_upgrade_raises_on_insufficient_evidence(self):
        """Calling upgrade() with insufficient evidence raises ValueError."""
        posture = TrustPosture(agent_id="agent-1")
        evidence = PostureEvidence()
        with pytest.raises(ValueError, match="Cannot upgrade"):
            posture.upgrade(evidence)


# ===========================================================================
# 9. Envelope Content Hash Edge Cases
# ===========================================================================


class TestEnvelopeHashEdgeCases:
    """Edge cases for envelope content hashing and versioning."""

    def test_different_ids_same_config_different_hashes(self):
        """Content hash excludes the ID, so two envelopes with same config
        but different IDs should have the SAME content hash."""
        env1 = ConstraintEnvelope(config=ConstraintEnvelopeConfig(id="env-a"))
        env2 = ConstraintEnvelope(config=ConstraintEnvelopeConfig(id="env-b"))
        # Content hash excludes ID per the implementation
        assert env1.content_hash() == env2.content_hash()

    def test_different_financial_limits_different_hashes(self):
        """Changing any config field should produce a different content hash."""
        env1 = ConstraintEnvelope(
            config=ConstraintEnvelopeConfig(
                id="env-x",
                financial=FinancialConstraintConfig(max_spend_usd=100.0),
            )
        )
        env2 = ConstraintEnvelope(
            config=ConstraintEnvelopeConfig(
                id="env-x",
                financial=FinancialConstraintConfig(max_spend_usd=200.0),
            )
        )
        assert env1.content_hash() != env2.content_hash()

    def test_envelope_version_defaults_to_one(self):
        """Default envelope version is 1."""
        env = ConstraintEnvelope(config=ConstraintEnvelopeConfig(id="env-v"))
        assert env.version == 1

    def test_envelope_id_matches_config_id(self):
        """The envelope's id property delegates to config.id."""
        env = ConstraintEnvelope(config=ConstraintEnvelopeConfig(id="my-envelope"))
        assert env.id == "my-envelope"
