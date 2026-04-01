# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Emergency Bypass — temporary envelope expansion under time-limited tiers.

When an operational emergency requires actions beyond a role's normal
envelope, an authorized party can create an emergency bypass.  Bypasses
are time-limited across three permitted tiers, auto-expire, and generate
audit anchors.  After expiry, a post-incident review is scheduled.

Permitted tier structure (PACT spec Section 9):
- TIER_1: 4 hours  (tactical response)
- TIER_2: 24 hours (extended incident)
- TIER_3: 72 hours (crisis management)

TIER_4 is DEPRECATED for creation.  The PACT spec (Section 9) states
that emergencies exceeding 72 hours are "not emergency — not permitted
via bypass."  Such situations must be re-authorized through normal
governance channels every 72 hours.  The enum value is retained for
backwards compatibility with existing records.

Additional controls:
- Expanded envelopes are validated against the approver's effective
  envelope to prevent privilege escalation (H2).
- Structural D/T/R authority is validated when addresses are provided
  to ensure the approver has the correct org-level position (H3).
- Rate limiting prevents perpetual bypass via sequential creation:
  MAX_BYPASSES_PER_WEEK per role with a COOLDOWN_HOURS gap (M4).
"""

from __future__ import annotations

import abc
import copy
import logging
import math
import os
import sqlite3
import threading
from collections import OrderedDict, deque
from types import MappingProxyType
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

__all__ = [
    "AuthorityLevel",
    "COOLDOWN_HOURS",
    "EmergencyBypass",
    "BypassRecord",
    "BypassTier",
    "MAX_BYPASSES_PER_WEEK",
    "MemoryRateLimitStore",
    "SqliteRateLimitStore",
    "RateLimitStore",
]

MAX_BYPASS_RECORDS = 10_000
_REVIEW_WINDOW_DAYS = 7

# M4: Rate limiting constants
MAX_BYPASSES_PER_WEEK = 3
COOLDOWN_HOURS = 4


class BypassTier(str, Enum):
    """Emergency bypass tier determining duration and review requirements."""

    TIER_1 = "tier_1"  # 4 hours
    TIER_2 = "tier_2"  # 24 hours
    TIER_3 = "tier_3"  # 72 hours
    TIER_4 = "tier_4"  # DEPRECATED for creation — retained for backwards compat only


class AuthorityLevel(str, Enum):
    """Authority level of the approver.  Higher levels can approve higher tiers.

    Per PACT thesis Section 9:
    - SUPERVISOR may approve TIER_1 (tactical, 4h).
    - DEPARTMENT_HEAD may approve TIER_1 and TIER_2 (extended, 24h).
    - EXECUTIVE may approve TIER_1 through TIER_3 (crisis, 72h).
    - COMPLIANCE may approve any tier including TIER_4 (full override).
    """

    SUPERVISOR = "supervisor"
    DEPARTMENT_HEAD = "department_head"
    EXECUTIVE = "executive"
    COMPLIANCE = "compliance"


# Minimum authority level required per tier (immutable).
# TIER_4 is excluded — it is not permitted for creation (PACT spec Section 9).
_TIER_MIN_AUTHORITY = MappingProxyType(
    {
        BypassTier.TIER_1: AuthorityLevel.SUPERVISOR,
        BypassTier.TIER_2: AuthorityLevel.DEPARTMENT_HEAD,
        BypassTier.TIER_3: AuthorityLevel.EXECUTIVE,
    }
)

# Ordered authority levels (lowest to highest, immutable).
_AUTHORITY_ORDER: tuple[AuthorityLevel, ...] = (
    AuthorityLevel.SUPERVISOR,
    AuthorityLevel.DEPARTMENT_HEAD,
    AuthorityLevel.EXECUTIVE,
    AuthorityLevel.COMPLIANCE,
)


def _authority_sufficient(approver_level: AuthorityLevel, required_level: AuthorityLevel) -> bool:
    """Return True if approver_level >= required_level in the authority ordering."""
    return _AUTHORITY_ORDER.index(approver_level) >= _AUTHORITY_ORDER.index(required_level)


# Duration per tier.  TIER_4 has no auto-expiry so it is absent.
_TIER_DURATION: dict[BypassTier, timedelta] = {
    BypassTier.TIER_1: timedelta(hours=4),
    BypassTier.TIER_2: timedelta(hours=24),
    BypassTier.TIER_3: timedelta(hours=72),
}


# ---------------------------------------------------------------------------
# Rate Limit Store — pluggable backend for cross-process rate limiting
# ---------------------------------------------------------------------------


class RateLimitStore(abc.ABC):
    """Abstract rate limit store for bypass creation tracking.

    Implementations must be safe for their declared concurrency model:
    - ``MemoryRateLimitStore``: thread-safe (single process)
    - ``SqliteRateLimitStore``: process-safe (multiple Gunicorn workers)
    """

    @abc.abstractmethod
    def record_creation(self, role_address: str, created_at: datetime) -> None:
        """Record a bypass creation timestamp for a role."""

    @abc.abstractmethod
    def get_history(self, role_address: str, since: datetime) -> list[datetime]:
        """Return creation timestamps for a role since the given cutoff, oldest first."""

    @abc.abstractmethod
    def cleanup_stale(self, before: datetime) -> int:
        """Remove entries older than *before*.  Return count of removed entries."""

    def atomic_check_and_record(
        self,
        role_address: str,
        now: datetime,
        max_per_week: int,
        cooldown_hours: float,
    ) -> None:
        """Atomically check rate limits and record a creation.

        This default implementation calls the individual methods sequentially.
        Subclasses may override to provide cross-process atomicity (e.g. via
        a database transaction).

        Raises:
            ValueError: If rate limit or cooldown is violated.
        """
        cutoff = now - timedelta(days=7)
        self.cleanup_stale(cutoff)
        history = self.get_history(role_address, cutoff)

        if history:
            last_creation = history[-1]
            hours_since_last = (now - last_creation).total_seconds() / 3600
            if hours_since_last < cooldown_hours:
                remaining = cooldown_hours - hours_since_last
                raise ValueError(
                    f"Bypass cooldown period active for role '{role_address}': "
                    f"{remaining:.1f} hours remaining. Minimum gap between bypasses "
                    f"is {cooldown_hours} hours."
                )
            if len(history) >= max_per_week:
                raise ValueError(
                    f"Bypass rate limit exceeded for role '{role_address}': "
                    f"{len(history)} bypasses in the last 7 days (maximum "
                    f"is {max_per_week} per week). Higher-tier authority "
                    f"or re-authorization through normal governance channels is required."
                )

        self.record_creation(role_address, now)


class MemoryRateLimitStore(RateLimitStore):
    """In-memory rate limit store — thread-safe, single-process only.

    This is the default backend.  It is NOT shared across Gunicorn workers.
    Use ``SqliteRateLimitStore`` for multi-process deployments.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: dict[str, deque[datetime]] = {}

    def record_creation(self, role_address: str, created_at: datetime) -> None:
        with self._lock:
            if role_address not in self._history:
                self._history[role_address] = deque(maxlen=MAX_BYPASSES_PER_WEEK * 2)
            self._history[role_address].append(created_at)

    def get_history(self, role_address: str, since: datetime) -> list[datetime]:
        with self._lock:
            history = self._history.get(role_address)
            if history is None:
                return []
            return [ts for ts in history if ts >= since]

    def cleanup_stale(self, before: datetime) -> int:
        removed = 0
        with self._lock:
            empty_keys: list[str] = []
            for key, history in self._history.items():
                while history and history[0] < before:
                    history.popleft()
                    removed += 1
                if not history:
                    empty_keys.append(key)
            for key in empty_keys:
                del self._history[key]
        return removed


