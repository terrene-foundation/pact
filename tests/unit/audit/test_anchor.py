# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for audit anchor chain."""

from pact_platform.build.config.schema import VerificationLevel
from pact_platform.trust.audit.anchor import AuditAnchor, AuditChain


class TestAuditAnchor:
    def test_seal_and_verify(self):
        anchor = AuditAnchor(
            anchor_id="a-0",
            sequence=0,
            agent_id="agent-1",
            action="read_metrics",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.seal()
        assert anchor.is_sealed
        assert anchor.verify_integrity()

    def test_tampered_anchor_fails_verification(self):
        anchor = AuditAnchor(
            anchor_id="a-0",
            sequence=0,
            agent_id="agent-1",
            action="read_metrics",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        anchor.seal()
        anchor.action = "delete_everything"  # tamper
        assert not anchor.verify_integrity()

    def test_unsealed_fails_verification(self):
        anchor = AuditAnchor(
            anchor_id="a-0",
            sequence=0,
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        assert not anchor.verify_integrity()


class TestAuditChain:
    def test_append_creates_sealed_anchor(self):
        chain = AuditChain(chain_id="test-chain")
        anchor = chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        assert anchor.is_sealed
        assert anchor.sequence == 0
        assert anchor.previous_hash is None  # genesis

    def test_chain_linkage(self):
        chain = AuditChain(chain_id="test-chain")
        a0 = chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        a1 = chain.append("agent-1", "write", VerificationLevel.FLAGGED)
        assert a1.previous_hash == a0.content_hash

    def test_chain_integrity_valid(self):
        chain = AuditChain(chain_id="test-chain")
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        chain.append("agent-1", "write", VerificationLevel.FLAGGED)
        chain.append("agent-2", "draft", VerificationLevel.HELD)
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid
        assert len(errors) == 0

    def test_chain_integrity_detects_tamper(self):
        chain = AuditChain(chain_id="test-chain")
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        chain.append("agent-1", "write", VerificationLevel.FLAGGED)
        chain.anchors[0].action = "tampered"  # tamper
        is_valid, errors = chain.verify_chain_integrity()
        assert not is_valid
        assert len(errors) > 0

    def test_filter_by_agent(self):
        chain = AuditChain(chain_id="test-chain")
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        chain.append("agent-2", "write", VerificationLevel.FLAGGED)
        chain.append("agent-1", "draft", VerificationLevel.HELD)
        agent_1_anchors = chain.filter_by_agent("agent-1")
        assert len(agent_1_anchors) == 2

    def test_filter_by_level(self):
        chain = AuditChain(chain_id="test-chain")
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        chain.append("agent-1", "write", VerificationLevel.HELD)
        held = chain.filter_by_level(VerificationLevel.HELD)
        assert len(held) == 1

    def test_export(self):
        chain = AuditChain(chain_id="test-chain")
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        chain.append("agent-2", "write", VerificationLevel.HELD)
        exported = chain.export(agent_id="agent-1")
        assert len(exported) == 1
        assert exported[0]["agent_id"] == "agent-1"

    def test_chain_length(self):
        chain = AuditChain(chain_id="test-chain")
        assert chain.length == 0
        chain.append("agent-1", "read", VerificationLevel.AUTO_APPROVED)
        assert chain.length == 1
