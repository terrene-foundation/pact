# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Approver authentication — cryptographic identity verification for approval decisions.

When the verification gradient determines an action must be HELD, it enters the
ApprovalQueue for a human to approve or reject. Previously, any string could be
passed as approver_id with no authentication. This module adds Ed25519 cryptographic
identity verification so that:

1. Each approver is registered with their Ed25519 public key (ApproverRegistry).
2. Approval/rejection decisions are signed by the approver's private key (sign_decision).
3. Signatures are verified against the registered public key (verify_decision).
4. AuthenticatedApprovalQueue wraps the existing ApprovalQueue, enforcing that
   every approve/reject call carries a valid signed decision.

Follows the same Ed25519 patterns as pact.trust.constraint.signing.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel, Field

from pact_platform.trust._compat import canonical_serialize
from pact_platform.use.execution.approval import ApprovalQueue, PendingAction, UrgencyLevel

if TYPE_CHECKING:
    from pact_platform.trust.audit.anchor import AuditChain

logger = logging.getLogger(__name__)

# Valid decision values
_VALID_DECISIONS = frozenset({"approved", "rejected"})

# Expected Ed25519 public key length in bytes
_ED25519_PUBLIC_KEY_LENGTH = 32


def _serialize_decision_for_signing(
    action_id: str, decision: str, reason: str, nonce: str, signed_at: str
) -> bytes:
    """Create a canonical byte representation of the decision for signing.

    RT4-H10: The payload covers action_id, decision, reason, nonce, and
    signed_at -- any modification to these fields after signing will be
    detected by verification.

    RT13-H3 / M15/1504: Migrated from json.dumps(sort_keys=True) to JCS
    canonical_serialize for consistency with constraint signing and audit
    anchor signing across the platform.

    Args:
        action_id: The pending action being decided on.
        decision: Either 'approved' or 'rejected'.
        reason: The human-readable reason for the decision.
        nonce: Unique nonce to prevent replay attacks.
        signed_at: ISO 8601 timestamp of when the decision was signed.

    Returns:
        Deterministic UTF-8 bytes suitable for Ed25519 signing.
    """
    signable = {
        "action_id": action_id,
        "decision": decision,
        "nonce": nonce,
        "reason": reason,
        "signed_at": signed_at,
    }
    return canonical_serialize(signable)


class SignedDecision(BaseModel):
    """An approval or rejection decision with Ed25519 cryptographic signature.

    RT4-H10: The signature covers action_id + decision + reason + nonce +
    signed_at. Any tampering with these fields after signing is detectable
    via verify_decision().
    """

    action_id: str = Field(description="The pending action this decision applies to")
    decision: str = Field(description="Either 'approved' or 'rejected'")
    reason: str = Field(description="Human-readable reason for the decision")
    signature: str = Field(description="Hex-encoded Ed25519 signature")
    signed_at: datetime = Field(description="When the decision was signed")
    nonce: str = Field(description="Unique nonce for replay protection (RT4-H10)")


def sign_decision(
    private_key: bytes,
    action_id: str,
    decision: str,
    reason: str,
) -> SignedDecision:
    """Sign an approval/rejection decision with Ed25519.

    RT4-H10: Generates a unique nonce and includes both the nonce and
    signed_at timestamp in the signed payload for replay protection.

    Args:
        private_key: Raw Ed25519 private key bytes (32 bytes).
        action_id: The pending action being decided on.
        decision: Must be 'approved' or 'rejected'.
        reason: Human-readable reason for the decision.

    Returns:
        A SignedDecision with the computed Ed25519 signature.

    Raises:
        ValueError: If decision is not 'approved' or 'rejected', or if the
            private key is invalid.
    """
    if decision not in _VALID_DECISIONS:
        raise ValueError(
            f"Invalid decision '{decision}': must be one of {sorted(_VALID_DECISIONS)}"
        )

    nonce = uuid.uuid4().hex
    signed_at = datetime.now(UTC)

    payload = _serialize_decision_for_signing(
        action_id, decision, reason, nonce, signed_at.isoformat()
    )

    try:
        priv = Ed25519PrivateKey.from_private_bytes(private_key)
    except Exception as exc:
        msg = f"Invalid Ed25519 private key: {exc}"
        raise ValueError(msg) from exc

    try:
        signature_bytes = priv.sign(payload)
    finally:
        # RT11-L5 / RT13: Remove reference to private key object after use
        del priv

    return SignedDecision(
        action_id=action_id,
        decision=decision,
        reason=reason,
        signature=signature_bytes.hex(),
        signed_at=signed_at,
        nonce=nonce,
    )


