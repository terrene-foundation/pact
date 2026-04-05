# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""D/T/R-aware assessor validation for posture changes.

Per PACT spec Section 12.9.4, posture upgrades require an independent
assessor. This module provides a validator that uses the D/T/R address
hierarchy to enforce structural independence:

- BLOCKED: Direct supervisor (parent role in accountability chain) --
  conflict of interest (they benefit from higher autonomy)
- ALLOWED: Peer supervisor (same depth, different branch)
- ALLOWED: Compliance role (registered via ``compliance_roles`` set)
- ALLOWED: Ancestor 2+ governance levels up (sufficient distance)

The "direct supervisor" is determined by the accountability chain, not
raw segment depth. In D/T/R grammar, every D or T must be followed by
an R, so a governance level is a (D|T)-R pair (2 segments). The direct
supervisor is the closest Role ancestor in the accountability chain.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kailash.trust.pact.engine import GovernanceEngine
    from pact_platform.trust.store.posture_history import PostureHistoryStore

from pact_platform.trust.store.posture_history import PostureHistoryError

logger = logging.getLogger(__name__)

__all__ = ["create_dtr_assessor_validator", "wire_assessor_validator"]


def create_dtr_assessor_validator(
    engine: GovernanceEngine,
    compliance_roles: set[str] | None = None,
) -> Callable[[str, str, str], None]:
    """Create a D/T/R-aware assessor validator for posture upgrades.

    Returns a validator callable compatible with
    :meth:`PostureHistoryStore.set_assessor_validator`.

    The validator checks (for upgrade-direction changes only):

    1. ``changed_by`` is a registered compliance role -> ALLOWED
    2. ``changed_by`` is the direct supervisor (immediate parent in
       the accountability chain) -> BLOCKED (conflict of interest)
    3. ``changed_by`` is an ancestor 2+ governance levels up -> ALLOWED
    4. ``changed_by`` is not an ancestor at all (peer/unrelated) -> ALLOWED

    Args:
        engine: The GovernanceEngine instance. Used for future
            extensions (e.g., org-aware validation). Currently the
            engine reference is stored but not queried.
        compliance_roles: Optional set of D/T/R address strings that
            are designated compliance roles. Compliance roles are
            always allowed to assess posture upgrades regardless of
            their position in the hierarchy. If ``None``, an empty
            set is used.

    Returns:
        A validator callable ``(agent_id, changed_by, direction) -> None``
        that raises :class:`PostureHistoryError` on independence violations.
    """
    _compliance = compliance_roles or set()

    def validator(agent_id: str, changed_by: str, direction: str) -> None:
        if direction != "upgrade":
            return

        from kailash.trust.pact.addressing import Address, AddressError

        try:
            agent_addr = Address.parse(agent_id)
            assessor_addr = Address.parse(changed_by)
        except (AddressError, Exception):
            # If addresses cannot be parsed, we cannot validate hierarchy.
            # Fail closed -- block the upgrade.
            raise PostureHistoryError(
                f"Cannot validate assessor independence: unable to parse "
                f"addresses agent='{agent_id}', assessor='{changed_by}'. "
                f"Both must be valid D/T/R addresses."
            )

        # Check if assessor is a registered compliance role
        if changed_by in _compliance:
            logger.debug(
                "Assessor '%s' is a registered compliance role -- approved",
                changed_by,
            )
            return

        # Check if assessor is an ancestor of the agent
        if assessor_addr.is_ancestor_of(agent_addr) and str(assessor_addr) != str(agent_addr):
            # Assessor is a proper ancestor. Determine governance distance
            # using the accountability chain.
            agent_chain = agent_addr.accountability_chain
            assessor_chain = assessor_addr.accountability_chain

            # Find the assessor's position in the agent's accountability chain.
            # The direct supervisor is the role immediately above in the chain.
            agent_chain_strs = [str(a) for a in agent_chain]
            assessor_str = str(assessor_addr)

            if assessor_str in agent_chain_strs:
                assessor_idx = agent_chain_strs.index(assessor_str)
                # The agent itself is at the last index.
                # Direct supervisor is at index len(chain) - 2.
                agent_idx = len(agent_chain_strs) - 1
                governance_distance = agent_idx - assessor_idx

                if governance_distance == 1:
                    # Direct supervisor -- BLOCKED (conflict of interest)
                    raise PostureHistoryError(
                        f"Assessor '{changed_by}' is the direct supervisor of "
                        f"agent '{agent_id}' in the accountability chain "
                        f"(governance distance: 1). Direct supervisors have a "
                        f"conflict of interest in posture upgrades -- they "
                        f"benefit from higher autonomy. Use a peer supervisor, "
                        f"compliance role, or ancestor 2+ levels up. "
                        f"(PACT spec 12.9.4)"
                    )
                else:
                    # Ancestor 2+ governance levels up -- ALLOWED
                    logger.debug(
                        "Assessor '%s' is %d governance levels up from '%s' " "-- approved",
                        changed_by,
                        governance_distance,
                        agent_id,
                    )
                    return
            else:
                # Assessor is a structural ancestor (segment prefix) but not
                # in the accountability chain (not a Role position). This is
                # an unusual case -- allow it since it's not a direct supervisor.
                logger.debug(
                    "Assessor '%s' is a structural ancestor of '%s' but not "
                    "in the accountability chain -- approved (no COI)",
                    changed_by,
                    agent_id,
                )
                return

        # Assessor is not an ancestor -- could be peer or unrelated.
        # Peer supervisors at same depth in different branches are fine.
        logger.debug(
            "Assessor '%s' is not an ancestor of '%s' -- approved " "(peer/unrelated)",
            changed_by,
            agent_id,
        )

    return validator


def wire_assessor_validator(
    engine: GovernanceEngine,
    posture_store: PostureHistoryStore,
    compliance_roles: set[str] | None = None,
) -> None:
    """Wire the D/T/R assessor validator into a PostureHistoryStore.

    Call this during platform initialization to enable structural
    independence checking for posture upgrades.

    Args:
        engine: The GovernanceEngine for hierarchy resolution.
        posture_store: The PostureHistoryStore to attach the validator to.
        compliance_roles: Optional set of D/T/R addresses for compliance
            roles that are always allowed to assess posture upgrades.
    """
    validator = create_dtr_assessor_validator(engine, compliance_roles)
    posture_store.set_assessor_validator(validator)
    logger.info(
        "D/T/R assessor validator wired into PostureHistoryStore "
        "(direct supervisor COI check active, %d compliance role(s) registered)",
        len(compliance_roles or set()),
    )
