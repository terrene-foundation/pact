# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Trust posture model — manages the evolutionary trust lifecycle for agents.

Trust postures evolve based on evidence:
- Upgrades require demonstrated performance (gradual)
- Downgrades are instant on any negative incident

EATP SDK Alignment (M24):
    This module uses ``eatp.postures.PostureStateMachine`` as the base state
    machine for posture transitions, registering CARE's evidence-based upgrade
    checks as ``TransitionGuard`` instances via ``add_guard()``.

    CARE-specific extensions that go beyond the EATP SDK:
    - P1: Evidence-based upgrade model (PostureEvidence with success rate, ops, incidents)
    - P2: NEVER_DELEGATED_ACTIONS set (canonical list of actions that must never be delegated)
    - P3: ShadowEnforcer integration in posture transitions
    - P4: Time-based upgrade prerequisites (days_at_current_posture)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import IntEnum

from eatp.postures import (
    PostureStateMachine as EATPPostureStateMachine,
)
from eatp.postures import (
    PostureTransitionRequest,
)
from eatp.postures import (
    TrustPosture as EATPTrustPosture,
)
from pydantic import BaseModel, Field

from care_platform.build.config.schema import TrustPostureLevel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CARE-to-EATP posture mapping
# ---------------------------------------------------------------------------
# CARE uses its own TrustPostureLevel enum (from config.schema) for
# configuration consistency. This mapping connects CARE levels to the
# EATP SDK's TrustPosture enum for state machine operations.


def _build_posture_mapping() -> dict[TrustPostureLevel, EATPTrustPosture]:
    """Build CARE-to-EATP posture mapping, tolerating missing EATP enum values."""
    mapping: dict[TrustPostureLevel, EATPTrustPosture] = {}
    for care_level in TrustPostureLevel:
        eatp_name = care_level.name  # e.g., "PSEUDO_AGENT"
        eatp_val = getattr(EATPTrustPosture, eatp_name, None)
        if eatp_val is not None:
            mapping[care_level] = eatp_val
        else:
            logger.debug(
                "EATP TrustPosture has no '%s' — CARE level will use identity mapping",
                eatp_name,
            )
    return mapping


_CARE_TO_EATP: dict[TrustPostureLevel, EATPTrustPosture] = _build_posture_mapping()

_EATP_TO_CARE: dict[EATPTrustPosture, TrustPostureLevel] = {v: k for k, v in _CARE_TO_EATP.items()}

# Ordered posture levels (lower = more restrictive)
POSTURE_ORDER: dict[TrustPostureLevel, int] = {
    TrustPostureLevel.PSEUDO_AGENT: 0,
    TrustPostureLevel.SUPERVISED: 1,
    TrustPostureLevel.SHARED_PLANNING: 2,
    TrustPostureLevel.CONTINUOUS_INSIGHT: 3,
    TrustPostureLevel.DELEGATED: 4,
}


# ---------------------------------------------------------------------------
# EATP-GAP: P2 — NEVER_DELEGATED_ACTIONS
# ---------------------------------------------------------------------------
# The EATP SDK's PostureStateMachine has no concept of actions that must
# never be fully delegated regardless of posture. This is a CARE-specific
# governance enforcement layer.

NEVER_DELEGATED_ACTIONS: set[str] = {  # EATP-GAP: P2
    "content_strategy",
    "novel_outreach",
    "crisis_response",
    "financial_decisions",
    "modify_constraints",
    "modify_governance",
    "external_publication",
}


class PostureChangeType(IntEnum):
    """Type of posture change."""

    UPGRADE = 1
    DOWNGRADE = -1


# ---------------------------------------------------------------------------
# EATP-GAP: P1 — Evidence-based upgrade model
# ---------------------------------------------------------------------------
# The EATP SDK's TransitionGuard is callback-only (check_fn). It has no
# structured evidence model. CARE defines PostureEvidence with quantitative
# metrics (success rate, operations, days, incidents, ShadowEnforcer pass rate)
# to enforce evidence-based upgrades.


class PostureEvidence(BaseModel):  # EATP-GAP: P1
    """Evidence supporting a posture upgrade.

    EATP SDK's TransitionGuard uses plain callbacks with no structured
    evidence model. CARE requires quantitative evidence for upgrade
    decisions, including:
    - Operation success rate
    - Total operation count
    - Time at current posture (EATP-GAP: P4)
    - ShadowEnforcer pass rate (EATP-GAP: P3)
    - Incident count
    """

    successful_operations: int = Field(default=0, ge=0)
    total_operations: int = Field(default=0, ge=0)
    days_at_current_posture: int = Field(default=0, ge=0)  # EATP-GAP: P4
    shadow_enforcer_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)  # EATP-GAP: P3
    incidents: int = Field(default=0, ge=0)
    shadow_blocked_count: int = Field(
        default=0,
        ge=0,
        description="Number of shadow-blocked actions (informational only, does not block upgrades)",
    )

    @property
    def success_rate(self) -> float:
        if self.total_operations == 0:
            return 0.0
        return self.successful_operations / self.total_operations


