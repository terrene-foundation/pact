# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for reasoning traces — structured records of WHY trust decisions were made."""

import json
from datetime import UTC, datetime

import pytest

from care_platform.trust.reasoning import (
    ConfidentialityLevel,
    ReasoningTrace,
    ReasoningTraceStore,
)


class TestReasoningTrace:
    """Tier 1 unit tests for ReasoningTrace model."""

    def test_create_trace_with_hash_computation(self):
        """Creating a trace should auto-compute a full SHA-256 content hash."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-001",
            reasoning="Agent demonstrated consistent performance over 90 days",
        )
        assert trace.trace_id.startswith("rt-")
        assert len(trace.trace_hash) == 64  # full SHA-256 hex digest
        assert trace.trace_hash != ""
        assert trace.parent_record_type == "delegation"
        assert trace.parent_record_id == "del-001"
        assert trace.confidentiality == ConfidentialityLevel.RESTRICTED

    def test_verify_integrity_passes_for_untampered(self):
        """An untampered trace should pass integrity verification."""
        trace = ReasoningTrace(
            parent_record_type="audit_anchor",
            parent_record_id="anchor-005",
            reasoning="Action was flagged due to financial threshold breach",
            confidentiality=ConfidentialityLevel.CONFIDENTIAL,
        )
        assert trace.verify_integrity() is True

    def test_tampered_trace_fails_integrity_check(self):
        """Modifying trace content after creation should fail integrity check."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-002",
            reasoning="Original reasoning",
        )
        original_hash = trace.trace_hash

        # Tamper with the reasoning
        trace.reasoning = "Tampered reasoning"

        assert trace.trace_hash == original_hash  # hash field unchanged
        assert trace.verify_integrity() is False  # but recomputation detects tampering

    def test_redaction_at_lower_confidentiality_level(self):
        """Viewer with lower clearance should see redacted reasoning."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-003",
            reasoning="Sensitive internal discussion about agent trust breach",
            confidentiality=ConfidentialityLevel.CONFIDENTIAL,
        )
        # PUBLIC viewer has less clearance than CONFIDENTIAL trace
        redacted = trace.redact(viewer_level=ConfidentialityLevel.PUBLIC)
        assert redacted.reasoning == "[REDACTED]"
        assert redacted.trace_id == trace.trace_id
        assert redacted.parent_record_id == trace.parent_record_id

    def test_redaction_at_equal_confidentiality_level(self):
        """Viewer with equal clearance should see full reasoning."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-004",
            reasoning="Standard operational decision",
            confidentiality=ConfidentialityLevel.RESTRICTED,
        )
        visible = trace.redact(viewer_level=ConfidentialityLevel.RESTRICTED)
        assert visible.reasoning == "Standard operational decision"

    def test_redaction_at_higher_confidentiality_level(self):
        """Viewer with higher clearance should see full reasoning."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-005",
            reasoning="Public reasoning about policy change",
            confidentiality=ConfidentialityLevel.PUBLIC,
        )
        visible = trace.redact(viewer_level=ConfidentialityLevel.SECRET)
        assert visible.reasoning == "Public reasoning about policy change"

    def test_top_secret_traces_only_visible_to_top_secret_clearance(self):
        """TOP_SECRET traces should only be visible to TOP_SECRET clearance."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-006",
            reasoning="Genesis authority override justification",
            confidentiality=ConfidentialityLevel.TOP_SECRET,
        )
        # All levels below TOP_SECRET should see redacted
        assert trace.redact(viewer_level=ConfidentialityLevel.PUBLIC).reasoning == "[REDACTED]"
        assert trace.redact(viewer_level=ConfidentialityLevel.RESTRICTED).reasoning == "[REDACTED]"
        assert (
            trace.redact(viewer_level=ConfidentialityLevel.CONFIDENTIAL).reasoning == "[REDACTED]"
        )
        assert trace.redact(viewer_level=ConfidentialityLevel.SECRET).reasoning == "[REDACTED]"
        # Only TOP_SECRET sees the real reasoning
        assert (
            trace.redact(viewer_level=ConfidentialityLevel.TOP_SECRET).reasoning
            == "Genesis authority override justification"
        )

    def test_hash_is_deterministic(self):
        """Same content should produce the same hash."""
        kwargs = dict(
            trace_id="rt-fixed",
            parent_record_type="delegation",
            parent_record_id="del-007",
            reasoning="Deterministic test",
            confidentiality=ConfidentialityLevel.PUBLIC,
            trace_hash="",  # force recomputation
        )
        trace_a = ReasoningTrace(**kwargs)
        trace_b = ReasoningTrace(**kwargs)
        assert trace_a.trace_hash == trace_b.trace_hash

    def test_structured_fields_compose_reasoning(self):
        """When reasoning is empty, decision+rationale should compose it."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-008",
            decision="Approve delegation",
            rationale="Agent met all threshold requirements",
        )
        assert "Decision: Approve delegation" in trace.reasoning
        assert "Rationale: Agent met all threshold requirements" in trace.reasoning

    def test_explicit_reasoning_not_overwritten(self):
        """When reasoning is explicitly provided, it should not be overwritten."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-009",
            reasoning="Explicit reasoning text",
            decision="Some decision",
            rationale="Some rationale",
        )
        assert trace.reasoning == "Explicit reasoning text"

    def test_structured_fields_defaults(self):
        """Structured fields should have sensible defaults."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-010",
            reasoning="Test",
        )
        assert trace.decision == ""
        assert trace.rationale == ""
        assert trace.alternatives_considered == []
        assert trace.evidence == []
        assert trace.confidence == 1.0

    def test_structured_fields_populated(self):
        """All structured fields should be storable and retrievable."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-011",
            decision="Upgrade posture",
            rationale="90-day track record with zero incidents",
            alternatives_considered=["Maintain current posture", "Downgrade"],
            evidence=["90 days at SUPERVISED", "0 incidents", "95% pass rate"],
            confidence=0.95,
        )
        assert trace.decision == "Upgrade posture"
        assert trace.rationale == "90-day track record with zero incidents"
        assert len(trace.alternatives_considered) == 2
        assert len(trace.evidence) == 3
        assert trace.confidence == 0.95


