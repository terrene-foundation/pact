# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Delegation Manager — manages delegation chains with monotonic tightening.

Provides:
- Delegation creation with constraint mapping
- Monotonic tightening validation across all five CARE dimensions
- Chain walking (agent -> genesis)
- Delegation depth calculation for trust scoring
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from eatp.chain import DelegationRecord
from pydantic import BaseModel, Field

from care_platform.build.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
)
from care_platform.trust.constraint.envelope import _is_time_window_tighter, _paths_covered_by
from care_platform.trust.eatp_bridge import EATPBridge
from care_platform.trust.lifecycle import TrustChainState, TrustChainStateMachine

if TYPE_CHECKING:
    from care_platform.trust.revocation import RevocationManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ChainStatus(str, Enum):
    """Status of a trust chain walk."""

    VALID = "valid"
    BROKEN = "broken"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ChainWalkResult(BaseModel):
    """Result of walking a trust chain from an agent back to genesis."""

    status: ChainStatus
    chain: list = Field(default_factory=list)
    depth: int = 0
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Delegation Manager
# ---------------------------------------------------------------------------


class DelegationManager:
    """Manages delegation chains with monotonic tightening.

    Wraps EATPBridge delegation operations with:
    - Monotonic tightening validation before delegation
    - Chain walking from any agent back to genesis
    - Delegation depth calculation
    """

    def __init__(
        self,
        bridge: EATPBridge,
        revocation_manager: RevocationManager | None = None,
    ) -> None:
        """Initialize with an EATP bridge.

        Args:
            bridge: Initialized EATPBridge instance.
            revocation_manager: Optional RevocationManager for automatic
                delegation registration. When provided, every delegation
                created through this manager is automatically registered
                in the revocation manager's delegation tree, ensuring
                cascade revocation can discover all downstream agents.
        """
        self.bridge = bridge
        self._revocation_manager = revocation_manager
        # Track delegate_id -> lifecycle state machine
        self._state_machines: dict[str, TrustChainStateMachine] = {}

    async def create_delegation(
        self,
        delegator_id: str,
        delegate_config: AgentConfig,
        envelope_config: ConstraintEnvelopeConfig,
        parent_envelope_config: ConstraintEnvelopeConfig | None = None,
    ) -> DelegationRecord:
        """Create a delegation with constraint mapping through the bridge.

        Args:
            delegator_id: ID of the delegating agent/authority.
            delegate_config: Configuration of the receiving agent.
            envelope_config: Constraint envelope for the delegatee.
            parent_envelope_config: Parent constraint envelope for monotonic
                tightening validation. When provided, the child envelope_config
                must be a valid tightening of this parent. When None, tightening
                check is skipped (backward compatible for genesis-level delegation).

        Returns:
            The EATP DelegationRecord.

        Raises:
            ValueError: If delegator is not established, delegation fails,
                or monotonic tightening is violated.
        """
        # Validate monotonic tightening before proceeding with delegation
        if parent_envelope_config is not None:
            is_valid, violations = self.validate_tightening(parent_envelope_config, envelope_config)
            if not is_valid:
                violation_details = "; ".join(violations)
                raise ValueError(f"Monotonic tightening violated: {violation_details}")

        # Track lifecycle: DRAFT -> PENDING -> ACTIVE
        sm = TrustChainStateMachine(initial_state=TrustChainState.DRAFT)
        sm.transition_to(
            TrustChainState.PENDING,
            reason=f"Delegation from '{delegator_id}' to '{delegate_config.id}' initiated",
        )

        delegation = await self.bridge.delegate(
            delegator_id=delegator_id,
            delegate_agent_config=delegate_config,
            envelope_config=envelope_config,
        )

        # Transition to ACTIVE now that delegation is established
        sm.transition_to(
            TrustChainState.ACTIVE,
            reason=f"Delegation from '{delegator_id}' to '{delegate_config.id}' established",
        )
        self._state_machines[delegate_config.id] = sm

        # RT10-DP4: Auto-register delegation in revocation manager so cascade
        # revocation can discover all downstream agents.
        if self._revocation_manager is not None:
            self._revocation_manager.register_delegation(delegator_id, delegate_config.id)

        logger.info(
            "Created delegation from '%s' to '%s' (delegation_id='%s')",
            delegator_id,
            delegate_config.id,
            delegation.id,
        )

        return delegation

    def get_state_machine(self, delegate_id: str) -> TrustChainStateMachine | None:
        """Get the lifecycle state machine for a delegated agent.

        Args:
            delegate_id: The delegate agent ID to look up.

        Returns:
            The TrustChainStateMachine if found, None otherwise.
        """
        return self._state_machines.get(delegate_id)

    def validate_tightening(
        self,
        parent_envelope: ConstraintEnvelopeConfig,
        child_envelope: ConstraintEnvelopeConfig,
    ) -> tuple[bool, list[str]]:
        """Validate monotonic tightening across all five CARE dimensions.

        A child envelope must not expand any constraint beyond the parent:
        - Financial: child budget <= parent budget
        - Operational: child actions subset of parent actions
        - Temporal: child window within parent window (or no parent window)
        - Data Access: child paths subset of parent paths (or no parent paths)
        - Communication: child cannot loosen restrictions

        Args:
            parent_envelope: The parent/delegator constraint envelope.
            child_envelope: The child/delegatee constraint envelope.

        Returns:
            Tuple of (is_valid, violations) where violations is a list of
            human-readable violation descriptions.
        """
        violations: list[str] = []

        # --- Financial ---
        # M23/2301: financial is Optional — not all agents handle money.
        # RT13-M02: Handle None financial on either side gracefully.
        parent_financial = parent_envelope.financial
        child_financial = child_envelope.financial
        if parent_financial is not None and child_financial is not None:
            if child_financial.max_spend_usd > parent_financial.max_spend_usd:
                violations.append(
                    f"Financial: child budget ${child_financial.max_spend_usd} "
                    f"exceeds parent budget ${parent_financial.max_spend_usd}"
                )
        elif parent_financial is None and child_financial is not None:
            # Parent has no financial capability but child claims some — loosening
            violations.append(
                f"Financial: parent has no financial capability but child "
                f"declares budget ${child_financial.max_spend_usd}"
            )

        # --- Operational: allowed actions must be subset ---
        if parent_envelope.operational.allowed_actions:
            parent_actions = set(parent_envelope.operational.allowed_actions)
            child_actions = set(child_envelope.operational.allowed_actions)
            extra_actions = child_actions - parent_actions
            if extra_actions:
                violations.append(
                    f"Operational: child has actions not in parent: {sorted(extra_actions)}"
                )

        # --- Operational: child must include all parent blocked actions ---
        parent_blocked = set(parent_envelope.operational.blocked_actions)
        child_blocked = set(child_envelope.operational.blocked_actions)
        missing_blocks = parent_blocked - child_blocked
        if missing_blocks:
            violations.append(
                f"Operational: child is missing parent blocked actions: {sorted(missing_blocks)}"
            )

        # --- Operational: rate limit ---
        if (
            parent_envelope.operational.max_actions_per_day is not None
            and child_envelope.operational.max_actions_per_day is None
        ):
            violations.append(
                f"Operational: child removes parent rate limit "
                f"({parent_envelope.operational.max_actions_per_day} actions/day)"
            )
        elif (
            parent_envelope.operational.max_actions_per_day is not None
            and child_envelope.operational.max_actions_per_day is not None
            and child_envelope.operational.max_actions_per_day
            > parent_envelope.operational.max_actions_per_day
        ):
            violations.append(
                f"Operational: child rate limit {child_envelope.operational.max_actions_per_day} "
                f"exceeds parent rate limit {parent_envelope.operational.max_actions_per_day}"
            )

        # --- Temporal: child window must be within parent window ---
        pt = parent_envelope.temporal
        ct = child_envelope.temporal
        if pt.active_hours_start is not None and pt.active_hours_end is not None:
            # Parent has a temporal window
            if ct.active_hours_start is None or ct.active_hours_end is None:
                # Child removes the window entirely — loosens temporal constraint
                violations.append(
                    "Temporal: child removes active hours window from parent "
                    f"({pt.active_hours_start}-{pt.active_hours_end})"
                )
            else:
                # RT9-06: Use minute-based comparison to handle overnight windows correctly.
                if not _is_time_window_tighter(
                    ct.active_hours_start,
                    ct.active_hours_end,
                    pt.active_hours_start,
                    pt.active_hours_end,
                ):
                    violations.append(
                        f"Temporal: child window ({ct.active_hours_start}-{ct.active_hours_end}) "
                        f"is not within parent window ({pt.active_hours_start}-{pt.active_hours_end})"
                    )

        # --- Data Access: read_paths must be covered by parent ---
        pd = parent_envelope.data_access
        cd = child_envelope.data_access
        if pd.read_paths:
            if not cd.read_paths:
                violations.append(
                    f"Data Access: child removes parent read_paths restriction "
                    f"({sorted(pd.read_paths)})"
                )
            elif not _paths_covered_by(list(cd.read_paths), list(pd.read_paths)):
                violations.append(
                    f"Data Access: child read paths {sorted(cd.read_paths)} "
                    f"not covered by parent {sorted(pd.read_paths)}"
                )

        # --- Data Access: write_paths must be covered by parent ---
        if pd.write_paths:
            if not cd.write_paths:
                violations.append(
                    f"Data Access: child removes parent write_paths restriction "
                    f"({sorted(pd.write_paths)})"
                )
            elif not _paths_covered_by(list(cd.write_paths), list(pd.write_paths)):
                violations.append(
                    f"Data Access: child write paths {sorted(cd.write_paths)} "
                    f"not covered by parent {sorted(pd.write_paths)}"
                )

        # --- Data Access: child must include all parent blocked_data_types ---
        parent_blocked_types = set(pd.blocked_data_types)
        child_blocked_types = set(cd.blocked_data_types)
        missing_blocked_types = parent_blocked_types - child_blocked_types
        if missing_blocked_types:
            violations.append(
                f"Data Access: child is missing parent blocked data types: "
                f"{sorted(missing_blocked_types)}"
            )

        # --- Communication: cannot loosen ---
        if (
            parent_envelope.communication.internal_only
            and not child_envelope.communication.internal_only
        ):
            violations.append("Communication: child removes internal_only restriction from parent")
        if (
            parent_envelope.communication.external_requires_approval
            and not child_envelope.communication.external_requires_approval
        ):
            violations.append(
                "Communication: child removes external_requires_approval restriction from parent"
            )

        is_valid = len(violations) == 0
        return is_valid, violations

    async def walk_chain(self, agent_id: str) -> ChainWalkResult:
        """Walk the trust chain from an agent back to genesis.

        Retrieves the trust lineage chain from the store and assembles
        it into a ChainWalkResult with status, depth, and any errors.

        Args:
            agent_id: The agent whose chain to walk.

        Returns:
            ChainWalkResult with chain status and contents.
        """
        chain = await self.bridge.get_trust_chain(agent_id)

        if chain is None:
            return ChainWalkResult(
                status=ChainStatus.BROKEN,
                chain=[],
                depth=0,
                errors=[f"No trust chain found for agent '{agent_id}'"],
            )

        # Check genesis
        genesis = chain.genesis
        if genesis is None:
            return ChainWalkResult(
                status=ChainStatus.BROKEN,
                chain=[],
                depth=0,
                errors=[f"Trust chain for agent '{agent_id}' has no genesis record"],
            )

        # Check if genesis is expired
        if genesis.is_expired():
            chain_records = [genesis, *chain.delegations]
            return ChainWalkResult(
                status=ChainStatus.EXPIRED,
                chain=chain_records,
                depth=len(chain.delegations),
                errors=[f"Genesis record for agent '{agent_id}' has expired"],
            )

        # Build the chain list: genesis + delegations from the local chain,
        # but calculate transitive depth from the bridge's parent tracking
        chain_records = [genesis, *chain.delegations]
        depth = self.bridge.get_transitive_depth(agent_id)

        return ChainWalkResult(
            status=ChainStatus.VALID,
            chain=chain_records,
            depth=depth,
            errors=[],
        )

    async def get_delegation_depth(self, agent_id: str) -> int:
        """Get the delegation depth for an agent.

        Uses the bridge's transitive depth tracking to calculate the
        number of delegation hops from the genesis root.
        Genesis = 0, direct delegate = 1, etc.

        Args:
            agent_id: The agent whose depth to calculate.

        Returns:
            The delegation depth (0 if not found or genesis).
        """
        return self.bridge.get_transitive_depth(agent_id)
