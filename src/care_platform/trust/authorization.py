# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Authorization check — separates authorization from capability.

An agent must pass BOTH checks to perform an action:
- **Authorization**: Constraint envelope check ("is this agent permitted?")
- **Capability**: Attestation check ("can this agent do this?")

This separation provides clear error messages distinguishing "not authorized"
(the constraint envelope blocks the action) from "not capable" (the agent's
attestation does not include the required capability).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from care_platform.constraint.envelope import ConstraintEnvelope
    from care_platform.trust.attestation import CapabilityAttestation

logger = logging.getLogger(__name__)


class AuthorizationResult(BaseModel):
    """Result of evaluating both authorization and capability.

    Attributes:
        authorized: True if the constraint envelope permits the action.
        capable: True if the agent's attestation includes the capability.
        denial_reason: Human-readable explanation when action is denied.
    """

    authorized: bool
    capable: bool
    denial_reason: str = ""

    @property
    def permitted(self) -> bool:
        """True only when both authorized and capable are True."""
        return self.authorized and self.capable


class AuthorizationCheck:
    """Evaluates both authorization (envelope) and capability (attestation).

    Both checks must pass for an action to proceed. Provides clear error
    messages distinguishing "not authorized" from "not capable".

    Args:
        envelope: The constraint envelope governing the agent.
        attestation: The agent's capability attestation.

    Raises:
        ValueError: If envelope or attestation is None.
    """

    def __init__(
        self,
        envelope: ConstraintEnvelope,
        attestation: CapabilityAttestation,
    ) -> None:
        if envelope is None:
            raise ValueError(
                "envelope is required and must not be None. "
                "Authorization checks require a constraint envelope to verify "
                "whether the agent is permitted to perform actions."
            )
        if attestation is None:
            raise ValueError(
                "attestation is required and must not be None. "
                "Authorization checks require a capability attestation to verify "
                "whether the agent has the required capabilities."
            )
        self._envelope = envelope
        self._attestation = attestation

    def evaluate(self, action: str, agent_id: str) -> AuthorizationResult:
        """Evaluate both authorization and capability for an action.

        Args:
            action: The action being attempted.
            agent_id: The agent attempting the action.

        Returns:
            An AuthorizationResult indicating whether the action is permitted,
            with clear denial reasons when it is not.
        """
        # Check authorization: does the constraint envelope permit this action?
        envelope_eval = self._envelope.evaluate_action(
            action=action,
            agent_id=agent_id,
        )
        authorized = envelope_eval.is_allowed or envelope_eval.is_near_boundary

        # Check capability: does the attestation include this capability?
        capable = self._attestation.has_capability(action)

        # Build denial reason
        denial_parts: list[str] = []
        if not authorized:
            denial_parts.append(
                f"Authorization denied: agent '{agent_id}' is not authorized "
                f"to perform action '{action}' per constraint envelope "
                f"'{self._envelope.id}'"
            )
        if not capable:
            if not self._attestation.is_valid:
                denial_parts.append(
                    f"Capability denied: agent '{agent_id}' attestation is not valid "
                    f"(revoked={self._attestation.revoked}, expired={self._attestation.is_expired})"
                )
            else:
                denial_parts.append(
                    f"Capability denied: agent '{agent_id}' is not capable of "
                    f"action '{action}' per attestation '{self._attestation.attestation_id}'. "
                    f"Available capabilities: {self._attestation.capabilities}"
                )

        denial_reason = "; ".join(denial_parts)

        if denial_reason:
            logger.info(
                "AuthorizationCheck: action=%s agent=%s authorized=%s capable=%s reason=%s",
                action,
                agent_id,
                authorized,
                capable,
                denial_reason,
            )

        return AuthorizationResult(
            authorized=authorized,
            capable=capable,
            denial_reason=denial_reason,
        )
