# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Post-execution TOCTOU comparison for governance envelope drift.

Compares envelope version hashes recorded in GovernanceVerdicts at
verify_action() time against the current envelope state. Divergences
indicate that the governance envelope was modified between the time an
action was approved and the time the audit runs — a Time-of-Check /
Time-of-Use gap.

Usage:
    from pact_platform.use.audit.toctou import audit_toctou_check

    divergences = audit_toctou_check(engine, recent_verdicts)
    for d in divergences:
        print(f"TOCTOU divergence: {d['role_address']} "
              f"recorded={d['recorded_version']} current={d['current_version']}")
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["audit_toctou_check", "compute_envelope_version"]


def compute_envelope_version(envelope: Any) -> str:
    """Compute a SHA-256 version hash for a constraint envelope.

    Args:
        envelope: A ConstraintEnvelopeConfig (Pydantic model with model_dump).

    Returns:
        Hex-encoded SHA-256 hash of the envelope's serialized fields.
    """
    data = envelope.model_dump()
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def audit_toctou_check(
    engine: Any,
    recent_verdicts: list[Any],
) -> list[dict[str, Any]]:
    """Compare recorded envelope snapshots against current org state.

    For each verdict that has a non-empty ``envelope_version``, re-computes
    the effective envelope for that role address and compares the version
    hash. If they differ, it means the governance envelope was modified
    after the verdict was issued.

    Args:
        engine: A GovernanceEngine instance with ``compute_envelope()`` method.
        recent_verdicts: List of GovernanceVerdict objects (or duck-typed
            objects with ``role_address``, ``envelope_version``, ``action``,
            and ``timestamp`` attributes).

    Returns:
        List of divergence dicts, each containing:
            - role_address: The D/T/R address
            - recorded_version: Hash from the original verdict
            - current_version: Hash from re-computed envelope (or None if removed)
            - action: The action from the original verdict
            - timestamp: When the original verdict was issued
            - error: (optional) Error message if envelope computation failed
    """
    if not recent_verdicts:
        return []

    divergences: list[dict[str, Any]] = []

    for verdict in recent_verdicts:
        recorded_version = getattr(verdict, "envelope_version", "")
        if not recorded_version:
            # No version hash recorded — cannot compare
            logger.debug(
                "Skipping verdict for %s: no envelope_version recorded",
                getattr(verdict, "role_address", "unknown"),
            )
            continue

        role_address = verdict.role_address
        action = getattr(verdict, "action", "unknown")
        timestamp = getattr(verdict, "timestamp", None)

        try:
            current_envelope = engine.compute_envelope(role_address)
        except Exception as exc:
            logger.warning(
                "TOCTOU check: compute_envelope failed for %s: %s",
                role_address,
                exc,
            )
            divergences.append(
                {
                    "role_address": role_address,
                    "recorded_version": recorded_version,
                    "current_version": None,
                    "action": action,
                    "timestamp": timestamp,
                    "error": f"compute_envelope failed: {exc}",
                }
            )
            continue

        if current_envelope is None:
            # Envelope was removed since the verdict — definite divergence
            logger.info(
                "TOCTOU divergence: envelope removed for %s " "(was %s at verdict time)",
                role_address,
                recorded_version,
            )
            divergences.append(
                {
                    "role_address": role_address,
                    "recorded_version": recorded_version,
                    "current_version": None,
                    "action": action,
                    "timestamp": timestamp,
                }
            )
            continue

        current_version = compute_envelope_version(current_envelope)

        if current_version != recorded_version:
            logger.info(
                "TOCTOU divergence for %s: recorded=%s current=%s",
                role_address,
                recorded_version,
                current_version,
            )
            divergences.append(
                {
                    "role_address": role_address,
                    "recorded_version": recorded_version,
                    "current_version": current_version,
                    "action": action,
                    "timestamp": timestamp,
                }
            )

    if divergences:
        logger.warning(
            "TOCTOU audit found %d divergence(s) across %d verdict(s)",
            len(divergences),
            len(recent_verdicts),
        )
    else:
        logger.info(
            "TOCTOU audit: no divergences found across %d verdict(s)",
            len(recent_verdicts),
        )

    return divergences