class TestReasoningTraceStore:
    """Tier 1 unit tests for ReasoningTraceStore."""

    def _make_store_with_traces(self) -> ReasoningTraceStore:
        """Helper to create a store with several traces."""
        store = ReasoningTraceStore()
        store.add(
            ReasoningTrace(
                parent_record_type="delegation",
                parent_record_id="del-001",
                reasoning="Delegation approved based on performance",
                confidentiality=ConfidentialityLevel.RESTRICTED,
            )
        )
        store.add(
            ReasoningTrace(
                parent_record_type="delegation",
                parent_record_id="del-001",
                reasoning="Secondary review confirmed trust threshold",
                confidentiality=ConfidentialityLevel.CONFIDENTIAL,
            )
        )
        store.add(
            ReasoningTrace(
                parent_record_type="audit_anchor",
                parent_record_id="anchor-010",
                reasoning="Audit triggered by anomalous pattern",
                confidentiality=ConfidentialityLevel.SECRET,
            )
        )
        store.add(
            ReasoningTrace(
                parent_record_type="delegation",
                parent_record_id="del-002",
                reasoning="Genesis authority sealed reasoning",
                confidentiality=ConfidentialityLevel.TOP_SECRET,
            )
        )
        return store

    def test_store_add_and_retrieve_by_record_id(self):
        """Store should retrieve all traces for a given parent record."""
        store = self._make_store_with_traces()
        traces = store.get_for_record("del-001")
        assert len(traces) == 2
        assert all(t.parent_record_id == "del-001" for t in traces)

    def test_store_retrieve_returns_empty_for_unknown_record(self):
        """Store should return empty list for unknown record ID."""
        store = self._make_store_with_traces()
        traces = store.get_for_record("nonexistent-999")
        assert traces == []

    def test_get_with_clearance_redacts_appropriately(self):
        """Clearance-aware retrieval should redact traces above viewer's level."""
        store = self._make_store_with_traces()
        traces = store.get_with_clearance("del-001", ConfidentialityLevel.RESTRICTED)
        assert len(traces) == 2
        # RESTRICTED viewer sees RESTRICTED reasoning
        restricted_trace = [
            t for t in traces if t.confidentiality == ConfidentialityLevel.RESTRICTED
        ][0]
        assert restricted_trace.reasoning != "[REDACTED]"
        # RESTRICTED viewer cannot see CONFIDENTIAL reasoning
        confidential_trace = [
            t for t in traces if t.confidentiality == ConfidentialityLevel.CONFIDENTIAL
        ][0]
        assert confidential_trace.reasoning == "[REDACTED]"

    def test_export_with_public_clearance(self):
        """Export with PUBLIC clearance should redact all non-PUBLIC traces."""
        store = self._make_store_with_traces()
        exported = store.export(viewer_level=ConfidentialityLevel.PUBLIC)
        assert len(exported) == 4
        for item in exported:
            # All traces are RESTRICTED or above, so all should be redacted for PUBLIC viewer
            assert item["reasoning"] == "[REDACTED]"

    def test_export_with_parent_type_filter(self):
        """Export with parent_type filter should only include matching traces."""
        store = self._make_store_with_traces()
        exported = store.export(
            viewer_level=ConfidentialityLevel.TOP_SECRET, parent_type="audit_anchor"
        )
        assert len(exported) == 1
        assert exported[0]["parent_record_type"] == "audit_anchor"
        assert exported[0]["reasoning"] == "Audit triggered by anomalous pattern"

    def test_export_with_top_secret_clearance_shows_everything(self):
        """Export with TOP_SECRET clearance should show all reasoning unredacted."""
        store = self._make_store_with_traces()
        exported = store.export(viewer_level=ConfidentialityLevel.TOP_SECRET)
        assert len(exported) == 4
        for item in exported:
            assert item["reasoning"] != "[REDACTED]"


