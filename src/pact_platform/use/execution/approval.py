# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Human approval queue — actions held for human decision.

When the verification gradient determines an action must be HELD,
it enters this queue for a human to approve, reject, or let expire.
Supports urgency-based sorting, batch operations, and capacity metrics.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QueueOverflowError(RuntimeError):
    """Raised when the approval queue exceeds its maximum depth.

    This protects against unbounded queue growth. When the pending queue
    reaches max_queue_depth (after lazy expiry), further submissions are
    rejected until existing actions are resolved.
    """


class UrgencyLevel(str, Enum):
    """How urgently an approval is needed."""

    IMMEDIATE = "immediate"
    STANDARD = "standard"
    BATCH = "batch"  # can be batched with similar items


# Urgency priority: lower number = higher priority (sorted first)
_URGENCY_PRIORITY: dict[UrgencyLevel, int] = {
    UrgencyLevel.IMMEDIATE: 0,
    UrgencyLevel.STANDARD: 1,
    UrgencyLevel.BATCH: 2,
}


class PendingAction(BaseModel):
    """An action held for human approval."""

    action_id: str = Field(default_factory=lambda: f"pa-{uuid4().hex[:8]}")
    agent_id: str
    team_id: str = ""
    action: str
    resource: str = ""
    reason: str  # why it was held
    constraint_details: dict = Field(default_factory=dict)
    urgency: UrgencyLevel = UrgencyLevel.STANDARD
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "pending"  # pending, approved, rejected, expired
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_reason: str = ""


