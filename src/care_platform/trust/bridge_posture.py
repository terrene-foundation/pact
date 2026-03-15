# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Bridge posture resolution — cross-team trust posture logic for Cross-Functional Bridges.

When an action crosses a bridge boundary, the effective posture is the
more restrictive of the two team postures. This ensures that bridge
actions never exceed the trust level established by either side.

Mapping from effective posture to CARE verification gradient level:
- PSEUDO_AGENT / SUPERVISED -> HELD (requires human approval)
- SHARED_PLANNING -> FLAGGED (flagged for review but proceeds)
- CONTINUOUS_INSIGHT / DELEGATED -> AUTO_APPROVED (proceeds automatically)
"""

from __future__ import annotations

from care_platform.config.schema import TrustPostureLevel, VerificationLevel
from care_platform.trust.posture import POSTURE_ORDER


def effective_posture(
    source_posture: TrustPostureLevel,
    target_posture: TrustPostureLevel,
) -> TrustPostureLevel:
    """Return the more restrictive of two postures (minimum by POSTURE_ORDER).

    Bridge actions operate at the trust level of the least-trusted side.
    A SUPERVISED source working with a CONTINUOUS_INSIGHT target yields
    a SUPERVISED effective posture for bridge actions.

    Args:
        source_posture: Trust posture of the source team.
        target_posture: Trust posture of the target team.

    Returns:
        The more restrictive TrustPostureLevel.
    """
    source_order = POSTURE_ORDER[source_posture]
    target_order = POSTURE_ORDER[target_posture]
    if source_order <= target_order:
        return source_posture
    return target_posture


def bridge_verification_level(effective: TrustPostureLevel) -> VerificationLevel:
    """Map an effective bridge posture to a CARE verification gradient level.

    Lower trust postures require more scrutiny:
    - PSEUDO_AGENT, SUPERVISED -> HELD (requires human approval)
    - SHARED_PLANNING -> FLAGGED (flagged for review but proceeds)
    - CONTINUOUS_INSIGHT, DELEGATED -> AUTO_APPROVED (proceeds automatically)

    This mapping ensures that cross-team actions through a bridge are
    governed at a level appropriate to the effective trust between the
    two teams.

    Note: These are CARE verification gradient levels (AUTO_APPROVED,
    FLAGGED, HELD, BLOCKED), not EATP verification levels (QUICK,
    STANDARD, FULL). EATP verification levels control how deeply to
    verify trust chains; CARE verification gradient levels control
    what happens to the action.

    Args:
        effective: The effective posture for the bridge action
            (typically from effective_posture()).

    Returns:
        The CARE VerificationLevel to apply to bridge actions.
    """
    order = POSTURE_ORDER.get(effective)
    if order is None:
        # RT13-03: Unknown posture -> BLOCKED (fail-closed). The CARE
        # verification gradient requires fail-closed behavior on error.
        return VerificationLevel.BLOCKED
    if order <= 1:
        # PSEUDO_AGENT (0) or SUPERVISED (1) -> HELD (human approval required)
        return VerificationLevel.HELD
    if order == 2:
        # SHARED_PLANNING -> FLAGGED (proceeds but flagged for review)
        return VerificationLevel.FLAGGED
    # CONTINUOUS_INSIGHT (3) or DELEGATED (4) -> AUTO_APPROVED
    return VerificationLevel.AUTO_APPROVED
