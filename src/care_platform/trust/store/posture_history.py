# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Posture history — append-only store for posture change records
and eligibility checking for posture upgrades.

The history is immutable once written: records can only be appended,
never modified or deleted. This ensures a tamper-evident audit trail
of every posture transition.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from care_platform.trust.posture import UPGRADE_REQUIREMENTS
from care_platform.trust.reasoning import ReasoningTrace  # noqa: F401

logger = logging.getLogger(__name__)

# Minimum days that must pass after a downgrade before an agent can upgrade.
_DOWNGRADE_COOLDOWN_DAYS = 30


class PostureHistoryError(Exception):
    """Raised when append-only invariants of the posture history are violated.

    This includes attempts to directly mutate the internal ``_records`` store
    or any other operation that would break the immutable audit trail.
    """


class PostureChangeTrigger(str, Enum):
    """What caused the posture change.

    Taxonomy of 10 trigger types covering all posture transition scenarios:

    Original 4:
        INCIDENT — security or operational incident
        REVIEW — periodic or ad-hoc review
        SCHEDULED — pre-planned scheduled transition
        CASCADE_REVOCATION — cascade from parent delegation revocation

    Added 6:
        MANUAL — human-initiated posture change (explicit operator action)
        TRUST_SCORE — triggered by automated scoring threshold
        ESCALATION — upward posture change (describes reason, not direction)
        DOWNGRADE — downward posture change not caused by incident
        DRIFT — detected behavioral drift from expected patterns
        APPROVAL — human approval of a pending posture change
    """

    INCIDENT = "incident"
    REVIEW = "review"
    SCHEDULED = "scheduled"
    CASCADE_REVOCATION = "cascade_revocation"
    MANUAL = "manual"
    TRUST_SCORE = "trust_score"
    ESCALATION = "escalation"
    DOWNGRADE = "downgrade"
    DRIFT = "drift"
    APPROVAL = "approval"


class PostureChangeRecord(BaseModel):
    """Record of a posture change (append-only).

    Fields added for enhanced traceability:
    - ``reasoning_trace``: optional structured reasoning for WHY the change was made
    - ``sequence_number``: monotonic sequence assigned by PostureHistoryStore on append
    """

    record_id: str = Field(default_factory=lambda: f"pc-{uuid4().hex[:8]}")
    agent_id: str
    from_posture: str
    to_posture: str
    direction: str  # "upgrade" or "downgrade"
    trigger: PostureChangeTrigger
    changed_by: str
    changed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""
    evidence_ref: str | None = None  # reference to ShadowEnforcer report
    reasoning_trace: ReasoningTrace | None = None  # optional structured reasoning
    sequence_number: int | None = None  # assigned by PostureHistoryStore on append


class EligibilityResult(str, Enum):
    """Result of an eligibility check for posture upgrade."""

    ELIGIBLE = "eligible"
    NOT_YET = "not_yet"
    BLOCKED = "blocked"


class PostureHistoryStore:
    """Append-only store for posture change records.

    Records are keyed by ``agent_id``. Once appended, a record is
    never modified or removed. Direct reassignment of ``_records``
    after initialization raises :class:`PostureHistoryError`.

    Each appended record is assigned a globally monotonic
    ``sequence_number`` to enforce ordering integrity.
    """

    def __init__(self) -> None:
        import threading

        # Use object.__setattr__ to bypass our __setattr__ guard during init.
        object.__setattr__(self, "_records", {})
        object.__setattr__(self, "_sequence_counter", 0)
        object.__setattr__(self, "_lock", threading.Lock())
        object.__setattr__(self, "_initialized", True)

    def __setattr__(self, name: str, value: object) -> None:
        """Block direct reassignment of _records after initialization.

        This enforces the append-only invariant at the attribute level.
        Any attempt to reassign _records is logged as a security event
        and raises PostureHistoryError.
        """
        if name == "_records" and getattr(self, "_initialized", False):
            logger.warning(
                "SECURITY: Attempted direct mutation of _records on "
                "PostureHistoryStore. This violates append-only invariant. "
                "Attempted value type: %s",
                type(value).__name__,
            )
            raise PostureHistoryError(
                "Direct reassignment of _records is prohibited. "
                "Use record_change() to append records. "
                "This attempt has been logged as a security event."
            )
        object.__setattr__(self, name, value)

    def record_change(self, record: PostureChangeRecord) -> None:
        """Append a posture change record. Never modifies existing records.

        Assigns a monotonically increasing sequence number to the record
        before appending it to the store. Thread-safe.
        """
        with self._lock:
            new_seq = self._sequence_counter + 1
            object.__setattr__(self, "_sequence_counter", new_seq)
            record.sequence_number = new_seq
            self._records.setdefault(record.agent_id, []).append(record)
        logger.info(
            "Posture change recorded: agent=%s, %s -> %s (%s, trigger=%s, seq=%d)",
            record.agent_id,
            record.from_posture,
            record.to_posture,
            record.direction,
            record.trigger.value,
            record.sequence_number,
        )

    def get_history(self, agent_id: str) -> list[PostureChangeRecord]:
        """Get full posture history for an agent (chronological order).

        Returns deep copies to preserve append-only invariant at record level.
        """
        return [r.model_copy() for r in self._records.get(agent_id, [])]

    def current_posture(self, agent_id: str) -> str:
        """Get current posture derived from the latest record.

        Raises :class:`KeyError` if no history exists for the agent.
        No silent defaults — the caller must handle unknown agents explicitly.
        """
        records = self._records.get(agent_id)
        if not records:
            raise KeyError(
                f"No posture history found for agent '{agent_id}'. "
                "Cannot determine current posture without history."
            )
        return records[-1].to_posture

    def get_duration_at_posture(self, agent_id: str, posture: str) -> timedelta:
        """Calculate total time spent at a given posture level.

        Walks the history and sums up each contiguous period where the
        agent was at the specified posture. The agent enters a posture
        when a record's ``to_posture`` matches, and exits when the next
        record changes away from it.

        Raises :class:`KeyError` if no history exists for the agent.
        """
        records = self._records.get(agent_id)
        if records is None:
            raise KeyError(
                f"No posture history found for agent '{agent_id}'. "
                "Cannot compute duration without history."
            )

        total = timedelta(0)
        entered_at: datetime | None = None

        for record in records:
            if record.to_posture == posture and entered_at is None:
                # Entering the target posture
                entered_at = record.changed_at
            elif record.to_posture != posture and entered_at is not None:
                # Leaving the target posture
                total += record.changed_at - entered_at
                entered_at = None

        # If still at the target posture, count up to now
        if entered_at is not None:
            total += datetime.now(UTC) - entered_at

        return total