def verify_decision(public_key: bytes, signed_decision: SignedDecision) -> bool:
    """Verify a signed decision against an Ed25519 public key.

    RT4-H10: Recomputes the canonical payload from action_id + decision +
    reason + nonce + signed_at and checks the signature.  Returns False if
    the signature is invalid, the key is wrong, or any field was tampered
    with after signing.

    Args:
        public_key: Raw Ed25519 public key bytes (32 bytes).
        signed_decision: The signed decision to verify.

    Returns:
        True if the signature is valid for the current content, False otherwise.
    """
    try:
        pub = Ed25519PublicKey.from_public_bytes(public_key)
        payload = _serialize_decision_for_signing(
            signed_decision.action_id,
            signed_decision.decision,
            signed_decision.reason,
            signed_decision.nonce,
            signed_decision.signed_at.isoformat(),
        )
        signature_bytes = bytes.fromhex(signed_decision.signature)
        pub.verify(signature_bytes, payload)
        return True
    except Exception:
        logger.debug(
            "Decision signature verification failed for action_id='%s'",
            signed_decision.action_id,
        )
        return False


class ApproverRegistry:
    """Maps approver identities to their Ed25519 public keys.

    Each approver must be registered before they can sign decisions that
    the AuthenticatedApprovalQueue will accept.
    """

    def __init__(self) -> None:
        self._approvers: dict[str, bytes] = {}
        self._lock = threading.Lock()  # RT7-05: thread-safe registry access

    def register(self, approver_id: str, public_key: bytes) -> None:
        """Register an approver with their Ed25519 public key.

        Args:
            approver_id: Unique identifier for the approver.
            public_key: Raw Ed25519 public key bytes (32 bytes).

        Raises:
            ValueError: If the approver_id is already registered or the
                public key is not valid Ed25519 (32 bytes).
        """
        # Validate the key before acquiring the lock (no need to hold the lock
        # during potentially expensive crypto validation)
        if len(public_key) != _ED25519_PUBLIC_KEY_LENGTH:
            raise ValueError(
                f"Invalid Ed25519 public key: expected {_ED25519_PUBLIC_KEY_LENGTH} bytes, "
                f"got {len(public_key)} bytes"
            )
        try:
            Ed25519PublicKey.from_public_bytes(public_key)
        except Exception as exc:
            raise ValueError(f"Invalid Ed25519 public key: {exc}") from exc

        with self._lock:
            if approver_id in self._approvers:
                raise ValueError(
                    f"Approver '{approver_id}' is already registered. "
                    "Remove the existing registration first."
                )
            self._approvers[approver_id] = public_key
        logger.info("Registered approver '%s'", approver_id)

    def remove(self, approver_id: str) -> None:
        """Remove an approver from the registry.

        Args:
            approver_id: The approver to remove.

        Raises:
            KeyError: If the approver_id is not registered.
        """
        with self._lock:
            if approver_id not in self._approvers:
                raise KeyError(f"Approver '{approver_id}' is not registered and cannot be removed")
            del self._approvers[approver_id]
        logger.info("Removed approver '%s'", approver_id)

    def get_public_key(self, approver_id: str) -> bytes:
        """Retrieve the public key for an approver.

        Args:
            approver_id: The approver to look up.

        Returns:
            Raw Ed25519 public key bytes (32 bytes).

        Raises:
            KeyError: If the approver_id is not registered.
        """
        with self._lock:
            if approver_id not in self._approvers:
                raise KeyError(
                    f"Approver '{approver_id}' is not registered in the approver registry"
                )
            return self._approvers[approver_id]

    def list_approver_ids(self) -> list[str]:
        """Return a list of all registered approver IDs.

        Returns:
            Sorted list of approver ID strings.
        """
        with self._lock:
            return sorted(self._approvers.keys())

    def __contains__(self, approver_id: str) -> bool:
        """Check if an approver is registered.

        Args:
            approver_id: The approver to check.

        Returns:
            True if the approver_id is in the registry.
        """
        with self._lock:
            return approver_id in self._approvers


