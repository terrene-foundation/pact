# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Execution layer — agents, teams, LLM backends, hook enforcement, approval, sessions, registry."""

from pact_platform.use.execution.agent import AgentDefinition, TeamDefinition
from pact_platform.use.execution.approval import (
    ApprovalQueue,
    PendingAction,
    QueueOverflowError,
    UrgencyLevel,
)
from pact_platform.use.execution.approver_auth import (
    ApproverRegistry,
    AuthenticatedApprovalQueue,
    SignedDecision,
    sign_decision,
    verify_decision,
)
from pact_platform.use.execution.hook_enforcer import HookEnforcer, HookResult, HookVerdict
from pact_platform.use.execution.llm_backend import (
    BackendRouter,
    LLMBackend,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    StubBackend,
)
from pact_platform.use.execution.registry import AgentRecord, AgentRegistry, AgentStatus
from pact_platform.use.execution.runtime import (
    ExecutionRuntime,
    Task,
    TaskExecutor,
    TaskResult,
    TaskStatus,
)
from pact_platform.use.execution.session import (
    PactSession,
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
    "PactSession",
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
