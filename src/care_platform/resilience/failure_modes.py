# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Five Failure Modes — detection, impact assessment, mitigation, and recovery.

The CARE specification defines five formal failure modes that the platform
must detect and handle:

1. **TRUST_CHAIN_BREAK**: Genesis record invalid or delegation chain broken.
2. **CONSTRAINT_VIOLATION**: Constraint envelopes not enforced.
3. **COMMUNICATION_ISOLATION**: Cross-Functional Bridges down or isolated.
4. **AUDIT_GAP**: Gaps in the audit anchor chain.
5. **POSTURE_REGRESSION**: Unexpected trust posture regressions.

Each mode has detection criteria, severity, impact assessment, immediate
mitigation actions, and a recovery plan.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FailureMode(str, Enum):
    """The five formal CARE failure modes."""

    TRUST_CHAIN_BREAK = "trust_chain_break"
    CONSTRAINT_VIOLATION = "constraint_violation"
    COMMUNICATION_ISOLATION = "communication_isolation"
    AUDIT_GAP = "audit_gap"
    POSTURE_REGRESSION = "posture_regression"


class FailureSeverity(str, Enum):
    """Severity levels for detected failures."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class MitigationAction(BaseModel):
    """Immediate mitigation actions for a detected failure."""

    description: str
    immediate_actions: list[str] = Field(default_factory=list)


class RecoveryPlan(BaseModel):
    """Recovery plan for restoring normal operations after a failure."""

    steps: list[str] = Field(default_factory=list)
    estimated_duration: str = ""
    requires_human_intervention: bool = False


class SystemHealth(BaseModel):
    """Snapshot of system health indicators used for failure detection.

    Each field represents whether that subsystem is healthy (True) or
    exhibiting failure indicators (False).
    """

    genesis_valid: bool
    delegation_chain_valid: bool
    constraints_enforced: bool
    audit_continuous: bool
    posture_stable: bool
    bridges_active: bool


class DetectionResult(BaseModel):
    """Result of detecting a specific failure mode."""

    failure_mode: FailureMode
    severity: FailureSeverity
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    impact_description: str
    mitigation: MitigationAction
    recovery: RecoveryPlan


# ---------------------------------------------------------------------------
# Failure Definitions
# ---------------------------------------------------------------------------

_FAILURE_DEFINITIONS: dict[FailureMode, dict] = {
    FailureMode.TRUST_CHAIN_BREAK: {
        "severity": FailureSeverity.CRITICAL,
        "impact": (
            "Trust chain integrity compromised. All agent actions lose "
            "cryptographic backing. Delegation records cannot be verified. "
            "The system cannot guarantee that agents operate within their "
            "authorized boundaries."
        ),
        "mitigation": MitigationAction(
            description="Immediately halt all agent operations pending trust chain restoration.",
            immediate_actions=[
                "Suspend all active agent sessions",
                "Block new delegation requests",
                "Notify all team leads of trust chain failure",
                "Preserve current audit state for forensic analysis",
            ],
        ),
        "recovery": RecoveryPlan(
            steps=[
                "Identify the point of chain breakage (genesis or delegation)",
                "If genesis is invalid, re-establish genesis with new key pair",
                "If delegation chain is broken, re-delegate from the last valid link",
                "Verify restored chain integrity end-to-end",
                "Re-validate all active constraint envelopes",
                "Resume agent operations under increased monitoring",
            ],
            estimated_duration="1-4 hours depending on chain depth",
            requires_human_intervention=True,
        ),
    },
    FailureMode.CONSTRAINT_VIOLATION: {
        "severity": FailureSeverity.HIGH,
        "impact": (
            "Constraint envelopes are not being enforced. Agents may be "
            "operating outside their authorized boundaries across one or "
            "more of the five CARE dimensions (Financial, Operational, "
            "Temporal, Data Access, Communication)."
        ),
        "mitigation": MitigationAction(
            description="Restrict agents to minimum-privilege mode until constraints are restored.",
            immediate_actions=[
                "Downgrade all affected agents to PSEUDO_AGENT posture",
                "Enable ShadowEnforcer on all agent actions",
                "Queue all pending actions for human approval",
                "Alert constraint envelope owners",
            ],
        ),
        "recovery": RecoveryPlan(
            steps=[
                "Identify which constraint dimensions are unenforced",
                "Verify constraint envelope configurations are valid",
                "Restore envelope evaluation in the verification middleware",
                "Run ShadowEnforcer validation pass on recent actions",
                "Gradually restore normal posture levels",
            ],
            estimated_duration="30 minutes to 2 hours",
            requires_human_intervention=True,
        ),
    },
    FailureMode.COMMUNICATION_ISOLATION: {
        "severity": FailureSeverity.MEDIUM,
        "impact": (
            "Cross-Functional Bridges are inactive or inaccessible. "
            "Agent teams cannot communicate or share data across team "
            "boundaries. Workflow coordination requiring cross-team "
            "collaboration will stall."
        ),
        "mitigation": MitigationAction(
            description="Enable fallback communication and notify affected teams.",
            immediate_actions=[
                "Notify affected team leads of bridge outage",
                "Enable ad-hoc bridge requests for urgent cross-team needs",
                "Log all failed bridge access attempts for audit",
                "Check bridge expiration and auto-renew if applicable",
            ],
        ),
        "recovery": RecoveryPlan(
            steps=[
                "Diagnose bridge connectivity failure (expired, revoked, or error)",
                "Re-establish standing bridges between affected teams",
                "Verify bridge permissions are correctly configured",
                "Run bridge access tests to confirm restoration",
                "Resume normal cross-team workflows",
            ],
            estimated_duration="15-60 minutes",
            requires_human_intervention=False,
        ),
    },
    FailureMode.AUDIT_GAP: {
        "severity": FailureSeverity.HIGH,
        "impact": (
            "Gaps detected in the audit anchor chain. Actions taken during "
            "the gap period cannot be cryptographically verified. This "
            "compromises the tamper-evident record and may violate "
            "compliance requirements."
        ),
        "mitigation": MitigationAction(
            description="Mark the gap period and increase verification for ongoing actions.",
            immediate_actions=[
                "Record the gap start and end timestamps",
                "Increase verification level for all actions to FULL thoroughness",
                "Enable redundant audit logging",
                "Notify compliance team of the audit discontinuity",
            ],
        ),
        "recovery": RecoveryPlan(
            steps=[
                "Identify the cause of audit chain discontinuity",
                "Reconstruct audit records from secondary logs if available",
                "Create a gap marker in the audit chain documenting the discontinuity",
                "Resume normal audit anchor creation",
                "Validate chain integrity from the gap marker forward",
            ],
            estimated_duration="30 minutes to 2 hours",
            requires_human_intervention=True,
        ),
    },
    FailureMode.POSTURE_REGRESSION: {
        "severity": FailureSeverity.MEDIUM,
        "impact": (
            "One or more agents have experienced unexpected trust posture "
            "regression. This may indicate performance degradation, policy "
            "violations, or security incidents affecting agent trust levels."
        ),
        "mitigation": MitigationAction(
            description="Stabilize posture levels and investigate root cause.",
            immediate_actions=[
                "Lock current posture levels to prevent further regression",
                "Review recent posture change history for affected agents",
                "Check for unresolved incidents triggering downgrades",
                "Enable enhanced monitoring on affected agents",
            ],
        ),
        "recovery": RecoveryPlan(
            steps=[
                "Investigate root cause of posture regression",
                "Resolve any incidents triggering the regression",
                "Reset posture evidence counters after resolution",
                "Allow natural posture evolution to resume",
                "Monitor for recurrence over the next evaluation period",
            ],
            estimated_duration="1-24 hours depending on root cause",
            requires_human_intervention=True,
        ),
    },
}


# ---------------------------------------------------------------------------
# Failure Detector
# ---------------------------------------------------------------------------


class FailureDetector:
    """Detects the five CARE failure modes from system health indicators.

    Given a SystemHealth snapshot, evaluates which failure modes are present
    and returns DetectionResult objects with severity, impact assessment,
    immediate mitigation actions, and recovery plans.
    """

    def detect(self, health: SystemHealth) -> list[DetectionResult]:
        """Detect all active failure modes from system health.

        Args:
            health: Current system health snapshot.

        Returns:
            List of DetectionResult for each detected failure mode.
            Empty list if no failures are detected.
        """
        results: list[DetectionResult] = []

        # 1. Trust Chain Break
        if not health.genesis_valid or not health.delegation_chain_valid:
            results.append(self._build_result(FailureMode.TRUST_CHAIN_BREAK))

        # 2. Constraint Violation
        if not health.constraints_enforced:
            results.append(self._build_result(FailureMode.CONSTRAINT_VIOLATION))

        # 3. Communication Isolation
        if not health.bridges_active:
            results.append(self._build_result(FailureMode.COMMUNICATION_ISOLATION))

        # 4. Audit Gap
        if not health.audit_continuous:
            results.append(self._build_result(FailureMode.AUDIT_GAP))

        # 5. Posture Regression
        if not health.posture_stable:
            results.append(self._build_result(FailureMode.POSTURE_REGRESSION))

        if results:
            logger.warning(
                "Detected %d failure mode(s): %s",
                len(results),
                ", ".join(r.failure_mode.value for r in results),
            )
        else:
            logger.info("System health check passed: no failure modes detected")

        return results

    def _build_result(self, mode: FailureMode) -> DetectionResult:
        """Build a DetectionResult from the failure definition."""
        defn = _FAILURE_DEFINITIONS[mode]
        return DetectionResult(
            failure_mode=mode,
            severity=defn["severity"],
            impact_description=defn["impact"],
            mitigation=defn["mitigation"],
            recovery=defn["recovery"],
        )
