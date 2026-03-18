# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Workspace management — workspace-as-knowledge-base with knowledge policy enforcement."""

from care_platform.build.workspace.bridge import (
    Bridge,
    BridgeManager,
    BridgePermission,
    BridgeReviewPolicy,
    BridgeStatus,
    BridgeType,
)
from care_platform.build.workspace.discovery import (
    DiscoveredWorkspace,
    WorkspaceDiscovery,
    WorkspaceManifest,
)
from care_platform.build.workspace.knowledge_policy import (
    KnowledgePolicy,
    KnowledgePolicyEnforcer,
    PolicyDecision,
    PolicyViolation,
)
from care_platform.build.workspace.models import (
    PhaseTransition,
    Workspace,
    WorkspacePhase,
    WorkspaceRegistry,
)

__all__ = [
    "Bridge",
    "BridgeManager",
    "BridgePermission",
    "BridgeReviewPolicy",
    "BridgeStatus",
    "BridgeType",
    "DiscoveredWorkspace",
    "KnowledgePolicy",
    "KnowledgePolicyEnforcer",
    "PhaseTransition",
    "PolicyDecision",
    "PolicyViolation",
    "Workspace",
    "WorkspaceDiscovery",
    "WorkspaceManifest",
    "WorkspacePhase",
    "WorkspaceRegistry",
]