class TestToSigningPayload:
    """Tier 1 unit tests for ReasoningTrace.to_signing_payload()."""

    def test_returns_bytes(self):
        """to_signing_payload() must return bytes suitable for Ed25519 signing."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-sign-001",
            decision="Approve delegation",
            rationale="Agent met requirements",
        )
        payload = trace.to_signing_payload()
        assert isinstance(payload, bytes)

    def test_is_deterministic(self):
        """Same trace content must produce identical signing payloads."""
        fixed_dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        kwargs = dict(
            trace_id="rt-signtest",
            parent_record_type="delegation",
            parent_record_id="del-sign-002",
            decision="Approve",
            rationale="Good track record",
            confidentiality=ConfidentialityLevel.RESTRICTED,
            created_at=fixed_dt,
            genesis_binding_hash="abc123",
        )
        trace_a = ReasoningTrace(**kwargs)
        trace_b = ReasoningTrace(**kwargs)
        assert trace_a.to_signing_payload() == trace_b.to_signing_payload()

    def test_excludes_trace_hash(self):
        """Signing payload must NOT include trace_hash (it is a derived field)."""
        trace = ReasoningTrace(
            trace_id="rt-excl",
            parent_record_type="delegation",
            parent_record_id="del-sign-003",
            decision="Test exclusion",
            rationale="Checking hash exclusion",
        )
        payload = trace.to_signing_payload()
        # Parse the canonical JSON to verify trace_hash is absent
        payload_dict = json.loads(payload)
        assert "trace_hash" not in payload_dict

    def test_includes_all_required_fields(self):
        """Signing payload must include trace_id, parent_record_type, parent_record_id,
        decision, rationale, confidentiality, created_at, genesis_binding_hash."""
        fixed_dt = datetime(2026, 3, 1, 10, 30, 0, tzinfo=UTC)
        trace = ReasoningTrace(
            trace_id="rt-fields",
            parent_record_type="delegation",
            parent_record_id="del-sign-004",
            decision="Grant access",
            rationale="Passed review",
            confidentiality=ConfidentialityLevel.CONFIDENTIAL,
            created_at=fixed_dt,
            genesis_binding_hash="genesis-hash-xyz",
        )
        payload = trace.to_signing_payload()
        payload_dict = json.loads(payload)
        assert payload_dict["trace_id"] == "rt-fields"
        assert payload_dict["parent_record_type"] == "delegation"
        assert payload_dict["parent_record_id"] == "del-sign-004"
        assert payload_dict["decision"] == "Grant access"
        assert payload_dict["rationale"] == "Passed review"
        assert payload_dict["confidentiality"] == "confidential"
        assert payload_dict["genesis_binding_hash"] == "genesis-hash-xyz"
        # created_at should be present as ISO string
        assert "created_at" in payload_dict

    def test_payload_is_canonical_json(self):
        """Signing payload must be RFC 8785 canonical JSON (sorted keys, no extra whitespace)."""
        trace = ReasoningTrace(
            trace_id="rt-canonical",
            parent_record_type="delegation",
            parent_record_id="del-sign-005",
            decision="Canonical test",
            rationale="Verify sorting",
        )
        payload = trace.to_signing_payload()
        payload_dict = json.loads(payload)
        # Keys should be sorted in the raw bytes
        keys = list(payload_dict.keys())
        assert keys == sorted(keys)


class TestFactoryMethods:
    """Tier 1 unit tests for ReasoningTrace factory class methods."""

    def test_create_delegation_trace_sets_correct_fields(self):
        """create_delegation_trace() must set parent_record_type='delegation' and correct decision."""
        trace = ReasoningTrace.create_delegation_trace(
            delegator_id="agent-A",
            delegatee_id="agent-B",
            capabilities=["read", "write"],
            constraints=["financial_limit=1000"],
            rationale="Agent-B proved trustworthy",
        )
        assert trace.parent_record_type == "delegation"
        assert trace.parent_record_id == "deleg-agent-A-agent-B"
        assert "read" in trace.decision
        assert "write" in trace.decision
        assert "agent-A" in trace.decision
        assert "agent-B" in trace.decision
        assert trace.confidence == 0.9
        assert trace.rationale == "Agent-B proved trustworthy"
        assert trace.trace_id.startswith("rt-")
        assert trace.trace_hash != ""

    def test_create_delegation_trace_without_optional_args(self):
        """create_delegation_trace() must work with only required arguments."""
        trace = ReasoningTrace.create_delegation_trace(
            delegator_id="root",
            delegatee_id="sub-agent",
            capabilities=["execute"],
        )
        assert trace.parent_record_type == "delegation"
        assert trace.parent_record_id == "deleg-root-sub-agent"
        assert "execute" in trace.decision
        assert trace.rationale == ""

    def test_create_posture_trace_sets_correct_fields(self):
        """create_posture_trace() must set parent_record_type='posture_change' and correct decision."""
        trace = ReasoningTrace.create_posture_trace(
            agent_id="agent-X",
            from_posture="SUPERVISED",
            to_posture="SHARED_PLANNING",
            trigger="threshold_met",
            evidence=["90 days at SUPERVISED", "zero incidents"],
        )
        assert trace.parent_record_type == "posture_change"
        assert trace.parent_record_id == "posture-agent-X"
        assert "SUPERVISED" in trace.decision
        assert "SHARED_PLANNING" in trace.decision
        assert trace.evidence == ["90 days at SUPERVISED", "zero incidents"]
        assert trace.trace_id.startswith("rt-")

    def test_create_posture_trace_without_evidence(self):
        """create_posture_trace() must work without optional evidence."""
        trace = ReasoningTrace.create_posture_trace(
            agent_id="agent-Y",
            from_posture="PSEUDO_AGENT",
            to_posture="SUPERVISED",
            trigger="manual_override",
        )
        assert trace.parent_record_type == "posture_change"
        assert "PSEUDO_AGENT" in trace.decision
        assert "SUPERVISED" in trace.decision
        assert trace.evidence == []

    def test_create_verification_trace_sets_correct_fields(self):
        """create_verification_trace() must set parent_record_type='verification' and correct decision."""
        trace = ReasoningTrace.create_verification_trace(
            agent_id="verifier-001",
            action="deploy_service",
            result="approved",
            level="AUTO_APPROVED",
        )
        assert trace.parent_record_type == "verification"
        assert trace.parent_record_id == "verify-verifier-001-deploy_service"
        assert "deploy_service" in trace.decision
        assert "verifier-001" in trace.decision
        assert "approved" in trace.decision
        assert trace.trace_id.startswith("rt-")
        assert trace.trace_hash != ""


class TestSizeValidation:
    """Tier 1 unit tests for size validation on ReasoningTrace fields."""

    def test_decision_exceeding_max_length_raises_error(self):
        """decision > 10,000 characters must raise ValueError."""
        with pytest.raises(ValueError, match="decision"):
            ReasoningTrace(
                parent_record_type="delegation",
                parent_record_id="del-size-001",
                decision="x" * 10_001,
            )

    def test_rationale_exceeding_max_length_raises_error(self):
        """rationale > 50,000 characters must raise ValueError."""
        with pytest.raises(ValueError, match="rationale"):
            ReasoningTrace(
                parent_record_type="delegation",
                parent_record_id="del-size-002",
                rationale="y" * 50_001,
            )

    def test_alternatives_exceeding_max_count_raises_error(self):
        """alternatives_considered > 100 items must raise ValueError."""
        with pytest.raises(ValueError, match="alternatives_considered"):
            ReasoningTrace(
                parent_record_type="delegation",
                parent_record_id="del-size-003",
                reasoning="Test",
                alternatives_considered=[f"alt-{i}" for i in range(101)],
            )

    def test_evidence_exceeding_max_count_raises_error(self):
        """evidence > 100 items must raise ValueError."""
        with pytest.raises(ValueError, match="evidence"):
            ReasoningTrace(
                parent_record_type="delegation",
                parent_record_id="del-size-004",
                reasoning="Test",
                evidence=[f"ev-{i}" for i in range(101)],
            )

    def test_at_limit_decision_passes(self):
        """decision at exactly 10,000 characters must be accepted."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-size-005",
            decision="x" * 10_000,
        )
        assert len(trace.decision) == 10_000

    def test_at_limit_rationale_passes(self):
        """rationale at exactly 50,000 characters must be accepted."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-size-006",
            rationale="y" * 50_000,
        )
        assert len(trace.rationale) == 50_000

    def test_at_limit_alternatives_passes(self):
        """alternatives_considered at exactly 100 items must be accepted."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-size-007",
            reasoning="Test",
            alternatives_considered=[f"alt-{i}" for i in range(100)],
        )
        assert len(trace.alternatives_considered) == 100

    def test_at_limit_evidence_passes(self):
        """evidence at exactly 100 items must be accepted."""
        trace = ReasoningTrace(
            parent_record_type="delegation",
            parent_record_id="del-size-008",
            reasoning="Test",
            evidence=[f"ev-{i}" for i in range(100)],
        )
        assert len(trace.evidence) == 100
