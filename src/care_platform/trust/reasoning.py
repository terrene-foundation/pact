# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Reasoning traces — structured records of WHY trust decisions were made.

Every trust decision (delegation, constraint change, posture upgrade) should
have a reasoning trace that explains the decision. These traces are
confidentiality-classified so that sensitive reasoning can be redacted
for viewers without sufficient clearance.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

# ConfidentialityLevel and _CONFIDENTIALITY_ORDER are canonically defined
# in config.schema to break a circular import chain. Re-export here so
# existing callers that import from care_platform.trust.reasoning continue
# to work. Do NOT redefine — use the canonical single source of truth.
from care_platform.build.config.schema import (  # noqa: F401
    _CONFIDENTIALITY_ORDER,
    ConfidentialityLevel,
)
from care_platform.trust.jcs import canonical_serialize


class ReasoningTrace(BaseModel):
    """Structured record of WHY a trust decision was made.

    Each trace is tied to a parent record (delegation or audit anchor)
    and carries a confidentiality classification that controls who can
    see the reasoning content.

    Structured fields (EATP-aligned):
    - decision: what was decided
    - rationale: why
    - alternatives_considered: options that were evaluated
    - evidence: supporting data points
    - confidence: decision confidence (0.0 to 1.0)
    - reasoning: backward-compatible free-text field (computed from
      decision+rationale if left empty)
    """

    trace_id: str = Field(default_factory=lambda: f"rt-{uuid4().hex[:8]}")
    parent_record_type: str  # "delegation" or "audit_anchor"
    parent_record_id: str
    reasoning: str = ""  # backward-compatible free-text WHY field
    decision: str = ""  # what was decided
    rationale: str = ""  # why
    alternatives_considered: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    confidentiality: ConfidentialityLevel = ConfidentialityLevel.RESTRICTED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_hash: str = ""  # computed after creation
    # M15/1505: Genesis binding hash for dual-binding signing
    genesis_binding_hash: str = Field(
        default="",
        description="Hash binding this trace to the trust chain genesis record",
    )

    # --- Size limits ---
    _MAX_DECISION_LENGTH: int = 10_000
    _MAX_RATIONALE_LENGTH: int = 50_000
    _MAX_ALTERNATIVES_COUNT: int = 100
    _MAX_EVIDENCE_COUNT: int = 100

    def model_post_init(self, __context: object) -> None:
        """Validate size limits, auto-compute reasoning, then compute hash."""
        # --- Size validation (before any derived computation) ---
        self._validate_size_limits()

        # If reasoning is empty but decision/rationale are set, compose it
        if not self.reasoning and (self.decision or self.rationale):
            parts: list[str] = []
            if self.decision:
                parts.append(f"Decision: {self.decision}")
            if self.rationale:
                parts.append(f"Rationale: {self.rationale}")
            self.reasoning = ". ".join(parts)
        if not self.trace_hash:
            self.trace_hash = self.compute_hash()

    def _validate_size_limits(self) -> None:
        """Validate field size limits and raise ValueError with clear context on violation."""
        if len(self.decision) > self._MAX_DECISION_LENGTH:
            raise ValueError(
                f"decision exceeds maximum length: "
                f"{len(self.decision)} characters > {self._MAX_DECISION_LENGTH} limit"
            )
        if len(self.rationale) > self._MAX_RATIONALE_LENGTH:
            raise ValueError(
                f"rationale exceeds maximum length: "
                f"{len(self.rationale)} characters > {self._MAX_RATIONALE_LENGTH} limit"
            )
        if len(self.alternatives_considered) > self._MAX_ALTERNATIVES_COUNT:
            raise ValueError(
                f"alternatives_considered exceeds maximum count: "
                f"{len(self.alternatives_considered)} items > {self._MAX_ALTERNATIVES_COUNT} limit"
            )
        if len(self.evidence) > self._MAX_EVIDENCE_COUNT:
            raise ValueError(
                f"evidence exceeds maximum count: "
                f"{len(self.evidence)} items > {self._MAX_EVIDENCE_COUNT} limit"
            )

    def compute_hash(self) -> str:
        """Compute full SHA-256 content hash for integrity verification.

        The hash covers the trace ID, parent record, reasoning content,
        confidentiality level, and genesis binding hash. Any change to
        these fields will produce a different hash, enabling tamper detection.

        Uses full 64-character hex digest (not truncated) for cryptographic
        integrity per EATP spec requirements.

        M15/1505: Now includes genesis_binding_hash in the content to ensure
        dual-binding integrity.
        """
        content = (
            f"{self.trace_id}:{self.parent_record_type}:{self.parent_record_id}"
            f":{self.reasoning}:{self.confidentiality.value}"
            f":{self.genesis_binding_hash}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify trace hasn't been tampered with.

        Recomputes the hash from current field values and compares
        against the stored hash using timing-safe comparison to prevent
        timing side-channel attacks. Returns False if any field has been
        modified since the hash was computed.
        """
        computed = self.compute_hash()
        return hmac.compare_digest(self.trace_hash, computed)

    def redact(self, viewer_level: ConfidentialityLevel) -> ReasoningTrace:
        """Return a copy with reasoning redacted if viewer lacks clearance.

        If the viewer's clearance level is strictly below the trace's
        confidentiality level, the reasoning is replaced with '[REDACTED]'.
        Otherwise the full trace is returned as a copy.
        """
        viewer_order = _CONFIDENTIALITY_ORDER[viewer_level]
        trace_order = _CONFIDENTIALITY_ORDER[self.confidentiality]

        if viewer_order < trace_order:
            return self.model_copy(update={"reasoning": "[REDACTED]"})
        return self.model_copy()

    def to_signing_payload(self) -> bytes:
        """Serialize trace to canonical JSON (RFC 8785) for Ed25519 signing.

        Includes the immutable identity and content fields that define this
        trace. Excludes ``trace_hash`` (derived) and mutable display fields.

        Returns:
            Canonical JSON bytes suitable for signing.
        """
        payload = {
            "confidentiality": self.confidentiality.value,
            "created_at": self.created_at.isoformat(),
            "decision": self.decision,
            "genesis_binding_hash": self.genesis_binding_hash,
            "parent_record_id": self.parent_record_id,
            "parent_record_type": self.parent_record_type,
            "rationale": self.rationale,
            "trace_id": self.trace_id,
        }
        return canonical_serialize(payload)

    # --- Factory class methods ---

    @classmethod
    def create_delegation_trace(
        cls,
        delegator_id: str,
        delegatee_id: str,
        capabilities: list[str],
        constraints: list[str] | None = None,
        rationale: str = "",
    ) -> ReasoningTrace:
        """Factory for DELEGATE operation traces.

        Args:
            delegator_id: ID of the entity delegating trust.
            delegatee_id: ID of the entity receiving trust.
            capabilities: List of capabilities being delegated.
            constraints: Optional list of constraints on the delegation.
            rationale: Why the delegation is being made.

        Returns:
            A new ReasoningTrace with delegation-specific fields populated.
        """
        return cls(
            parent_record_type="delegation",
            parent_record_id=f"deleg-{delegator_id}-{delegatee_id}",
            decision=f"Delegate capabilities [{', '.join(capabilities)}] from {delegator_id} to {delegatee_id}",
            rationale=rationale,
            confidence=0.9,
            evidence=[f"constraint:{c}" for c in constraints] if constraints else [],
        )

    @classmethod
    def create_posture_trace(
        cls,
        agent_id: str,
        from_posture: str,
        to_posture: str,
        trigger: str,
        evidence: list[str] | None = None,
    ) -> ReasoningTrace:
        """Factory for posture transition traces.

        Args:
            agent_id: ID of the agent whose posture is changing.
            from_posture: Current posture name.
            to_posture: Target posture name.
            trigger: What triggered the posture change.
            evidence: Optional supporting evidence for the change.

        Returns:
            A new ReasoningTrace with posture-change-specific fields populated.
        """
        # Confidence depends on trigger type: automated triggers get higher
        # confidence than manual overrides since they are policy-driven.
        trigger_confidence = {
            "threshold_met": 0.95,
            "policy_rule": 0.9,
            "manual_override": 0.7,
        }
        confidence = trigger_confidence.get(trigger, 0.8)

        return cls(
            parent_record_type="posture_change",
            parent_record_id=f"posture-{agent_id}",
            decision=f"Change posture from {from_posture} to {to_posture}",
            rationale=f"Triggered by: {trigger}",
            confidence=confidence,
            evidence=evidence if evidence is not None else [],
        )

    @classmethod
    def create_verification_trace(
        cls,
        agent_id: str,
        action: str,
        result: str,
        level: str,
    ) -> ReasoningTrace:
        """Factory for VERIFY operation traces.

        Args:
            agent_id: ID of the agent being verified.
            action: The action that was verified.
            result: Verification result (e.g. 'approved', 'denied').
            level: Verification gradient level (e.g. 'AUTO_APPROVED', 'BLOCKED').

        Returns:
            A new ReasoningTrace with verification-specific fields populated.
        """
        return cls(
            parent_record_type="verification",
            parent_record_id=f"verify-{agent_id}-{action}",
            decision=f"Verification of '{action}' by agent '{agent_id}': {result}",
            rationale=f"Verification level: {level}",
            confidence=1.0,
        )


class ReasoningTraceStore(BaseModel):
    """Store for reasoning traces with confidentiality-aware retrieval.

    Provides methods to add traces, retrieve them by parent record,
    and export them with appropriate redaction based on viewer clearance.

    Args:
        maxlen: Maximum number of traces to retain. When exceeded, the oldest
                10% are trimmed. Default: 10,000.
    """

    traces: list[ReasoningTrace] = Field(default_factory=list)
    maxlen: int = 10_000

    def add(self, trace: ReasoningTrace) -> None:
        """Add a reasoning trace to the store."""
        self.traces.append(trace)
        if len(self.traces) > self.maxlen:
            trim_count = max(1, self.maxlen // 10)
            self.traces = self.traces[trim_count:]

    def get_for_record(self, record_id: str) -> list[ReasoningTrace]:
        """Get all traces for a parent record, regardless of confidentiality."""
        return [t for t in self.traces if t.parent_record_id == record_id]

    def get_with_clearance(
        self,
        record_id: str,
        viewer_level: ConfidentialityLevel,
    ) -> list[ReasoningTrace]:
        """Get traces for a record, redacted to the viewer's clearance level.

        All traces for the record are returned, but those above the viewer's
        clearance level will have their reasoning replaced with '[REDACTED]'.
        """
        raw = self.get_for_record(record_id)
        return [t.redact(viewer_level) for t in raw]

    def export(
        self,
        *,
        viewer_level: ConfidentialityLevel = ConfidentialityLevel.PUBLIC,
        parent_type: str | None = None,
    ) -> list[dict]:
        """Export traces as dicts with appropriate redaction.

        Args:
            viewer_level: The clearance level of the viewer. Traces above
                this level will have reasoning redacted.
            parent_type: Optional filter to only include traces for a
                specific parent record type (e.g., 'delegation', 'audit_anchor').

        Returns:
            List of trace dictionaries with redaction applied.
        """
        filtered = self.traces
        if parent_type is not None:
            filtered = [t for t in filtered if t.parent_record_type == parent_type]

        redacted = [t.redact(viewer_level) for t in filtered]
        return [t.model_dump(mode="json") for t in redacted]
