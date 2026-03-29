# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Emergency Bypass — temporary envelope expansion under time-limited tiers.

When an operational emergency requires actions beyond a role's normal
envelope, an authorized party can create an emergency bypass.  Bypasses
are time-limited across four tiers, auto-expire, and generate audit
anchors.  After expiry, a post-incident review is scheduled.

Tier structure:
- TIER_1: 4 hours  (tactical response)
- TIER_2: 24 hours (extended incident)
- TIER_3: 72 hours (crisis management)
- TIER_4: No auto-expiry (requires compliance review to close)
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

__all__ = [
    "EmergencyBypass",
    "BypassRecord",
    "BypassTier",
]

MAX_BYPASS_RECORDS = 10_000
_REVIEW_WINDOW_DAYS = 7


class BypassTier(str, Enum):
    """Emergency bypass tier determining duration and review requirements."""

    TIER_1 = "tier_1"  # 4 hours
    TIER_2 = "tier_2"  # 24 hours
    TIER_3 = "tier_3"  # 72 hours
    TIER_4 = "tier_4"  # No auto-expiry, requires compliance review


# Duration per tier.  TIER_4 has no auto-expiry so it is absent.
_TIER_DURATION: dict[BypassTier, timedelta] = {
    BypassTier.TIER_1: timedelta(hours=4),
    BypassTier.TIER_2: timedelta(hours=24),
    BypassTier.TIER_3: timedelta(hours=72),
}