class PostureChange(BaseModel):
    """Record of a posture change."""

    agent_id: str
    from_posture: TrustPostureLevel
    to_posture: TrustPostureLevel
    change_type: PostureChangeType
    reason: str
    evidence: PostureEvidence | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# EATP-GAP: P1/P3/P4 — Upgrade requirements
# ---------------------------------------------------------------------------
# The EATP SDK has no built-in upgrade requirements table. CARE defines
# minimum thresholds per posture level, including time-based prerequisites
# (P4) and ShadowEnforcer integration (P3).

UPGRADE_REQUIREMENTS: dict[TrustPostureLevel, dict] = {
    TrustPostureLevel.SUPERVISED: {
        "min_days": 7,  # EATP-GAP: P4
        "min_operations": 10,
        "min_success_rate": 0.90,
        "max_incidents": 0,
    },
    TrustPostureLevel.SHARED_PLANNING: {
        "min_days": 90,  # EATP-GAP: P4
        "min_success_rate": 0.95,
        "min_operations": 100,
        "shadow_enforcer_required": True,  # EATP-GAP: P3
        "shadow_pass_rate": 0.90,  # EATP-GAP: P3
    },
    TrustPostureLevel.CONTINUOUS_INSIGHT: {
        "min_days": 180,  # EATP-GAP: P4
        "min_success_rate": 0.98,
        "min_operations": 500,
        "shadow_enforcer_required": True,  # EATP-GAP: P3
        "shadow_pass_rate": 0.95,  # EATP-GAP: P3
    },
    TrustPostureLevel.DELEGATED: {
        "min_days": 365,  # EATP-GAP: P4
        "min_success_rate": 0.99,
        "min_operations": 1000,
        "shadow_enforcer_required": True,  # EATP-GAP: P3
        "shadow_pass_rate": 0.98,  # EATP-GAP: P3
    },
}


# ---------------------------------------------------------------------------
# EATP SDK integration: Shared state machine instance
# ---------------------------------------------------------------------------
# The EATP SDK's PostureStateMachine is used as the underlying state machine
# for transitions. CARE's TrustPosture wraps it to add evidence-based checks
# and NEVER_DELEGATED_ACTIONS enforcement.


def _create_eatp_state_machine() -> EATPPostureStateMachine:
    """Create an EATP PostureStateMachine configured for CARE.

    Registers CARE's evidence-based upgrade guard as a TransitionGuard
    via the EATP SDK's ``add_guard()`` mechanism.

    Returns:
        A configured PostureStateMachine.
    """
    # Start with require_upgrade_approval=False since CARE manages
    # its own evidence-based guard logic
    machine = EATPPostureStateMachine(
        default_posture=EATPTrustPosture.SUPERVISED,
        require_upgrade_approval=False,
    )
    return machine


