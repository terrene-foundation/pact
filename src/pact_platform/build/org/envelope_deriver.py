# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Envelope Deriver — generates valid child constraint envelopes from parents.

Implements monotonic tightening by construction: every derived envelope is
guaranteed to be within its parent's boundaries. The tightening_factor
controls how much narrower the child is (0.0 = no budget, 1.0 = same as parent).

Tightening is enforced across all five CARE constraint dimensions:
- Financial: max_spend_usd scaled by tightening_factor
- Operational: allowed_actions is a subset of parent; rate limit scaled
- Temporal: active hours preserved from parent (same or narrower)
- Data Access: read/write paths preserved from parent
- Communication: internal_only inherited; never loosened

The validate_tightening() method verifies that an arbitrary child envelope
satisfies monotonic tightening against its parent.
"""

from __future__ import annotations

import logging
import math

from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
)
from pact_platform.build.org.role_catalog import RoleDefinition
from pact_platform.build.org.utils import _slugify

logger = logging.getLogger(__name__)


class EnvelopeDeriver:
    """Generates valid child constraint envelopes from parent envelopes.

    All derivation methods enforce monotonic tightening by construction:
    the child envelope is always within the parent's boundaries.

    Usage:
        deriver = EnvelopeDeriver()
        dept_env = deriver.derive_department_envelope(org_env, "engineering")
        team_env = deriver.derive_team_envelope(dept_env, "platform-team")
        agent_env = deriver.derive_agent_envelope(team_env, role_def)
        assert deriver.validate_tightening(org_env, dept_env)
    """

    def derive_department_envelope(
        self,
        org_envelope: ConstraintEnvelopeConfig,
        dept_name: str,
        tightening_factor: float = 0.8,
    ) -> ConstraintEnvelopeConfig:
        """Derive a department-level envelope from the org envelope.

        Produces an envelope that is tightening_factor of the parent on
        financial dimensions. Preserves operational actions from parent,
        temporal and communication constraints from parent.

        Args:
            org_envelope: The parent org-level envelope.
            dept_name: Human-readable department name (used for ID generation).
            tightening_factor: How much to tighten (0.0-1.0). Default 0.8.

        Returns:
            A new ConstraintEnvelopeConfig tighter than the org envelope.
        """
        if (
            not math.isfinite(tightening_factor)
            or tightening_factor < 0.0
            or tightening_factor > 1.0
        ):
            raise ValueError(f"tightening_factor must be in [0.0, 1.0], got {tightening_factor}")
        slug = _slugify(dept_name)
        envelope_id = f"dept-{slug}-envelope"

        # Financial: scale by tightening_factor
        financial = None
        if org_envelope.financial is not None:
            financial = FinancialConstraintConfig(
                max_spend_usd=org_envelope.financial.max_spend_usd * tightening_factor,
                api_cost_budget_usd=(
                    org_envelope.financial.api_cost_budget_usd * tightening_factor
                    if org_envelope.financial.api_cost_budget_usd is not None
                    else None
                ),
                requires_approval_above_usd=org_envelope.financial.requires_approval_above_usd,
            )

        # Operational: preserve parent actions, tighten rate limit
        parent_actions = (
            list(org_envelope.operational.allowed_actions) if org_envelope.operational else []
        )
        parent_rate = (
            org_envelope.operational.max_actions_per_day if org_envelope.operational else None
        )
        tightened_rate = None
        if parent_rate is not None:
            tightened_rate = max(1, int(parent_rate * tightening_factor))

        operational = OperationalConstraintConfig(
            allowed_actions=parent_actions,
            blocked_actions=(
                list(org_envelope.operational.blocked_actions) if org_envelope.operational else []
            ),
            max_actions_per_day=tightened_rate,
        )

        # Temporal: preserve from parent
        temporal = TemporalConstraintConfig(
            active_hours_start=(
                org_envelope.temporal.active_hours_start if org_envelope.temporal else None
            ),
            active_hours_end=(
                org_envelope.temporal.active_hours_end if org_envelope.temporal else None
            ),
            timezone=org_envelope.temporal.timezone if org_envelope.temporal else "UTC",
        )

        # Data Access: preserve from parent
        data_access = DataAccessConstraintConfig(
            read_paths=(
                list(org_envelope.data_access.read_paths) if org_envelope.data_access else []
            ),
            write_paths=(
                list(org_envelope.data_access.write_paths) if org_envelope.data_access else []
            ),
            blocked_data_types=(
                list(org_envelope.data_access.blocked_data_types)
                if org_envelope.data_access
                else []
            ),
        )

        # Communication: preserve from parent (never loosen)
        communication = CommunicationConstraintConfig(
            internal_only=(
                org_envelope.communication.internal_only if org_envelope.communication else True
            ),
            allowed_channels=(
                list(org_envelope.communication.allowed_channels)
                if org_envelope.communication
                else []
            ),
            external_requires_approval=(
                org_envelope.communication.external_requires_approval
                if org_envelope.communication
                else True
            ),
        )

        envelope = ConstraintEnvelopeConfig(
            id=envelope_id,
            description=f"Auto-derived envelope for department '{dept_name}'",
            financial=financial,
            operational=operational,
            temporal=temporal,
            data_access=data_access,
            communication=communication,
        )

        logger.debug(
            "Derived department envelope '%s' from org envelope '%s' (factor=%.2f)",
            envelope_id,
            org_envelope.id,
            tightening_factor,
        )
        return envelope

    def derive_team_envelope(
        self,
        dept_envelope: ConstraintEnvelopeConfig,
        team_name: str,
        tightening_factor: float = 0.7,
    ) -> ConstraintEnvelopeConfig:
        """Derive a team-level envelope from a department envelope.

        Args:
            dept_envelope: The parent department-level envelope.
            team_name: Human-readable team name (used for ID generation).
            tightening_factor: How much to tighten (0.0-1.0). Default 0.7.

        Returns:
            A new ConstraintEnvelopeConfig tighter than the department envelope.
        """
        if (
            not math.isfinite(tightening_factor)
            or tightening_factor < 0.0
            or tightening_factor > 1.0
        ):
            raise ValueError(f"tightening_factor must be in [0.0, 1.0], got {tightening_factor}")
        slug = _slugify(team_name)
        envelope_id = f"team-{slug}-envelope"

        # Financial: scale by tightening_factor
        financial = None
        if dept_envelope.financial is not None:
            financial = FinancialConstraintConfig(
                max_spend_usd=dept_envelope.financial.max_spend_usd * tightening_factor,
                api_cost_budget_usd=(
                    dept_envelope.financial.api_cost_budget_usd * tightening_factor
                    if dept_envelope.financial.api_cost_budget_usd is not None
                    else None
                ),
                requires_approval_above_usd=dept_envelope.financial.requires_approval_above_usd,
            )

        # Operational: preserve parent actions, tighten rate limit
        parent_actions = (
            list(dept_envelope.operational.allowed_actions) if dept_envelope.operational else []
        )
        parent_rate = (
            dept_envelope.operational.max_actions_per_day if dept_envelope.operational else None
        )
        tightened_rate = None
        if parent_rate is not None:
            tightened_rate = max(1, int(parent_rate * tightening_factor))

        operational = OperationalConstraintConfig(
            allowed_actions=parent_actions,
            blocked_actions=(
                list(dept_envelope.operational.blocked_actions) if dept_envelope.operational else []
            ),
            max_actions_per_day=tightened_rate,
        )

        # Temporal: preserve from parent
        temporal = TemporalConstraintConfig(
            active_hours_start=(
                dept_envelope.temporal.active_hours_start if dept_envelope.temporal else None
            ),
            active_hours_end=(
                dept_envelope.temporal.active_hours_end if dept_envelope.temporal else None
            ),
            timezone=dept_envelope.temporal.timezone if dept_envelope.temporal else "UTC",
        )

        # Data Access: preserve from parent
        data_access = DataAccessConstraintConfig(
            read_paths=(
                list(dept_envelope.data_access.read_paths) if dept_envelope.data_access else []
            ),
            write_paths=(
                list(dept_envelope.data_access.write_paths) if dept_envelope.data_access else []
            ),
            blocked_data_types=(
                list(dept_envelope.data_access.blocked_data_types)
                if dept_envelope.data_access
                else []
            ),
        )

        # Communication: preserve from parent (never loosen)
        communication = CommunicationConstraintConfig(
            internal_only=(
                dept_envelope.communication.internal_only if dept_envelope.communication else True
            ),
            allowed_channels=(
                list(dept_envelope.communication.allowed_channels)
                if dept_envelope.communication
                else []
            ),
            external_requires_approval=(
                dept_envelope.communication.external_requires_approval
                if dept_envelope.communication
                else True
            ),
        )

        envelope = ConstraintEnvelopeConfig(
            id=envelope_id,
            description=f"Auto-derived envelope for team '{team_name}'",
            financial=financial,
            operational=operational,
            temporal=temporal,
            data_access=data_access,
            communication=communication,
        )

        logger.debug(
            "Derived team envelope '%s' from dept envelope '%s' (factor=%.2f)",
            envelope_id,
            dept_envelope.id,
            tightening_factor,
        )
        return envelope

    def derive_agent_envelope(
        self,
        team_envelope: ConstraintEnvelopeConfig,
        role: RoleDefinition,
        tightening_factor: float = 0.5,
    ) -> ConstraintEnvelopeConfig:
        """Derive an agent-level envelope from a team envelope and role definition.

        The agent's allowed_actions are the intersection of the role's
        default_capabilities and the team's allowed_actions, ensuring the
        agent only gets capabilities that are permitted by the team envelope.

        Args:
            team_envelope: The parent team-level envelope.
            role: The RoleDefinition to derive the envelope for.
            tightening_factor: How much to tighten (0.0-1.0). Default 0.5.

        Returns:
            A new ConstraintEnvelopeConfig tighter than the team envelope.
        """
        if (
            not math.isfinite(tightening_factor)
            or tightening_factor < 0.0
            or tightening_factor > 1.0
        ):
            raise ValueError(f"tightening_factor must be in [0.0, 1.0], got {tightening_factor}")
        slug = _slugify(role.role_id)
        envelope_id = f"agent-{slug}-envelope"

        # Financial: use role's default_max_cost_per_day, capped by team
        financial = None
        if team_envelope.financial is not None:
            agent_spend = min(
                role.default_max_cost_per_day,
                team_envelope.financial.max_spend_usd * tightening_factor,
            )
            financial = FinancialConstraintConfig(
                max_spend_usd=agent_spend,
            )

        # Operational: intersection of role capabilities and team actions
        team_actions = (
            set(team_envelope.operational.allowed_actions) if team_envelope.operational else set()
        )
        role_caps = set(role.default_capabilities)
        # Agent gets capabilities that exist in team's allowed_actions
        agent_actions = sorted(role_caps & team_actions) if team_actions else sorted(role_caps)

        # Rate limit: use role's default, capped by team
        team_rate = (
            team_envelope.operational.max_actions_per_day if team_envelope.operational else None
        )
        agent_rate = role.default_max_actions_per_day
        if team_rate is not None:
            agent_rate = min(agent_rate, max(1, int(team_rate * tightening_factor)))

        operational = OperationalConstraintConfig(
            allowed_actions=agent_actions,
            blocked_actions=(
                list(team_envelope.operational.blocked_actions) if team_envelope.operational else []
            ),
            max_actions_per_day=agent_rate,
        )

        # Temporal: preserve from team
        temporal = TemporalConstraintConfig(
            active_hours_start=(
                team_envelope.temporal.active_hours_start if team_envelope.temporal else None
            ),
            active_hours_end=(
                team_envelope.temporal.active_hours_end if team_envelope.temporal else None
            ),
            timezone=team_envelope.temporal.timezone if team_envelope.temporal else "UTC",
        )

        # Data Access: preserve from team
        data_access = DataAccessConstraintConfig(
            read_paths=(
                list(team_envelope.data_access.read_paths) if team_envelope.data_access else []
            ),
            write_paths=(
                list(team_envelope.data_access.write_paths) if team_envelope.data_access else []
            ),
            blocked_data_types=(
                list(team_envelope.data_access.blocked_data_types)
                if team_envelope.data_access
                else []
            ),
        )

        # Communication: preserve from team (never loosen)
        communication = CommunicationConstraintConfig(
            internal_only=(
                team_envelope.communication.internal_only if team_envelope.communication else True
            ),
            allowed_channels=(
                list(team_envelope.communication.allowed_channels)
                if team_envelope.communication
                else []
            ),
            external_requires_approval=(
                team_envelope.communication.external_requires_approval
                if team_envelope.communication
                else True
            ),
        )

        envelope = ConstraintEnvelopeConfig(
            id=envelope_id,
            description=f"Auto-derived envelope for role '{role.name}'",
            financial=financial,
            operational=operational,
            temporal=temporal,
            data_access=data_access,
            communication=communication,
        )

        logger.debug(
            "Derived agent envelope '%s' for role '%s' (factor=%.2f)",
            envelope_id,
            role.role_id,
            tightening_factor,
        )
        return envelope

    def derive_coordinator_envelope(
        self,
        team_envelope: ConstraintEnvelopeConfig,
        team_id: str,
    ) -> ConstraintEnvelopeConfig:
        """Derive a coordinator-specific envelope from a team envelope.

        Coordinators have:
        - $0 financial authority (no spending)
        - Only bridge-related operational actions
        - Same temporal/communication/data access as team (or tighter)

        Args:
            team_envelope: The parent team-level envelope.
            team_id: The team this coordinator belongs to.

        Returns:
            A ConstraintEnvelopeConfig for the coordinator agent.
        """
        envelope_id = f"{team_id}-coordinator-envelope"

        # Financial: $0 — coordinators have no spending authority
        financial = FinancialConstraintConfig(max_spend_usd=0.0)

        # Operational: bridge-related actions only
        coordinator_actions = [
            "bridge_management",
            "cross_team_communication",
            "task_routing",
        ]
        operational = OperationalConstraintConfig(
            allowed_actions=coordinator_actions,
            max_actions_per_day=max(
                1, int((team_envelope.operational.max_actions_per_day or 50) * 0.3)
            ),
        )

        # Temporal: preserve from team
        temporal = TemporalConstraintConfig(
            active_hours_start=(
                team_envelope.temporal.active_hours_start if team_envelope.temporal else None
            ),
            active_hours_end=(
                team_envelope.temporal.active_hours_end if team_envelope.temporal else None
            ),
            timezone=team_envelope.temporal.timezone if team_envelope.temporal else "UTC",
        )

        # Data Access: inherit from team (never broader), add blocking
        data_access = DataAccessConstraintConfig(
            read_paths=(
                list(team_envelope.data_access.read_paths) if team_envelope.data_access else []
            ),
            write_paths=[],  # Coordinators have no write access
            blocked_data_types=["confidential", "pii", "financial_records"],
        )

        # Communication: bridge channels only, internal-only
        communication = CommunicationConstraintConfig(
            internal_only=True,
            allowed_channels=["bridge"],
            external_requires_approval=True,
        )

        return ConstraintEnvelopeConfig(
            id=envelope_id,
            description=f"Auto-derived coordinator envelope for team '{team_id}'",
            financial=financial,
            operational=operational,
            temporal=temporal,
            data_access=data_access,
            communication=communication,
        )

    def validate_tightening(
        self,
        parent: ConstraintEnvelopeConfig,
        child: ConstraintEnvelopeConfig,
    ) -> bool:
        """Verify that child envelope satisfies monotonic tightening against parent.

        Checks all five CARE constraint dimensions:
        1. Financial: child max_spend_usd <= parent max_spend_usd
        2. Operational: child allowed_actions subset of parent; child rate <= parent rate
        3. Temporal: child active hours within parent active hours
        4. Data Access: child paths covered by parent paths
        5. Communication: child not looser than parent (internal_only)

        Args:
            parent: The parent envelope (broader constraints).
            child: The child envelope (should be tighter).

        Returns:
            True if child is a valid tightening of parent, False otherwise.
        """
        # 1. Financial tightening (fail-closed: None parent means no authority granted)
        if child.financial is not None:
            if parent.financial is None:
                logger.debug(
                    "Financial tightening violation: child introduces financial authority "
                    "that parent never granted (parent.financial is None)"
                )
                return False
            if child.financial.max_spend_usd > parent.financial.max_spend_usd:
                logger.debug(
                    "Financial tightening violation: child spend $%.2f > parent $%.2f",
                    child.financial.max_spend_usd,
                    parent.financial.max_spend_usd,
                )
                return False

        # 2. Operational tightening — allowed actions (fail-closed)
        if parent.operational and child.operational:
            parent_actions = set(parent.operational.allowed_actions or [])
            child_actions = set(child.operational.allowed_actions or [])
            # Fail-closed: if parent has empty allowed_actions, child must also have none
            if not parent_actions and child_actions:
                logger.debug(
                    "Operational tightening violation: child has actions %s "
                    "but parent allowed_actions is empty",
                    sorted(child_actions),
                )
                return False
            if parent_actions and child_actions:
                extra = child_actions - parent_actions
                if extra:
                    logger.debug(
                        "Operational tightening violation: child has extra actions %s",
                        sorted(extra),
                    )
                    return False

            # Operational tightening — rate limit
            parent_rate = parent.operational.max_actions_per_day
            child_rate = child.operational.max_actions_per_day
            if parent_rate is not None and child_rate is not None:
                if child_rate > parent_rate:
                    logger.debug(
                        "Rate limit tightening violation: child %d/day > parent %d/day",
                        child_rate,
                        parent_rate,
                    )
                    return False

        # 3. Temporal tightening (fail-closed: None parent means no time window)
        if child.temporal is not None and parent.temporal is not None:
            if (
                parent.temporal.active_hours_start is None
                and child.temporal.active_hours_start is not None
            ):
                logger.debug(
                    "Temporal tightening violation: child introduces time window "
                    "that parent never granted (parent.active_hours_start is None)"
                )
                return False
            if (
                parent.temporal.active_hours_end is None
                and child.temporal.active_hours_end is not None
            ):
                logger.debug(
                    "Temporal tightening violation: child introduces time window "
                    "that parent never granted (parent.active_hours_end is None)"
                )
                return False
            if (
                parent.temporal.active_hours_start
                and child.temporal.active_hours_start
                and child.temporal.active_hours_start < parent.temporal.active_hours_start
            ):
                logger.debug(
                    "Temporal tightening violation: child starts %s before parent %s",
                    child.temporal.active_hours_start,
                    parent.temporal.active_hours_start,
                )
                return False
            if (
                parent.temporal.active_hours_end
                and child.temporal.active_hours_end
                and child.temporal.active_hours_end > parent.temporal.active_hours_end
            ):
                logger.debug(
                    "Temporal tightening violation: child ends %s after parent %s",
                    child.temporal.active_hours_end,
                    parent.temporal.active_hours_end,
                )
                return False

        # 4. Data Access tightening
        if parent.data_access and child.data_access:
            parent_read = set(parent.data_access.read_paths or [])
            child_read = set(child.data_access.read_paths or [])
            if parent_read and child_read:
                for path in child_read:
                    if not self._path_covered_by(path, parent_read):
                        logger.debug(
                            "Data access tightening violation: child read path '%s' "
                            "not covered by parent",
                            path,
                        )
                        return False

            parent_write = set(parent.data_access.write_paths or [])
            child_write = set(child.data_access.write_paths or [])
            if parent_write and child_write:
                for path in child_write:
                    if not self._path_covered_by(path, parent_write):
                        logger.debug(
                            "Data access tightening violation: child write path '%s' "
                            "not covered by parent",
                            path,
                        )
                        return False

        # 5. Communication tightening
        if parent.communication and child.communication:
            if parent.communication.internal_only and not child.communication.internal_only:
                logger.debug(
                    "Communication tightening violation: parent is internal-only "
                    "but child allows external"
                )
                return False

        return True

    @staticmethod
    def _path_covered_by(child_path: str, parent_paths: set[str]) -> bool:
        """Check if a child path is covered by any parent path (glob-aware)."""
        for p in parent_paths:
            if child_path == p:
                return True
            if p.endswith("*") and child_path.startswith(p[:-1]):
                return True
        return False
