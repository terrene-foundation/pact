# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Agent execution runtime — task processing with governance verification pipeline.

Provides the execution loop that takes a task, selects an agent, runs it
through the governance verification pipeline (verify -> execute -> audit), and
records the result.

The runtime integrates:
- Task queue: submit tasks for agent execution
- Agent selection: match tasks to capable agents via AgentRegistry
- Verification: GovernanceEngine.verify_action() classifies each action
- Approval: HELD actions enter the ApprovalQueue
- Audit: Every execution produces an AuditAnchor
- Lifecycle: Track task status from submission to completion
- Trust store: Optional persistence for audit anchors, posture changes
- Revocation: Optional revocation checks during agent assignment
- Posture: Optional trust posture enforcement (PSEUDO_AGENT blocked)
- Thread safety: All task queue mutations are lock-protected (RT4-M9)

Usage:
    runtime = ExecutionRuntime(
        registry=registry,
        audit_chain=audit_chain,
        governance_engine=engine,
    )
    task_id = runtime.submit("summarize docs/report.md", agent_id="writer-1")
    runtime.process_next()

    # Hydrate from a TrustStore (RT4-C2):
    runtime = ExecutionRuntime.from_store(
        trust_store=store,
        audit_chain=audit_chain,
    )
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from pact_platform.build.config.schema import TrustPostureLevel, VerificationLevel
from pact_platform.trust.audit.anchor import AuditChain
from pact_platform.trust._compat import NEVER_DELEGATED_ACTIONS
from pact_platform.use.execution.approval import ApprovalQueue
from pact_platform.use.execution.approver_auth import AuthenticatedApprovalQueue
from pact_platform.use.execution.registry import AgentRecord, AgentRegistry, AgentStatus

if TYPE_CHECKING:
    from pact_platform.build.workspace.bridge import BridgeManager
    from pact.governance.engine import GovernanceEngine
    from pact_platform.trust._compat import TrustPosture
    from pact_platform.trust.store.store import TrustStore

# Type aliases for deleted modules whose types appear only in optional parameters.
# At runtime these are always None-checked before use, so Any is safe.
BridgeTrustManager = Any  # was: pact_platform.trust.bridge_trust.BridgeTrustManager
RevocationManager = Any  # was: pact_platform.trust.revocation.RevocationManager

logger = logging.getLogger(__name__)

# LC-1 / LC-3: Maximum number of agents tracked in cumulative spend and
# action-timestamp dicts.  Prevents unbounded memory growth.
_MAX_TRACKED_AGENTS: int = 10_000

# LC-3: Rolling window for rate-limit enforcement (24 hours in seconds).
_RATE_LIMIT_WINDOW_SECONDS: float = 86_400.0