class AuthenticatedApprovalQueue:
    """Wraps an ApprovalQueue with cryptographic identity verification.

    Every approve() and reject() call must include a SignedDecision that:
    1. Was signed by a registered approver (checked via ApproverRegistry).
    2. Has a valid Ed25519 signature (tamper detection).
    3. Matches the action_id and decision type being requested.
    4. Has a fresh, unique nonce (RT4-H10 replay protection).

    The underlying ApprovalQueue is NOT modified — this is purely a wrapper.
    submit() and pending are delegated directly to the inner queue.
    """

    def __init__(
        self,
        queue: ApprovalQueue,
        registry: ApproverRegistry,
        *,
        max_decision_age_seconds: int = 300,
        audit_chain: AuditChain | None = None,
    ) -> None:
        """Initialize with an existing ApprovalQueue and ApproverRegistry.

        Args:
            queue: The underlying approval queue to wrap.
            registry: The approver registry for public key lookups.
            max_decision_age_seconds: Maximum age of a signed decision before
                it is rejected as stale (RT4-H10). Default: 5 minutes.
            audit_chain: Optional audit chain for recording approval decisions
                (RT4-L2). When provided, every approve/reject is recorded.
        """
        self._queue = queue
        self._registry = registry
        self._max_decision_age_seconds = max_decision_age_seconds
        self._used_nonces: dict[str, datetime] = {}
        # RT6-03: Thread-safe nonce access — protects _used_nonces from
        # concurrent check/write races in multi-threaded runtimes.
        self._nonce_lock = threading.Lock()
        self._audit_chain = audit_chain

    def submit(
        self,
        agent_id: str,
        action: str,
        reason: str,
        team_id: str = "",
        resource: str = "",
        urgency: UrgencyLevel = UrgencyLevel.STANDARD,
        constraint_details: dict | None = None,
    ) -> PendingAction:
        """Submit an action for approval (delegates to inner queue).

        No authentication is required for submission — only for decisions.

        Args:
            agent_id: The agent requesting approval.
            action: The action being requested.
            reason: Why this action was held for approval.
            team_id: The team the agent belongs to.
            resource: The resource targeted by the action.
            urgency: How urgently approval is needed.
            constraint_details: Additional constraint context.

        Returns:
            The newly created PendingAction.
        """
        return self._queue.submit(
            agent_id=agent_id,
            action=action,
            reason=reason,
            team_id=team_id,
            resource=resource,
            urgency=urgency,
            constraint_details=constraint_details,
        )

    @property
    def pending(self) -> list[PendingAction]:
        """Get all pending actions (delegates to inner queue)."""
        return self._queue.pending

    def approve(
        self,
        action_id: str,
        approver_id: str,
        signed_decision: SignedDecision,
        reason: str = "",
    ) -> PendingAction:
        """Approve a pending action with cryptographic verification.

        Args:
            action_id: The action to approve.
            approver_id: Who is approving (must be registered in the registry).
            signed_decision: The cryptographically signed decision.
            reason: Optional additional reason (the signed reason takes precedence).

        Returns:
            The approved PendingAction.

        Raises:
            PermissionError: If the approver is not registered, signature
                verification fails, nonce is reused, or decision is too old.
            ValueError: If the signed decision's action_id or decision type
                does not match the request.
        """
        self._verify_signed_decision(
            action_id=action_id,
            approver_id=approver_id,
            signed_decision=signed_decision,
            expected_decision="approved",
        )
        effective_reason = reason if reason else signed_decision.reason
        result = self._queue.approve(action_id, approver_id, effective_reason)

        # RT4-L2: Record in audit chain if configured
        self._record_decision_audit(approver_id, action_id, signed_decision, effective_reason)

        return result

    def reject(
        self,
        action_id: str,
        approver_id: str,
        signed_decision: SignedDecision,
        reason: str = "",
    ) -> PendingAction:
        """Reject a pending action with cryptographic verification.

        Args:
            action_id: The action to reject.
            approver_id: Who is rejecting (must be registered in the registry).
            signed_decision: The cryptographically signed decision.
            reason: Optional additional reason (the signed reason takes precedence).

        Returns:
            The rejected PendingAction.

        Raises:
            PermissionError: If the approver is not registered, signature
                verification fails, nonce is reused, or decision is too old.
            ValueError: If the signed decision's action_id or decision type
                does not match the request.
        """
        self._verify_signed_decision(
            action_id=action_id,
            approver_id=approver_id,
            signed_decision=signed_decision,
            expected_decision="rejected",
        )
        effective_reason = reason if reason else signed_decision.reason
        result = self._queue.reject(action_id, approver_id, effective_reason)

        # RT4-L2: Record in audit chain if configured
        self._record_decision_audit(approver_id, action_id, signed_decision, effective_reason)

        return result

    def _verify_signed_decision(
        self,
        action_id: str,
        approver_id: str,
        signed_decision: SignedDecision,
        expected_decision: str,
    ) -> None:
        """Verify a signed decision before allowing it to proceed.

        Checks:
        1. approver_id is registered in the registry.
        2. signed_decision.action_id matches the requested action_id.
        3. signed_decision.decision matches the expected decision type.
        4. The Ed25519 signature is valid against the registered public key.
        5. RT4-H10: Nonce has not been used before (replay protection).
        6. RT4-H10: Decision is not too old (freshness check).

        Args:
            action_id: The action being decided on.
            approver_id: The claimed approver identity.
            signed_decision: The signed decision to verify.
            expected_decision: 'approved' or 'rejected'.

        Raises:
            PermissionError: If the approver is not registered, signature fails,
                nonce is replayed, or decision is stale.
            ValueError: If action_id or decision type does not match.
        """
        # 1. Check approver is registered (RT7-05: atomic lookup avoids
        #    TOCTOU race between __contains__ and get_public_key)
        try:
            public_key = self._registry.get_public_key(approver_id)
        except KeyError:
            raise PermissionError(
                f"Approver '{approver_id}' is not registered in the approver registry"
            )

        # 2. Check action_id matches
        if signed_decision.action_id != action_id:
            raise ValueError(
                f"Signed decision action_id mismatch: signed for "
                f"'{signed_decision.action_id}' but approving '{action_id}'"
            )

        # 3. Check decision type matches
        if signed_decision.decision != expected_decision:
            raise ValueError(
                f"Signed decision mismatch: signed as '{signed_decision.decision}' "
                f"but called {expected_decision}()"
            )

        # 4. Verify cryptographic signature
        if not verify_decision(public_key, signed_decision):
            raise PermissionError(
                f"Approver '{approver_id}' signature verification failed for "
                f"action '{action_id}' — the signature is invalid or the decision "
                f"was tampered with"
            )

        # 5. RT5-05: Reject future-dated signed_at (clock skew or tampering)
        age = (datetime.now(UTC) - signed_decision.signed_at).total_seconds()
        if age < 0:
            raise PermissionError(
                f"Signed decision has a future timestamp ({age:.0f}s ahead — clock skew or tampering)"
            )

        # 5b. RT4-H10: Check decision freshness
        if age > self._max_decision_age_seconds:
            raise PermissionError(
                f"Signed decision is too old ({age:.0f}s > {self._max_decision_age_seconds}s)"
            )

        # 6. RT6-03 + RT4-H10: Thread-safe nonce replay protection.
        # The lock ensures that concurrent _verify_signed_decision() calls
        # cannot race on the nonce check/write, and that eviction is atomic
        # with respect to the check.
        with self._nonce_lock:
            # RT5-16: Evict expired nonces to prevent unbounded growth
            self._evict_expired_nonces()

            if signed_decision.nonce in self._used_nonces:
                raise PermissionError(
                    f"Decision nonce '{signed_decision.nonce}' has already been used "
                    f"(replay detected)"
                )
            self._used_nonces[signed_decision.nonce] = datetime.now(UTC)

        logger.info(
            "Authenticated decision verified: approver='%s' action='%s' decision='%s'",
            approver_id,
            action_id,
            expected_decision,
        )

    def _evict_expired_nonces(self) -> None:
        """RT5-16 / RT13-H2: Remove nonces older than 2x max_decision_age_seconds.

        Nonces older than the freshness window can never be replayed (the
        freshness check rejects them), so they can safely be evicted.

        RT13-H2: Use a 2x safety margin to guard against clock drift — a
        nonce should never be evicted before the freshness check would have
        rejected its associated decision.
        """
        cutoff = datetime.now(UTC) - timedelta(seconds=self._max_decision_age_seconds * 2)
        expired = [n for n, ts in self._used_nonces.items() if ts < cutoff]
        for n in expired:
            del self._used_nonces[n]

    def _record_decision_audit(
        self,
        approver_id: str,
        action_id: str,
        signed_decision: SignedDecision,
        effective_reason: str,
    ) -> None:
        """Record an approval decision in the audit chain (RT4-L2)."""
        if self._audit_chain is None:
            return

        from pact_platform.build.config.schema import VerificationLevel

        self._audit_chain.append(
            agent_id=approver_id,
            action=f"approval_decision:{action_id}",
            verification_level=VerificationLevel.AUTO_APPROVED,
            result=f"{signed_decision.decision}: {effective_reason}",
            metadata={
                "action_id": action_id,
                "decision": signed_decision.decision,
                "nonce": signed_decision.nonce,
            },
        )