class PostureEligibilityChecker:
    """Check if an agent is eligible for a posture upgrade.

    Uses the posture history to evaluate time-at-posture, operational
    requirements, ShadowEnforcer pass rate, and downgrade cooldown.
    """

    def __init__(self, history: PostureHistoryStore) -> None:
        self.history = history

    def check(
        self,
        agent_id: str,
        target_posture: str,
        shadow_pass_rate: float = 0.0,
        total_operations: int = 0,
    ) -> tuple[EligibilityResult, str]:
        """Check eligibility for upgrade to *target_posture*.

        Returns ``(result, reason)`` tuple.

        Raises :class:`KeyError` if no history exists for the agent.
        """
        records = self.history.get_history(agent_id)
        if not records:
            raise KeyError(
                f"No posture history found for agent '{agent_id}'. "
                "Cannot check eligibility without history."
            )

        # Check for recent downgrade (cooldown period)
        last_downgrade = self._last_downgrade(records)
        if last_downgrade is not None:
            days_since = (datetime.now(UTC) - last_downgrade.changed_at).days
            if days_since < _DOWNGRADE_COOLDOWN_DAYS:
                return (
                    EligibilityResult.BLOCKED,
                    f"Recent downgrade {days_since} days ago due to "
                    f"{last_downgrade.trigger.value}. "
                    f"Must wait {_DOWNGRADE_COOLDOWN_DAYS} days before upgrade.",
                )

        # Look up requirements for the target posture
        requirements = self._get_requirements(target_posture)
        if requirements is None:
            return (
                EligibilityResult.NOT_YET,
                f"No upgrade requirements defined for '{target_posture}'",
            )

        # Check time at current posture
        current_posture = self.history.current_posture(agent_id)
        duration = self.history.get_duration_at_posture(agent_id, current_posture)
        days_at_current = duration.days
        min_days = requirements.get("min_days", 0)
        if days_at_current < min_days:
            return (
                EligibilityResult.NOT_YET,
                f"Need {min_days} days at current posture, have {days_at_current} days",
            )

        # Check total operations
        min_ops = requirements.get("min_operations", 0)
        if total_operations < min_ops:
            return (
                EligibilityResult.NOT_YET,
                f"Need {min_ops} operations, have {total_operations}",
            )

        # Check ShadowEnforcer pass rate
        min_shadow = requirements.get("shadow_pass_rate", 0.0)
        if requirements.get("shadow_enforcer_required") and shadow_pass_rate < min_shadow:
            return (
                EligibilityResult.NOT_YET,
                f"Need {min_shadow:.0%} ShadowEnforcer pass rate, have {shadow_pass_rate:.0%}",
            )

        return (EligibilityResult.ELIGIBLE, f"Agent is eligible for {target_posture}")

    @staticmethod
    def _last_downgrade(
        records: list[PostureChangeRecord],
    ) -> PostureChangeRecord | None:
        """Find the most recent downgrade record, or None."""
        for record in reversed(records):
            if record.direction == "downgrade":
                return record
        return None

    @staticmethod
    def _get_requirements(target_posture: str) -> dict | None:
        """Look up UPGRADE_REQUIREMENTS by posture string value."""
        for level, reqs in UPGRADE_REQUIREMENTS.items():
            if level.value == target_posture:
                return reqs
        return None
