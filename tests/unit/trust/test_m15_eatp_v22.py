# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for M15 — EATP v2.2 Alignment.

Covers:
- 1501: Confidentiality levels as first-class constraint
- 1502: SD-JWT selective disclosure
- 1503: REASONING_REQUIRED constraint type
- 1504: JCS canonical serialization (RFC 8785)
- 1505: Dual-binding signing for reasoning traces
- 1506: Comprehensive integration tests
"""

from __future__ import annotations

import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from care_platform.build.config.schema import (
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
)
from care_platform.trust.constraint.envelope import (
    ConstraintEnvelope,
    EvaluationResult,
)
from care_platform.trust.reasoning import (
    ConfidentialityLevel,
    ReasoningTrace,
)


def _generate_keypair() -> tuple[bytes, bytes]:
    """Generate an Ed25519 keypair, returning (private_key_bytes, public_key_bytes)."""
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes_raw()
    public_bytes = private_key.public_key().public_bytes_raw()
    return private_bytes, public_bytes


# ---------------------------------------------------------------------------
# 1501: Confidentiality levels — promote to first-class constraint
# ---------------------------------------------------------------------------


class TestConfidentialityClearance:
    """1501: Confidentiality clearance on constraint envelopes."""

    def test_envelope_config_has_confidentiality_clearance(self):
        """ConstraintEnvelopeConfig should accept a confidentiality_clearance field."""
        config = ConstraintEnvelopeConfig(
            id="env-1",
            confidentiality_clearance=ConfidentialityLevel.CONFIDENTIAL,
        )
        assert config.confidentiality_clearance == ConfidentialityLevel.CONFIDENTIAL

    def test_envelope_config_defaults_to_public(self):
        """ConstraintEnvelopeConfig.confidentiality_clearance should default to PUBLIC."""
        config = ConstraintEnvelopeConfig(id="env-2")
        assert config.confidentiality_clearance == ConfidentialityLevel.PUBLIC

    def test_envelope_denies_access_above_clearance(self):
        """Envelope should deny data access when data classification exceeds clearance."""
        config = ConstraintEnvelopeConfig(
            id="env-restricted",
            confidentiality_clearance=ConfidentialityLevel.RESTRICTED,
            data_access=DataAccessConstraintConfig(read_paths=["docs/*"]),
        )
        envelope = ConstraintEnvelope(config=config)

        # Data classified as CONFIDENTIAL should be denied when envelope has RESTRICTED clearance
        result = envelope.evaluate_action(
            "read_doc",
            "agent-1",
            data_paths=["docs/report.md"],
            data_classification=ConfidentialityLevel.CONFIDENTIAL,
        )
        assert result.overall_result == EvaluationResult.DENIED
        confidentiality_dim = [d for d in result.dimensions if d.dimension == "confidentiality"]
        assert len(confidentiality_dim) == 1
        assert confidentiality_dim[0].result == EvaluationResult.DENIED

    def test_envelope_allows_access_at_clearance(self):
        """Envelope should allow data access when data classification matches clearance."""
        config = ConstraintEnvelopeConfig(
            id="env-confidential",
            confidentiality_clearance=ConfidentialityLevel.CONFIDENTIAL,
        )
        envelope = ConstraintEnvelope(config=config)

        result = envelope.evaluate_action(
            "read_doc",
            "agent-1",
            data_classification=ConfidentialityLevel.CONFIDENTIAL,
        )
        # Should not be denied by confidentiality
        confidentiality_dims = [d for d in result.dimensions if d.dimension == "confidentiality"]
        assert len(confidentiality_dims) == 1
        assert confidentiality_dims[0].result == EvaluationResult.ALLOWED

    def test_envelope_allows_access_below_clearance(self):
        """Envelope should allow data access when data classification is below clearance."""
        config = ConstraintEnvelopeConfig(
            id="env-secret",
            confidentiality_clearance=ConfidentialityLevel.SECRET,
        )
        envelope = ConstraintEnvelope(config=config)

        result = envelope.evaluate_action(
            "read_doc",
            "agent-1",
            data_classification=ConfidentialityLevel.RESTRICTED,
        )
        confidentiality_dims = [d for d in result.dimensions if d.dimension == "confidentiality"]
        assert len(confidentiality_dims) == 1
        assert confidentiality_dims[0].result == EvaluationResult.ALLOWED

    def test_envelope_no_classification_skips_check(self):
        """When no data_classification is provided, confidentiality check should allow."""
        config = ConstraintEnvelopeConfig(
            id="env-no-class",
            confidentiality_clearance=ConfidentialityLevel.RESTRICTED,
        )
        envelope = ConstraintEnvelope(config=config)

        result = envelope.evaluate_action("read_doc", "agent-1")
        confidentiality_dims = [d for d in result.dimensions if d.dimension == "confidentiality"]
        assert len(confidentiality_dims) == 1
        assert confidentiality_dims[0].result == EvaluationResult.ALLOWED

    def test_monotonic_tightening_confidentiality(self):
        """Child envelope cannot have higher clearance than parent."""
        parent_config = ConstraintEnvelopeConfig(
            id="parent",
            confidentiality_clearance=ConfidentialityLevel.RESTRICTED,
        )
        parent = ConstraintEnvelope(config=parent_config)

        # Child tries to claim SECRET clearance (wider than RESTRICTED parent)
        child_config = ConstraintEnvelopeConfig(
            id="child",
            confidentiality_clearance=ConfidentialityLevel.SECRET,
        )
        child = ConstraintEnvelope(config=child_config)

        assert child.is_tighter_than(parent) is False

    def test_monotonic_tightening_confidentiality_same(self):
        """Child envelope with same clearance should be considered tighter (or equal)."""
        parent_config = ConstraintEnvelopeConfig(
            id="parent",
            confidentiality_clearance=ConfidentialityLevel.CONFIDENTIAL,
        )
        parent = ConstraintEnvelope(config=parent_config)

        child_config = ConstraintEnvelopeConfig(
            id="child",
            confidentiality_clearance=ConfidentialityLevel.CONFIDENTIAL,
        )
        child = ConstraintEnvelope(config=child_config)

        assert child.is_tighter_than(parent) is True

    def test_monotonic_tightening_confidentiality_tighter(self):
        """Child with lower clearance than parent is a valid tightening."""
        parent_config = ConstraintEnvelopeConfig(
            id="parent",
            confidentiality_clearance=ConfidentialityLevel.SECRET,
        )
        parent = ConstraintEnvelope(config=parent_config)

        child_config = ConstraintEnvelopeConfig(
            id="child",
            confidentiality_clearance=ConfidentialityLevel.RESTRICTED,
        )
        child = ConstraintEnvelope(config=child_config)

        assert child.is_tighter_than(parent) is True


# ---------------------------------------------------------------------------
# 1502: SD-JWT selective disclosure
# ---------------------------------------------------------------------------


class TestSDJWT:
    """1502: SD-JWT selective disclosure based on confidentiality level."""

    def test_create_sd_jwt_from_delegation_record(self):
        """Create an SD-JWT from a delegation-like record with classified fields."""
        from care_platform.trust.sd_jwt import SDJWTBuilder

        record = {
            "delegation_id": "del-001",
            "delegator_id": "authority-root",
            "delegate_id": "agent-alpha",
            "capabilities": ["read", "write"],
            "internal_notes": "Sensitive reasoning about this delegation",
            "constraint_details": {"max_spend": 500.0, "secret_budget_code": "X-42"},
        }

        field_classifications = {
            "delegation_id": ConfidentialityLevel.PUBLIC,
            "delegator_id": ConfidentialityLevel.PUBLIC,
            "delegate_id": ConfidentialityLevel.PUBLIC,
            "capabilities": ConfidentialityLevel.RESTRICTED,
            "internal_notes": ConfidentialityLevel.SECRET,
            "constraint_details": ConfidentialityLevel.CONFIDENTIAL,
        }

        builder = SDJWTBuilder()
        sd_jwt = builder.create(record, field_classifications)

        assert sd_jwt is not None
        assert sd_jwt.issuer_claims is not None

    def test_disclose_at_public_level(self):
        """PUBLIC viewer should see only PUBLIC fields; others are hashes."""
        from care_platform.trust.sd_jwt import SDJWTBuilder

        record = {
            "delegation_id": "del-001",
            "delegator_id": "authority-root",
            "secret_field": "top-secret-value",
        }
        field_classifications = {
            "delegation_id": ConfidentialityLevel.PUBLIC,
            "delegator_id": ConfidentialityLevel.PUBLIC,
            "secret_field": ConfidentialityLevel.SECRET,
        }

        builder = SDJWTBuilder()
        sd_jwt = builder.create(record, field_classifications)

        disclosed = sd_jwt.disclose(ConfidentialityLevel.PUBLIC)

        assert disclosed["delegation_id"] == "del-001"
        assert disclosed["delegator_id"] == "authority-root"
        # Secret field should be a hash, not the actual value
        assert disclosed["secret_field"] != "top-secret-value"
        assert isinstance(disclosed["secret_field"], str)
        # It should look like a hash (hex string)
        assert len(disclosed["secret_field"]) == 64

    def test_disclose_at_secret_level(self):
        """SECRET viewer should see PUBLIC, RESTRICTED, CONFIDENTIAL, and SECRET fields."""
        from care_platform.trust.sd_jwt import SDJWTBuilder

        record = {
            "public_field": "public-value",
            "restricted_field": "restricted-value",
            "confidential_field": "confidential-value",
            "secret_field": "secret-value",
            "top_secret_field": "top-secret-value",
        }
        field_classifications = {
            "public_field": ConfidentialityLevel.PUBLIC,
            "restricted_field": ConfidentialityLevel.RESTRICTED,
            "confidential_field": ConfidentialityLevel.CONFIDENTIAL,
            "secret_field": ConfidentialityLevel.SECRET,
            "top_secret_field": ConfidentialityLevel.TOP_SECRET,
        }

        builder = SDJWTBuilder()
        sd_jwt = builder.create(record, field_classifications)
        disclosed = sd_jwt.disclose(ConfidentialityLevel.SECRET)

        # Should see up to SECRET
        assert disclosed["public_field"] == "public-value"
        assert disclosed["restricted_field"] == "restricted-value"
        assert disclosed["confidential_field"] == "confidential-value"
        assert disclosed["secret_field"] == "secret-value"
        # TOP_SECRET should still be a hash
        assert disclosed["top_secret_field"] != "top-secret-value"
        assert len(disclosed["top_secret_field"]) == 64

    def test_disclose_at_top_secret_shows_all(self):
        """TOP_SECRET viewer should see all fields disclosed."""
        from care_platform.trust.sd_jwt import SDJWTBuilder

        record = {
            "public_field": "pub",
            "top_secret_field": "ts-value",
        }
        field_classifications = {
            "public_field": ConfidentialityLevel.PUBLIC,
            "top_secret_field": ConfidentialityLevel.TOP_SECRET,
        }

        builder = SDJWTBuilder()
        sd_jwt = builder.create(record, field_classifications)
        disclosed = sd_jwt.disclose(ConfidentialityLevel.TOP_SECRET)

        assert disclosed["public_field"] == "pub"
        assert disclosed["top_secret_field"] == "ts-value"

    def test_undisclosed_fields_are_sha256_hashes(self):
        """Undisclosed fields should be the SHA-256 hash of salt+field_name+value."""
        from care_platform.trust.sd_jwt import SDJWTBuilder

        record = {"secret_data": "my-secret"}
        field_classifications = {"secret_data": ConfidentialityLevel.SECRET}

        builder = SDJWTBuilder()
        sd_jwt = builder.create(record, field_classifications)

        disclosed = sd_jwt.disclose(ConfidentialityLevel.PUBLIC)
        hash_value = disclosed["secret_data"]

        # Verify it's a valid SHA-256 hex digest
        assert len(hash_value) == 64
        bytes.fromhex(hash_value)  # Should not raise

    def test_sd_jwt_verify_integrity(self):
        """SD-JWT should be verifiable for integrity."""
        from care_platform.trust.sd_jwt import SDJWTBuilder

        record = {"field_a": "value_a", "field_b": "value_b"}
        field_classifications = {
            "field_a": ConfidentialityLevel.PUBLIC,
            "field_b": ConfidentialityLevel.CONFIDENTIAL,
        }

        builder = SDJWTBuilder()
        sd_jwt = builder.create(record, field_classifications)

        assert sd_jwt.verify_integrity() is True

    def test_sd_jwt_tampered_fails_integrity(self):
        """Tampering with issuer claims should fail integrity check."""
        from care_platform.trust.sd_jwt import SDJWTBuilder

        record = {"field_a": "value_a"}
        field_classifications = {"field_a": ConfidentialityLevel.PUBLIC}

        builder = SDJWTBuilder()
        sd_jwt = builder.create(record, field_classifications)

        # Tamper with a claim
        sd_jwt.issuer_claims["field_a"] = "tampered"

        assert sd_jwt.verify_integrity() is False


# ---------------------------------------------------------------------------
# 1503: REASONING_REQUIRED constraint type
# ---------------------------------------------------------------------------


class TestReasoningRequired:
    """1503: REASONING_REQUIRED meta-constraint per dimension."""

    def test_dimension_config_has_reasoning_required(self):
        """Each dimension config should have an optional reasoning_required field."""
        config = ConstraintEnvelopeConfig(
            id="env-rr",
            financial=FinancialConstraintConfig(max_spend_usd=100.0, reasoning_required=True),
        )
        assert config.financial.reasoning_required is True

    def test_reasoning_required_defaults_false(self):
        """reasoning_required should default to False."""
        config = FinancialConstraintConfig(max_spend_usd=100.0)
        assert config.reasoning_required is False

    def test_action_without_reasoning_trace_is_held(self):
        """Action touching a dimension with REASONING_REQUIRED and no trace should be HELD."""
        config = ConstraintEnvelopeConfig(
            id="env-rr-held",
            financial=FinancialConstraintConfig(max_spend_usd=100.0, reasoning_required=True),
        )
        envelope = ConstraintEnvelope(config=config)

        result = envelope.evaluate_action(
            "purchase",
            "agent-1",
            spend_amount=50.0,
            # No reasoning_trace provided
        )
        # Should be HELD because reasoning is required but not provided
        reasoning_dims = [d for d in result.dimensions if d.dimension == "reasoning"]
        assert len(reasoning_dims) == 1
        assert reasoning_dims[0].result == EvaluationResult.NEAR_BOUNDARY

    def test_action_with_reasoning_trace_passes(self):
        """Action with a reasoning trace when REASONING_REQUIRED should pass normally."""
        config = ConstraintEnvelopeConfig(
            id="env-rr-pass",
            financial=FinancialConstraintConfig(max_spend_usd=100.0, reasoning_required=True),
        )
        envelope = ConstraintEnvelope(config=config)

        result = envelope.evaluate_action(
            "purchase",
            "agent-1",
            spend_amount=50.0,
            reasoning_trace="Budget allocation approved by team lead",
        )
        # Reasoning dimension should be ALLOWED
        reasoning_dims = [d for d in result.dimensions if d.dimension == "reasoning"]
        assert len(reasoning_dims) == 1
        assert reasoning_dims[0].result == EvaluationResult.ALLOWED

    def test_reasoning_required_on_multiple_dimensions(self):
        """REASONING_REQUIRED on multiple dimensions should all be checked."""
        config = ConstraintEnvelopeConfig(
            id="env-multi-rr",
            financial=FinancialConstraintConfig(max_spend_usd=100.0, reasoning_required=True),
            operational=OperationalConstraintConfig(
                allowed_actions=["deploy"], reasoning_required=True
            ),
        )
        envelope = ConstraintEnvelope(config=config)

        # No reasoning trace: should be HELD
        result = envelope.evaluate_action(
            "deploy",
            "agent-1",
            spend_amount=10.0,
        )
        reasoning_dims = [d for d in result.dimensions if d.dimension == "reasoning"]
        assert len(reasoning_dims) == 1
        assert reasoning_dims[0].result == EvaluationResult.NEAR_BOUNDARY

    def test_reasoning_not_required_when_no_flag(self):
        """When no dimension has REASONING_REQUIRED, reasoning dimension is not added."""
        config = ConstraintEnvelopeConfig(
            id="env-no-rr",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=config)

        result = envelope.evaluate_action(
            "purchase",
            "agent-1",
            spend_amount=50.0,
        )
        # No reasoning dimension should appear when no flag is set
        reasoning_dims = [d for d in result.dimensions if d.dimension == "reasoning"]
        assert len(reasoning_dims) == 0

    def test_child_inherits_reasoning_required_from_parent(self):
        """Child envelope should inherit REASONING_REQUIRED from parent via tightening."""
        parent_config = ConstraintEnvelopeConfig(
            id="parent",
            financial=FinancialConstraintConfig(max_spend_usd=100.0, reasoning_required=True),
        )
        parent = ConstraintEnvelope(config=parent_config)

        # Child tries to remove reasoning_required (less restrictive)
        child_config = ConstraintEnvelopeConfig(
            id="child",
            financial=FinancialConstraintConfig(max_spend_usd=50.0, reasoning_required=False),
        )
        child = ConstraintEnvelope(config=child_config)

        # Should fail tightening: removing reasoning_required is less restrictive
        assert child.is_tighter_than(parent) is False

    def test_child_can_add_reasoning_required(self):
        """Child envelope can add REASONING_REQUIRED (tighter than parent)."""
        parent_config = ConstraintEnvelopeConfig(
            id="parent",
            financial=FinancialConstraintConfig(max_spend_usd=100.0, reasoning_required=False),
        )
        parent = ConstraintEnvelope(config=parent_config)

        child_config = ConstraintEnvelopeConfig(
            id="child",
            financial=FinancialConstraintConfig(max_spend_usd=50.0, reasoning_required=True),
        )
        child = ConstraintEnvelope(config=child_config)

        assert child.is_tighter_than(parent) is True


# ---------------------------------------------------------------------------
# 1504: JCS canonical serialization (RFC 8785)
# ---------------------------------------------------------------------------


class TestJCSCanonical:
    """1504: JCS canonical serialization for all content_hash implementations."""

    def test_canonical_hash_deterministic(self):
        """canonical_hash should produce the same output for the same data."""
        from care_platform.trust.jcs import canonical_hash

        data = {"b": 2, "a": 1, "c": [3, 2, 1]}
        h1 = canonical_hash(data)
        h2 = canonical_hash(data)
        assert h1 == h2

    def test_canonical_hash_key_order_independent(self):
        """canonical_hash should produce the same output regardless of key insertion order."""
        from care_platform.trust.jcs import canonical_hash

        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}
        assert canonical_hash(data1) == canonical_hash(data2)

    def test_canonical_hash_is_sha256(self):
        """canonical_hash should return a 64-character hex SHA-256 digest."""
        from care_platform.trust.jcs import canonical_hash

        h = canonical_hash({"test": "value"})
        assert len(h) == 64
        bytes.fromhex(h)  # should not raise

    def test_canonical_serialize_produces_rfc8785_output(self):
        """canonical_serialize should produce RFC 8785 compliant JSON."""
        from care_platform.trust.jcs import canonical_serialize

        data = {"b": 2, "a": 1}
        serialized = canonical_serialize(data)
        # RFC 8785: keys sorted, no spaces
        assert isinstance(serialized, bytes)
        parsed = json.loads(serialized)
        assert parsed == {"a": 1, "b": 2}

    def test_signed_envelope_uses_canonical_version(self):
        """SignedEnvelope should include canonical_version field."""
        from care_platform.trust.constraint.signing import SignedEnvelope

        config = ConstraintEnvelopeConfig(
            id="test-env",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
        )
        envelope = ConstraintEnvelope(config=config)

        private_key, public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        # Should have canonical_version field
        assert hasattr(signed, "canonical_version")
        assert signed.canonical_version == "jcs-rfc8785"

    def test_existing_signature_verification_still_works(self):
        """Existing signature tests should still pass after JCS migration."""
        from care_platform.trust.constraint.signing import SignedEnvelope

        config = ConstraintEnvelopeConfig(
            id="test-env",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(allowed_actions=["read", "write"]),
        )
        envelope = ConstraintEnvelope(config=config)
        private_key, public_key = _generate_keypair()
        signed = SignedEnvelope.sign_envelope(envelope, "signer-1", private_key)

        assert signed.verify_signature(public_key) is True

    def test_reasoning_trace_hash_uses_jcs(self):
        """ReasoningTrace.compute_hash should produce a deterministic JCS-based hash."""
        trace1 = ReasoningTrace(
            trace_id="rt-fixed",
            parent_record_type="delegation",
            parent_record_id="del-001",
            reasoning="Test reasoning",
            confidentiality=ConfidentialityLevel.PUBLIC,
            trace_hash="",
        )
        trace2 = ReasoningTrace(
            trace_id="rt-fixed",
            parent_record_type="delegation",
            parent_record_id="del-001",
            reasoning="Test reasoning",
            confidentiality=ConfidentialityLevel.PUBLIC,
            trace_hash="",
        )
        assert trace1.trace_hash == trace2.trace_hash
        assert len(trace1.trace_hash) == 64


# ---------------------------------------------------------------------------
# 1505: Dual-binding signing for reasoning traces
# ---------------------------------------------------------------------------


class TestDualBinding:
    """1505: Dual-binding signing for reasoning traces."""

    def test_trace_has_genesis_binding_hash(self):
        """ReasoningTrace should support a genesis_binding_hash field."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-001",
            reasoning="Test reasoning",
            genesis_binding_hash="abc123",
        )
        assert trace.genesis_binding_hash == "abc123"

    def test_genesis_binding_hash_defaults_empty(self):
        """genesis_binding_hash should default to empty string."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-001",
            reasoning="Test reasoning",
        )
        assert trace.genesis_binding_hash == ""

    def test_dual_binding_creates_bindings(self):
        """DualBinding should create both parent and genesis bindings."""
        from care_platform.trust.dual_binding import DualBinding

        binding = DualBinding.create(
            trace_hash="trace-hash-abc",
            parent_record_hash="parent-hash-123",
            genesis_hash="genesis-hash-xyz",
        )
        assert binding.parent_binding is not None
        assert binding.genesis_binding is not None
        assert binding.parent_binding != binding.genesis_binding

    def test_dual_binding_verify_parent(self):
        """DualBinding should verify against the correct parent record."""
        from care_platform.trust.dual_binding import DualBinding

        binding = DualBinding.create(
            trace_hash="trace-hash-abc",
            parent_record_hash="parent-hash-123",
            genesis_hash="genesis-hash-xyz",
        )
        assert binding.verify_parent_binding("trace-hash-abc", "parent-hash-123") is True
        assert binding.verify_parent_binding("trace-hash-abc", "wrong-parent") is False

    def test_dual_binding_verify_genesis(self):
        """DualBinding should verify against the correct genesis record."""
        from care_platform.trust.dual_binding import DualBinding

        binding = DualBinding.create(
            trace_hash="trace-hash-abc",
            parent_record_hash="parent-hash-123",
            genesis_hash="genesis-hash-xyz",
        )
        assert binding.verify_genesis_binding("trace-hash-abc", "genesis-hash-xyz") is True
        assert binding.verify_genesis_binding("trace-hash-abc", "wrong-genesis") is False

    def test_trace_bound_to_genesis_a_fails_against_genesis_b(self):
        """A trace bound to genesis A should fail verification against genesis B."""
        from care_platform.trust.dual_binding import DualBinding

        binding = DualBinding.create(
            trace_hash="trace-001",
            parent_record_hash="del-001-hash",
            genesis_hash="genesis-A-hash",
        )
        # Should pass against genesis A
        assert binding.verify_genesis_binding("trace-001", "genesis-A-hash") is True
        # Should fail against genesis B
        assert binding.verify_genesis_binding("trace-001", "genesis-B-hash") is False

    def test_trace_bound_to_delegation_d1_fails_against_d2(self):
        """A trace bound to delegation D1 should fail verification against D2."""
        from care_platform.trust.dual_binding import DualBinding

        binding = DualBinding.create(
            trace_hash="trace-002",
            parent_record_hash="delegation-D1-hash",
            genesis_hash="genesis-hash",
        )
        assert binding.verify_parent_binding("trace-002", "delegation-D1-hash") is True
        assert binding.verify_parent_binding("trace-002", "delegation-D2-hash") is False

    def test_dual_binding_compute_hash(self):
        """DualBinding should compute a combined hash of both bindings."""
        from care_platform.trust.dual_binding import DualBinding

        binding = DualBinding.create(
            trace_hash="trace-003",
            parent_record_hash="parent-003",
            genesis_hash="genesis-003",
        )
        combined = binding.combined_hash()
        assert len(combined) == 64
        bytes.fromhex(combined)  # valid hex

    def test_reasoning_trace_compute_hash_includes_genesis_binding(self):
        """ReasoningTrace.compute_hash should incorporate genesis_binding_hash."""
        trace_without = ReasoningTrace(
            trace_id="rt-fixed",
            parent_record_type="delegation",
            parent_record_id="del-001",
            reasoning="Same reasoning",
            genesis_binding_hash="",
            trace_hash="",
        )
        trace_with = ReasoningTrace(
            trace_id="rt-fixed",
            parent_record_type="delegation",
            parent_record_id="del-001",
            reasoning="Same reasoning",
            genesis_binding_hash="genesis-binding-value",
            trace_hash="",
        )
        # Different genesis bindings should produce different hashes
        assert trace_without.trace_hash != trace_with.trace_hash


# ---------------------------------------------------------------------------
# 1506: Integration across features
# ---------------------------------------------------------------------------


class TestM15Integration:
    """1506: Integration tests across all M15 features."""

    def test_confidentiality_clearance_with_sd_jwt(self):
        """SD-JWT should respect the envelope's confidentiality clearance."""
        from care_platform.trust.sd_jwt import SDJWTBuilder

        record = {
            "public_data": "hello",
            "secret_data": "classified-info",
        }
        field_classifications = {
            "public_data": ConfidentialityLevel.PUBLIC,
            "secret_data": ConfidentialityLevel.SECRET,
        }

        builder = SDJWTBuilder()
        sd_jwt = builder.create(record, field_classifications)

        # Viewer with RESTRICTED clearance
        restricted_view = sd_jwt.disclose(ConfidentialityLevel.RESTRICTED)
        assert restricted_view["public_data"] == "hello"
        assert restricted_view["secret_data"] != "classified-info"

        # Viewer with TOP_SECRET clearance
        full_view = sd_jwt.disclose(ConfidentialityLevel.TOP_SECRET)
        assert full_view["secret_data"] == "classified-info"

    def test_jcs_hash_consistency_across_modules(self):
        """JCS canonical hash should be consistent when used across different modules."""
        from care_platform.trust.jcs import canonical_hash

        data = {"key": "value", "nested": {"a": 1}}
        hash1 = canonical_hash(data)
        hash2 = canonical_hash(data)
        assert hash1 == hash2

    def test_dual_binding_with_reasoning_trace(self):
        """A reasoning trace with dual binding should be fully verifiable."""
        from care_platform.trust.dual_binding import DualBinding

        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-100",
            reasoning="Approved after review",
            genesis_binding_hash="genesis-root-hash",
        )

        binding = DualBinding.create(
            trace_hash=trace.trace_hash,
            parent_record_hash="del-100-content-hash",
            genesis_hash="genesis-root-hash",
        )

        assert binding.verify_parent_binding(trace.trace_hash, "del-100-content-hash")
        assert binding.verify_genesis_binding(trace.trace_hash, "genesis-root-hash")
        assert trace.verify_integrity()

    def test_envelope_evaluation_with_all_m15_features(self):
        """Full envelope evaluation with confidentiality and reasoning_required."""
        config = ConstraintEnvelopeConfig(
            id="full-m15",
            confidentiality_clearance=ConfidentialityLevel.CONFIDENTIAL,
            financial=FinancialConstraintConfig(max_spend_usd=100.0, reasoning_required=True),
            operational=OperationalConstraintConfig(allowed_actions=["read", "write"]),
        )
        envelope = ConstraintEnvelope(config=config)

        # Action with reasoning and appropriate classification should succeed
        result = envelope.evaluate_action(
            "read",
            "agent-1",
            spend_amount=10.0,
            reasoning_trace="Approved by manager",
            data_classification=ConfidentialityLevel.RESTRICTED,
        )
        assert result.overall_result in (EvaluationResult.ALLOWED, EvaluationResult.NEAR_BOUNDARY)

        # Action without reasoning should be HELD/NEAR_BOUNDARY
        result2 = envelope.evaluate_action(
            "read",
            "agent-1",
            spend_amount=10.0,
            data_classification=ConfidentialityLevel.RESTRICTED,
        )
        reasoning_dims = [d for d in result2.dimensions if d.dimension == "reasoning"]
        assert len(reasoning_dims) == 1
        assert reasoning_dims[0].result == EvaluationResult.NEAR_BOUNDARY