class SqliteRateLimitStore(RateLimitStore):
    """SQLite-backed rate limit store — safe across multiple processes.

    Uses WAL mode for concurrent readers and a single writer.  Each write
    is an independent transaction with SQLite's file-level locking, so
    separate Gunicorn workers can share the same database file.

    Args:
        db_path: Path to the SQLite database file.  Parent directory must
            exist.  Defaults to ``./pact_bypass_ratelimit.db``.
    """

    _DDL = """
        CREATE TABLE IF NOT EXISTS bypass_rate_limit (
            id INTEGER PRIMARY KEY,
            role_address TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """
    _IDX = """
        CREATE INDEX IF NOT EXISTS idx_brl_role_created
        ON bypass_rate_limit (role_address, created_at)
    """

    _MAX_ROWS = 100_000

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_path = os.environ.get("PACT_BYPASS_RATELIMIT_DB", "pact_bypass_ratelimit.db")
        self._db_path = db_path
        self._local = threading.local()
        # Set restrictive file permissions before SQLite creates sidecar files.
        if os.name != "nt" and not os.path.exists(db_path):
            import stat

            open(db_path, "a").close()  # noqa: SIM115
            os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Return a thread-local connection (SQLite connections are not thread-safe)."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return conn

    def _init_schema(self) -> None:
        conn = self._get_conn()
        conn.execute(self._DDL)
        conn.execute(self._IDX)
        conn.commit()

    def record_creation(self, role_address: str, created_at: datetime) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO bypass_rate_limit (role_address, created_at) VALUES (?, ?)",
            (role_address, created_at.isoformat()),
        )
        # Enforce bounded table size — evict oldest rows when at capacity.
        count = conn.execute("SELECT COUNT(*) FROM bypass_rate_limit").fetchone()[0]
        if count > self._MAX_ROWS:
            conn.execute(
                "DELETE FROM bypass_rate_limit WHERE id IN "
                "(SELECT id FROM bypass_rate_limit ORDER BY created_at LIMIT ?)",
                (count - self._MAX_ROWS,),
            )
        conn.commit()

    def get_history(self, role_address: str, since: datetime) -> list[datetime]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT created_at FROM bypass_rate_limit "
            "WHERE role_address = ? AND created_at >= ? "
            "ORDER BY created_at",
            (role_address, since.isoformat()),
        ).fetchall()
        return [datetime.fromisoformat(row[0]) for row in rows]

    def cleanup_stale(self, before: datetime) -> int:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM bypass_rate_limit WHERE created_at < ?",
            (before.isoformat(),),
        )
        conn.commit()
        return cursor.rowcount

    def atomic_check_and_record(
        self,
        role_address: str,
        now: datetime,
        max_per_week: int,
        cooldown_hours: float,
    ) -> None:
        """Atomically check rate limits and record — cross-process safe.

        Uses ``BEGIN IMMEDIATE`` to acquire the SQLite write lock before
        reading, preventing TOCTOU races where two processes both pass the
        check before either records.
        """
        conn = self._get_conn()
        cutoff = now - timedelta(days=7)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM bypass_rate_limit WHERE created_at < ?",
                (cutoff.isoformat(),),
            )
            rows = conn.execute(
                "SELECT created_at FROM bypass_rate_limit "
                "WHERE role_address = ? AND created_at >= ? "
                "ORDER BY created_at",
                (role_address, cutoff.isoformat()),
            ).fetchall()
            history = [datetime.fromisoformat(r[0]) for r in rows]

            if history:
                last_creation = history[-1]
                hours_since_last = (now - last_creation).total_seconds() / 3600
                if hours_since_last < cooldown_hours:
                    conn.execute("ROLLBACK")
                    remaining = cooldown_hours - hours_since_last
                    raise ValueError(
                        f"Bypass cooldown period active for role '{role_address}': "
                        f"{remaining:.1f} hours remaining. Minimum gap between bypasses "
                        f"is {cooldown_hours} hours."
                    )
                if len(history) >= max_per_week:
                    conn.execute("ROLLBACK")
                    raise ValueError(
                        f"Bypass rate limit exceeded for role '{role_address}': "
                        f"{len(history)} bypasses in the last 7 days (maximum "
                        f"is {max_per_week} per week). Higher-tier authority "
                        f"or re-authorization through normal governance channels is required."
                    )

            conn.execute(
                "INSERT INTO bypass_rate_limit (role_address, created_at) VALUES (?, ?)",
                (role_address, now.isoformat()),
            )
            conn.execute("COMMIT")
        except ValueError:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def close(self) -> None:
        """Close the thread-local connection."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


# ---------------------------------------------------------------------------
# Bypass Record
# ---------------------------------------------------------------------------


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

    def __post_init__(self) -> None:
        """Deep-copy mutable fields to prevent mutation via external references (M3 fix)."""
        object.__setattr__(self, "expanded_envelope", copy.deepcopy(self.expanded_envelope))

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
        rate_limit_store: Pluggable rate limit backend.  Defaults to
            ``MemoryRateLimitStore`` (single-process, thread-safe).
            Use ``SqliteRateLimitStore`` for multi-process deployments
            (e.g. Gunicorn with multiple workers).
    """

    def __init__(
        self,
        audit_callback: Any | None = None,
        rate_limit_store: RateLimitStore | None = None,
    ) -> None:
        self._lock = threading.Lock()
        # OrderedDict preserves insertion order for FIFO eviction.
        self._bypasses: OrderedDict[str, BypassRecord] = OrderedDict()
        self._audit_callback = audit_callback
        self._rate_limit_store = rate_limit_store or MemoryRateLimitStore()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_expanded_envelope(
        self,
        expanded_envelope: dict[str, Any],
        approver_envelope: dict[str, Any],
    ) -> None:
        """Validate that expanded_envelope does not exceed approver_envelope.

        Checks four constraint dimensions:
        - financial.max_spend_usd: expanded must be <= approver's
        - operational.allowed_actions: expanded must be a subset
        - data_access.read_paths: expanded must be a subset
        - communication.allowed_channels: expanded must be a subset

        Also validates that all numeric values in the expanded envelope are
        finite (not NaN or Inf).

        Args:
            expanded_envelope: The temporary envelope override.
            approver_envelope: The approver's effective envelope.

        Raises:
            ValueError: If a numeric field contains NaN or Inf.
            PermissionError: If any dimension exceeds the approver's bounds.
        """
        # Financial dimension
        exp_financial = expanded_envelope.get("financial", {})
        app_financial = approver_envelope.get("financial", {})
        exp_max_spend = exp_financial.get("max_spend_usd")
        if exp_max_spend is not None:
            if not isinstance(exp_max_spend, (int, float)):
                raise ValueError(
                    f"financial.max_spend_usd must be numeric, got {type(exp_max_spend).__name__}"
                )
            if not math.isfinite(exp_max_spend):
                raise ValueError(f"financial.max_spend_usd must be finite, got {exp_max_spend}")
            app_max_spend = app_financial.get("max_spend_usd")
            if app_max_spend is not None:
                if not math.isfinite(app_max_spend):
                    raise ValueError(
                        f"approver financial.max_spend_usd must be finite, got {app_max_spend}"
                    )
                if exp_max_spend > app_max_spend:
                    raise PermissionError(
                        f"Expanded envelope exceeds approver's bounds on "
                        f"financial.max_spend_usd: {exp_max_spend} > {app_max_spend}"
                    )

        # Operational dimension
        exp_operational = expanded_envelope.get("operational", {})
        app_operational = approver_envelope.get("operational", {})
        exp_actions = exp_operational.get("allowed_actions")
        if exp_actions is not None:
            app_actions = app_operational.get("allowed_actions")
            if app_actions is not None:
                exp_set = set(exp_actions)
                app_set = set(app_actions)
                excess = exp_set - app_set
                if excess:
                    raise PermissionError(
                        f"Expanded envelope exceeds approver's bounds on "
                        f"operational.allowed_actions: {sorted(excess)} not in approver's set"
                    )

        # Data access dimension
        exp_data = expanded_envelope.get("data_access", {})
        app_data = approver_envelope.get("data_access", {})
        exp_paths = exp_data.get("read_paths")
        if exp_paths is not None:
            app_paths = app_data.get("read_paths")
            if app_paths is not None:
                exp_set = set(exp_paths)
                app_set = set(app_paths)
                excess = exp_set - app_set
                if excess:
                    raise PermissionError(
                        f"Expanded envelope exceeds approver's bounds on "
                        f"data_access.read_paths: {sorted(excess)} not in approver's set"
                    )

        # Temporal dimension
        exp_temporal = expanded_envelope.get("temporal", {})
        app_temporal = approver_envelope.get("temporal", {})
        exp_active_hours = exp_temporal.get("active_hours")
        if exp_active_hours is not None:
            app_active_hours = app_temporal.get("active_hours")
            if app_active_hours is not None:
                exp_set = (
                    set(exp_active_hours)
                    if isinstance(exp_active_hours, list)
                    else {exp_active_hours}
                )
                app_set = (
                    set(app_active_hours)
                    if isinstance(app_active_hours, list)
                    else {app_active_hours}
                )
                excess = exp_set - app_set
                if excess:
                    raise PermissionError(
                        f"Expanded envelope exceeds approver's bounds on "
                        f"temporal.active_hours: {sorted(excess)} not in approver's set"
                    )
        exp_blackout = exp_temporal.get("blackout_periods")
        if exp_blackout is not None:
            app_blackout = app_temporal.get("blackout_periods")
            if app_blackout is not None:
                # Child blackout must be superset of parent's (more restrictive)
                exp_set = set(exp_blackout) if isinstance(exp_blackout, list) else set()
                app_set = set(app_blackout) if isinstance(app_blackout, list) else set()
                missing = app_set - exp_set
                if missing:
                    raise PermissionError(
                        f"Expanded envelope must include all approver's "
                        f"temporal.blackout_periods: missing {sorted(missing)}"
                    )

        # Communication dimension
        exp_comm = expanded_envelope.get("communication", {})
        app_comm = approver_envelope.get("communication", {})
        exp_channels = exp_comm.get("allowed_channels")
        if exp_channels is not None:
            app_channels = app_comm.get("allowed_channels")
            if app_channels is not None:
                exp_set = set(exp_channels)
                app_set = set(app_channels)
                excess = exp_set - app_set
                if excess:
                    raise PermissionError(
                        f"Expanded envelope exceeds approver's bounds on "
                        f"communication.allowed_channels: {sorted(excess)} not in approver's set"
                    )

    def _validate_structural_authority(
        self,
        approver_address: str,
        target_address: str,
        tier: BypassTier,
    ) -> None:
        """Validate D/T/R structural relationship for bypass approval.

        Uses the accountability chain to determine the approver's position
        relative to the target.

        Args:
            approver_address: D/T/R address of the approver.
            target_address: D/T/R address of the target role.
            tier: Requested bypass tier.

        Raises:
            PermissionError: If structural authority is insufficient for the tier.
        """
        from kailash.trust.pact.addressing import Address

        approver = Address.parse(approver_address)
        target = Address.parse(target_address)

        target_chain = target.accountability_chain

        # Find the approver's position in the target's accountability chain
        approver_str = str(approver)
        approver_index: int | None = None
        for idx, chain_addr in enumerate(target_chain):
            if str(chain_addr) == approver_str:
                approver_index = idx
                break

        if approver_index is None:
            raise PermissionError(
                f"Insufficient structural authority: approver '{approver_address}' "
                f"is not in the accountability chain of target '{target_address}'"
            )

        target_index = len(target_chain) - 1
        levels_above = target_index - approver_index

        if tier == BypassTier.TIER_1:
            # Tier 1: approver must be the immediate parent R (1 level above)
            if levels_above < 1:
                raise PermissionError(
                    f"Insufficient structural authority for {tier.value}: "
                    f"approver '{approver_address}' must be at least 1 level above "
                    f"target '{target_address}' in the accountability chain "
                    f"(found {levels_above} levels)"
                )
        elif tier == BypassTier.TIER_2:
            # Tier 2: approver must be 2+ levels up in the accountability chain
            if levels_above < 2:
                raise PermissionError(
                    f"Insufficient structural authority for {tier.value}: "
                    f"approver '{approver_address}' must be at least 2 levels above "
                    f"target '{target_address}' in the accountability chain "
                    f"(found {levels_above} levels)"
                )
        elif tier == BypassTier.TIER_3:
            # Tier 3: approver must be at index 0 or 1 in the chain (top-level, C-Suite)
            if approver_index > 1:
                raise PermissionError(
                    f"Insufficient structural authority for {tier.value}: "
                    f"approver '{approver_address}' must be at position 0 or 1 "
                    f"in the accountability chain (found position {approver_index})"
                )

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
        *,
        authority_level: AuthorityLevel | None = None,
        approver_envelope: dict[str, Any] | None = None,
        approver_address: str | None = None,
        target_address: str | None = None,
    ) -> BypassRecord:
        """Create and store a new emergency bypass.

        Args:
            role_address: D/T/R address of the role to expand.
            tier: Bypass tier (determines duration).  TIER_4 is rejected
                per PACT spec Section 9 — emergencies over 72 hours must
                be re-authorized through normal governance channels.
            reason: Justification for the emergency bypass.
            approved_by: Identity of the authorizing party.
            expanded_envelope: Temporary envelope override dict.
            authority_level: Authority level of the approver.  When
                provided, the level is validated against the tier
                requirement (PACT thesis Section 9).  When ``None``,
                authorization is not enforced (backwards-compatible).
            approver_envelope: The approver's effective envelope for scope
                validation (H2).  When provided, the expanded_envelope is
                validated to ensure it does not exceed the approver's
                bounds.  When ``None``, scope validation is skipped with
                a deprecation warning.
            approver_address: D/T/R address of the approver for structural
                authority validation (H3).  Used together with
                ``target_address``.
            target_address: D/T/R address of the target role for structural
                authority validation (H3).  Used together with
                ``approver_address``.

        Returns:
            The newly created ``BypassRecord``.

        Raises:
            ValueError: If role_address, reason, or approved_by is empty;
                if tier is TIER_4; if rate limits are exceeded; if
                numeric values in expanded_envelope are non-finite.
            PermissionError: If authority_level is insufficient for the
                tier; if expanded_envelope exceeds approver's bounds; if
                structural authority is insufficient.
        """
        # C2: Reject Tier 4 creation (PACT spec Section 9)
        if tier == BypassTier.TIER_4:
            raise ValueError(
                "Tier 4 (>72h) is not permitted — emergencies over 72 hours "
                "must be re-authorized through normal governance channels "
                "every 72 hours (PACT spec Section 9)"
            )

        if not role_address:
            raise ValueError("role_address must not be empty")
        if not reason:
            raise ValueError("reason must not be empty")
        if not approved_by:
            raise ValueError("approved_by must not be empty")

        # H5: Validate authority level against tier requirement
        if authority_level is not None:
            required = _TIER_MIN_AUTHORITY[tier]
            if not _authority_sufficient(authority_level, required):
                raise PermissionError(
                    f"Authority level '{authority_level.value}' is insufficient "
                    f"for {tier.value} — requires at least '{required.value}'"
                )
        else:
            import warnings

            warnings.warn(
                "authority_level=None skips tier authorization — "
                "this will become required in a future version",
                DeprecationWarning,
                stacklevel=2,
            )

        # H2: Validate expanded_envelope against approver's envelope
        effective_envelope = expanded_envelope if expanded_envelope is not None else {}
        if approver_envelope is not None:
            self._validate_expanded_envelope(effective_envelope, approver_envelope)
        elif effective_envelope:
            import warnings

            warnings.warn(
                "approver_envelope=None skips scope validation — "
                "this will become required in a future version when "
                "expanded_envelope is provided",
                DeprecationWarning,
                stacklevel=2,
            )

        # H3: Validate structural D/T/R authority
        if approver_address is not None and target_address is not None:
            self._validate_structural_authority(approver_address, target_address, tier)

        now = datetime.now(UTC)

        bypass_id = f"eb-{uuid4().hex[:12]}"

        # Compute expiry
        duration = _TIER_DURATION.get(tier)
        expires_at = (now + duration) if duration is not None else None

        # Compute review_due_by: 7 days after expiry
        review_anchor = expires_at if expires_at is not None else now
        review_due_by = review_anchor + timedelta(days=_REVIEW_WINDOW_DAYS)

        # Create audit anchor (outside lock — may do I/O)
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
                    "Audit callback failed for bypass '%s' — aborting bypass creation (fail-closed)",
                    bypass_id,
                )
                raise RuntimeError(
                    f"Cannot create emergency bypass '{bypass_id}': "
                    f"audit anchor creation failed — governance mutations require audit trail"
                )

        record = BypassRecord(
            bypass_id=bypass_id,
            role_address=role_address,
            tier=tier,
            reason=reason,
            approved_by=approved_by,
            expanded_envelope=effective_envelope,
            created_at=now,
            expires_at=expires_at,
            expired_manually=False,
            review_due_by=review_due_by,
            audit_anchor_id=audit_anchor_id,
        )

        # M4: Rate limit check + record — atomic to prevent TOCTOU.
        # For MemoryRateLimitStore the outer threading.Lock provides
        # per-process atomicity.  For SqliteRateLimitStore the overridden
        # atomic_check_and_record uses BEGIN IMMEDIATE for cross-process
        # atomicity via SQLite's write lock.
        with self._lock:
            self._rate_limit_store.atomic_check_and_record(
                role_address,
                now,
                MAX_BYPASSES_PER_WEEK,
                COOLDOWN_HOURS,
            )
            # Enforce bounded collection for in-memory bypass records
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

    def check_overdue_reviews(self, as_of: datetime | None = None) -> list[BypassRecord]:
        """Return bypass records whose post-incident review deadline has passed.

        Per PACT spec Section 9, post-incident review is mandatory within
        7 days. This method surfaces bypasses where the review deadline
        has passed without resolution.

        Args:
            as_of: Reference time.  Defaults to ``datetime.now(UTC)``.

        Returns:
            List of ``BypassRecord`` instances with overdue reviews,
            sorted oldest-first.
        """
        if as_of is None:
            as_of = datetime.now(UTC)
        with self._lock:
            overdue = [
                r
                for r in self._bypasses.values()
                if (r.is_expired(as_of) and r.review_due_by is not None and as_of > r.review_due_by)
            ]
        overdue.sort(key=lambda r: r.review_due_by or r.created_at)
        return overdue
