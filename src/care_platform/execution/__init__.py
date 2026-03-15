# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Execution layer — agents, teams, LLM backends, hook enforcement, approval, sessions, registry."""

from care_platform.execution.agent import AgentDefinition, TeamDefinition
from care_platform.execution.approval import (
    ApprovalQueue,
    PendingAction,
    QueueOverflowError,
    UrgencyLevel,
)
from care_platform.execution.approver_auth import (
    ApproverRegistry,
    AuthenticatedApprovalQueue,
    SignedDecision,
    sign_decision,
    verify_decision,
)
from care_platform.execution.hook_enforcer import HookEnforcer, HookResult, HookVerdict
from care_platform.execution.llm_backend import (
    BackendRouter,
    LLMBackend,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    StubBackend,
)
from care_platform.execution.registry import AgentRecord, AgentRegistry, AgentStatus
from care_platform.execution.runtime import (
    ExecutionRuntime,
    Task,
    TaskExecutor,
    TaskResult,
    TaskStatus,
)
from care_platform.execution.session import (
    PlatformSession,
    SessionCheckpoint,
    SessionManager,
    SessionState,
)

__all__ = [
    "AgentDefinition",
    "AgentRecord",
    "ExecutionRuntime",
    "AgentRegistry",
    "AgentStatus",
    "ApprovalQueue",
    "ApproverRegistry",
    "AuthenticatedApprovalQueue",
    "BackendRouter",
    "HookEnforcer",
    "HookResult",
    "HookVerdict",
    "LLMBackend",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "PendingAction",
    "PlatformSession",
    "QueueOverflowError",
    "SessionCheckpoint",
    "SessionManager",
    "SessionState",
    "SignedDecision",
    "StubBackend",
    "Task",
    "TaskExecutor",
    "TaskResult",
    "TaskStatus",
    "TeamDefinition",
    "UrgencyLevel",
    "sign_decision",
    "verify_decision",
]
