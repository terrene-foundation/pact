# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Cross-Functional Bridges — controlled data and communication flow between agent teams.

Three bridge types enable inter-team collaboration under CARE governance:

- **Standing**: Permanent relationships (e.g., DM <-> Standards)
- **Scoped**: Time-bounded, purpose-bounded (e.g., 7-day read access for a review)
- **Ad-Hoc**: One-time request/response (e.g., governance review of content)

All bridges require dual-side approval, enforce path-level access control,
and maintain a complete audit log of every data access.
"""

from __future__ import annotations

import fnmatch
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BridgeType(str, Enum):
    """Type of cross-functional bridge."""

    STANDING = "standing"
    SCOPED = "scoped"
    AD_HOC = "ad_hoc"


class BridgeStatus(str, Enum):
    """Lifecycle status of a bridge.

    CARE formal spec states: PROPOSED, NEGOTIATING, ACTIVE, SUSPENDED, CLOSED.
    PENDING maps to PROPOSED. EXPIRED and REVOKED are implementation-specific
    extensions for time-bounded and trust-revoked bridges respectively.
    """

    PENDING = "pending"  # awaiting both sides' approval (maps to PROPOSED)
    NEGOTIATING = "negotiating"  # RT5-13: terms under discussion
    ACTIVE = "active"  # approved and operational
    SUSPENDED = "suspended"  # RT5-13: temporarily paused (ACTIVE -> SUSPENDED)
    EXPIRED = "expired"  # time-bounded bridge expired
    CLOSED = "closed"  # manually closed or ad-hoc completed
    REVOKED = "revoked"  # revoked due to trust revocation


_TERMINAL_STATES = frozenset({BridgeStatus.EXPIRED, BridgeStatus.CLOSED, BridgeStatus.REVOKED})


class BridgePermission(BaseModel):
    """What can flow through the bridge."""

    read_paths: list[str] = Field(default_factory=list)  # workspace paths readable (glob patterns)
    write_paths: list[str] = Field(
        default_factory=list
    )  # workspace paths writable (glob patterns, rare)
    message_types: list[str] = Field(default_factory=list)  # allowed message types
    requires_attribution: bool = False  # must credit source


# Default review intervals by bridge type (in days).
_REVIEW_INTERVAL_DAYS: dict[BridgeType, int] = {
    BridgeType.STANDING: 90,
    BridgeType.SCOPED: 90,  # default; overridden per-bridge if milestone dates exist
    BridgeType.AD_HOC: 0,  # ad-hoc bridges are reviewed in aggregate, not individually
}


class BridgeReviewPolicy(BaseModel):
    """Review policy for a bridge based on type.

    Standing bridges are reviewed quarterly (90 days). Scoped bridges use
    their valid_until as a milestone proxy; if not set, fall back to 90 days.
    Ad-Hoc bridges have no individual review — they are analysed in aggregate
    via ``BridgeManager.get_adhoc_bridge_frequency``.
    """

    review_interval_days: int = 90
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None
    review_notes: list[str] = Field(default_factory=list)


class Bridge(BaseModel):
    """Base model for all cross-functional bridges.

    A bridge connects a source team to a target team with explicit permissions,
    dual-side approval, and a full audit trail.
    """

    bridge_id: str = Field(default_factory=lambda: f"br-{uuid4().hex[:8]}")
    bridge_type: BridgeType
    source_team_id: str
    target_team_id: str
    purpose: str
    permissions: BridgePermission = Field(default_factory=BridgePermission)
    status: BridgeStatus = BridgeStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str = ""
    # RT12-014 / RT13: Store approver identity, not just boolean
    approved_by_source: str | None = None  # approver_id or None if not yet approved
    approved_by_target: str | None = None  # approver_id or None if not yet approved
    # Scoped bridge fields
    valid_until: datetime | None = None
    one_time_use: bool = False
    used: bool = False
    # Ad-hoc fields
    request_payload: dict = Field(default_factory=dict)
    response_payload: dict | None = None
    responded_at: datetime | None = None
    # Audit
    access_log: list[dict] = Field(default_factory=list)
    # Replacement chain (Task 3402)
    replaced_by: str | None = None  # bridge_id of the replacement bridge
    replacement_for: str | None = None  # bridge_id this replaces
    # Review tracking (Task 3403)
    review_policy: BridgeReviewPolicy | None = None
    reviews: list[dict] = Field(default_factory=list)
    # M32/3202: Field-level sharing policy for information flow control
    sharing_policy: object | None = Field(
        default=None,
        description=(
            "BridgeSharingPolicy controlling field-level data flow through this bridge. "
            "Typed as object to avoid circular import — actual type is "
            "pact.trust.constraint.bridge_envelope.BridgeSharingPolicy."
        ),
    )

    # RT2-13: Regular Pydantic field so it survives serialization/deserialization
    frozen_permissions: BridgePermission | None = Field(
        default=None,
        description="RT-22: Frozen snapshot of permissions set on activation",
    )
    # RT2-22: Snapshot of permissions at creation time to prevent bait-and-switch
    creation_permissions: BridgePermission | None = Field(
        default=None,
        description="RT2-22: Deep copy of permissions at creation time",
    )

    def model_post_init(self, __context: object) -> None:
        """RT2-22: Snapshot permissions at creation time to prevent bait-and-switch."""
        if self.creation_permissions is None:
            self.creation_permissions = self.permissions.model_copy(deep=True)

    @property
    def is_active(self) -> bool:
        """Bridge is active if approved, not expired, not revoked.

        Checks status, time bounds, and one-time-use flag.
        """
        if self.status != BridgeStatus.ACTIVE:
            return False
        if self.valid_until is not None and datetime.now(UTC) > self.valid_until:
            return False
        return not (self.one_time_use and self.used)

    @property
    def effective_permissions(self) -> BridgePermission:
        """RT-22/RT2-13: Returns frozen permissions if active, otherwise current permissions."""
        if self.frozen_permissions is not None and self.status == BridgeStatus.ACTIVE:
            return self.frozen_permissions
        return self.permissions

    @property
    def next_review_date(self) -> datetime | None:
        """Compute the next review date based on bridge type and review history.

        - Standing: 90 days after last review, or 90 days after creation if never reviewed.
        - Scoped: uses valid_until as milestone proxy; falls back to 90 days.
        - Ad-Hoc: no individual review date (returns None).
        """
        if self.bridge_type == BridgeType.AD_HOC:
            return None

        interval_days = _REVIEW_INTERVAL_DAYS.get(self.bridge_type, 90)

        # If reviews exist, next date is interval_days after the most recent review.
        if self.reviews:
            last_ts_str = self.reviews[-1].get("timestamp")
            if last_ts_str:
                last_ts = datetime.fromisoformat(last_ts_str)
                return last_ts + timedelta(days=interval_days)

        # If review_policy has an explicit next_review_at, honour it.
        if self.review_policy and self.review_policy.next_review_at:
            return self.review_policy.next_review_at

        # Default: interval_days after creation.
        return self.created_at + timedelta(days=interval_days)

    def mark_reviewed(self, reviewer_id: str, notes: str = "") -> dict:
        """Record a review and schedule the next review date.

        Args:
            reviewer_id: Identifier of the reviewer.
            notes: Optional review notes.

        Returns:
            The review entry dict that was appended.
        """
        now = datetime.now(UTC)
        entry = {
            "reviewer_id": reviewer_id,
            "timestamp": now.isoformat(),
            "notes": notes,
        }
        self.reviews.append(entry)

        # Update the review policy to reflect the new review.
        interval = _REVIEW_INTERVAL_DAYS.get(self.bridge_type, 90)
        if self.review_policy is None:
            self.review_policy = BridgeReviewPolicy(review_interval_days=interval)
        self.review_policy.last_reviewed_at = now
        self.review_policy.next_review_at = now + timedelta(days=interval)
        if notes:
            self.review_policy.review_notes.append(notes)

        logger.info(
            "Bridge %s: reviewed by %s, next review at %s",
            self.bridge_id,
            reviewer_id,
            self.review_policy.next_review_at.isoformat(),
        )
        return entry

    def _activate(self) -> None:
        """Transition to ACTIVE and freeze permissions.

        RT2-22: Freezes from creation-time snapshot, not current permissions,
        to prevent bait-and-switch attacks where permissions are mutated
        between creation and approval.

        RT5-13: Accepts transitions from both PENDING and NEGOTIATING states.
        """
        if self.status not in (BridgeStatus.PENDING, BridgeStatus.NEGOTIATING):
            logger.warning(
                "Bridge %s: cannot activate from state %s (expected PENDING or NEGOTIATING)",
                self.bridge_id,
                self.status.value,
            )
            return
        self.status = BridgeStatus.ACTIVE
        # RT2-22: Freeze from creation-time snapshot
        source = (
            self.creation_permissions if self.creation_permissions is not None else self.permissions
        )
        self.frozen_permissions = source.model_copy(deep=True)
        logger.info(
            "Bridge %s: now ACTIVE (both sides approved, permissions frozen)", self.bridge_id
        )

    def approve_source(self, approver_id: str) -> None:
        """Source team approves the bridge.

        If the target has already approved, the bridge transitions to ACTIVE.

        Args:
            approver_id: Identifier of the agent approving on behalf of the source team.
        """
        # RT12-014 / RT13: Store approver identity for audit traceability
        self.approved_by_source = approver_id
        logger.info(
            "Bridge %s: source approved by %s",
            self.bridge_id,
            approver_id,
        )
        if self.approved_by_source and self.approved_by_target:
            self._activate()

    def approve_target(self, approver_id: str) -> None:
        """Target team approves the bridge.

        If the source has already approved, the bridge transitions to ACTIVE.

        Args:
            approver_id: Identifier of the agent approving on behalf of the target team.
        """
        # RT12-014 / RT13: Store approver identity for audit traceability
        self.approved_by_target = approver_id
        logger.info(
            "Bridge %s: target approved by %s",
            self.bridge_id,
            approver_id,
        )
        if self.approved_by_source and self.approved_by_target:
            self._activate()

    def check_access(self, path: str, access_type: str = "read") -> bool:
        """Check if a specific path can be accessed through this bridge.

        Access is denied if:
        - The bridge is not active
        - The path does not match any permitted pattern for the access type
        - The access type is not 'read' or 'write'

        Args:
            path: The workspace path being accessed.
            access_type: Either 'read' or 'write'.

        Returns:
            True if access is allowed, False otherwise.
        """
        if not self.is_active:
            return False

        # RT-22: Use frozen permissions for active bridges
        perms = self.effective_permissions
        if access_type == "read":
            permitted_patterns = perms.read_paths
        elif access_type == "write":
            permitted_patterns = perms.write_paths
        else:
            logger.warning(
                "Bridge %s: unknown access_type '%s' denied",
                self.bridge_id,
                access_type,
            )
            return False

        return _path_matches_any_pattern(path, permitted_patterns)

    def record_access(self, agent_id: str, path: str, access_type: str = "read") -> None:
        """Record a data access through the bridge.

        For one-time-use bridges, this marks the bridge as used.
        RT13-008: Evicts oldest entries when log exceeds _MAX_ACCESS_LOG_ENTRIES
        to prevent unbounded memory growth.

        Args:
            agent_id: The agent performing the access.
            path: The workspace path accessed.
            access_type: Either 'read' or 'write'.
        """
        entry = {
            "agent_id": agent_id,
            "path": path,
            "access_type": access_type,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.access_log.append(entry)
        # RT13-008: Cap access log to prevent unbounded growth
        if len(self.access_log) > _MAX_ACCESS_LOG_ENTRIES:
            self.access_log = self.access_log[-_MAX_ACCESS_LOG_ENTRIES:]
        logger.info(
            "Bridge %s: access recorded — agent=%s path=%s type=%s",
            self.bridge_id,
            agent_id,
            path,
            access_type,
        )

        if self.one_time_use:
            self.used = True
            logger.info(
                "Bridge %s: one-time-use bridge marked as used",
                self.bridge_id,
            )

    def close(self, reason: str = "") -> None:
        """Close the bridge. Only non-terminal bridges can be closed.

        Args:
            reason: Human-readable reason for closure.
        """
        if self.status in _TERMINAL_STATES:
            logger.warning(
                "Bridge %s: cannot close from terminal state %s",
                self.bridge_id,
                self.status.value,
            )
            return
        self.status = BridgeStatus.CLOSED
        logger.info("Bridge %s: CLOSED — reason: %s", self.bridge_id, reason or "(none)")

    def revoke(self, reason: str = "") -> None:
        """Revoke the bridge due to trust revocation. Only non-terminal bridges can be revoked.

        Args:
            reason: Human-readable reason for revocation.
        """
        if self.status in _TERMINAL_STATES:
            logger.warning(
                "Bridge %s: cannot revoke from terminal state %s",
                self.bridge_id,
                self.status.value,
            )
            return
        self.status = BridgeStatus.REVOKED
        logger.info("Bridge %s: REVOKED — reason: %s", self.bridge_id, reason or "(none)")


_MAX_ACCESS_LOG_ENTRIES = 10_000
"""RT13-008: Maximum number of entries in a bridge's access_log before
oldest entries are evicted. Prevents unbounded memory growth from
high-frequency bridge usage."""

_MAX_BRIDGES_PER_TEAM = 100
"""RT13-002: Maximum number of non-terminal bridges per team. Prevents
bridge flooding DoS where an adversary creates thousands of bridges to
exhaust memory or overwhelm approval queues."""

_MAX_ID_LENGTH = 256
"""RT13-H7: Maximum length for team_id, agent_id, bridge_id, and purpose
strings. Prevents memory exhaustion from pathologically long identifiers."""


class BridgeManager:
    """Manages cross-functional bridges between teams.

    Provides factory methods for creating standing, scoped, and ad-hoc bridges,
    plus lifecycle operations (approval, revocation, expiry) and access control.

    Each bridge is tracked by a BridgeStateMachine that enforces valid state
    transitions according to the CARE formal specification.

    Args:
        trust_callback: Optional callable invoked when a bridge transitions to ACTIVE.
            Receives the activated Bridge. Use this to create EATP trust records
            without introducing a direct dependency on the trust module.
        closure_callback: Optional callable invoked when a bridge is closed.
            Receives the Bridge being closed.
        suspension_callback: Optional callable invoked when a bridge is suspended.
            Receives the Bridge being suspended.
        revocation_callback: Optional callable invoked when a bridge is revoked.
            Receives the revoked Bridge. Use this to trigger EATP bridge delegation
            revocation (RT13-05: cascade revocation on bridge state changes).
    """

    def __init__(
        self,
        trust_callback: Callable[[Bridge], None] | None = None,
        closure_callback: Callable[[Bridge], None] | None = None,
        suspension_callback: Callable[[Bridge], None] | None = None,
        revocation_callback: Callable[[Bridge], None] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._bridges: dict[str, Bridge] = {}
        self._trust_callback = trust_callback
        self._closure_callback = closure_callback
        self._suspension_callback = suspension_callback
        # RT13-05: Callback invoked when a bridge is revoked (team or individual).
        # Use this to trigger EATP bridge delegation revocation via
        # RevocationManager.revoke_bridge_delegations().
        self._revocation_callback = revocation_callback
        # Lazy import to avoid circular dependency (bridge_lifecycle imports BridgeStatus from here)
        from pact_platform.build.workspace.bridge_lifecycle import BridgeStateMachine

        self._BridgeStateMachine = BridgeStateMachine
        self._state_machines: dict[str, BridgeStateMachine] = {}

    def _validate_bridge_params(self, source_team: str, target_team: str, purpose: str) -> None:
        """Validate common bridge creation parameters.

        RT13-001: Rejects self-bridges (source == target).
        RT13-002: Rejects creation if the team already has too many non-terminal bridges.
        RT13-H7: Rejects pathologically long identifiers.

        Args:
            source_team: Identifier of the source team.
            target_team: Identifier of the target team.
            purpose: Human-readable description of the bridge's purpose.

        Raises:
            ValueError: If validation fails.
        """
        # RT13-001: Prevent self-bridges — a team bridging to itself bypasses
        # all cross-team verification since the bridge merely re-exposes the
        # team's own permissions.
        if source_team == target_team:
            raise ValueError(
                f"Cannot create a bridge from team '{source_team}' to itself. "
                f"Cross-Functional Bridges connect different teams."
            )

        # RT13-H7: Input length validation
        for label, value in [
            ("source_team", source_team),
            ("target_team", target_team),
            ("purpose", purpose),
        ]:
            if len(value) > _MAX_ID_LENGTH:
                raise ValueError(f"{label} exceeds maximum length of {_MAX_ID_LENGTH} characters.")

        # RT13-002: Bridge count limit per team
        with self._lock:
            non_terminal = sum(
                1
                for b in self._bridges.values()
                if b.status not in _TERMINAL_STATES
                and (b.source_team_id == source_team or b.target_team_id == source_team)
            )
            if non_terminal >= _MAX_BRIDGES_PER_TEAM:
                raise ValueError(
                    f"Team '{source_team}' has reached the maximum of "
                    f"{_MAX_BRIDGES_PER_TEAM} non-terminal bridges. "
                    f"Close or revoke existing bridges before creating new ones."
                )
            non_terminal_target = sum(
                1
                for b in self._bridges.values()
                if b.status not in _TERMINAL_STATES
                and (b.source_team_id == target_team or b.target_team_id == target_team)
            )
            if non_terminal_target >= _MAX_BRIDGES_PER_TEAM:
                raise ValueError(
                    f"Team '{target_team}' has reached the maximum of "
                    f"{_MAX_BRIDGES_PER_TEAM} non-terminal bridges. "
                    f"Close or revoke existing bridges before creating new ones."
                )

    def _get_or_create_sm(self, bridge_id: str, initial_state: BridgeStatus | None = None):
        """Get or create a BridgeStateMachine for a bridge.

        Args:
            bridge_id: The bridge identifier.
            initial_state: Initial state for new state machines. Defaults to PENDING.

        Returns:
            The BridgeStateMachine for the bridge.
        """
        if bridge_id not in self._state_machines:
            state = initial_state if initial_state is not None else BridgeStatus.PENDING
            self._state_machines[bridge_id] = self._BridgeStateMachine(initial_state=state)
        return self._state_machines[bridge_id]

    def get_state_machine(self, bridge_id: str):
        """Get the lifecycle state machine for a bridge.

        Args:
            bridge_id: The bridge identifier.

        Returns:
            The BridgeStateMachine if found, None otherwise.
        """
        return self._state_machines.get(bridge_id)

    def create_standing_bridge(
        self,
        source_team: str,
        target_team: str,
        purpose: str,
        permissions: BridgePermission,
        created_by: str,
    ) -> Bridge:
        """Create a standing (permanent) bridge.

        Standing bridges have no expiry and remain active until explicitly
        closed or revoked.

        Args:
            source_team: Identifier of the source team.
            target_team: Identifier of the target team.
            purpose: Human-readable description of the bridge's purpose.
            permissions: Access permissions for the bridge.
            created_by: Identifier of the agent creating the bridge.

        Returns:
            The newly created Bridge in PENDING status.

        Raises:
            ValueError: If source_team == target_team (RT13-001), bridge count
                limit exceeded (RT13-002), or input length exceeded (RT13-H7).
        """
        self._validate_bridge_params(source_team, target_team, purpose)
        bridge = Bridge(
            bridge_type=BridgeType.STANDING,
            source_team_id=source_team,
            target_team_id=target_team,
            purpose=purpose,
            permissions=permissions,
            created_by=created_by,
        )
        with self._lock:
            self._bridges[bridge.bridge_id] = bridge
        self._get_or_create_sm(bridge.bridge_id, initial_state=BridgeStatus.PENDING)
        logger.info(
            "Standing bridge %s created: %s -> %s (by %s)",
            bridge.bridge_id,
            source_team,
            target_team,
            created_by,
        )
        return bridge

    def create_scoped_bridge(
        self,
        source_team: str,
        target_team: str,
        purpose: str,
        permissions: BridgePermission,
        created_by: str,
        valid_days: int = 7,
        one_time: bool = False,
    ) -> Bridge:
        """Create a scoped (time-bounded) bridge.

        Scoped bridges expire after valid_days and can optionally be one-time-use.

        Args:
            source_team: Identifier of the source team.
            target_team: Identifier of the target team.
            purpose: Human-readable description of the bridge's purpose.
            permissions: Access permissions for the bridge.
            created_by: Identifier of the agent creating the bridge.
            valid_days: Number of days the bridge remains valid.
            one_time: If True, the bridge is consumed after a single access.

        Returns:
            The newly created Bridge in PENDING status with valid_until set.

        Raises:
            ValueError: If source_team == target_team (RT13-001), bridge count
                limit exceeded (RT13-002), or input length exceeded (RT13-H7).
        """
        self._validate_bridge_params(source_team, target_team, purpose)
        bridge = Bridge(
            bridge_type=BridgeType.SCOPED,
            source_team_id=source_team,
            target_team_id=target_team,
            purpose=purpose,
            permissions=permissions,
            created_by=created_by,
            valid_until=datetime.now(UTC) + timedelta(days=valid_days),
            one_time_use=one_time,
        )
        with self._lock:
            self._bridges[bridge.bridge_id] = bridge
        self._get_or_create_sm(bridge.bridge_id, initial_state=BridgeStatus.PENDING)
        logger.info(
            "Scoped bridge %s created: %s -> %s (expires in %d days, one_time=%s, by %s)",
            bridge.bridge_id,
            source_team,
            target_team,
            valid_days,
            one_time,
            created_by,
        )
        return bridge

    def create_adhoc_bridge(
        self,
        source_team: str,
        target_team: str,
        purpose: str,
        request_payload: dict,
        created_by: str,
    ) -> Bridge:
        """Create an ad-hoc (one-time request/response) bridge.

        Ad-hoc bridges carry a request payload and auto-close after a response
        is provided.

        Args:
            source_team: Identifier of the requesting team.
            target_team: Identifier of the responding team.
            purpose: Human-readable description of what is being requested.
            request_payload: The request data to be processed by the target team.
            created_by: Identifier of the agent creating the request.

        Returns:
            The newly created Bridge in PENDING status with request_payload set.

        Raises:
            ValueError: If source_team == target_team (RT13-001), bridge count
                limit exceeded (RT13-002), or input length exceeded (RT13-H7).
        """
        self._validate_bridge_params(source_team, target_team, purpose)
        bridge = Bridge(
            bridge_type=BridgeType.AD_HOC,
            source_team_id=source_team,
            target_team_id=target_team,
            purpose=purpose,
            created_by=created_by,
            one_time_use=True,
            request_payload=request_payload,
        )
        with self._lock:
            self._bridges[bridge.bridge_id] = bridge
        self._get_or_create_sm(bridge.bridge_id, initial_state=BridgeStatus.PENDING)
        logger.info(
            "Ad-hoc bridge %s created: %s -> %s (by %s) — purpose: %s",
            bridge.bridge_id,
            source_team,
            target_team,
            created_by,
            purpose,
        )
        return bridge

    def respond_to_adhoc(
        self,
        bridge_id: str,
        response: dict,
        responder_id: str,
    ) -> Bridge:
        """Respond to an ad-hoc bridge request. Auto-closes after response.

        Args:
            bridge_id: The bridge to respond to.
            response: The response data.
            responder_id: Identifier of the agent providing the response.

        Returns:
            The updated Bridge with response_payload set and status CLOSED.

        Raises:
            ValueError: If the bridge is not found or is not an ad-hoc bridge.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot respond to a non-existent bridge."
                )
            if bridge.bridge_type != BridgeType.AD_HOC:
                raise ValueError(
                    f"Bridge '{bridge_id}' is type '{bridge.bridge_type.value}', not ad-hoc. "
                    f"Only ad-hoc bridges accept responses."
                )

            bridge.response_payload = response
            bridge.responded_at = datetime.now(UTC)
            bridge.close(reason=f"Ad-hoc response provided by {responder_id}")
        logger.info(
            "Ad-hoc bridge %s: response recorded by %s, bridge closed",
            bridge_id,
            responder_id,
        )
        return bridge

    def request_adhoc_bridge(
        self,
        source_team: str,
        target_team: str,
        purpose: str,
        request_payload: dict,
        created_by: str,
        *,
        auto_approve: bool = False,
    ) -> Bridge:
        """Create an ad-hoc bridge for a one-off cross-team request.

        Creates an ad-hoc bridge and optionally auto-approves it for immediate
        use when both teams have standing trust. After creation, checks whether
        the ad-hoc bridge frequency between these teams exceeds the promotion
        threshold and logs a suggestion to create a Standing bridge if so.

        Args:
            source_team: Identifier of the requesting team.
            target_team: Identifier of the responding team.
            purpose: Human-readable description of the request.
            request_payload: The request data for the target team.
            created_by: Identifier of the agent creating the request.
            auto_approve: If True and both teams have standing trust,
                auto-approve the bridge for immediate use.

        Returns:
            The newly created Bridge (ACTIVE if auto-approved, PENDING otherwise).
        """
        bridge = self.create_adhoc_bridge(
            source_team=source_team,
            target_team=target_team,
            purpose=purpose,
            request_payload=request_payload,
            created_by=created_by,
        )

        if auto_approve:
            # Check for standing trust: an ACTIVE standing bridge between the teams
            has_standing_trust = False
            with self._lock:
                for existing in self._bridges.values():
                    if existing.bridge_type != BridgeType.STANDING:
                        continue
                    if existing.status != BridgeStatus.ACTIVE:
                        continue
                    pair_match = (
                        existing.source_team_id == source_team
                        and existing.target_team_id == target_team
                    ) or (
                        existing.source_team_id == target_team
                        and existing.target_team_id == source_team
                    )
                    if pair_match:
                        has_standing_trust = True
                        break

            if has_standing_trust:
                # Auto-approve both sides
                self.approve_bridge_source(bridge.bridge_id, created_by)
                self.approve_bridge_target(bridge.bridge_id, created_by)
                logger.info(
                    "M33-3303: Auto-approved ad-hoc bridge %s between '%s' and '%s' "
                    "(standing trust exists)",
                    bridge.bridge_id,
                    source_team,
                    target_team,
                )

        # Check ad-hoc frequency for promotion detection
        freq = self.get_adhoc_bridge_frequency(source_team, target_team)
        if freq.get("suggest_standing", False):
            logger.warning(
                "M33-3303: Ad-hoc bridge frequency between '%s' and '%s' is %d "
                "(exceeds threshold). Consider creating a Standing bridge.",
                source_team,
                target_team,
                freq.get("count", 0),
            )

        return bridge

    def get_bridges_for_team(self, team_id: str) -> list[Bridge]:
        """Get all bridges for a team (both as source and target).

        Args:
            team_id: The team identifier to look up.

        Returns:
            List of Bridge objects where the team is source or target.
        """
        with self._lock:
            return [
                bridge
                for bridge in self._bridges.values()
                if bridge.source_team_id == team_id or bridge.target_team_id == team_id
            ]

    def list_all_bridges(self) -> list[Bridge]:
        """List all bridges regardless of team or status.

        Returns:
            A list of all bridges managed by this BridgeManager.
        """
        with self._lock:
            return list(self._bridges.values())

    def get_bridge(self, bridge_id: str) -> Bridge | None:
        """Get a bridge by ID.

        Args:
            bridge_id: The bridge identifier.

        Returns:
            The Bridge if found, None otherwise.
        """
        with self._lock:
            return self._bridges.get(bridge_id)

    def revoke_team_bridges(self, team_id: str, reason: str) -> list[Bridge]:
        """Revoke all bridges involving a team (on team trust revocation).

        Args:
            team_id: The team whose bridges should be revoked.
            reason: Human-readable reason for the revocation.

        Returns:
            List of Bridge objects that were revoked.
        """
        revoked: list[Bridge] = []
        with self._lock:
            for bridge in self._bridges.values():
                if bridge.source_team_id == team_id or bridge.target_team_id == team_id:
                    if bridge.status not in _TERMINAL_STATES:  # RT6-11: skip already-terminal
                        bridge.revoke(reason=reason)
                        revoked.append(bridge)
        # RT13-05: Trigger EATP bridge delegation revocation for each revoked bridge
        if self._revocation_callback:
            for bridge in revoked:
                self._revocation_callback(bridge)
        logger.info(
            "Revoked %d bridges for team %s — reason: %s",
            len(revoked),
            team_id,
            reason,
        )
        return revoked

    def negotiate_bridge(self, bridge_id: str) -> Bridge:
        """Transition a bridge from PENDING to NEGOTIATING.

        RT5-13: The NEGOTIATING state indicates that bridge terms are being
        discussed between the two teams.

        Args:
            bridge_id: The bridge to transition.

        Returns:
            The updated Bridge in NEGOTIATING status.

        Raises:
            ValueError: If the bridge is not found or is not in PENDING state.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot negotiate a non-existent bridge."
                )
            if bridge.status != BridgeStatus.PENDING:
                raise ValueError(
                    f"Bridge '{bridge_id}' is in state '{bridge.status.value}', not PENDING. "
                    f"Only PENDING bridges can transition to NEGOTIATING."
                )
            bridge.status = BridgeStatus.NEGOTIATING
            sm = self._get_or_create_sm(bridge_id, initial_state=BridgeStatus.PENDING)
            if sm.state == BridgeStatus.PENDING:
                sm.transition_to(BridgeStatus.NEGOTIATING, reason="Bridge entering negotiation")
        logger.info("Bridge %s: PENDING -> NEGOTIATING", bridge_id)
        return bridge

    def suspend_bridge(self, bridge_id: str, reason: str) -> Bridge:
        """Suspend an active bridge temporarily.

        RT5-13: The SUSPENDED state allows pausing an active bridge
        without closing or revoking it. The bridge can be resumed later.

        Args:
            bridge_id: The bridge to suspend.
            reason: Human-readable reason for suspension.

        Returns:
            The updated Bridge in SUSPENDED status.

        Raises:
            ValueError: If the bridge is not found or is not ACTIVE.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot suspend a non-existent bridge."
                )
            if bridge.status != BridgeStatus.ACTIVE:
                raise ValueError(
                    f"Bridge '{bridge_id}' is in state '{bridge.status.value}', not ACTIVE. "
                    f"Only ACTIVE bridges can be suspended."
                )
            bridge.status = BridgeStatus.SUSPENDED
            sm = self._get_or_create_sm(bridge_id, initial_state=BridgeStatus.ACTIVE)
            if sm.state == BridgeStatus.ACTIVE:
                sm.transition_to(BridgeStatus.SUSPENDED, reason=reason)
        logger.info("Bridge %s: ACTIVE -> SUSPENDED — reason: %s", bridge_id, reason)
        if self._suspension_callback:
            self._suspension_callback(bridge)
        return bridge

    def resume_bridge(self, bridge_id: str) -> Bridge:
        """Resume a suspended bridge back to ACTIVE.

        RT5-13: Restores a SUSPENDED bridge to ACTIVE status. Frozen
        permissions remain intact from the original activation.

        Args:
            bridge_id: The bridge to resume.

        Returns:
            The updated Bridge in ACTIVE status.

        Raises:
            ValueError: If the bridge is not found or is not SUSPENDED.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot resume a non-existent bridge."
                )
            if bridge.status != BridgeStatus.SUSPENDED:
                raise ValueError(
                    f"Bridge '{bridge_id}' is in state '{bridge.status.value}', not SUSPENDED. "
                    f"Only SUSPENDED bridges can be resumed."
                )
            # RT7-12: Check if bridge has expired while suspended
            if bridge.valid_until is not None and datetime.now(UTC) > bridge.valid_until:
                bridge.status = BridgeStatus.EXPIRED
                sm = self._get_or_create_sm(bridge_id, initial_state=BridgeStatus.SUSPENDED)
                if sm.state == BridgeStatus.SUSPENDED:
                    sm.transition_to(
                        BridgeStatus.EXPIRED,
                        reason="Bridge expired while suspended",
                    )
                logger.info(
                    "Bridge %s: SUSPENDED -> EXPIRED (valid_until passed while suspended)",
                    bridge_id,
                )
                raise ValueError(
                    f"Bridge '{bridge_id}' has expired "
                    f"(valid_until={bridge.valid_until.isoformat()}) "
                    f"and cannot be resumed"
                )
            bridge.status = BridgeStatus.ACTIVE
            sm = self._get_or_create_sm(bridge_id, initial_state=BridgeStatus.SUSPENDED)
            if sm.state == BridgeStatus.SUSPENDED:
                sm.transition_to(BridgeStatus.ACTIVE, reason="Bridge resumed")
        logger.info("Bridge %s: SUSPENDED -> ACTIVE (resumed)", bridge_id)
        return bridge

    def update_bridge_permissions(
        self, bridge_id: str, new_permissions: BridgePermission
    ) -> Bridge:
        """Update the permissions of a bridge.

        RT5-13: Once a bridge is ACTIVE (or SUSPENDED, EXPIRED, CLOSED,
        REVOKED), its terms are immutable per the CARE spec. Permissions
        can only be modified while the bridge is in PENDING or NEGOTIATING
        state.

        Args:
            bridge_id: The bridge to update.
            new_permissions: The new permissions to set.

        Returns:
            The updated Bridge with new permissions.

        Raises:
            ValueError: If the bridge is not found or is in an immutable state.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot update a non-existent bridge."
                )
            mutable_states = (BridgeStatus.PENDING, BridgeStatus.NEGOTIATING)
            if bridge.status not in mutable_states:
                raise ValueError(
                    f"Bridge '{bridge_id}' is in state '{bridge.status.value}'. "
                    f"Bridge terms are immutable once activated. "
                    f"Permissions can only be updated in PENDING or NEGOTIATING states."
                )
            bridge.permissions = new_permissions
            bridge.creation_permissions = new_permissions.model_copy(deep=True)
        logger.info("Bridge %s: permissions updated (state=%s)", bridge_id, bridge.status.value)
        return bridge

    def expire_bridges(self) -> list[Bridge]:
        """Check and expire time-bounded bridges that have passed their valid_until.

        Returns:
            List of Bridge objects that were transitioned to EXPIRED.
        """
        now = datetime.now(UTC)
        expired: list[Bridge] = []
        with self._lock:
            for bridge in self._bridges.values():
                if (
                    bridge.status in (BridgeStatus.ACTIVE, BridgeStatus.SUSPENDED)  # RT6-05
                    and bridge.valid_until is not None
                    and now > bridge.valid_until
                ):
                    previous_status = bridge.status
                    bridge.status = BridgeStatus.EXPIRED
                    sm = self._get_or_create_sm(bridge.bridge_id, initial_state=previous_status)
                    if sm.can_transition_to(BridgeStatus.EXPIRED):
                        sm.transition_to(
                            BridgeStatus.EXPIRED,
                            reason="Bridge time window expired",
                        )
                    expired.append(bridge)
        for b in expired:
            logger.info(
                "Bridge %s expired (valid_until=%s)",
                b.bridge_id,
                b.valid_until.isoformat() if b.valid_until else "?",
            )
        return expired

    def access_through_bridge(
        self,
        bridge_id: str,
        agent_id: str,
        path: str,
        access_type: str = "read",
        *,
        revoked_agents: set[str] | None = None,
        agent_team_id: str | None = None,
    ) -> bool:
        """Attempt to access data through a bridge.

        Checks permissions, agent revocation status, and team membership,
        then records the access in the bridge audit log.

        Args:
            bridge_id: The bridge to access through.
            agent_id: The agent performing the access.
            path: The workspace path being accessed.
            access_type: Either 'read' or 'write'.
            revoked_agents: RT2-05: Set of revoked agent IDs for defense-in-depth.
            agent_team_id: RT2-16: Team the agent belongs to, for membership verification.

        Returns:
            True if access was allowed, False if denied.
        """
        # RT13-H1: Hold lock for the entire access-check flow to prevent
        # TOCTOU — a bridge could be revoked between lookup and use.
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                logger.warning(
                    "access_through_bridge: bridge '%s' not found",
                    bridge_id,
                )
                return False

            # RT2-05: Defense-in-depth — reject revoked agents
            if revoked_agents and agent_id in revoked_agents:
                logger.warning(
                    "Bridge %s: access DENIED for revoked agent=%s",
                    bridge_id,
                    agent_id,
                )
                return False

            # RT8-05: Fail-closed on missing team context. Bridge directionality
            # requires knowing which team the agent belongs to. Without this
            # information, we cannot enforce source->target permissions.
            if agent_team_id is None:
                logger.warning(
                    "Bridge %s: access DENIED — agent=%s provided no team context, "
                    "cannot enforce directionality",
                    bridge_id,
                    agent_id,
                )
                return False

            # RT2-16: Verify agent belongs to source or target team
            if agent_team_id != bridge.source_team_id and agent_team_id != bridge.target_team_id:
                logger.warning(
                    "Bridge %s: access DENIED — agent=%s team=%s not in source (%s) or target (%s)",
                    bridge_id,
                    agent_id,
                    agent_team_id,
                    bridge.source_team_id,
                    bridge.target_team_id,
                )
                return False

            # RT7-07: Enforce bridge directionality.
            # read_paths/write_paths grant the SOURCE team access to the
            # TARGET team's data.  A target-team agent cannot use those
            # same permissions — they need a separate reverse bridge.
            if agent_team_id == bridge.target_team_id:
                logger.warning(
                    "Bridge %s: access DENIED — agent=%s is on target team (%s), "
                    "bridge permissions flow source->target only",
                    bridge_id,
                    agent_id,
                    agent_team_id,
                )
                return False

            # RT13-H1: Re-check bridge is still active after all pre-checks.
            # This guards against a concurrent revoke between lookup and use.
            if not bridge.is_active:
                logger.warning(
                    "Bridge %s: access DENIED — bridge no longer active "
                    "(revoked/closed during access check)",
                    bridge_id,
                )
                return False

            if not bridge.check_access(path, access_type):
                logger.info(
                    "Bridge %s: access DENIED for agent=%s path=%s type=%s",
                    bridge_id,
                    agent_id,
                    path,
                    access_type,
                )
                return False

            # RT12-004: Enforce NEVER_SHARE at data flow level
            if bridge.sharing_policy is not None:
                from pact_platform.trust.constraint.bridge_envelope import SharingMode

                sharing_mode = bridge.sharing_policy.check_field(path)  # type: ignore[union-attr]
                if sharing_mode == SharingMode.NEVER_SHARE:
                    logger.warning(
                        "Bridge %s: access DENIED — path=%s is NEVER_SHARE per sharing policy",
                        bridge_id,
                        path,
                    )
                    return False

            bridge.record_access(agent_id, path, access_type)
            return True

    # ------------------------------------------------------------------
    # Task 3401: Manager-level approval with trust callback
    # ------------------------------------------------------------------

    def approve_bridge_source(self, bridge_id: str, approver_id: str) -> Bridge:
        """Approve a bridge on behalf of the source team.

        Delegates to ``Bridge.approve_source`` and, if the bridge becomes ACTIVE,
        invokes the trust_callback to create EATP trust records.

        Args:
            bridge_id: The bridge to approve.
            approver_id: Identifier of the approving agent.

        Returns:
            The updated Bridge.

        Raises:
            ValueError: If the bridge is not found.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot approve a non-existent bridge."
                )
            was_active_before = bridge.status == BridgeStatus.ACTIVE
            bridge.approve_source(approver_id)
            became_active = bridge.status == BridgeStatus.ACTIVE and not was_active_before
            if became_active:
                sm = self._get_or_create_sm(bridge_id)
                if sm.can_transition_to(BridgeStatus.ACTIVE):
                    sm.transition_to(BridgeStatus.ACTIVE, reason="Both sides approved")
        if became_active and self._trust_callback:
            self._trust_callback(bridge)
        return bridge

    def approve_bridge_target(self, bridge_id: str, approver_id: str) -> Bridge:
        """Approve a bridge on behalf of the target team.

        Delegates to ``Bridge.approve_target`` and, if the bridge becomes ACTIVE,
        invokes the trust_callback to create EATP trust records.

        Args:
            bridge_id: The bridge to approve.
            approver_id: Identifier of the approving agent.

        Returns:
            The updated Bridge.

        Raises:
            ValueError: If the bridge is not found.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot approve a non-existent bridge."
                )
            was_active_before = bridge.status == BridgeStatus.ACTIVE
            bridge.approve_target(approver_id)
            became_active = bridge.status == BridgeStatus.ACTIVE and not was_active_before
            if became_active:
                sm = self._get_or_create_sm(bridge_id)
                if sm.can_transition_to(BridgeStatus.ACTIVE):
                    sm.transition_to(BridgeStatus.ACTIVE, reason="Both sides approved")
        if became_active and self._trust_callback:
            self._trust_callback(bridge)
        return bridge

    # ------------------------------------------------------------------
    # Task 3401: Manager-level closure with callback
    # ------------------------------------------------------------------

    def close_bridge(self, bridge_id: str, reason: str) -> Bridge:
        """Close a bridge — marks as CLOSED and invokes closure_callback if set.

        This is the manager-level close that orchestrates state machine
        transitions and trust cleanup via the closure callback.

        Args:
            bridge_id: The bridge to close.
            reason: Human-readable reason for closure.

        Returns:
            The updated Bridge in CLOSED status.

        Raises:
            ValueError: If the bridge is not found or is already in a terminal state.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot close a non-existent bridge."
                )
            if bridge.status in _TERMINAL_STATES:
                raise ValueError(
                    f"Bridge '{bridge_id}' is in terminal state '{bridge.status.value}'. "
                    f"Cannot close."
                )
            previous_status = bridge.status
            bridge.close(reason=reason)
            sm = self._get_or_create_sm(bridge_id, initial_state=previous_status)
            if sm.can_transition_to(BridgeStatus.CLOSED):
                sm.transition_to(BridgeStatus.CLOSED, reason=reason)
        if self._closure_callback:
            self._closure_callback(bridge)
        # RT13-05: Bridge closure is terminal — revoke bridge delegations
        if self._revocation_callback:
            self._revocation_callback(bridge)
        return bridge

    # ------------------------------------------------------------------
    # Task 3402: Bridge modification via replacement
    # ------------------------------------------------------------------

    def modify_bridge(
        self,
        bridge_id: str,
        new_permissions: BridgePermission,
        new_purpose: str | None = None,
        modifier_id: str = "",
    ) -> Bridge:
        """Modify a bridge by suspending the current one and creating a replacement.

        CARE spec says bridge terms are immutable once ACTIVE. This method
        implements the suspend-replace pattern that preserves the full audit trail.

        1. Suspend the current bridge.
        2. Create a new bridge with updated terms.
        3. Link old -> new bridge via replacement fields.
        4. New bridge requires fresh bilateral approval (starts in PENDING).
        5. Old bridge remains SUSPENDED with a reference to the replacement.

        Args:
            bridge_id: The bridge to modify.
            new_permissions: Updated permissions for the replacement bridge.
            new_purpose: Optional new purpose description. Defaults to the original purpose.
            modifier_id: Identifier of the agent requesting modification.

        Returns:
            The NEW bridge (in PENDING status).

        Raises:
            ValueError: If the bridge is not found or is not ACTIVE.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot modify a non-existent bridge."
                )
            if bridge.status != BridgeStatus.ACTIVE:
                raise ValueError(
                    f"Bridge '{bridge_id}' is in state '{bridge.status.value}', not ACTIVE. "
                    f"Only ACTIVE bridges can be modified via replacement."
                )

        # Suspend the old bridge (releases the lock internally).
        self.suspend_bridge(bridge_id, reason=f"Suspended for modification by {modifier_id}")

        # Determine the factory method based on bridge type.
        purpose = new_purpose if new_purpose is not None else bridge.purpose
        if bridge.bridge_type == BridgeType.STANDING:
            new_bridge = self.create_standing_bridge(
                source_team=bridge.source_team_id,
                target_team=bridge.target_team_id,
                purpose=purpose,
                permissions=new_permissions,
                created_by=modifier_id or bridge.created_by,
            )
        elif bridge.bridge_type == BridgeType.SCOPED:
            # Preserve the remaining validity window for scoped bridges.
            remaining_days = 7
            if bridge.valid_until:
                remaining = bridge.valid_until - datetime.now(UTC)
                remaining_days = max(1, remaining.days)
            new_bridge = self.create_scoped_bridge(
                source_team=bridge.source_team_id,
                target_team=bridge.target_team_id,
                purpose=purpose,
                permissions=new_permissions,
                created_by=modifier_id or bridge.created_by,
                valid_days=remaining_days,
                one_time=bridge.one_time_use,
            )
        else:
            # Ad-hoc bridges are one-time; modification creates a new ad-hoc.
            new_bridge = self.create_adhoc_bridge(
                source_team=bridge.source_team_id,
                target_team=bridge.target_team_id,
                purpose=purpose,
                request_payload=bridge.request_payload,
                created_by=modifier_id or bridge.created_by,
            )

        # Link the bridges.
        with self._lock:
            new_bridge.replacement_for = bridge.bridge_id
            bridge.replaced_by = new_bridge.bridge_id

        logger.info(
            "Bridge %s: modified — old bridge SUSPENDED, new bridge %s created (PENDING)",
            bridge_id,
            new_bridge.bridge_id,
        )
        return new_bridge

    # ------------------------------------------------------------------
    # Task 3403: Bridge review cadence
    # ------------------------------------------------------------------

    def get_bridges_needing_review(self) -> list[Bridge]:
        """Get all active bridges that are due for review.

        Returns bridges whose ``next_review_date`` is in the past. Excludes
        ad-hoc bridges (reviewed in aggregate) and non-ACTIVE bridges.

        Returns:
            List of Bridge objects that are overdue for review.
        """
        now = datetime.now(UTC)
        result: list[Bridge] = []
        with self._lock:
            for bridge in self._bridges.values():
                if bridge.status != BridgeStatus.ACTIVE:
                    continue
                if bridge.bridge_type == BridgeType.AD_HOC:
                    continue
                review_date = bridge.next_review_date
                if review_date is not None and now > review_date:
                    result.append(bridge)
        return result

    def mark_bridge_reviewed(self, bridge_id: str, reviewer_id: str, notes: str = "") -> Bridge:
        """Mark a bridge as reviewed and schedule the next review.

        Delegates to ``Bridge.mark_reviewed`` which appends the review entry
        and updates the review policy.

        Args:
            bridge_id: The bridge to mark as reviewed.
            reviewer_id: Identifier of the reviewer.
            notes: Optional review notes.

        Returns:
            The updated Bridge.

        Raises:
            ValueError: If the bridge is not found.
        """
        with self._lock:
            bridge = self._bridges.get(bridge_id)
            if bridge is None:
                raise ValueError(
                    f"Bridge '{bridge_id}' not found. Cannot review a non-existent bridge."
                )
            bridge.mark_reviewed(reviewer_id, notes)
        return bridge

    def get_adhoc_bridge_frequency(
        self,
        source_team: str,
        target_team: str,
        threshold: int = 5,
    ) -> dict:
        """Get frequency of ad-hoc bridges between two teams.

        Analyses all ad-hoc bridges (regardless of status) between the given
        team pair and suggests upgrading to a Standing bridge if the count
        exceeds the threshold.

        Args:
            source_team: Source team identifier.
            target_team: Target team identifier.
            threshold: Number of ad-hoc bridges above which a Standing bridge
                is recommended.

        Returns:
            Dict with keys ``count``, ``suggest_standing``, and ``bridges``.
        """
        matching: list[Bridge] = []
        with self._lock:
            for bridge in self._bridges.values():
                if bridge.bridge_type != BridgeType.AD_HOC:
                    continue
                # Match the team pair in either direction.
                pair_match = (
                    bridge.source_team_id == source_team and bridge.target_team_id == target_team
                ) or (bridge.source_team_id == target_team and bridge.target_team_id == source_team)
                if pair_match:
                    matching.append(bridge)

        count = len(matching)
        return {
            "count": count,
            "suggest_standing": count > threshold,
            "bridges": [b.bridge_id for b in matching],
        }


def _path_matches_any_pattern(path: str, patterns: list[str]) -> bool:
    """Check if a path matches any of the given glob patterns.

    Args:
        path: The filesystem-style path to check.
        patterns: List of glob patterns (supporting * and ** wildcards).

    Returns:
        True if the path matches at least one pattern.
    """
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
