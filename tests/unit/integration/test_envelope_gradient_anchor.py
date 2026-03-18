# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Integration tests for the envelope -> gradient -> anchor pipeline.

Tests the full EATP trust chain flow:
1. Create a constraint envelope with all 5 dimensions configured
2. Evaluate an action through the envelope
3. Pass the evaluation result to the gradient engine for classification
4. Record the classification result in the audit chain
5. Verify the entire audit chain is intact and contains correct data
"""

from datetime import UTC, datetime

from care_platform.trust.audit.anchor import AuditChain
from care_platform.build.config.schema import (
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
from care_platform.trust.constraint.envelope import (
    ConstraintEnvelope,
    EvaluationResult,
)
from care_platform.trust.constraint.gradient import (
    GradientEngine,
    VerificationThoroughness,
)
from care_platform.trust.attestation import CapabilityAttestation


def _make_full_envelope(envelope_id: str = "env-full") -> ConstraintEnvelope:
    """Create a constraint envelope with all 5 dimensions configured."""
    config = ConstraintEnvelopeConfig(
        id=envelope_id,
        description="Full integration test envelope",
        financial=FinancialConstraintConfig(
            max_spend_usd=500.0,
            api_cost_budget_usd=5000.0,
            requires_approval_above_usd=200.0,
        ),
        operational=OperationalConstraintConfig(
            allowed_actions=[
                "read_metrics",
                "draft_content",
                "send_internal_msg",
                "analyze_data",
                "generate_report",
            ],
            blocked_actions=["delete_data", "modify_governance"],
            max_actions_per_day=50,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="08:00",
            active_hours_end="20:00",
            timezone="UTC",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["reports/", "metrics/"],
            write_paths=["drafts/"],
            blocked_data_types=["pii", "financial_records"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["slack-internal"],
            external_requires_approval=True,
        ),
    )
    return ConstraintEnvelope(config=config)


def _make_gradient_engine() -> GradientEngine:
    """Create a gradient engine with rules covering multiple levels."""
    config = VerificationGradientConfig(
        rules=[
            GradientRuleConfig(
                pattern="read_*",
                level=VerificationLevel.AUTO_APPROVED,
                reason="Read operations are low risk",
            ),
            GradientRuleConfig(
                pattern="draft_*",
                level=VerificationLevel.FLAGGED,
                reason="Content creation requires review",
            ),
            GradientRuleConfig(
                pattern="send_*",
                level=VerificationLevel.HELD,
                reason="Outbound messages need approval",
            ),
            GradientRuleConfig(
                pattern="delete_*",
                level=VerificationLevel.BLOCKED,
                reason="Destructive operations blocked",
            ),
        ],
        default_level=VerificationLevel.HELD,
    )
    return GradientEngine(config)


class TestEnvelopeToGradientToAnchor:
    """Full pipeline: envelope evaluation -> gradient classification -> audit recording."""

    def test_allowed_action_flows_through_full_chain(self):
        """An allowed action at low utilization gets auto-approved and recorded."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-1")
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Step 1: Evaluate action against envelope
        eval_result = envelope.evaluate_action(
            "read_metrics",
            "agent-1",
            spend_amount=10.0,
            current_action_count=5,
            current_time=work_time,
        )
        assert eval_result.is_allowed, f"Expected allowed but got {eval_result.overall_result}"
        assert len(eval_result.dimensions) == 5

        # Step 2: Classify through gradient engine
        gradient_result = engine.classify(
            "read_metrics",
            "agent-1",
            thoroughness=VerificationThoroughness.STANDARD,
            envelope_evaluation=eval_result,
        )
        assert gradient_result.is_auto_approved, (
            f"Expected auto_approved but got {gradient_result.level}"
        )
        assert gradient_result.matched_rule == "read_*"

        # Step 3: Record in audit chain
        anchor = chain.append(
            agent_id="agent-1",
            action="read_metrics",
            verification_level=gradient_result.level,
            envelope_id=envelope.id,
            result="success",
            metadata={"spend": 10.0, "action_count": 5},
        )

        # Step 4: Verify chain integrity
        assert anchor.is_sealed
        assert anchor.sequence == 0
        assert anchor.previous_hash is None  # genesis anchor
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"
        assert chain.length == 1

    def test_denied_action_blocked_and_recorded(self):
        """A blocked action is denied by envelope, blocked by gradient, and recorded."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-2")
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Step 1: Evaluate blocked action against envelope
        eval_result = envelope.evaluate_action(
            "delete_data",
            "agent-1",
            current_time=work_time,
        )
        assert not eval_result.is_allowed

        # Confirm the operational dimension specifically denied it
        op_dim = next(d for d in eval_result.dimensions if d.dimension == "operational")
        assert op_dim.result == EvaluationResult.DENIED

        # Step 2: Gradient engine should block due to denied envelope
        gradient_result = engine.classify(
            "delete_data",
            "agent-1",
            envelope_evaluation=eval_result,
        )
        assert gradient_result.is_blocked
        assert gradient_result.reason == "Blocked by constraint envelope"

        # Step 3: Record the blocked action
        anchor = chain.append(
            agent_id="agent-1",
            action="delete_data",
            verification_level=gradient_result.level,
            envelope_id=envelope.id,
            result="blocked",
        )

        # Step 4: Verify
        assert anchor.verification_level == VerificationLevel.BLOCKED
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"

    def test_near_boundary_flagged_and_recorded(self):
        """An action near the financial boundary gets flagged and recorded."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-3")
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Step 1: Spend 85% of budget -> near boundary
        eval_result = envelope.evaluate_action(
            "analyze_data",
            "agent-1",
            spend_amount=425.0,  # 85% of $500
            current_action_count=5,
            current_time=work_time,
        )
        assert eval_result.is_near_boundary, (
            f"Expected near_boundary but got {eval_result.overall_result}"
        )

        # Confirm financial dimension is the near-boundary trigger
        fin_dim = next(d for d in eval_result.dimensions if d.dimension == "financial")
        assert fin_dim.result == EvaluationResult.NEAR_BOUNDARY
        assert fin_dim.utilization > 0.8

        # Step 2: Gradient engine flags near-boundary (overrides any rule match)
        gradient_result = engine.classify(
            "analyze_data",
            "agent-1",
            envelope_evaluation=eval_result,
        )
        assert gradient_result.level == VerificationLevel.FLAGGED
        assert gradient_result.reason == "Near constraint boundary"

        # Step 3: Record
        anchor = chain.append(
            agent_id="agent-1",
            action="analyze_data",
            verification_level=gradient_result.level,
            envelope_id=envelope.id,
            result="flagged_for_review",
            metadata={"spend": 425.0, "utilization": fin_dim.utilization},
        )

        # Step 4: Verify
        assert anchor.verification_level == VerificationLevel.FLAGGED
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"

    def test_multi_action_sequence_builds_valid_chain(self):
        """Multiple actions in sequence produce a linked, verifiable audit chain."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-4")
        work_time = datetime(2026, 3, 11, 10, 0, tzinfo=UTC)

        actions = [
            ("read_metrics", 0.0, 0),
            ("read_metrics", 0.0, 1),
            ("draft_content", 5.0, 2),
            ("read_metrics", 10.0, 3),
            ("analyze_data", 20.0, 4),
        ]

        for action, spend, count in actions:
            eval_result = envelope.evaluate_action(
                action,
                "agent-1",
                spend_amount=spend,
                current_action_count=count,
                current_time=work_time,
            )
            gradient_result = engine.classify(action, "agent-1", envelope_evaluation=eval_result)
            chain.append(
                agent_id="agent-1",
                action=action,
                verification_level=gradient_result.level,
                envelope_id=envelope.id,
                result="executed",
            )

        # Full chain should be valid
        assert chain.length == 5
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed with {len(errors)} error(s): {errors}"

        # Each anchor should link to the previous
        for i in range(1, chain.length):
            assert chain.anchors[i].previous_hash == chain.anchors[i - 1].content_hash, (
                f"Anchor {i} does not link to anchor {i - 1}"
            )

        # Genesis anchor has no previous hash
        assert chain.anchors[0].previous_hash is None

    def test_multi_agent_actions_recorded_in_shared_chain(self):
        """Two agents operating under different envelopes share one audit chain."""
        env_reader = _make_full_envelope(envelope_id="env-reader")
        env_writer = _make_full_envelope(envelope_id="env-writer")
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="shared-chain")
        work_time = datetime(2026, 3, 11, 12, 0, tzinfo=UTC)

        # Agent 1 reads
        eval1 = env_reader.evaluate_action("read_metrics", "agent-reader", current_time=work_time)
        grad1 = engine.classify("read_metrics", "agent-reader", envelope_evaluation=eval1)
        chain.append(
            agent_id="agent-reader",
            action="read_metrics",
            verification_level=grad1.level,
            envelope_id=env_reader.id,
            result="success",
        )

        # Agent 2 drafts
        eval2 = env_writer.evaluate_action("draft_content", "agent-writer", current_time=work_time)
        grad2 = engine.classify("draft_content", "agent-writer", envelope_evaluation=eval2)
        chain.append(
            agent_id="agent-writer",
            action="draft_content",
            verification_level=grad2.level,
            envelope_id=env_writer.id,
            result="success",
        )

        # Agent 1 reads again
        eval3 = env_reader.evaluate_action("read_metrics", "agent-reader", current_time=work_time)
        grad3 = engine.classify("read_metrics", "agent-reader", envelope_evaluation=eval3)
        chain.append(
            agent_id="agent-reader",
            action="read_metrics",
            verification_level=grad3.level,
            envelope_id=env_reader.id,
            result="success",
        )

        # Chain integrity holds across agents
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Shared chain integrity failed: {errors}"
        assert chain.length == 3

        # Filter by agent
        reader_anchors = chain.filter_by_agent("agent-reader")
        writer_anchors = chain.filter_by_agent("agent-writer")
        assert len(reader_anchors) == 2
        assert len(writer_anchors) == 1

    def test_outside_hours_denied_and_recorded(self):
        """Action outside active hours is denied by temporal dimension and recorded."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-temporal")
        late_time = datetime(2026, 3, 11, 23, 30, tzinfo=UTC)

        # Step 1: Evaluate during off-hours
        eval_result = envelope.evaluate_action(
            "read_metrics",
            "agent-1",
            current_time=late_time,
        )
        assert not eval_result.is_allowed

        # Confirm temporal dimension denied it
        temp_dim = next(d for d in eval_result.dimensions if d.dimension == "temporal")
        assert temp_dim.result == EvaluationResult.DENIED

        # Step 2: Gradient blocks because envelope denied
        gradient_result = engine.classify(
            "read_metrics", "agent-1", envelope_evaluation=eval_result
        )
        assert gradient_result.is_blocked

        # Step 3: Record
        chain.append(
            agent_id="agent-1",
            action="read_metrics",
            verification_level=gradient_result.level,
            envelope_id=envelope.id,
            result="denied_outside_hours",
        )

        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"

    def test_blocked_data_access_denied_and_recorded(self):
        """Access to blocked data types is denied and properly recorded."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-data")
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Step 1: Try to access PII data
        eval_result = envelope.evaluate_action(
            "read_metrics",
            "agent-1",
            current_time=work_time,
            data_paths=["users/pii/records"],
        )
        assert not eval_result.is_allowed

        # Confirm data_access dimension denied it
        data_dim = next(d for d in eval_result.dimensions if d.dimension == "data_access")
        assert data_dim.result == EvaluationResult.DENIED
        assert "pii" in data_dim.reason.lower()

        # Step 2: Gradient blocks
        gradient_result = engine.classify(
            "read_metrics", "agent-1", envelope_evaluation=eval_result
        )
        assert gradient_result.is_blocked

        # Step 3: Record
        chain.append(
            agent_id="agent-1",
            action="read_metrics",
            verification_level=gradient_result.level,
            envelope_id=envelope.id,
            result="denied_pii_access",
        )

        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"

    def test_external_communication_denied_and_recorded(self):
        """External communication blocked when internal_only is set."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-comm")
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Step 1: Try external communication
        eval_result = envelope.evaluate_action(
            "send_internal_msg",
            "agent-1",
            current_time=work_time,
            is_external=True,
        )
        assert not eval_result.is_allowed

        # Confirm communication dimension denied it
        comm_dim = next(d for d in eval_result.dimensions if d.dimension == "communication")
        assert comm_dim.result == EvaluationResult.DENIED

        # Step 2: Gradient blocks
        gradient_result = engine.classify(
            "send_internal_msg", "agent-1", envelope_evaluation=eval_result
        )
        assert gradient_result.is_blocked

        # Step 3: Record
        chain.append(
            agent_id="agent-1",
            action="send_internal_msg",
            verification_level=gradient_result.level,
            envelope_id=envelope.id,
            result="denied_external_comm",
        )

        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"

    def test_attestation_verified_before_envelope_evaluation(self):
        """Attestation validity check gates the envelope evaluation flow."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-att")
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Create a valid attestation
        attestation = CapabilityAttestation(
            attestation_id="att-integ-1",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id=envelope.id,
            capabilities=["read_metrics", "draft_content", "analyze_data"],
            issuer_id="root-authority",
        )

        # Verify attestation is valid and consistent with envelope actions
        assert attestation.is_valid
        is_consistent, drift = attestation.verify_consistency(
            envelope.config.operational.allowed_actions
        )
        assert is_consistent, f"Attestation has drift: {drift}"

        # Verify the agent has the capability for the action
        assert attestation.has_capability("read_metrics")

        # Proceed with envelope evaluation
        eval_result = envelope.evaluate_action("read_metrics", "agent-1", current_time=work_time)
        assert eval_result.is_allowed

        # Classify
        gradient_result = engine.classify(
            "read_metrics", "agent-1", envelope_evaluation=eval_result
        )

        # Record with attestation metadata
        chain.append(
            agent_id="agent-1",
            action="read_metrics",
            verification_level=gradient_result.level,
            envelope_id=envelope.id,
            result="success",
            metadata={
                "attestation_id": attestation.attestation_id,
                "attestation_hash": attestation.content_hash(),
            },
        )

        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"

        # Verify attestation info recorded in anchor metadata
        latest = chain.latest
        assert latest is not None
        assert latest.metadata["attestation_id"] == "att-integ-1"
        assert latest.metadata["attestation_hash"] == attestation.content_hash()

    def test_revoked_attestation_prevents_action(self):
        """A revoked attestation should gate the action from proceeding."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-revoked")

        # Create and then revoke an attestation
        attestation = CapabilityAttestation(
            attestation_id="att-revoked",
            agent_id="agent-1",
            delegation_id="del-1",
            constraint_envelope_id=envelope.id,
            capabilities=["read_metrics"],
            issuer_id="root-authority",
        )
        attestation.revoke("Agent compromised")

        # Attestation check gates the flow
        assert not attestation.is_valid
        assert attestation.revoked
        assert attestation.revocation_reason == "Agent compromised"

        # Record the denial in the audit chain (application-level enforcement)
        chain.append(
            agent_id="agent-1",
            action="read_metrics",
            verification_level=VerificationLevel.BLOCKED,
            envelope_id=envelope.id,
            result="denied_revoked_attestation",
            metadata={"revocation_reason": "Agent compromised"},
        )

        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"
        assert chain.latest.result == "denied_revoked_attestation"

    def test_monotonic_tightening_with_child_envelope_in_chain(self):
        """Child envelope must be tighter; both parent and child actions recorded."""
        parent_envelope = _make_full_envelope(envelope_id="env-parent")
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-hierarchy")
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Create tighter child envelope
        child_config = ConstraintEnvelopeConfig(
            id="env-child",
            description="Restricted child envelope",
            financial=FinancialConstraintConfig(max_spend_usd=100.0),
            operational=OperationalConstraintConfig(
                allowed_actions=["read_metrics", "draft_content"],
                blocked_actions=["delete_data", "modify_governance", "send_internal_msg"],
                max_actions_per_day=20,
            ),
            temporal=TemporalConstraintConfig(
                active_hours_start="09:00",
                active_hours_end="17:00",
            ),
            data_access=DataAccessConstraintConfig(
                read_paths=["reports/"],  # subset of parent ["reports/", "metrics/"]
                write_paths=["drafts/"],  # same as parent
                blocked_data_types=["pii", "financial_records"],
            ),
            communication=CommunicationConstraintConfig(
                internal_only=True,
                external_requires_approval=True,
            ),
        )
        child_envelope = ConstraintEnvelope(config=child_config, parent_envelope_id="env-parent")

        # Verify monotonic tightening
        assert child_envelope.is_tighter_than(parent_envelope)

        # Parent agent action
        eval_parent = parent_envelope.evaluate_action(
            "read_metrics", "agent-parent", current_time=work_time
        )
        grad_parent = engine.classify(
            "read_metrics", "agent-parent", envelope_evaluation=eval_parent
        )
        chain.append(
            agent_id="agent-parent",
            action="read_metrics",
            verification_level=grad_parent.level,
            envelope_id=parent_envelope.id,
            result="success",
        )

        # Child agent action
        eval_child = child_envelope.evaluate_action(
            "read_metrics", "agent-child", current_time=work_time
        )
        grad_child = engine.classify("read_metrics", "agent-child", envelope_evaluation=eval_child)
        chain.append(
            agent_id="agent-child",
            action="read_metrics",
            verification_level=grad_child.level,
            envelope_id=child_envelope.id,
            result="success",
        )

        # Both recorded, chain valid
        is_valid, errors = chain.verify_chain_integrity()
        assert is_valid, f"Chain integrity failed: {errors}"
        assert chain.length == 2

        # Child has different envelope_id
        assert chain.anchors[0].envelope_id == "env-parent"
        assert chain.anchors[1].envelope_id == "env-child"

    def test_export_filtered_audit_chain(self):
        """Export functionality filters by agent and preserves integrity data."""
        envelope = _make_full_envelope()
        engine = _make_gradient_engine()
        chain = AuditChain(chain_id="integration-chain-export")
        work_time = datetime(2026, 3, 11, 14, 0, tzinfo=UTC)

        # Record several actions from different agents
        for agent_id in ["agent-a", "agent-b", "agent-a"]:
            eval_result = envelope.evaluate_action("read_metrics", agent_id, current_time=work_time)
            grad_result = engine.classify("read_metrics", agent_id, envelope_evaluation=eval_result)
            chain.append(
                agent_id=agent_id,
                action="read_metrics",
                verification_level=grad_result.level,
                envelope_id=envelope.id,
                result="success",
            )

        # Export all
        all_exported = chain.export()
        assert len(all_exported) == 3

        # Export filtered by agent
        agent_a_exported = chain.export(agent_id="agent-a")
        assert len(agent_a_exported) == 2
        assert all(e["agent_id"] == "agent-a" for e in agent_a_exported)

        # Exported data includes content_hash for external verification
        for entry in all_exported:
            assert "content_hash" in entry
            assert entry["content_hash"] != ""
