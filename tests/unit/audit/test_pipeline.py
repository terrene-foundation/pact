# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for audit pipeline — action recording, per-agent chains,
integrity verification, export filtering, and team timelines.
"""

from datetime import UTC, datetime, timedelta

from pact_platform.build.config.schema import VerificationLevel
from pact_platform.trust.audit.anchor import AuditChain
from pact_platform.trust.audit.pipeline import ActionRecord, AuditPipeline


class TestActionRecord:
    def test_action_record_defaults(self):
        """ActionRecord should generate an action_id and timestamp by default."""
        record = ActionRecord(
            agent_id="agent-1",
            action="read_metrics",
            verification_result=VerificationLevel.AUTO_APPROVED,
            envelope_evaluation="ALLOWED",
            result="SUCCESS",
        )
        assert record.action_id.startswith("act-")
        assert record.agent_id == "agent-1"
        assert record.timestamp is not None

    def test_action_record_with_reasoning(self):
        """ActionRecord should store reasoning for audit trail."""
        record = ActionRecord(
            agent_id="agent-1",
            action="delete_file",
            verification_result=VerificationLevel.BLOCKED,
            envelope_evaluation="DENIED",
            result="DENIED",
            reasoning="Action blocked by operational constraint",
        )
        assert record.reasoning == "Action blocked by operational constraint"
        assert record.result == "DENIED"


class TestAuditPipelineRecording:
    def test_record_action_creates_sealed_anchor(self):
        """Recording an action should produce a sealed audit anchor."""
        pipeline = AuditPipeline()
        anchor = pipeline.record_action(
            agent_id="agent-1",
            action="read_metrics",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="SUCCESS",
        )
        assert anchor.is_sealed
        assert anchor.agent_id == "agent-1"
        assert anchor.action == "read_metrics"
        assert anchor.verification_level == VerificationLevel.AUTO_APPROVED

    def test_record_action_stores_resource_in_metadata(self):
        """Recording with a resource should include it in anchor metadata."""
        pipeline = AuditPipeline()
        anchor = pipeline.record_action(
            agent_id="agent-1",
            action="read_file",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result="SUCCESS",
            resource="/data/metrics.csv",
        )
        assert anchor.metadata.get("resource") == "/data/metrics.csv"

    def test_record_action_stores_reasoning_in_metadata(self):
        """Recording with reasoning should include it in anchor metadata."""
        pipeline = AuditPipeline()
        anchor = pipeline.record_action(
            agent_id="agent-1",
            action="deploy",
            verification_level=VerificationLevel.HELD,
            result="HELD",
            reasoning="Requires human approval for deployment",
        )
        assert anchor.metadata.get("reasoning") == "Requires human approval for deployment"

    def test_multiple_actions_create_chain(self):
        """Multiple recorded actions should form a linked chain."""
        pipeline = AuditPipeline()
        a1 = pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        a2 = pipeline.record_action(
            agent_id="agent-1",
            action="write",
            verification_level=VerificationLevel.FLAGGED,
        )
        # Second anchor should chain to first
        assert a2.previous_hash == a1.content_hash


class TestPerAgentChains:
    def test_separate_chains_per_agent(self):
        """Each agent should have its own independent audit chain."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-2",
            action="write",
            verification_level=VerificationLevel.FLAGGED,
        )
        pipeline.record_action(
            agent_id="agent-1",
            action="draft",
            verification_level=VerificationLevel.HELD,
        )

        chain_1 = pipeline.get_agent_chain("agent-1")
        chain_2 = pipeline.get_agent_chain("agent-2")

        assert chain_1.length == 2
        assert chain_2.length == 1

    def test_get_agent_chain_creates_new_for_unknown_agent(self):
        """Getting a chain for an agent with no actions should return an empty chain."""
        pipeline = AuditPipeline()
        chain = pipeline.get_agent_chain("agent-unknown")
        assert chain.length == 0

    def test_agent_chain_is_independently_valid(self):
        """Each agent's chain should be independently verifiable."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-1",
            action="write",
            verification_level=VerificationLevel.FLAGGED,
        )

        is_valid, errors = pipeline.verify_agent_integrity("agent-1")
        assert is_valid
        assert len(errors) == 0


class TestIntegrityVerification:
    def test_valid_chain_passes_verification(self):
        """An untampered chain should pass integrity verification."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-1",
            action="write",
            verification_level=VerificationLevel.FLAGGED,
        )

        is_valid, errors = pipeline.verify_agent_integrity("agent-1")
        assert is_valid
        assert errors == []

    def test_tampered_chain_fails_verification(self):
        """Tampering with an anchor should cause integrity verification to fail."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-1",
            action="write",
            verification_level=VerificationLevel.FLAGGED,
        )

        # Tamper with the first anchor
        chain = pipeline.get_agent_chain("agent-1")
        chain.anchors[0].action = "tampered_action"

        is_valid, errors = pipeline.verify_agent_integrity("agent-1")
        assert not is_valid
        assert len(errors) > 0

    def test_empty_chain_passes_verification(self):
        """An empty chain (no actions) should pass integrity verification."""
        pipeline = AuditPipeline()
        is_valid, errors = pipeline.verify_agent_integrity("agent-nonexistent")
        assert is_valid
        assert errors == []


class TestExportForReview:
    def test_export_all(self):
        """Exporting without filters should return all records."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-2",
            action="write",
            verification_level=VerificationLevel.FLAGGED,
        )

        records = pipeline.export_for_review()
        assert len(records) == 2

    def test_export_filtered_by_agent(self):
        """Exporting with agent_id filter should return only that agent's records."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-2",
            action="write",
            verification_level=VerificationLevel.FLAGGED,
        )
        pipeline.record_action(
            agent_id="agent-1",
            action="draft",
            verification_level=VerificationLevel.HELD,
        )

        records = pipeline.export_for_review(agent_id="agent-1")
        assert len(records) == 2
        assert all(r["agent_id"] == "agent-1" for r in records)

    def test_export_filtered_by_since(self):
        """Exporting with since filter should return only recent records."""
        pipeline = AuditPipeline()

        # Record an old action
        pipeline.record_action(
            agent_id="agent-1",
            action="old_action",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        # Force the timestamp to be old
        chain = pipeline.get_agent_chain("agent-1")
        chain.anchors[0].timestamp = datetime.now(UTC) - timedelta(days=10)

        # Record a new action
        pipeline.record_action(
            agent_id="agent-1",
            action="new_action",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )

        cutoff = datetime.now(UTC) - timedelta(days=1)
        records = pipeline.export_for_review(since=cutoff)
        assert len(records) == 1
        assert records[0]["action"] == "new_action"

    def test_export_filtered_by_verification_level(self):
        """Exporting with verification_levels filter should match only those levels."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="auto_task",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-1",
            action="flagged_task",
            verification_level=VerificationLevel.FLAGGED,
        )
        pipeline.record_action(
            agent_id="agent-1",
            action="held_task",
            verification_level=VerificationLevel.HELD,
        )

        records = pipeline.export_for_review(
            verification_levels=[VerificationLevel.FLAGGED, VerificationLevel.HELD],
        )
        assert len(records) == 2
        levels = {r["verification_level"] for r in records}
        assert levels == {"FLAGGED", "HELD"}

    def test_export_combined_filters(self):
        """Multiple filters should be combined (AND logic)."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="task_a",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-1",
            action="task_b",
            verification_level=VerificationLevel.FLAGGED,
        )
        pipeline.record_action(
            agent_id="agent-2",
            action="task_c",
            verification_level=VerificationLevel.FLAGGED,
        )

        records = pipeline.export_for_review(
            agent_id="agent-1",
            verification_levels=[VerificationLevel.FLAGGED],
        )
        assert len(records) == 1
        assert records[0]["action"] == "task_b"


class TestTeamTimeline:
    def test_team_timeline_ordered_by_timestamp(self):
        """Team timeline should return anchors sorted chronologically."""
        pipeline = AuditPipeline()

        # Create actions with controlled timestamps
        pipeline.record_action(
            agent_id="agent-1",
            action="first",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-2",
            action="second",
            verification_level=VerificationLevel.FLAGGED,
        )
        pipeline.record_action(
            agent_id="agent-1",
            action="third",
            verification_level=VerificationLevel.HELD,
        )

        timeline = pipeline.get_team_timeline(["agent-1", "agent-2"])
        assert len(timeline) == 3

        # Verify chronological order
        for i in range(len(timeline) - 1):
            assert timeline[i].timestamp <= timeline[i + 1].timestamp

    def test_team_timeline_filters_by_agents(self):
        """Team timeline should only include requested agents."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        pipeline.record_action(
            agent_id="agent-2",
            action="write",
            verification_level=VerificationLevel.FLAGGED,
        )
        pipeline.record_action(
            agent_id="agent-3",
            action="draft",
            verification_level=VerificationLevel.HELD,
        )

        timeline = pipeline.get_team_timeline(["agent-1", "agent-3"])
        assert len(timeline) == 2
        agent_ids = {a.agent_id for a in timeline}
        assert agent_ids == {"agent-1", "agent-3"}

    def test_team_timeline_empty_for_no_agents(self):
        """Team timeline for an empty agent list should return no anchors."""
        pipeline = AuditPipeline()
        pipeline.record_action(
            agent_id="agent-1",
            action="read",
            verification_level=VerificationLevel.AUTO_APPROVED,
        )
        timeline = pipeline.get_team_timeline([])
        assert len(timeline) == 0


class TestPipelineWithExistingChain:
    def test_pipeline_with_provided_chain(self):
        """Pipeline should accept a pre-existing chain."""
        existing_chain = AuditChain(chain_id="existing-chain")
        existing_chain.append("agent-0", "genesis", VerificationLevel.AUTO_APPROVED)

        pipeline = AuditPipeline(chain=existing_chain)

        # The provided chain should be used as the main chain
        assert pipeline.chain.chain_id == "existing-chain"
        assert pipeline.chain.length == 1