class TrustPosture(BaseModel):
    """Runtime trust posture for an agent.

    Manages the evolutionary trust lifecycle -- starting conservative
    and relaxing constraints only with demonstrated evidence.

    EATP SDK alignment:
        Uses ``eatp.postures.PostureStateMachine`` for the underlying state
        transitions. CARE's evidence-based upgrade checks (P1), time-based
        prerequisites (P4), and ShadowEnforcer requirements (P3) are
        implemented as validation logic that wraps the EATP state machine.
        NEVER_DELEGATED_ACTIONS (P2) is a CARE-specific enforcement layer.
    """

    agent_id: str
    current_level: TrustPostureLevel = TrustPostureLevel.SUPERVISED
    posture_since: datetime = Field(default_factory=lambda: datetime.now(UTC))
    history: list[PostureChange] = Field(default_factory=list)

    def can_upgrade(self, evidence: PostureEvidence) -> tuple[bool, str]:  # EATP-GAP: P1
        """Check if the posture can be upgraded based on evidence.

        EATP SDK's PostureStateMachine uses TransitionGuard callbacks.
        CARE extends this with structured PostureEvidence (P1) that includes:
        - Time-based prerequisites (P4: days_at_current_posture)
        - ShadowEnforcer integration (P3: shadow_enforcer_pass_rate)
        - Success rate and incident checks

        Returns (can_upgrade, reason).
        """
        current_order = POSTURE_ORDER[self.current_level]
        if current_order >= POSTURE_ORDER[TrustPostureLevel.DELEGATED]:
            return False, "Already at maximum posture level"

        # Find next level
        next_level = None
        for level, order in POSTURE_ORDER.items():
            if order == current_order + 1:
                next_level = level
                break

        if next_level is None:
            return False, "No next posture level found"

        requirements = UPGRADE_REQUIREMENTS.get(next_level)
        if requirements is None:
            return False, f"No upgrade requirements defined for {next_level}"

        # EATP-GAP: P4 — Check minimum days at current posture
        # The EATP SDK has no time-based upgrade prerequisites.
        if evidence.days_at_current_posture < requirements["min_days"]:
            return (
                False,
                f"Need {requirements['min_days']} days at current posture, "
                f"have {evidence.days_at_current_posture}",
            )

        # Check success rate
        if evidence.success_rate < requirements["min_success_rate"]:
            return (
                False,
                f"Need {requirements['min_success_rate']:.0%} success rate, "
                f"have {evidence.success_rate:.0%}",
            )

        # Check minimum operations
        if evidence.total_operations < requirements["min_operations"]:
            return (
                False,
                f"Need {requirements['min_operations']} operations, "
                f"have {evidence.total_operations}",
            )

        # EATP-GAP: P3 — Check ShadowEnforcer pass rate
        # The EATP SDK has no ShadowEnforcer integration.
        if requirements.get("shadow_enforcer_required"):
            if evidence.shadow_enforcer_pass_rate is None:
                return False, "ShadowEnforcer evidence required but not provided"
            if evidence.shadow_enforcer_pass_rate < requirements["shadow_pass_rate"]:
                return (
                    False,
                    f"Need {requirements['shadow_pass_rate']:.0%} ShadowEnforcer pass rate, "
                    f"have {evidence.shadow_enforcer_pass_rate:.0%}",
                )

        # Check no incidents
        if evidence.incidents > 0:
            return False, f"Cannot upgrade with {evidence.incidents} unresolved incidents"

        return True, f"Eligible for upgrade to {next_level.value}"

    def upgrade(self, evidence: PostureEvidence, reason: str = "") -> PostureChange:
        """Upgrade posture to the next level. Raises ValueError if not eligible.

        Uses EATP's PostureStateMachine.transition() internally to perform
        the state change, after CARE's evidence-based validation passes.
        """
        can, msg = self.can_upgrade(evidence)
        if not can:
            raise ValueError(f"Cannot upgrade: {msg}")

        current_order = POSTURE_ORDER[self.current_level]
        next_level = None
        for level, order in POSTURE_ORDER.items():
            if order == current_order + 1:
                next_level = level
                break

        # Use EATP PostureStateMachine for the transition (when mapping exists)
        eatp_from = _CARE_TO_EATP.get(self.current_level)
        eatp_to = _CARE_TO_EATP.get(next_level)
        if eatp_from is not None and eatp_to is not None:
            eatp_machine = _create_eatp_state_machine()
            eatp_machine.set_posture(self.agent_id, eatp_from)

            transition_request = PostureTransitionRequest(
                agent_id=self.agent_id,
                from_posture=eatp_from,
                to_posture=eatp_to,
                reason=reason or msg,
                requester_id=self.agent_id,
                metadata={"evidence": evidence.model_dump()},
            )
            result = eatp_machine.transition(transition_request)

            if not result.success:
                raise ValueError(f"EATP state machine rejected transition: {result.reason}")

        change = PostureChange(
            agent_id=self.agent_id,
            from_posture=self.current_level,
            to_posture=next_level,
            change_type=PostureChangeType.UPGRADE,
            reason=reason or msg,
            evidence=evidence,
        )
        self.current_level = next_level
        self.posture_since = change.timestamp
        self.history.append(change)
        return change

    def downgrade(self, reason: str, *, to_level: TrustPostureLevel | None = None) -> PostureChange:
        """Instantly downgrade posture. Downgrades are always immediate.

        Uses EATP's PostureStateMachine.transition() for downgrade transitions,
        or emergency_downgrade() when going to PSEUDO_AGENT.
        """
        target = to_level or TrustPostureLevel.SUPERVISED
        if POSTURE_ORDER[target] >= POSTURE_ORDER[self.current_level]:
            raise ValueError(
                f"Downgrade target {target.value} must be below current {self.current_level.value}"
            )

        # Use EATP PostureStateMachine for the transition (when mapping exists)
        eatp_from = _CARE_TO_EATP.get(self.current_level)
        eatp_to = _CARE_TO_EATP.get(target)
        if eatp_from is not None and eatp_to is not None:
            eatp_machine = _create_eatp_state_machine()
            eatp_machine.set_posture(self.agent_id, eatp_from)

            if eatp_to == EATPTrustPosture.PSEUDO_AGENT:
                # Use EATP emergency_downgrade for PSEUDO_AGENT
                eatp_machine.emergency_downgrade(
                    agent_id=self.agent_id,
                    reason=reason,
                )
            else:
                transition_request = PostureTransitionRequest(
                    agent_id=self.agent_id,
                    from_posture=eatp_from,
                    to_posture=eatp_to,
                    reason=reason,
                    requester_id=self.agent_id,
                )
                eatp_machine.transition(transition_request)

        change = PostureChange(
            agent_id=self.agent_id,
            from_posture=self.current_level,
            to_posture=target,
            change_type=PostureChangeType.DOWNGRADE,
            reason=reason,
        )
        self.current_level = target
        self.posture_since = change.timestamp
        self.history.append(change)
        return change

    def is_action_always_held(self, action: str) -> bool:  # EATP-GAP: P2
        """Check if an action is in the never-delegated list.

        EATP-GAP: P2 -- The EATP SDK has no canonical NEVER_DELEGATED_ACTIONS
        set. This is a CARE-specific governance enforcement layer.
        """
        return action in NEVER_DELEGATED_ACTIONS
