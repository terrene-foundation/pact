# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""M23 Security Hardening — tests for task 2310.

Tests audit chain EATP completeness — ensuring all required fields are present.
"""

from __future__ import annotations

from pact_platform.build.config.schema import VerificationLevel
from pact_platform.trust.audit.anchor import AuditAnchor, AuditChain


class TestAuditEATPCompleteness:
    """Audit records must include all EATP-required fields."""

    def test_anchor_has_delegation_chain_ref(self):
        """AuditAnchor should have a delegation_chain_ref field."""
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
            delegation_chain_ref="del-chain-abc",
        )
        assert anchor.delegation_chain_ref == "del-chain-abc"

    def test_anchor_delegation_chain_ref_defaults_to_none(self):
        """delegation_chain_ref should default to None."""
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert anchor.delegation_chain_ref is None

    def test_anchor_has_constraint_envelope_ref(self):
        """AuditAnchor should have a constraint_envelope_ref field."""
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
            constraint_envelope_ref="env-123",
        )
        assert anchor.constraint_envelope_ref == "env-123"

    def test_anchor_constraint_envelope_ref_defaults_to_none(self):
        """constraint_envelope_ref should default to None."""
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert anchor.constraint_envelope_ref is None

    def test_anchor_has_verification_reason(self):
        """AuditAnchor should have a verification_reason field."""
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.FLAGGED,
            verification_reason="Near budget boundary",
        )
        assert anchor.verification_reason == "Near budget boundary"

    def test_anchor_verification_reason_defaults_to_empty(self):
        """verification_reason should default to empty string."""
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert anchor.verification_reason == ""

    def test_anchor_has_agent_trust_posture(self):
        """AuditAnchor should have an agent_trust_posture field."""
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
            agent_trust_posture="supervised",
        )
        assert anchor.agent_trust_posture == "supervised"

    def test_anchor_agent_trust_posture_defaults_to_none(self):
        """agent_trust_posture should default to None."""
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert anchor.agent_trust_posture is None

    def test_anchor_timestamp_has_timezone(self):
        """AuditAnchor timestamp should always include timezone info."""
        anchor = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert anchor.timestamp.tzinfo is not None

    def test_eatp_fields_included_in_hash(self):
        """EATP fields should be included in the content hash computation."""
        anchor1 = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
            delegation_chain_ref="del-chain-abc",
            constraint_envelope_ref="env-123",
            verification_reason="test reason",
            agent_trust_posture="supervised",
        )
        anchor1.seal()

        anchor2 = AuditAnchor(
            anchor_id="test-0",
            sequence=0,
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
            delegation_chain_ref="del-chain-xyz",  # different
            constraint_envelope_ref="env-123",
            verification_reason="test reason",
            agent_trust_posture="supervised",
        )
        anchor2.seal()

        # Different delegation_chain_ref should produce different hashes
        assert anchor1.content_hash != anchor2.content_hash

    def test_chain_append_accepts_eatp_fields(self):
        """AuditChain.append should accept EATP fields."""
        chain = AuditChain(chain_id="test")
        anchor = chain.append(
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
            delegation_chain_ref="del-abc",
            constraint_envelope_ref="env-123",
            verification_reason="auto approved by gradient",
            agent_trust_posture="supervised",
        )
        assert anchor.delegation_chain_ref == "del-abc"
        assert anchor.constraint_envelope_ref == "env-123"
        assert anchor.verification_reason == "auto approved by gradient"
        assert anchor.agent_trust_posture == "supervised"

    def test_existing_anchors_still_work_without_new_fields(self):
        """Existing anchors without new fields should still be valid."""
        chain = AuditChain(chain_id="test")
        anchor = chain.append(
            agent_id="agent-1",
            action="read_data",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert anchor.is_sealed
        assert anchor.verify_integrity()
        assert anchor.delegation_chain_ref is None
        assert anchor.constraint_envelope_ref is None
        assert anchor.verification_reason == ""
        assert anchor.agent_trust_posture is None
