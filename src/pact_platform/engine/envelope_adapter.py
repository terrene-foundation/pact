# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""PlatformEnvelopeAdapter — converts GovernanceEngine envelopes to
GovernedSupervisor initialization parameters.

The adapter is the translation layer between the governance policy
(ConstraintEnvelopeConfig from kailash-pact) and the execution policy
(GovernedSupervisor kwargs from kaizen-agents).  It resolves the
effective envelope for a D/T/R address, NaN-guards every numeric field,
and maps governance concepts (confidentiality clearance, financial limits,
operational tools) to supervisor concepts (budget_usd, tools list,
data_clearance string, timeout, child limits).
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

from pact_platform.models import validate_finite

if TYPE_CHECKING:
    from pact.governance.engine import GovernanceEngine

logger = logging.getLogger(__name__)

__all__ = ["PlatformEnvelopeAdapter"]

# Mapping from ConfidentialityLevel enum values to supervisor data_clearance
# strings.  GovernedSupervisor expects lowercase clearance names that align
# with PACT's five-level classification.
_CLEARANCE_MAP: dict[str, str] = {
    "public": "public",
    "restricted": "restricted",
    "confidential": "confidential",
    "secret": "secret",
    "top_secret": "top_secret",
}

# Default timeout when no temporal constraints are specified (5 minutes).
_DEFAULT_TIMEOUT_SECONDS: float = 300.0

# Default max children and depth when not constrained by the envelope.
_DEFAULT_MAX_CHILDREN: int = 10
_DEFAULT_MAX_DEPTH: int = 5


