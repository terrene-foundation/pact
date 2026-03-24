# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""ShadowEnforcer live mode — parallel observation without enforcement.

Collects agreement/divergence metrics between real enforcement decisions
and shadow (proposed) decisions. Never blocks, delays, or alters execution.

This is the production telemetry layer for posture upgrade evidence:
when agreement rates are consistently high for an agent, the operator
has quantitative evidence to justify a posture upgrade.

Usage:
    enforcer = ShadowEnforcerLive(enabled=True)
    enforcer.record(
        action="summarize report",
        agent_id="agent-1",
        real_decision=VerificationLevel.AUTO_APPROVED,
        shadow_decision=VerificationLevel.AUTO_APPROVED,
        posture=TrustPostureLevel.SUPERVISED,
    )
    metrics = enforcer.get_metrics("agent-1")
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from pact_platform.trust._compat import TrustPostureLevel, VerificationLevel

logger = logging.getLogger(__name__)


@dataclass
class ShadowMetrics:
    """Agreement/divergence metrics for one agent."""

    total_evaluations: int = 0
    agreement_count: int = 0
    divergence_count: int = 0

    @property
    def agreement_rate(self) -> float:
        """Fraction of evaluations where real and shadow agreed."""
        if self.total_evaluations == 0:
            return 0.0
        return self.agreement_count / self.total_evaluations


class ShadowEnforcerLive:
    """Live ShadowEnforcer — observes real vs. shadow decisions without interfering.

    When enabled, each call to ``record()`` stores the comparison. When
    disabled, ``record()`` is a no-op with zero overhead.

    Thread-safe: all state mutations are lock-protected.
    """

    # L2-FIX: Maximum number of distinct agents tracked to prevent unbounded growth.
    _MAX_AGENTS: int = 1000

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = enabled
        self._lock = threading.Lock()
        self._metrics: dict[str, ShadowMetrics] = {}
        self._posture_metrics: dict[str, dict[TrustPostureLevel, ShadowMetrics]] = {}
        # L2-FIX: Insertion-ordered tracking for eviction (Python 3.7+ dicts are ordered)
        self._agent_order: list[str] = []

    @property
    def is_enabled(self) -> bool:
        """Whether live mode observation is active."""
        return self._enabled

    def record(
        self,
        *,
        action: str,
        agent_id: str,
        real_decision: VerificationLevel,
        shadow_decision: VerificationLevel,
        posture: TrustPostureLevel | None = None,
    ) -> None:
        """Record a comparison between real and shadow enforcement decisions.

        When disabled, this is a no-op. Never raises, blocks, or delays.
        """
        if not self._enabled:
            return

        agreed = real_decision == shadow_decision

        with self._lock:
            if agent_id not in self._metrics:
                # L2-FIX: Evict oldest agent when at capacity
                if len(self._metrics) >= self._MAX_AGENTS:
                    evict_id = self._agent_order.pop(0)
                    self._metrics.pop(evict_id, None)
                    self._posture_metrics.pop(evict_id, None)
                    logger.info(
                        "ShadowEnforcer: evicted oldest agent '%s' (capacity %d reached)",
                        evict_id,
                        self._MAX_AGENTS,
                    )
                self._metrics[agent_id] = ShadowMetrics()
                self._agent_order.append(agent_id)

            m = self._metrics[agent_id]
            m.total_evaluations += 1
            if agreed:
                m.agreement_count += 1
            else:
                m.divergence_count += 1

            if posture is not None:
                if agent_id not in self._posture_metrics:
                    self._posture_metrics[agent_id] = {}

                posture_map = self._posture_metrics[agent_id]
                if posture not in posture_map:
                    posture_map[posture] = ShadowMetrics()

                pm = posture_map[posture]
                pm.total_evaluations += 1
                if agreed:
                    pm.agreement_count += 1
                else:
                    pm.divergence_count += 1

        if not agreed:
            logger.info(
                "ShadowEnforcer divergence: agent=%s action='%s' real=%s shadow=%s",
                agent_id,
                action,
                real_decision.value,
                shadow_decision.value,
            )

    def get_metrics(self, agent_id: str) -> ShadowMetrics:
        """Get aggregate metrics for an agent.

        Raises:
            KeyError: If no metrics have been recorded for this agent.
        """
        with self._lock:
            return self._metrics[agent_id]

    def get_posture_metrics(self, agent_id: str) -> dict[TrustPostureLevel, ShadowMetrics]:
        """Get per-posture metrics for an agent.

        Raises:
            KeyError: If no posture metrics have been recorded for this agent.
        """
        with self._lock:
            return dict(self._posture_metrics[agent_id])
