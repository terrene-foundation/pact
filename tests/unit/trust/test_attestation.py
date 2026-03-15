# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for capability attestation model."""

from care_platform.trust.attestation import CapabilityAttestation


class TestCapabilityAttestation:
    def test_create_attestation(self):
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read", "write"],
            issuer_id="root",
        )
        assert att.is_valid
        assert att.has_capability("read")
        assert not att.has_capability("delete")

    def test_revoke(self):
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="root",
        )
        att.revoke("Security concern")
        assert not att.is_valid
        assert att.revoked
        assert att.revocation_reason == "Security concern"

    def test_content_hash_stable(self):
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="root",
        )
        assert att.content_hash() == att.content_hash()

    def test_default_expiry_90_days(self):
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read"],
            issuer_id="root",
        )
        delta = att.expires_at - att.issued_at
        assert delta.days == 90

    def test_consistency_check_pass(self):
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read", "write"],
            issuer_id="root",
        )
        is_consistent, drift = att.verify_consistency(["read", "write", "admin"])
        assert is_consistent
        assert len(drift) == 0

    def test_consistency_check_drift(self):
        att = CapabilityAttestation(
            attestation_id="att-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id="env-1",
            capabilities=["read", "write", "delete"],
            issuer_id="root",
        )
        is_consistent, drift = att.verify_consistency(["read", "write"])
        assert not is_consistent
        assert "delete" in drift
