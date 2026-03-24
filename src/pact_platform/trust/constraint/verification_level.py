# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Adaptive verification level selection — determines how thoroughly to verify
an agent action based on context.

The EATP spec defines three verification levels:
- QUICK (~1ms): cache hit + routine action — pattern match only
- STANDARD (~5ms): default — pattern match + envelope check
- FULL (~50ms): cross-team, high-stakes, first action — full chain verification

This module selects the appropriate level based on action context.
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class VerificationThoroughness(str, Enum):
    """Verification thoroughness levels for the adaptive selector.

    These map to the EATP spec performance targets:
    - QUICK: ~1ms (cache hit, routine action)
    - STANDARD: ~5ms (default)
    - FULL: ~50ms (cross-team, high-stakes, first action)
    """

    QUICK = "quick"
    STANDARD = "standard"
    FULL = "full"


def select_verification_level(
    *,
    action_type: str,
    cache_hit: bool,
    is_cross_team: bool,
    is_first_action: bool,
) -> VerificationThoroughness:
    """Select the appropriate verification level based on action context.

    Decision logic (highest priority first):
    1. FULL: cross-team operations require full chain verification
    2. FULL: first action of a session requires full verification
    3. QUICK: cache hit on a routine (non-cross-team, non-first) action
    4. STANDARD: everything else

    Args:
        action_type: The type of action being performed (for logging/context).
        cache_hit: Whether there is a valid cached verification result.
        is_cross_team: Whether this is a cross-team operation.
        is_first_action: Whether this is the first action in the agent's session.

    Returns:
        The selected VerificationThoroughness.
    """
    # FULL: cross-team operations always require full chain verification
    if is_cross_team:
        logger.debug(
            "Verification level FULL: cross-team operation action_type=%s",
            action_type,
        )
        return VerificationThoroughness.FULL

    # FULL: first action always requires full verification to establish trust
    if is_first_action:
        logger.debug(
            "Verification level FULL: first action of session action_type=%s",
            action_type,
        )
        return VerificationThoroughness.FULL

    # QUICK: cache hit on a routine action
    if cache_hit:
        logger.debug(
            "Verification level QUICK: cache hit for routine action action_type=%s",
            action_type,
        )
        return VerificationThoroughness.QUICK

    # STANDARD: default for everything else
    logger.debug(
        "Verification level STANDARD: default for action_type=%s",
        action_type,
    )
    return VerificationThoroughness.STANDARD