class PlatformEnvelopeAdapter:
    """Converts governance envelopes to GovernedSupervisor parameters.

    This is a stateless adapter — it holds a reference to the
    GovernanceEngine only for envelope resolution.

    Args:
        engine: The GovernanceEngine instance to resolve envelopes from.
    """

    def __init__(self, engine: GovernanceEngine) -> None:
        self._engine = engine

    def adapt(
        self,
        envelope: dict[str, Any] | None,
        role_address: str,
    ) -> dict[str, Any]:
        """Convert a ConstraintEnvelopeConfig dict to GovernedSupervisor kwargs.

        If *envelope* is ``None``, the adapter calls
        ``engine.compute_envelope()`` to resolve the effective envelope for
        *role_address*.  If that also returns ``None`` (no envelopes
        configured), returns maximally restrictive defaults (budget 0,
        no tools, public clearance).

        Rules:
        - financial.max_cost=None -> budget_usd=0.0 (NOT $1 default)
        - NaN/Inf on any numeric -> raise ValueError
        - confidentiality_level -> data_clearance string mapping
        - All tool lists are passed through (empty = no tools)

        Args:
            envelope: Pre-resolved envelope as a dict (from
                ``ConstraintEnvelopeConfig.model_dump()``) or ``None``
                to trigger resolution.
            role_address: The D/T/R address of the role.

        Returns:
            Dict with keys ``budget_usd``, ``tools``, ``data_clearance``,
            ``timeout_seconds``, ``max_children``, ``max_depth``.

        Raises:
            ValueError: If any numeric field in the envelope is NaN or Inf.
        """
        if envelope is None:
            config = self._engine.compute_envelope(role_address)
            if config is None:
                logger.warning(
                    "No effective envelope for role_address='%s' — "
                    "returning maximally restrictive defaults",
                    role_address,
                )
                return {
                    "budget_usd": 0.0,
                    "tools": [],
                    "data_clearance": "public",
                    "timeout_seconds": _DEFAULT_TIMEOUT_SECONDS,
                    "max_children": _DEFAULT_MAX_CHILDREN,
                    "max_depth": _DEFAULT_MAX_DEPTH,
                }
            envelope = config.model_dump()

        return self._convert(envelope, role_address)

    # ------------------------------------------------------------------
    # Internal conversion
    # ------------------------------------------------------------------

    def _convert(
        self,
        envelope: dict[str, Any],
        role_address: str,
    ) -> dict[str, Any]:
        """Perform the actual field-by-field conversion with NaN guards.

        Raises:
            ValueError: If any numeric field is NaN or Inf.
        """
        # ----- Financial dimension -----
        budget_usd = 0.0
        financial = envelope.get("financial")
        if financial is not None:
            max_cost = financial.get("max_spend_usd")
            api_budget = financial.get("api_cost_budget_usd")

            # NaN-guard both financial numerics
            _guard_finite(max_spend_usd=max_cost, api_cost_budget_usd=api_budget)

            if max_cost is not None:
                budget_usd = float(max_cost)
            elif api_budget is not None:
                budget_usd = float(api_budget)
            # If both are None, budget_usd stays 0.0 (NOT a $1 default)

        # ----- Operational dimension (tools) -----
        operational = envelope.get("operational", {})
        allowed_actions = operational.get("allowed_actions", [])
        # Pass through whatever the envelope says — empty = no tools.
        tools: list[str] = list(allowed_actions) if allowed_actions else []

        # ----- Confidentiality -> data_clearance -----
        clearance_raw = envelope.get("confidentiality_clearance", "public")
        # Handle both enum objects and plain strings
        if hasattr(clearance_raw, "value"):
            clearance_raw = clearance_raw.value
        data_clearance = _CLEARANCE_MAP.get(str(clearance_raw).lower(), "public")

        # ----- Temporal dimension -> timeout_seconds -----
        timeout_seconds = _DEFAULT_TIMEOUT_SECONDS
        # No direct timeout field in ConstraintEnvelopeConfig, but we
        # preserve the default.  If active_hours_start/end are set, the
        # supervisor has limited operating windows; keep the default.
        # Future: derive timeout from active window size.

        # ----- Delegation depth -----
        max_delegation_depth = envelope.get("max_delegation_depth")
        _guard_finite(max_delegation_depth=max_delegation_depth)
        max_depth = (
            int(max_delegation_depth)
            if max_delegation_depth is not None
            else _DEFAULT_MAX_DEPTH
        )

        # max_children is not directly in ConstraintEnvelopeConfig; use
        # the default unless a future config field provides it.
        max_children = _DEFAULT_MAX_CHILDREN

        # ----- Rate limits -> logged for observability -----
        max_per_day = operational.get("max_actions_per_day")
        max_per_hour = operational.get("max_actions_per_hour")
        _guard_finite(max_actions_per_day=max_per_day, max_actions_per_hour=max_per_hour)

        if max_per_day is not None or max_per_hour is not None:
            logger.info(
                "Rate limits active for '%s': %s/day, %s/hour",
                role_address,
                max_per_day,
                max_per_hour,
            )

        result = {
            "budget_usd": budget_usd,
            "tools": tools,
            "data_clearance": data_clearance,
            "timeout_seconds": timeout_seconds,
            "max_children": max_children,
            "max_depth": max_depth,
        }

        logger.debug(
            "Adapted envelope for '%s': budget=$%.2f, tools=%d, "
            "clearance=%s, timeout=%.0fs, depth=%d",
            role_address,
            budget_usd,
            len(tools),
            data_clearance,
            timeout_seconds,
            max_depth,
        )

        return result


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _guard_finite(**fields: float | int | None) -> None:
    """Validate that all numeric fields are finite.

    Uses the canonical ``validate_finite`` from ``pact_platform.models``
    as the primary check, and adds an explicit ``math.isfinite`` loop
    for fields that may arrive as raw values before model validation.

    Raises:
        ValueError: If any value is NaN or Inf.
    """
    for name, value in fields.items():
        if value is not None and isinstance(value, (int, float)):
            if not math.isfinite(float(value)):
                raise ValueError(
                    f"Envelope field '{name}' must be finite, got {value!r}. "
                    f"NaN/Inf values bypass governance checks."
                )
    # Delegate to the canonical validator for consistent error messages
    validate_finite(**fields)