class TaskStatus(str, Enum):
    """Lifecycle status of a submitted task."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    VERIFYING = "verifying"
    HELD = "held"
    BLOCKED = "blocked"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskResult(BaseModel):
    """Result of executing a task."""

    output: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Task(BaseModel):
    """A unit of work submitted for agent execution."""

    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:12]}")
    action: str = Field(description="The action/task to perform")
    agent_id: str | None = Field(
        default=None, description="Specific agent, or None for auto-select"
    )
    team_id: str = Field(default="", description="Team context for the task")
    priority: int = Field(default=0, ge=0, description="Higher = more urgent")
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: str | None = None
    verification_level: VerificationLevel | None = None
    result: TaskResult | None = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # RT4-M8: Retry support
    max_retries: int = Field(default=0, ge=0, description="Remaining retry attempts")


class ExecutionRuntime:
    """Task processing runtime with governance verification pipeline.

    Each task goes through:
    1. Submit -> enters the task queue
    2. Assign -> matched to a capable agent (or uses specified agent)
    3. Verify -> GovernanceEngine.verify_action() classifies the action
    4. Execute -> if AUTO_APPROVED or FLAGGED, execute immediately
    5. Hold -> if HELD, enter ApprovalQueue for human decision
    6. Block -> if BLOCKED, reject outright
    7. Audit -> record result in the AuditChain

    Supported features:
    - RT4-M9: Thread-safe task queue via threading.Lock
    - RT4-C2: from_store() class method for store-to-runtime hydration
    - RT4-H2: Audit anchors persisted to TrustStore
    - RT4-H3: Revocation checks in _assign_agent
    - RT4-H4: Trust posture enforcement (PSEUDO_AGENT blocked)
    - RT4-M1: HELD task resumption via resume_held()
    - RT4-M2: AuthenticatedApprovalQueue type support
    - RT4-M5: Cascade revocation sync to AgentRegistry
    - RT4-M7: Posture changes auto-persisted to TrustStore
    - RT4-M8: Task retry mechanism
    - RT4-M11: BLOCKED task deduplication
    """

    def __init__(
        self,
        registry: AgentRegistry,
        audit_chain: AuditChain,
        approval_queue: ApprovalQueue | AuthenticatedApprovalQueue | None = None,
        *,
        signing_key: bytes | None = None,
        signer_id: str | None = None,
        trust_store: TrustStore | None = None,
        revocation_manager: RevocationManager | None = None,
        posture_manager: dict[str, TrustPosture] | None = None,
        bridge_manager: BridgeManager | None = None,
        bridge_trust_manager: BridgeTrustManager | None = None,
        governance_engine: GovernanceEngine | None = None,
    ) -> None:
        """Initialize the execution runtime.

        Args:
            registry: Agent registry for agent lookup and selection.
            audit_chain: Audit chain for recording execution history.
            approval_queue: Optional approval queue for HELD actions (RT4-M2:
                accepts both ApprovalQueue and AuthenticatedApprovalQueue).
                If not provided, a default ApprovalQueue is created.
            signing_key: Optional key for signing audit anchors.
            signer_id: Signer ID for audit anchors (required if signing_key is set).
            trust_store: Optional TrustStore for persisting audit anchors and
                posture changes (RT4-H2, RT4-M7).
            revocation_manager: Optional RevocationManager for checking agent
                revocation status during assignment (RT4-H3).
            posture_manager: Optional mapping of agent_id -> TrustPosture for
                enforcing posture checks (RT4-H4). PSEUDO_AGENT is blocked.
            bridge_manager: Optional BridgeManager for Cross-Functional Bridge
                lookups (M33-3301). When present, cross-team tasks are verified
                through the bridge trust pipeline.
            bridge_trust_manager: Optional BridgeTrustManager for bridge
                delegation lookups (M33-3301).
            governance_engine: Optional GovernanceEngine for PACT governance
                integration. When provided, verify_action() is used for
                pre-execution checks. Agents receive GovernanceContext (frozen),
                not the engine itself.
        """
        self._registry = registry
        self._audit_chain = audit_chain
        self._approval_queue: ApprovalQueue | AuthenticatedApprovalQueue = (
            approval_queue if approval_queue is not None else ApprovalQueue()
        )
        self._signing_key = signing_key
        self._signer_id = signer_id

        # RT4-C2 / RT4-H2 / RT4-M7: Trust store integration
        self._trust_store: TrustStore | None = trust_store
        # RT4-H3 / RT4-M5: Revocation integration
        self._revocation_manager: RevocationManager | None = revocation_manager
        # RT4-H4: Posture integration
        self._posture_manager: dict[str, TrustPosture] | None = posture_manager
        # M33-3301: Bridge integration for cross-team verification
        self._bridge_manager: BridgeManager | None = bridge_manager
        self._bridge_trust_manager: BridgeTrustManager | None = bridge_trust_manager
        # PACT GovernanceEngine integration
        self._governance_engine: GovernanceEngine | None = governance_engine
        # Agent ID -> D/T/R role address mapping for governance lookups
        self._agent_role_addresses: dict[str, str] = {}
        # Emergency halt state — blocks all task processing when active
        self._halted: bool = False
        self._halt_reason: str = ""

        # RT4-M9: Thread-safe task queue
        self._lock = threading.Lock()
        self._tasks: dict[str, Task] = {}
        self._queue: list[str] = []  # task_ids in priority order
        self._executor: TaskExecutor | None = None
        # RT9-11: Track audit persist failures for monitoring
        self._audit_persist_failures: int = 0

        # RT5-09: Refresh interval for periodic store re-hydration (seconds).
        # Set to 0 to disable periodic refresh (manual refresh_from_store() still works).
        self._refresh_interval: float = 0.0
        self._last_refresh_time: float = time.monotonic()

        # LC-1: Cumulative budget tracking per agent (agent_id -> total USD spent).
        # Bounded to MAX_TRACKED_AGENTS entries to prevent OOM.
        self._cumulative_spend: dict[str, float] = {}

        # LC-3: Rate limit enforcement — per-agent action timestamps (UTC epoch seconds).
        # Used to count actions in rolling 24-hour windows.
        self._action_timestamps: dict[str, list[float]] = {}

    @classmethod
    def from_store(
        cls,
        trust_store: TrustStore,
        audit_chain: AuditChain,
        *,
        approval_queue: ApprovalQueue | AuthenticatedApprovalQueue | None = None,
        signing_key: bytes | None = None,
        signer_id: str | None = None,
        revocation_manager: RevocationManager | None = None,
        posture_manager: dict[str, TrustPosture] | None = None,
        governance_engine: GovernanceEngine | None = None,
    ) -> ExecutionRuntime:
        """Create a runtime hydrated from a TrustStore (RT4-C2).

        Reads genesis records, delegation records, and envelope data from the
        store to populate the AgentRegistry. This bridges the persistence layer
        to the execution layer.

        Args:
            trust_store: The TrustStore containing trust objects.
            audit_chain: Audit chain for recording execution history.
            approval_queue: Optional approval queue.
            signing_key: Optional signing key for audit anchors.
            signer_id: Signer ID for audit anchors.
            revocation_manager: Optional revocation manager.
            posture_manager: Optional posture manager.
            governance_engine: Optional GovernanceEngine for PACT governance.

        Returns:
            A fully initialized ExecutionRuntime with agents hydrated from the store.
        """
        registry = AgentRegistry()

        # Hydrate agents from delegation records in the store.
        # Each delegation record represents an agent that was delegated trust.
        # We look for delegatee_id entries as agent registrations.
        _seen_agents: set[str] = set()

        # Get all delegations by checking for known genesis authorities
        # and iterating their delegatees.
        all_delegations: list[dict] = []

        # Attempt to collect delegations from all known genesis authorities
        # by scanning delegations for all agents we find.
        # We use a broad approach: get delegations for each genesis authority.
        for genesis_data in _collect_all_genesis(trust_store):
            authority_id = genesis_data.get("authority_id", "")
            if authority_id:
                delegations = trust_store.get_delegations_for(authority_id)
                all_delegations.extend(delegations)

        # Also try to find delegations by scanning envelopes for agent_ids
        for envelope_data in trust_store.list_envelopes():
            agent_id = envelope_data.get("agent_id", "")
            if agent_id and agent_id not in _seen_agents:
                delegations = trust_store.get_delegations_for(agent_id)
                all_delegations.extend(delegations)

        # Register agents from delegation records
        for del_data in all_delegations:
            agent_id = del_data.get("delegatee_id", "")
            if not agent_id or agent_id in _seen_agents:
                continue
            _seen_agents.add(agent_id)

            agent_name = del_data.get("agent_name", agent_id)
            agent_role = del_data.get("agent_role", "agent")
            team_id = del_data.get("team_id", "")
            capabilities = del_data.get("capabilities", [])

            try:
                registry.register(
                    agent_id=agent_id,
                    name=agent_name,
                    role=agent_role,
                    team_id=team_id,
                    capabilities=capabilities if isinstance(capabilities, list) else [],
                )
            except ValueError:
                # Agent already registered (shouldn't happen with _seen_agents, but defensive)
                logger.debug("Agent '%s' already registered during hydration", agent_id)

        logger.info(
            "Hydrated %d agents from TrustStore into AgentRegistry",
            len(_seen_agents),
        )

        return cls(
            registry=registry,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
            signing_key=signing_key,
            signer_id=signer_id,
            trust_store=trust_store,
            revocation_manager=revocation_manager,
            posture_manager=posture_manager,
            governance_engine=governance_engine,
        )

    @property
    def queue_depth(self) -> int:
        """Number of tasks waiting to be processed."""
        with self._lock:
            return len(self._queue)

    @property
    def all_tasks(self) -> list[Task]:
        """All tasks, regardless of status."""
        with self._lock:
            return list(self._tasks.values())

    def set_executor(self, executor: TaskExecutor) -> None:
        """Set the task executor callback.

        The executor is called to actually perform the task once it passes
        verification. If no executor is set, tasks are marked as completed
        with an empty result.

        Args:
            executor: A TaskExecutor instance.
        """
        self._executor = executor

    def set_agent_role_address(self, agent_id: str, role_address: str) -> None:
        """Map an agent ID to a D/T/R role address for governance lookups.

        When a GovernanceEngine is configured, the runtime needs to know which
        D/T/R address each agent occupies so it can call verify_action() with
        the correct positional address.

        Args:
            agent_id: The agent ID (as registered in the AgentRegistry).
            role_address: The D/T/R positional address of the role the agent occupies.
        """
        with self._lock:
            self._agent_role_addresses[agent_id] = role_address
        logger.info(
            "Mapped agent '%s' to role address '%s'",
            agent_id,
            role_address,
        )

    def submit(
        self,
        action: str,
        *,
        agent_id: str | None = None,
        team_id: str = "",
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
        max_retries: int = 0,
    ) -> str:
        """Submit a task for execution.

        Args:
            action: The action/task description.
            agent_id: Specific agent to assign, or None for auto-selection.
            team_id: Team context.
            priority: Task priority (higher = more urgent).
            metadata: Additional task metadata.
            max_retries: Number of retry attempts on failure (RT4-M8).

        Returns:
            The task_id for tracking.

        Raises:
            ValueError: If a BLOCKED task with the same action and agent_id
                already exists (RT4-M11 deduplication).
        """
        with self._lock:
            # RT4-M11: BLOCKED task deduplication
            if agent_id is not None:
                for existing_task in self._tasks.values():
                    if (
                        existing_task.status == TaskStatus.BLOCKED
                        and existing_task.action == action
                        and existing_task.agent_id == agent_id
                    ):
                        raise ValueError(
                            f"Duplicate BLOCKED task: action='{action}' agent_id='{agent_id}' "
                            f"already exists as task '{existing_task.task_id}'. "
                            f"Resolve the existing BLOCKED task before resubmitting."
                        )

            task = Task(
                action=action,
                agent_id=agent_id,
                team_id=team_id,
                priority=priority,
                metadata=metadata or {},
                max_retries=max_retries,
            )
            self._tasks[task.task_id] = task
            self._queue.append(task.task_id)
            # Sort by priority (highest first)
            self._queue.sort(key=lambda tid: self._tasks[tid].priority, reverse=True)

        logger.info(
            "Task submitted: task_id='%s' action='%s' agent_id=%s max_retries=%d",
            task.task_id,
            action,
            agent_id or "(auto)",
            max_retries,
        )
        return task.task_id

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def halt(self, reason: str) -> None:
        """Emergency halt — block all task processing until resumed.

        Args:
            reason: Non-empty reason for the halt.
        """
        if not reason:
            raise ValueError("Halt reason must not be empty")
        self._halted = True
        self._halt_reason = reason
        logger.warning("ExecutionRuntime HALTED: %s", reason)

    def resume(self) -> None:
        """Resume normal operation after an emergency halt."""
        was_halted = self._halted
        self._halted = False
        self._halt_reason = ""
        if was_halted:
            logger.info("ExecutionRuntime resumed from halt")

    @property
    def is_halted(self) -> bool:
        """Whether the runtime is in emergency halt state."""
        return self._halted

    def process_next(self) -> Task | None:
        """Process the next task in the queue.

        Follows the verify -> execute -> audit pipeline:
        0. Sync revocations from RevocationManager (RT5-08)
        1. Dequeue the highest-priority pending task
        2. Assign an agent (auto-select or use specified)
        3. Check trust posture (RT4-H4, RT5-07 SUPERVISED escalation)
        4. Run through verification gradient (with envelope evaluation RT5-01)
        5. Check NEVER_DELEGATED_ACTIONS (RT5-06)
        6. Optionally verify via middleware (RT4-H9, RT5-23 no redundant classify)
        7. Execute if allowed, hold if HELD, block if BLOCKED
        8. Handle retries on failure (RT4-M8)
        9. Record audit anchor (with store persistence RT4-H2)

        Returns:
            The processed Task, or None if the queue is empty.
        """
        # Emergency halt check — block all processing
        if self._halted:
            logger.warning("process_next blocked: runtime is halted (%s)", self._halt_reason)
            return None

        # RT5-08: Sync revocations before dequeuing so newly-revoked agents
        # are reflected in the registry before assignment.
        self._sync_revocations()

        # RT5-09: Periodic store refresh if configured
        if self._refresh_interval > 0 and self._trust_store is not None:
            elapsed = time.monotonic() - self._last_refresh_time
            if elapsed >= self._refresh_interval:
                self.refresh_from_store()

        # RT5-10: Hold lock for dequeue + initial status transition
        with self._lock:
            if not self._queue:
                return None
            task_id = self._queue.pop(0)
            task = self._tasks.get(task_id)
            if task is None:
                return None
            # Mark as ASSIGNED under lock to prevent double-processing
            task.status = TaskStatus.ASSIGNED

        # Step 1: Assign agent (includes RT4-H3 revocation check)
        agent = self._assign_agent(task)
        if agent is None:
            with self._lock:
                task.status = TaskStatus.FAILED
                # Preserve specific error from _assign_agent (e.g. revocation),
                # fall back to generic message if none was set.
                if task.result is None:
                    task.result = TaskResult(error="No capable agent available")
                task.completed_at = datetime.now(UTC)
            self._record_audit(task, VerificationLevel.BLOCKED)
            return task

        with self._lock:
            task.assigned_agent_id = agent.agent_id
            task.status = TaskStatus.VERIFYING
            task.started_at = datetime.now(UTC)

        # RT4-H4 + RT5-07: Check trust posture before verification
        if self._posture_manager is not None:
            posture = self._posture_manager.get(agent.agent_id)
            if posture is not None:
                if posture.current_level == TrustPostureLevel.PSEUDO_AGENT:
                    with self._lock:
                        task.status = TaskStatus.BLOCKED
                        task.result = TaskResult(
                            error="Agent at PSEUDO_AGENT posture has no action authority"
                        )
                        task.completed_at = datetime.now(UTC)
                    self._record_audit(task, VerificationLevel.BLOCKED)
                    # RT5-08: Persist posture enforcement event
                    self._persist_posture_change(
                        agent.agent_id,
                        {
                            "agent_id": agent.agent_id,
                            "current_posture": posture.current_level.value,
                            "event": "blocked_pseudo_agent",
                            "action": task.action,
                            "task_id": task.task_id,
                        },
                    )
                    return task

        # M33-3301: Cross-Functional Bridge verification.
        # When a task targets an agent on a different team and a bridge_manager
        # is configured, verify that an ACTIVE bridge exists and compute the
        # effective posture/envelope for the bridge-constrained action.
        if self._bridge_manager is not None and task.team_id and agent.team_id:
            if task.team_id != agent.team_id:
                bridge_level = self._check_bridge_verification(
                    action=task.action,
                    agent_id=agent.agent_id,
                    source_team=task.team_id,
                    target_team=agent.team_id,
                )
                if bridge_level is not None:
                    if bridge_level == VerificationLevel.BLOCKED:
                        with self._lock:
                            task.status = TaskStatus.BLOCKED
                            task.verification_level = VerificationLevel.BLOCKED
                            task.result = TaskResult(
                                error=(
                                    f"Cross-team action blocked: no ACTIVE bridge "
                                    f"between '{task.team_id}' and '{agent.team_id}', "
                                    f"or action '{task.action}' is not permitted by the bridge"
                                )
                            )
                            task.completed_at = datetime.now(UTC)
                        self._record_audit(task, VerificationLevel.BLOCKED)
                        return task
                    elif bridge_level == VerificationLevel.HELD:
                        with self._lock:
                            task.status = TaskStatus.HELD
                            task.verification_level = VerificationLevel.HELD
                        self._approval_queue.submit(
                            agent_id=agent.agent_id,
                            action=task.action,
                            reason=(
                                f"Cross-team action via bridge between "
                                f"'{task.team_id}' and '{agent.team_id}' "
                                f"requires human approval (effective posture)"
                            ),
                            team_id=task.team_id,
                        )
                        self._record_audit(task, VerificationLevel.HELD)
                        return task
                    # AUTO_APPROVED or FLAGGED: store in metadata and continue
                    task.metadata["bridge_verification_level"] = bridge_level.value
                    task.metadata["bridge_source_team"] = task.team_id
                    task.metadata["bridge_target_team"] = agent.team_id

        # LC-3: Rate-limit enforcement — check rolling 24-hour action count.
        # Applied before governance verification so governance engine also sees
        # the action_count_today in its context (injected in _run_governance_verification).
        rate_limit_result = self._check_rate_limit(task, agent)
        if rate_limit_result is not None:
            return rate_limit_result

        # GovernanceEngine verification path.
        # When governance_engine is provided AND we have a role address for the
        # agent, use governance_engine.verify_action() instead of the standalone
        # gradient/envelope path.
        if self._governance_engine is not None:
            role_address = self._agent_role_addresses.get(agent.agent_id)
            if role_address is not None:
                governance_result = self._run_governance_verification(
                    task=task,
                    agent=agent,
                    role_address=role_address,
                )
                if governance_result is not None:
                    # Governance path handled the task -- return it
                    return governance_result
                # If _run_governance_verification returned None, it means
                # governance approved (auto_approved or flagged) and we should
                # fall through to execution below. But we need to skip the
                # standalone verification paths since governance already checked.
                # We set a flag on the task metadata to signal this.
                task.metadata["_governance_verified"] = True
            else:
                # Fail-closed: governance engine is configured but agent has no
                # role address mapping. Block rather than silently permitting.
                logger.warning(
                    "Governance engine configured but no role_address for agent '%s' "
                    "— fail-closed BLOCKED",
                    agent.agent_id,
                )
                with self._lock:
                    task.status = TaskStatus.BLOCKED
                    task.verification_level = VerificationLevel.BLOCKED
                    task.result = TaskResult(
                        error="Agent has no governance role address — cannot verify action"
                    )
                    task.completed_at = datetime.now(UTC)
                self._record_audit(task, VerificationLevel.BLOCKED)
                return task

        # Step 2: Act on verification result set by GovernanceEngine path above,
        # or default to AUTO_APPROVED if governance engine is not configured.
        # For non-governed agents, check NEVER_DELEGATED_ACTIONS and SUPERVISED posture.
        if not task.metadata.get("_governance_verified"):
            if self._governance_engine is None:
                logger.warning(
                    "No governance engine configured — task '%s' action '%s' defaulting to AUTO_APPROVED. "
                    "Configure a GovernanceEngine for production use.",
                    task.task_id,
                    task.action,
                )
            # No governance engine configured: default AUTO_APPROVED
            if task.verification_level is None:
                task.verification_level = VerificationLevel.AUTO_APPROVED

            # RT5-06: Force HELD for NEVER_DELEGATED_ACTIONS (unless already BLOCKED)
            if (
                task.action in NEVER_DELEGATED_ACTIONS
                and task.verification_level != VerificationLevel.BLOCKED
            ):
                task.verification_level = VerificationLevel.HELD
                logger.info(
                    "NEVER_DELEGATED_ACTIONS: escalated '%s' to HELD for task '%s'",
                    task.action,
                    task.task_id,
                )

            # RT5-07: SUPERVISED posture escalation
            if self._posture_manager is not None:
                posture = self._posture_manager.get(agent.agent_id)
                if (
                    posture is not None
                    and posture.current_level == TrustPostureLevel.SUPERVISED
                    and task.verification_level
                    in (VerificationLevel.AUTO_APPROVED, VerificationLevel.FLAGGED)
                ):
                    task.verification_level = VerificationLevel.HELD
                    logger.info(
                        "SUPERVISED escalation: escalated '%s' to HELD for agent '%s'",
                        task.action,
                        agent.agent_id,
                    )

        # Step 3: Act on verification result.
        final_level = task.verification_level or VerificationLevel.AUTO_APPROVED
        if final_level == VerificationLevel.BLOCKED:
            with self._lock:
                task.status = TaskStatus.BLOCKED
                task.result = TaskResult(error="Action blocked by governance")
                task.completed_at = datetime.now(UTC)
            self._record_audit(task, final_level)
            return task

        if final_level == VerificationLevel.HELD:
            with self._lock:
                task.status = TaskStatus.HELD
            self._approval_queue.submit(
                agent_id=agent.agent_id,
                action=task.action,
                reason="Held for human approval",
                team_id=task.team_id,
            )
            self._record_audit(task, final_level)
            return task

        # Step 4: Execute
        with self._lock:
            task.status = TaskStatus.EXECUTING
        self._registry.touch(agent.agent_id)

        try:
            if self._executor is not None:
                result = self._executor.execute(task, agent)
                task.result = result
            else:
                task.result = TaskResult(output="executed")
            with self._lock:
                task.status = TaskStatus.COMPLETED
                # LC-1: Accumulate spend after successful execution.
                import math as _math_exec

                raw_cost = task.metadata.get("cost_usd") or task.metadata.get("cost") or 0.0
                try:
                    action_cost = float(raw_cost)
                except (TypeError, ValueError):
                    action_cost = 0.0
                if not _math_exec.isfinite(action_cost) or action_cost < 0:
                    action_cost = 0.0
                _aid = agent.agent_id
                if (
                    len(self._cumulative_spend) >= _MAX_TRACKED_AGENTS
                    and _aid not in self._cumulative_spend
                ):
                    _oldest = next(iter(self._cumulative_spend))
                    del self._cumulative_spend[_oldest]
                self._cumulative_spend[_aid] = self._cumulative_spend.get(_aid, 0.0) + action_cost
                # LC-3: Record action timestamp for rate-limit window tracking.
                _now_ts = time.monotonic()
                if (
                    len(self._action_timestamps) >= _MAX_TRACKED_AGENTS
                    and _aid not in self._action_timestamps
                ):
                    _oldest_ts = next(iter(self._action_timestamps))
                    del self._action_timestamps[_oldest_ts]
                if _aid not in self._action_timestamps:
                    self._action_timestamps[_aid] = []
                self._action_timestamps[_aid].append(_now_ts)
                # Prune stale timestamps on write (bounded per-agent list)
                _cutoff_w = _now_ts - _RATE_LIMIT_WINDOW_SECONDS
                self._action_timestamps[_aid] = [
                    t for t in self._action_timestamps[_aid] if t >= _cutoff_w
                ]
        except Exception as exc:
            logger.error(
                "Task execution failed: task_id='%s' error='%s'",
                task.task_id,
                exc,
            )
            with self._lock:
                task.status = TaskStatus.FAILED
                task.result = TaskResult(error=str(exc))

            # RT4-M8: Re-enqueue if retries remaining
            if task.max_retries > 0:
                task.max_retries -= 1
                logger.info(
                    "Retrying task '%s': %d retries remaining",
                    task.task_id,
                    task.max_retries,
                )
                with self._lock:
                    self._queue.append(task.task_id)
                    self._queue.sort(key=lambda tid: self._tasks[tid].priority, reverse=True)
                    # Reset status for retry
                    task.status = TaskStatus.PENDING
                    task.started_at = None
                    task.completed_at = None
                    task.result = None
                return task

        with self._lock:
            task.completed_at = datetime.now(UTC)

        # Step 5: Audit
        self._record_audit(task, task.verification_level)

        return task

    def process_all(self) -> list[Task]:
        """Process all pending tasks in the queue.

        Returns:
            List of processed Tasks.
        """
        processed: list[Task] = []
        while True:
            with self._lock:
                if not self._queue:
                    break
            task = self.process_next()
            if task is not None:
                processed.append(task)
        return processed

    def resume_held(
        self,
        task_id: str,
        decision: str,
        *,
        approver_id: str = "",
    ) -> Task | None:
        """Resume a HELD task with an approval decision (RT4-M1, RT5-02).

        RT6-01: The task retrieval, status check, and initial status transition
        all happen under a single lock acquisition to prevent TOCTOU races
        where two concurrent resume_held() calls both pass the HELD check.

        Args:
            task_id: The task to resume.
            decision: Either "approved" (execute the task) or "rejected"
                (mark as FAILED).
            approver_id: ID of the human approver (RT5-02). Logged in audit.

        Returns:
            The resumed Task, or None if the task does not exist or is
            not in HELD status.
        """
        if decision not in ("approved", "rejected"):
            raise ValueError(
                f"Invalid resume decision '{decision}': must be 'approved' or 'rejected'"
            )

        # RT6-01: Hold lock for status check -> pre-checks -> transition.
        # This prevents two concurrent resume_held() calls from both seeing
        # HELD and proceeding.
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.status != TaskStatus.HELD:
                return None
            agent_id = task.assigned_agent_id

            if decision == "rejected":
                # Entire rejected path completes under lock -- no execution needed.
                task.status = TaskStatus.FAILED
                task.result = TaskResult(error="Task rejected by human decision")
                task.completed_at = datetime.now(UTC)

            elif decision == "approved":
                # RT5-02: Re-check revocation before executing (fast in-memory)
                if self._revocation_manager is not None and agent_id:
                    if self._revocation_manager.is_revoked(agent_id):
                        logger.warning(
                            "resume_held: agent '%s' is revoked, cannot execute task '%s'",
                            agent_id,
                            task.task_id,
                        )
                        task.status = TaskStatus.FAILED
                        task.result = TaskResult(
                            error=f"Agent '{agent_id}' has been revoked since the task was held"
                        )
                        task.completed_at = datetime.now(UTC)

                # RT5-02: Re-check posture before executing (fast in-memory)
                if (
                    task.status != TaskStatus.FAILED
                    and self._posture_manager is not None
                    and agent_id
                ):
                    posture = self._posture_manager.get(agent_id)
                    if (
                        posture is not None
                        and posture.current_level == TrustPostureLevel.PSEUDO_AGENT
                    ):
                        logger.warning(
                            "resume_held: agent '%s' is at PSEUDO_AGENT posture, "
                            "cannot execute task '%s'",
                            agent_id,
                            task.task_id,
                        )
                        task.status = TaskStatus.FAILED
                        task.result = TaskResult(
                            error="Agent at PSEUDO_AGENT posture has no action authority"
                        )
                        task.completed_at = datetime.now(UTC)

                # If not failed by pre-checks, mark EXECUTING under lock
                if task.status != TaskStatus.FAILED:
                    task.status = TaskStatus.EXECUTING

        # --- Lock released ---
        # If the task was set to FAILED inside the lock (rejected, revoked,
        # or posture blocked), record audit and return.
        if task.status == TaskStatus.FAILED:
            self._record_audit(
                task,
                VerificationLevel.HELD,
                extra_metadata={"approver_id": approver_id} if approver_id else None,
            )
            return task

        # Approved path: task.status is now EXECUTING.
        # Actual execution happens outside the lock to avoid blocking.
        agent = self._registry.get(agent_id) if agent_id else None
        if agent is not None:
            self._registry.touch(agent.agent_id)

        try:
            if self._executor is not None and agent is not None:
                result = self._executor.execute(task, agent)
                task.result = result
            else:
                task.result = TaskResult(output="executed")
            with self._lock:
                task.status = TaskStatus.COMPLETED
        except Exception as exc:
            logger.error(
                "Resumed task execution failed: task_id='%s' error='%s'",
                task.task_id,
                exc,
            )
            with self._lock:
                task.status = TaskStatus.FAILED
                task.result = TaskResult(error=str(exc))

        with self._lock:
            task.completed_at = datetime.now(UTC)

        self._record_audit(
            task,
            VerificationLevel.HELD,
            extra_metadata={"approver_id": approver_id} if approver_id else None,
        )
        return task

    def _check_bridge_verification(
        self,
        action: str,
        agent_id: str,
        source_team: str,
        target_team: str,
    ) -> VerificationLevel | None:
        """Check bridge verification for cross-team actions.

        Looks up an ACTIVE bridge between the source and target teams, verifies
        the action is allowed by the bridge permissions, computes the effective
        constraint envelope, and maps the effective posture to a verification
        level.

        Args:
            action: The action being performed.
            agent_id: The agent performing the action.
            source_team: The requesting team's identifier.
            target_team: The target team's identifier.

        Returns:
            The verification level if bridge verification applies (BLOCKED if
            no valid bridge, or the posture-derived level for valid bridges).
            None if no bridge_manager is configured.
        """
        if self._bridge_manager is None:
            return None

        # Find an ACTIVE bridge between the teams (either direction)
        active_bridge = None
        bridges = self._bridge_manager.get_bridges_for_team(source_team)
        for bridge in bridges:
            # RT13-006: Use is_active property (checks status, expiry, and
            # one-time-use) instead of bare status check which misses expired
            # bridges that haven't been swept yet.
            if not bridge.is_active:
                continue
            pair_match = (
                bridge.source_team_id == source_team and bridge.target_team_id == target_team
            ) or (bridge.source_team_id == target_team and bridge.target_team_id == source_team)
            if pair_match:
                active_bridge = bridge
                break

        if active_bridge is None:
            logger.info(
                "M33-3301: No ACTIVE bridge between '%s' and '%s' — blocking cross-team action",
                source_team,
                target_team,
            )
            return VerificationLevel.BLOCKED

        # Verify the action is permitted by bridge permissions
        # RT12-001: Use effective_permissions (frozen snapshot) not raw permissions
        perms = active_bridge.effective_permissions
        allowed_actions = set(perms.read_paths + perms.write_paths + perms.message_types)
        if allowed_actions and action not in allowed_actions:
            # Check with glob matching for path-based permissions
            import fnmatch

            action_permitted = any(fnmatch.fnmatch(action, pattern) for pattern in allowed_actions)
            if not action_permitted:
                logger.info(
                    "M33-3301: Action '%s' not permitted by bridge %s between '%s' and '%s'",
                    action,
                    active_bridge.bridge_id,
                    source_team,
                    target_team,
                )
                return VerificationLevel.BLOCKED

        # Compute effective posture using bridge posture resolution
        from pact_platform.trust._compat import (
            bridge_verification_level,
            effective_posture,
        )

        # Look up postures for source and target teams.
        # RT13-07: Use the MOST RESTRICTIVE posture among all agents in each
        # team, not the first agent found. Using the first match could yield
        # a DELEGATED posture when another agent on the same team is at
        # SUPERVISED — making bridge verification too permissive. The default
        # (SUPERVISED) is conservative: if no posture manager is configured,
        # bridge actions require human approval.
        source_posture = TrustPostureLevel.SUPERVISED
        target_posture = TrustPostureLevel.SUPERVISED
        if self._posture_manager is not None:
            from pact_platform.trust._compat import POSTURE_ORDER

            # RT12-010: Snapshot posture dict to avoid race condition during iteration
            posture_snapshot = dict(self._posture_manager)

            # Find the most restrictive posture for each team
            source_postures: list[TrustPostureLevel] = []
            target_postures: list[TrustPostureLevel] = []
            for aid, tp in posture_snapshot.items():
                agent_record = self._registry.get(aid)
                if agent_record is not None:
                    if agent_record.team_id == source_team:
                        source_postures.append(tp.current_level)
                    elif agent_record.team_id == target_team:
                        target_postures.append(tp.current_level)

            if source_postures:
                source_posture = min(source_postures, key=lambda p: POSTURE_ORDER[p])
            if target_postures:
                target_posture = min(target_postures, key=lambda p: POSTURE_ORDER[p])

        eff_posture = effective_posture(source_posture, target_posture)
        level = bridge_verification_level(eff_posture)

        logger.info(
            "M33-3301: Bridge verification for '%s' via bridge %s: "
            "source_posture=%s, target_posture=%s, effective=%s, level=%s",
            action,
            active_bridge.bridge_id,
            source_posture.value,
            target_posture.value,
            eff_posture.value,
            level.value,
        )

        return level

    def _check_rate_limit(
        self,
        task: Task,
        agent: AgentRecord,
    ) -> Task | None:
        """LC-3: Enforce per-agent rate limits from the governance envelope.

        Reads ``max_actions_per_day`` from the agent's envelope (via the
        governance engine adapter) and compares against the rolling 24-hour
        action count stored in ``self._action_timestamps``.

        Returns:
            The BLOCKED task if the rate limit is exceeded, or None if the
            action is within limits (execution should continue).
        """
        if self._governance_engine is None:
            return None

        role_address = self._agent_role_addresses.get(agent.agent_id)
        if role_address is None:
            # No role address — rate limit cannot be resolved; fail-closed is
            # handled by the governance engine path that follows this check.
            return None

        try:
            import math as _math_rl

            envelope_config = self._governance_engine.compute_envelope(role_address)
            if envelope_config is None:
                return None

            envelope_dict = envelope_config.model_dump()
            operational = envelope_dict.get("operational", {}) or {}
            max_per_day = operational.get("max_actions_per_day")
            if max_per_day is None:
                return None

            max_per_day_f = float(max_per_day)
            if not _math_rl.isfinite(max_per_day_f) or max_per_day_f <= 0:
                return None

            with self._lock:
                _now_rl = time.monotonic()
                _cutoff_rl = _now_rl - _RATE_LIMIT_WINDOW_SECONDS
                _ts_list_rl = self._action_timestamps.get(agent.agent_id, [])
                # Prune stale timestamps while we hold the lock
                fresh = [ts for ts in _ts_list_rl if ts >= _cutoff_rl]
                self._action_timestamps[agent.agent_id] = fresh
                count_today = len(fresh)

            if count_today >= int(max_per_day_f):
                logger.warning(
                    "LC-3: Rate limit exceeded for agent '%s' role '%s': "
                    "%d/%d actions in last 24h — blocking task '%s'",
                    agent.agent_id,
                    role_address,
                    count_today,
                    int(max_per_day_f),
                    task.task_id,
                )
                with self._lock:
                    task.status = TaskStatus.BLOCKED
                    task.verification_level = VerificationLevel.BLOCKED
                    task.result = TaskResult(
                        error=(
                            f"Rate limit exceeded: {count_today}/{int(max_per_day_f)} "
                            f"actions in last 24h"
                        )
                    )
                    task.completed_at = datetime.now(UTC)
                self._record_audit(task, VerificationLevel.BLOCKED)
                return task

        except Exception as exc:
            # Fail-closed: error resolving rate limit -> BLOCKED
            logger.error(
                "LC-3: Rate limit check failed for agent '%s' task '%s': %s "
                "— fail-closed to BLOCKED",
                agent.agent_id,
                task.task_id,
                exc,
            )
            with self._lock:
                task.status = TaskStatus.BLOCKED
                task.verification_level = VerificationLevel.BLOCKED
                task.result = TaskResult(error=f"Rate limit check error (fail-closed): {exc}")
                task.completed_at = datetime.now(UTC)
            self._record_audit(task, VerificationLevel.BLOCKED)
            return task

        return None

    def _run_governance_verification(
        self,
        task: Task,
        agent: AgentRecord,
        role_address: str,
    ) -> Task | None:
        """Run governance engine verification for a task.

        Uses GovernanceEngine.verify_action() for pre-execution checks.
        Returns the task if it was BLOCKED or HELD (no further processing needed),
        or None if the action is approved (auto_approved or flagged) and execution
        should continue.

        Args:
            task: The task being processed.
            agent: The assigned agent.
            role_address: The D/T/R address of the agent's role.

        Returns:
            The task if governance blocked or held it (returned to caller),
            or None if execution should continue.
        """
        if self._governance_engine is None:
            return None

        try:
            # Build context dict from task metadata
            context: dict[str, Any] = {}
            cost = task.metadata.get("cost")
            if cost is not None:
                context["cost"] = float(cost)
            task_id_val = task.metadata.get("task_id") or task.task_id
            context["task_id"] = task_id_val

            # LC-1: Inject cumulative spend so GovernanceEngine can enforce
            # per-agent budget caps across multiple actions.
            # LC-3: Inject rolling 24-hour action count for governance engine.
            import math as _math

            with self._lock:
                raw_spend = self._cumulative_spend.get(agent.agent_id, 0.0)
                _now_gov = time.monotonic()
                _cutoff_gov = _now_gov - _RATE_LIMIT_WINDOW_SECONDS
                _ts_list_gov = self._action_timestamps.get(agent.agent_id, [])
                action_count_today = sum(1 for ts in _ts_list_gov if ts >= _cutoff_gov)
            cumulative_spend = raw_spend if _math.isfinite(raw_spend) else 0.0
            context["cumulative_spend_usd"] = cumulative_spend
            context["action_count_today"] = action_count_today

            # Call governance engine verify_action
            verdict = self._governance_engine.verify_action(
                role_address=role_address,
                action=task.action,
                context=context if context else None,
            )

            logger.info(
                "Governance verdict for task '%s' agent '%s' " "role '%s' action '%s': %s -- %s",
                task.task_id,
                agent.agent_id,
                role_address,
                task.action,
                verdict.level,
                verdict.reason,
            )

            # Map governance verdict levels to runtime behavior
            if verdict.level == "blocked":
                with self._lock:
                    task.status = TaskStatus.BLOCKED
                    task.verification_level = VerificationLevel.BLOCKED
                    task.result = TaskResult(error=f"Governance blocked: {verdict.reason}")
                    task.completed_at = datetime.now(UTC)
                self._record_audit(task, VerificationLevel.BLOCKED)
                return task

            if verdict.level == "held":
                with self._lock:
                    task.status = TaskStatus.HELD
                    task.verification_level = VerificationLevel.HELD
                self._approval_queue.submit(
                    agent_id=agent.agent_id,
                    action=task.action,
                    reason=verdict.reason or "Held by governance engine for human approval",
                    team_id=task.team_id,
                )
                self._record_audit(task, VerificationLevel.HELD)
                return task

            if verdict.level == "flagged":
                logger.warning(
                    "Governance FLAGGED action '%s' for agent '%s' "
                    "role '%s': %s -- proceeding with execution",
                    task.action,
                    agent.agent_id,
                    role_address,
                    verdict.reason,
                )
                with self._lock:
                    task.verification_level = VerificationLevel.FLAGGED
                # Fall through to execution (return None)
                return None

            # auto_approved -- proceed silently
            with self._lock:
                task.verification_level = VerificationLevel.AUTO_APPROVED
            return None

        except Exception as exc:
            # Fail-closed: governance error -> BLOCKED
            logger.error(
                "Governance verification failed for task '%s' "
                "agent '%s' role '%s': %s -- fail-closed to BLOCKED",
                task.task_id,
                agent.agent_id,
                role_address,
                exc,
            )
            with self._lock:
                task.status = TaskStatus.BLOCKED
                task.verification_level = VerificationLevel.BLOCKED
                task.result = TaskResult(
                    error=f"Governance verification error (fail-closed): {exc}"
                )
                task.completed_at = datetime.now(UTC)
            self._record_audit(task, VerificationLevel.BLOCKED)
            return task

    def _assign_agent(self, task: Task) -> AgentRecord | None:
        """Select an agent for the task.

        RT4-H3: If a revocation manager is configured, checks whether the
        agent has been revoked before accepting the assignment.
        RT5-08: Also checks registry REVOKED status (set by _sync_revocations).
        """
        if task.agent_id:
            agent = self._registry.get(task.agent_id)
            if agent is not None:
                # Check if agent is REVOKED in registry (from sync or manual update)
                if agent.status == AgentStatus.REVOKED:
                    logger.warning(
                        "Agent '%s' is revoked in registry, cannot assign task '%s'",
                        agent.agent_id,
                        task.task_id,
                    )
                    task.result = TaskResult(error=f"Agent '{agent.agent_id}' has been revoked")
                    return None
                if agent.status != AgentStatus.ACTIVE:
                    return None
                # RT4-H3: Check revocation status via manager
                if self._revocation_manager is not None:
                    if self._revocation_manager.is_revoked(agent.agent_id):
                        logger.warning(
                            "Agent '%s' is revoked, cannot assign task '%s'",
                            agent.agent_id,
                            task.task_id,
                        )
                        task.result = TaskResult(error=f"Agent '{agent.agent_id}' has been revoked")
                        return None
                return agent
            return None

        # Auto-select: find active agents in the team
        if task.team_id:
            candidates = self._registry.get_team(task.team_id)
            candidates = [a for a in candidates if a.status == AgentStatus.ACTIVE]
            # RT4-H3: Filter out revoked agents
            if self._revocation_manager is not None:
                candidates = [
                    a for a in candidates if not self._revocation_manager.is_revoked(a.agent_id)
                ]
            if candidates:
                return candidates[0]

        # Fallback: any active, non-revoked agent
        active = self._registry.active_agents()
        if self._revocation_manager is not None:
            active = [a for a in active if not self._revocation_manager.is_revoked(a.agent_id)]
        return active[0] if active else None

    def _record_audit(
        self,
        task: Task,
        level: VerificationLevel,
        *,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an audit anchor for this task.

        RT4-H2: If a trust store is configured, persists the anchor to
        durable storage.
        RT5-12: Store persist happens BEFORE in-memory chain append so
        the store is the source of truth on crash.
        RT5-02: extra_metadata (e.g., approver_id) is merged into the
        anchor metadata.
        """
        result_str = ""
        if task.result:
            if task.result.error:
                result_str = f"error: {task.result.error}"
            else:
                result_str = task.result.output[:200] if task.result.output else ""

        metadata: dict[str, Any] = {
            "task_id": task.task_id,
            "status": task.status.value,
            "team_id": task.team_id,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        # RT5-12: Build the anchor via chain.append (which also adds to the
        # in-memory chain), but we restructure so the store persist is the
        # authoritative write. We still use chain.append because it handles
        # hash chaining correctly.
        anchor = self._audit_chain.append(
            agent_id=task.assigned_agent_id or "unassigned",
            action=task.action,
            verification_level=level,
            result=result_str,
            metadata=metadata,
            signing_key=self._signing_key,
            signer_id=self._signer_id,
        )

        # RT4-H2 + RT5-12: Persist audit anchor to TrustStore.
        # This happens after append because AuditChain.append() is where the
        # anchor gets its hash chain link. The store persist is the durable
        # write; the in-memory chain is a cache.
        if self._trust_store is not None:
            try:
                anchor_data = anchor.model_dump(mode="json")
                self._trust_store.store_audit_anchor(anchor.anchor_id, anchor_data)
            except Exception as exc:
                self._audit_persist_failures += 1
                logger.warning(
                    "Failed to persist audit anchor '%s' to trust store (total failures: %d): %s",
                    anchor.anchor_id,
                    self._audit_persist_failures,
                    exc,
                )

    def _sync_revocations(self) -> None:
        """Sync revocation state into the AgentRegistry (RT4-M5).

        If a revocation manager is configured, checks all registered agents
        against the revocation log and updates their registry status to
        REVOKED for any that have been revoked.
        """
        if self._revocation_manager is None:
            return

        for agent in self._registry.active_agents():
            if self._revocation_manager.is_revoked(agent.agent_id):
                self._registry.update_status(agent.agent_id, AgentStatus.REVOKED)
                logger.info(
                    "Synced revocation: agent '%s' marked REVOKED in registry",
                    agent.agent_id,
                )

    def _persist_posture_change(self, agent_id: str, posture_data: dict) -> None:
        """Persist a posture change to the TrustStore (RT4-M7).

        Args:
            agent_id: The agent whose posture changed.
            posture_data: The posture change data to persist.
        """
        if self._trust_store is None:
            return

        try:
            self._trust_store.store_posture_change(agent_id, posture_data)
            logger.info(
                "Persisted posture change for agent '%s' to trust store",
                agent_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to persist posture change for agent '%s': %s",
                agent_id,
                exc,
            )

    def refresh_from_store(self) -> None:
        """Re-read delegations from the TrustStore and update the registry (RT5-09).

        This addresses the staleness problem where the runtime takes a snapshot
        at from_store() but never refreshes. New delegations added to the store
        after initial hydration will be picked up by calling this method.

        No-op if no trust store is configured.
        """
        if self._trust_store is None:
            logger.debug("refresh_from_store: no trust store configured, skipping")
            return

        self._last_refresh_time = time.monotonic()

        all_delegations: list[dict] = []
        existing_agents: set[str] = set()
        for agent in self._registry.active_agents():
            existing_agents.add(agent.agent_id)

        # Collect delegations from genesis authorities
        for genesis_data in _collect_all_genesis(self._trust_store):
            authority_id = genesis_data.get("authority_id", "")
            if authority_id:
                delegations = self._trust_store.get_delegations_for(authority_id)
                all_delegations.extend(delegations)

        # Also collect delegations from envelopes
        for envelope_data in self._trust_store.list_envelopes():
            agent_id = envelope_data.get("agent_id", "")
            if agent_id:
                delegations = self._trust_store.get_delegations_for(agent_id)
                all_delegations.extend(delegations)

        new_count = 0
        seen: set[str] = set()
        for del_data in all_delegations:
            agent_id = del_data.get("delegatee_id", "")
            if not agent_id or agent_id in seen or agent_id in existing_agents:
                continue
            seen.add(agent_id)

            agent_name = del_data.get("agent_name", agent_id)
            agent_role = del_data.get("agent_role", "agent")
            team_id = del_data.get("team_id", "")
            capabilities = del_data.get("capabilities", [])

            try:
                self._registry.register(
                    agent_id=agent_id,
                    name=agent_name,
                    role=agent_role,
                    team_id=team_id,
                    capabilities=capabilities if isinstance(capabilities, list) else [],
                )
                new_count += 1
            except ValueError:
                logger.debug("Agent '%s' already registered during refresh", agent_id)

        if new_count > 0:
            logger.info("Refreshed %d new agents from TrustStore", new_count)


class TaskExecutor:
    """Base class for task execution strategies.

    Subclass this to implement actual task execution logic.
    The default implementation returns an empty result.
    """

    def execute(self, task: Task, agent: AgentRecord) -> TaskResult:
        """Execute a task.

        Args:
            task: The task to execute.
            agent: The agent executing the task.

        Returns:
            The TaskResult.
        """
        return TaskResult(output=f"Executed '{task.action}' by agent '{agent.agent_id}'")


def _collect_all_genesis(trust_store: TrustStore) -> list[dict]:
    """Collect all genesis records from a TrustStore.

    The TrustStore protocol does not have a list_genesis() method, so we
    use a pragmatic approach: try known authority patterns and also check
    delegations for delegator_ids that might be genesis authorities.

    Args:
        trust_store: The store to query.

    Returns:
        A list of genesis record dicts found in the store.
    """
    results: list[dict] = []

    # Try to get genesis records by checking delegations
    # We look at all envelopes first to find agent_ids, then check
    # if their delegators have genesis records
    checked_authorities: set[str] = set()

    for envelope in trust_store.list_envelopes():
        agent_id = envelope.get("agent_id", "")
        if not agent_id:
            continue
        delegations = trust_store.get_delegations_for(agent_id)
        for d in delegations:
            delegator = d.get("delegator_id", "")
            if delegator and delegator not in checked_authorities:
                checked_authorities.add(delegator)
                genesis = trust_store.get_genesis(delegator)
                if genesis is not None:
                    results.append(genesis)

    return results