@dataclass(frozen=True)
class BypassRecord:
    """Immutable record of an emergency bypass.

    Fields:
        bypass_id: Unique identifier for this bypass.
        role_address: The D/T/R address whose envelope is expanded.
        tier: The bypass tier determining duration.
        reason: Human-readable justification for the bypass.
        approved_by: Identity of the authorizing party.
        expanded_envelope: The temporary envelope override (dict).
        created_at: When the bypass was created.
        expires_at: When the bypass auto-expires (None for TIER_4).
        expired_manually: Whether the bypass was manually expired.
        review_due_by: Date by which a post-incident review must occur.
        audit_anchor_id: ID of the audit anchor created on bypass creation.
    """

    bypass_id: str
    role_address: str
    tier: BypassTier
    reason: str
    approved_by: str
    expanded_envelope: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    expired_manually: bool = False
    review_due_by: datetime | None = None
    audit_anchor_id: str = ""

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check whether this bypass has expired.

        A bypass is expired if:
        - It was manually expired (``expired_manually`` is True), OR
        - It has an ``expires_at`` and that time has passed.

        TIER_4 bypasses have ``expires_at=None`` and never auto-expire;
        they must be manually expired or closed via compliance review.

        Args:
            now: Reference time.  Defaults to ``datetime.now(UTC)``.

        Returns:
            True if the bypass is no longer active.
        """
        if self.expired_manually:
            return True
        if self.expires_at is None:
            # TIER_4: no auto-expiry
            return False
        if now is None:
            now = datetime.now(UTC)
        return now >= self.expires_at

    def is_active(self, now: datetime | None = None) -> bool:
        """Convenience inverse of ``is_expired``."""
        return not self.is_expired(now)


class EmergencyBypass:
    """Manages emergency bypass lifecycle: creation, lookup, expiry, and review scheduling.

    Thread-safe via ``threading.Lock``.  Stores are bounded to
    ``MAX_BYPASS_RECORDS`` entries (oldest evicted on overflow).

    Args:
        audit_callback: Optional callable invoked with audit anchor details
            on bypass creation.  Signature:
            ``(event: str, details: dict) -> str`` returning an anchor ID.
    """

    def __init__(
        self,
        audit_callback: Any | None = None,
    ) -> None:
        self._lock = threading.Lock()
        # OrderedDict preserves insertion order for FIFO eviction.
        self._bypasses: OrderedDict[str, BypassRecord] = OrderedDict()
        self._audit_callback = audit_callback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_bypass(
        self,
        role_address: str,
        tier: BypassTier,
        reason: str,
        approved_by: str,
        expanded_envelope: dict[str, Any] | None = None,
    ) -> BypassRecord:
        """Create and store a new emergency bypass.

        Args:
            role_address: D/T/R address of the role to expand.
            tier: Bypass tier (determines duration).
            reason: Justification for the emergency bypass.
            approved_by: Identity of the authorizing party.
            expanded_envelope: Temporary envelope override dict.

        Returns:
            The newly created ``BypassRecord``.

        Raises:
            ValueError: If role_address, reason, or approved_by is empty.
        """
        if not role_address:
            raise ValueError("role_address must not be empty")
        if not reason:
            raise ValueError("reason must not be empty")
        if not approved_by:
            raise ValueError("approved_by must not be empty")

        now = datetime.now(UTC)
        bypass_id = f"eb-{uuid4().hex[:12]}"

        # Compute expiry
        duration = _TIER_DURATION.get(tier)
        expires_at = (now + duration) if duration is not None else None

        # Compute review_due_by: 7 days after expiry (or 7 days after creation for TIER_4)
        review_anchor = expires_at if expires_at is not None else now
        review_due_by = review_anchor + timedelta(days=_REVIEW_WINDOW_DAYS)

        # Create audit anchor
        audit_anchor_id = ""
        audit_details = {
            "bypass_id": bypass_id,
            "role_address": role_address,
            "tier": tier.value,
            "reason": reason,
            "approved_by": approved_by,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "review_due_by": review_due_by.isoformat(),
        }
        if self._audit_callback is not None:
            try:
                audit_anchor_id = str(
                    self._audit_callback("emergency_bypass_created", audit_details)
                )
            except Exception:
                logger.exception(
                    "Audit callback failed for bypass '%s' — bypass still created",
                    bypass_id,
                )

        record = BypassRecord(
            bypass_id=bypass_id,
            role_address=role_address,
            tier=tier,
            reason=reason,
            approved_by=approved_by,
            expanded_envelope=expanded_envelope if expanded_envelope is not None else {},
            created_at=now,
            expires_at=expires_at,
            expired_manually=False,
            review_due_by=review_due_by,
            audit_anchor_id=audit_anchor_id,
        )

        with self._lock:
            # Enforce bounded collection
            while len(self._bypasses) >= MAX_BYPASS_RECORDS:
                self._bypasses.popitem(last=False)  # Evict oldest
            self._bypasses[bypass_id] = record

        logger.info(
            "Emergency bypass created: id=%s role=%s tier=%s expires=%s approved_by=%s",
            bypass_id,
            role_address,
            tier.value,
            expires_at.isoformat() if expires_at else "never",
            approved_by,
        )

        return record

    def check_bypass(self, role_address: str) -> BypassRecord | None:
        """Return the active (non-expired) bypass for a role, or None.

        If multiple bypasses exist for the same role, returns the most
        recently created active one.

        Fail-closed: if the check raises an unexpected error, returns None
        (no bypass granted).

        Args:
            role_address: D/T/R address to look up.

        Returns:
            Active ``BypassRecord`` or ``None``.
        """
        try:
            now = datetime.now(UTC)
            with self._lock:
                # Iterate in reverse insertion order (newest first)
                for record in reversed(list(self._bypasses.values())):
                    if record.role_address == role_address and record.is_active(now):
                        return record
            return None
        except Exception:
            # Fail-closed: bypass check errors mean no bypass
            logger.exception(
                "Error checking bypass for role '%s' — returning None (fail-closed)",
                role_address,
            )
            return None

    def expire_bypass(self, bypass_id: str) -> BypassRecord | None:
        """Manually expire a bypass.

        Since BypassRecord is frozen, we replace it with a copy that has
        ``expired_manually=True``.

        Args:
            bypass_id: The bypass to expire.

        Returns:
            The updated ``BypassRecord``, or ``None`` if not found.
        """
        with self._lock:
            record = self._bypasses.get(bypass_id)
            if record is None:
                return None

            # Create a new frozen record with expired_manually=True
            expired_record = BypassRecord(
                bypass_id=record.bypass_id,
                role_address=record.role_address,
                tier=record.tier,
                reason=record.reason,
                approved_by=record.approved_by,
                expanded_envelope=record.expanded_envelope,
                created_at=record.created_at,
                expires_at=record.expires_at,
                expired_manually=True,
                review_due_by=record.review_due_by,
                audit_anchor_id=record.audit_anchor_id,
            )
            self._bypasses[bypass_id] = expired_record

        logger.info("Emergency bypass manually expired: id=%s", bypass_id)
        return expired_record

    def list_active_bypasses(self) -> list[BypassRecord]:
        """Return all non-expired bypass records.

        Returns:
            List of active ``BypassRecord`` instances.
        """
        now = datetime.now(UTC)
        with self._lock:
            return [r for r in self._bypasses.values() if r.is_active(now)]

    def list_reviews_due(self, as_of: datetime | None = None) -> list[BypassRecord]:
        """Return bypass records whose post-incident review is due.

        A review is due when the bypass has expired and ``review_due_by``
        has not yet passed.

        Args:
            as_of: Reference time.  Defaults to ``datetime.now(UTC)``.

        Returns:
            List of ``BypassRecord`` instances with reviews due.
        """
        if as_of is None:
            as_of = datetime.now(UTC)
        with self._lock:
            return [
                r
                for r in self._bypasses.values()
                if r.is_expired(as_of) and r.review_due_by is not None and as_of <= r.review_due_by
            ]