class ApprovalQueue:
    """Queue for actions requiring human approval.

    Actions are submitted by the constraint enforcement layer when the
    verification gradient evaluates to HELD. Humans approve or reject
    them, or they expire after a configurable timeout.

    RT-10 enhancements:
    - Lazy expiry: _check_expiry() is called at the start of submit(),
      pending, approve(), and reject() to automatically expire stale actions.
    - Queue overflow protection: max_queue_depth prevents unbounded growth.
    - oldest_pending_age_seconds() for monitoring.
    """

    def __init__(
        self,
        authorized_approvers: set[str] | None = None,
        max_queue_depth: int = 100,
        max_resolved_history: int = 10000,
        on_expire: Callable[[PendingAction], None] | None = None,
    ) -> None:
        self._lock = threading.Lock()  # RT9-03: thread-safe queue access
        self._pending: list[PendingAction] = []
        self._resolved: deque[PendingAction] = deque(maxlen=max_resolved_history)
        # None = no restriction (backward compat)
        # empty set = no one can approve
        # populated set = only those identities can approve
        self._authorized_approvers: set[str] | None = authorized_approvers
        self.max_queue_depth: int = max_queue_depth
        # RT2-35: Optional callback invoked for each expired action (e.g., audit recording)
        self._on_expire: Callable[[PendingAction], None] | None = on_expire

    def _check_expiry(self) -> None:
        """Lazily expire old pending actions.

        Called at the start of submit(), pending, approve(), and reject()
        to ensure stale actions are cleaned up automatically without
        requiring manual calls to expire_old().
        """
        self.expire_old()

    def _check_approver_authorization(self, approver_id: str) -> None:
        """Validate that approver_id is in the authorized set, if configured.

        Raises:
            PermissionError: If authorized_approvers is set and approver_id is not in it.
        """
        if self._authorized_approvers is not None:
            if approver_id not in self._authorized_approvers:
                raise PermissionError(
                    f"Approver '{approver_id}' is not in the authorized approvers set"
                )

    def _check_self_approval(self, approver_id: str, pending_action: PendingAction) -> None:
        """Validate that the approver is not the same agent that submitted the action.

        Raises:
            PermissionError: If approver_id matches the agent that submitted the action.
        """
        if approver_id == pending_action.agent_id:
            raise PermissionError("Self-approval is not permitted")

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
        """Submit an action for approval.

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

        Raises:
            QueueOverflowError: If the queue is at max_queue_depth after
                lazy expiry.
        """
        pa = PendingAction(
            agent_id=agent_id,
            action=action,
            reason=reason,
            team_id=team_id,
            resource=resource,
            urgency=urgency,
            constraint_details=constraint_details if constraint_details is not None else {},
        )
        with self._lock:
            self._check_expiry()
            if len(self._pending) >= self.max_queue_depth:
                raise QueueOverflowError(
                    f"Approval queue overflow: {len(self._pending)} pending actions "
                    f"at max depth of {self.max_queue_depth}. Resolve existing actions "
                    f"before submitting new ones."
                )
            self._pending.append(pa)
        logger.info(
            "Action submitted for approval: action_id=%s agent=%s action=%s urgency=%s",
            pa.action_id,
            agent_id,
            action,
            urgency.value,
        )
        return pa

    def _find_pending(self, action_id: str) -> PendingAction:
        """Find a pending action by ID, raising ValueError if not found or not pending."""
        for pa in self._pending:
            if pa.action_id == action_id:
                return pa
        # Check if it exists in resolved (already decided)
        for pa in self._resolved:
            if pa.action_id == action_id:
                raise ValueError(
                    f"Action '{action_id}' is not pending (current status: {pa.status})"
                )
        raise ValueError(f"Action '{action_id}' not found in approval queue")

    def approve(self, action_id: str, approver_id: str, reason: str = "") -> PendingAction:
        """Approve a pending action.

        Args:
            action_id: The action to approve.
            approver_id: Who is approving.
            reason: Optional reason for approval.

        Returns:
            The approved PendingAction.

        Raises:
            ValueError: If action_id is not found or not pending.
            PermissionError: If approver is not authorized or is self-approving.
        """
        with self._lock:
            self._check_expiry()
            pa = self._find_pending(action_id)
            self._check_approver_authorization(approver_id)
            self._check_self_approval(approver_id, pa)
            pa.status = "approved"
            pa.decided_by = approver_id
            pa.decided_at = datetime.now(UTC)
            pa.decision_reason = reason
            self._pending.remove(pa)
            self._resolved.append(pa)
        logger.info("Action approved: action_id=%s approver=%s", action_id, approver_id)
        return pa

    def reject(self, action_id: str, approver_id: str, reason: str = "") -> PendingAction:
        """Reject a pending action.

        Self-rejection is allowed (conservative direction), but authorization
        checks still apply.

        Args:
            action_id: The action to reject.
            approver_id: Who is rejecting.
            reason: Optional reason for rejection.

        Returns:
            The rejected PendingAction.

        Raises:
            ValueError: If action_id is not found or not pending.
            PermissionError: If approver is not authorized.
        """
        with self._lock:
            self._check_expiry()
            pa = self._find_pending(action_id)
            self._check_approver_authorization(approver_id)
            # Note: self-rejection is allowed (conservative direction)
            pa.status = "rejected"
            pa.decided_by = approver_id
            pa.decided_at = datetime.now(UTC)
            pa.decision_reason = reason
            self._pending.remove(pa)
            self._resolved.append(pa)
        logger.info(
            "Action rejected: action_id=%s approver=%s reason=%s",
            action_id,
            approver_id,
            reason,
        )
        return pa

    def batch_approve(self, action_ids: list[str], approver_id: str) -> list[PendingAction]:
        """Approve multiple actions at once.

        All authorization and self-approval checks are performed BEFORE any
        actions are approved. If any check fails, no actions are modified.

        Args:
            action_ids: List of action IDs to approve.
            approver_id: Who is approving.

        Returns:
            List of approved PendingActions.

        Raises:
            ValueError: If any action_id is not found or not pending.
            PermissionError: If approver is not authorized or is self-approving any action.
        """
        if not action_ids:
            return []

        with self._lock:
            # Validate all IDs exist and are pending before approving any
            actions_to_approve: list[PendingAction] = []
            for action_id in action_ids:
                pa = self._find_pending(action_id)
                actions_to_approve.append(pa)

            # Check authorization and self-approval for ALL actions before modifying any
            self._check_approver_authorization(approver_id)
            for pa in actions_to_approve:
                self._check_self_approval(approver_id, pa)

            # All validated, now approve them
            results: list[PendingAction] = []
            now = datetime.now(UTC)
            for pa in actions_to_approve:
                pa.status = "approved"
                pa.decided_by = approver_id
                pa.decided_at = now
                self._pending.remove(pa)
                self._resolved.append(pa)
                results.append(pa)

        logger.info("Batch approved %d actions by approver=%s", len(results), approver_id)
        return results

    @property
    def pending(self) -> list[PendingAction]:
        """Get all pending actions, sorted by urgency (immediate first) then submission time."""
        with self._lock:
            self._check_expiry()
            return sorted(
                self._pending,
                key=lambda pa: (_URGENCY_PRIORITY.get(pa.urgency, 99), pa.submitted_at),
            )

    @property
    def queue_depth(self) -> int:
        """Number of pending items."""
        with self._lock:
            return len(self._pending)

    def get_capacity_metrics(self) -> dict:
        """Track approval load: pending count, resolved count, average resolution time.

        Returns:
            Dictionary with capacity metrics.
        """
        resolved_times: list[float] = []
        for pa in self._resolved:
            if pa.decided_at is not None:
                delta = (pa.decided_at - pa.submitted_at).total_seconds()
                resolved_times.append(delta)

        avg_resolution_seconds = (
            sum(resolved_times) / len(resolved_times) if resolved_times else 0.0
        )

        return {
            "pending_count": len(self._pending),
            "resolved_count": len(self._resolved),
            "avg_resolution_seconds": avg_resolution_seconds,
        }

    def oldest_pending_age_seconds(self) -> float:
        """Get the age in seconds of the oldest pending action.

        Returns:
            Age in seconds, or 0.0 if the queue is empty.
        """
        if not self._pending:
            return 0.0
        oldest = min(self._pending, key=lambda pa: pa.submitted_at)
        return (datetime.now(UTC) - oldest.submitted_at).total_seconds()

    def expire_old(self, max_age_hours: int = 48) -> list[PendingAction]:
        """Expire actions older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before an action expires.

        Returns:
            List of expired PendingActions.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        expired: list[PendingAction] = []
        still_pending: list[PendingAction] = []
        callbacks: list[PendingAction] = []

        # Note: when called from submit/approve/reject, the lock is already held.
        # When called directly, we need the lock. Use reentrant pattern or
        # document that _check_expiry is always called under lock.
        for pa in self._pending:
            if pa.submitted_at < cutoff:
                pa.status = "expired"
                pa.decided_at = datetime.now(UTC)
                expired.append(pa)
                self._resolved.append(pa)
                logger.info(
                    "Action expired: action_id=%s agent=%s (age > %dh)",
                    pa.action_id,
                    pa.agent_id,
                    max_age_hours,
                )
                if self._on_expire is not None:
                    callbacks.append(pa)
            else:
                still_pending.append(pa)

        self._pending = still_pending

        # RT9-03: Fire callbacks outside lock (they may do I/O)
        for pa in callbacks:
            if self._on_expire is not None:
                self._on_expire(pa)

        return expired
