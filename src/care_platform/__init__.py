# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
# Timestamp naming: timestamp (generic), created_at (creation), <verb>_at (lifecycle events)
"""
CARE Platform — Governed operational model for running organizations
with AI agents under EATP trust governance.

Architecture:
    care_platform.trust       — EATP trust layer (genesis, delegation, verification)
    care_platform.constraint  — Constraint envelope evaluation (5 dimensions)
    care_platform.execution   — Agent execution plane (Kaizen-based runtime)
    care_platform.audit       — Audit anchor chain (tamper-evident records)
    care_platform.workspace   — Workspace-as-knowledge-base management
    care_platform.config      — Platform configuration and agent definitions
"""

__version__ = "0.1.0"

# --- Audit ---
from care_platform.audit.anchor import AuditAnchor, AuditChain

# --- Config ---
from care_platform.config.schema import (
    AgentConfig,
    ConstraintEnvelopeConfig,
    PlatformConfig,
    TeamConfig,
    WorkspaceConfig,
)

# --- Constraint ---
from care_platform.constraint.envelope import ConstraintEnvelope, EvaluationResult
from care_platform.constraint.gradient import GradientEngine

# --- Execution ---
from care_platform.execution.agent import AgentDefinition, TeamDefinition
from care_platform.execution.approval import ApprovalQueue, PendingAction, UrgencyLevel
from care_platform.execution.registry import AgentRecord, AgentRegistry, AgentStatus
from care_platform.execution.session import (
    PlatformSession,
    SessionCheckpoint,
    SessionManager,
    SessionState,
)

# --- Trust ---
from care_platform.trust.attestation import CapabilityAttestation
from care_platform.trust.posture import TrustPosture
from care_platform.trust.scoring import TrustScore, calculate_trust_score

# --- Workspace ---
from care_platform.workspace.models import Workspace, WorkspacePhase, WorkspaceRegistry

__all__ = [
    # Config
    "PlatformConfig",
    "AgentConfig",
    "TeamConfig",
    "WorkspaceConfig",
    "ConstraintEnvelopeConfig",
    # Constraint
    "ConstraintEnvelope",
    "GradientEngine",
    "EvaluationResult",
    # Trust
    "TrustPosture",
    "CapabilityAttestation",
    "TrustScore",
    "calculate_trust_score",
    # Audit
    "AuditAnchor",
    "AuditChain",
    # Workspace
    "Workspace",
    "WorkspacePhase",
    "WorkspaceRegistry",
    # Execution
    "AgentDefinition",
    "TeamDefinition",
    "ApprovalQueue",
    "PendingAction",
    "UrgencyLevel",
    "AgentRecord",
    "AgentRegistry",
    "AgentStatus",
    "PlatformSession",
    "SessionCheckpoint",
    "SessionManager",
    "SessionState",
]
