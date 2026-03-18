# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Capability attestation — EATP Trust Lineage Chain Element 4.

A signed declaration of what an agent is authorized to do.
Links an agent's identity to its constraint envelope and capabilities.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field


class CapabilityAttestation(BaseModel):
    """EATP Element 4: A signed declaration of agent capabilities.

    Attests that a specific agent is authorized to perform specific capabilities
    within the bounds of a constraint envelope. Created during delegation and
    verified before every action.
    """

    attestation_id: str = Field(description="Unique attestation identifier")
    agent_id: str = Field(description="Agent this attestation applies to")
    delegation_id: str = Field(description="Delegation record that created this attestation")
    constraint_envelope_id: str = Field(description="Constraint envelope governing this agent")
    capabilities: list[str] = Field(description="Specific capabilities attested")
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = Field(default=None)
    issuer_id: str = Field(description="ID of the authority that issued this attestation")
    revoked: bool = Field(default=False)
    revoked_at: datetime | None = Field(default=None)
    revocation_reason: str | None = Field(default=None)
    signature_hash: str | None = Field(default=None)

    def model_post_init(self, __context: object) -> None:
        if self.expires_at is None:
            self.expires_at = self.issued_at + timedelta(days=90)
        # RT2-28: Populate signature_hash if not already set
        if not self.signature_hash:
            self.signature_hash = self.content_hash()

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired

    def has_capability(self, capability: str) -> bool:
        """Check if this attestation includes a specific capability.

        RT2-10: Returns False if the attestation is not valid (revoked or expired).
        """
        if not self.is_valid:
            return False
        return capability in self.capabilities

    def content_hash(self) -> str:
        """SHA-256 hash of attestation content for integrity verification."""
        content = (
            f"{self.attestation_id}:{self.agent_id}:{self.delegation_id}:"
            f"{self.constraint_envelope_id}:{','.join(sorted(self.capabilities))}:"
            f"{self.issued_at.isoformat()}:{self.issuer_id}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def revoke(self, reason: str) -> None:
        """Revoke this attestation."""
        self.revoked = True
        self.revoked_at = datetime.now(UTC)
        self.revocation_reason = reason

    def has_authorization(self, action: str, envelope: object) -> bool:
        """Check if the agent is both capable and authorized for an action.

        Combines capability check (does the attestation list this capability?)
        with authorization check (does the envelope permit this action?).

        Args:
            action: The action to check.
            envelope: A ConstraintEnvelope instance to check authorization against.

        Returns:
            True if the attestation is valid, the action is in capabilities,
            and the envelope does not deny the action. False otherwise.
        """
        if not self.is_valid:
            return False
        if not self.has_capability(action):
            return False
        # Check envelope authorization
        evaluation = envelope.evaluate_action(action=action, agent_id=self.agent_id)
        # DENIED means the envelope blocks the action
        from care_platform.trust.constraint.envelope import EvaluationResult

        return evaluation.overall_result != EvaluationResult.DENIED

    def verify_consistency(self, envelope_capabilities: list[str]) -> tuple[bool, list[str]]:
        """Verify attestation capabilities are subset of envelope allowed actions.

        Returns (is_consistent, drift_list) where drift_list contains capabilities
        in the attestation but not in the envelope.
        """
        envelope_set = set(envelope_capabilities)
        attestation_set = set(self.capabilities)
        drift = attestation_set - envelope_set
        return len(drift) == 0, list(drift)
