# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""DMTeamRunner — orchestrator for the Digital Media team vertical.

Wires the DM team configuration (5 agents, 5 envelopes, verification gradient)
into a runnable execution pipeline using KaizenBridge components.

Features:
- Capability-based task routing (keyword matching to agent capabilities)
- Verification gradient classification (AUTO_APPROVED, FLAGGED, HELD, BLOCKED)
- StubBackend by default (dry-run mode) with optional real LLM switching
- ShadowEnforcerLive integration for agreement/divergence tracking
- Shadow calibration for baseline metrics
- Approval queue for HELD actions
- Task lifecycle tracking with audit trail
- Per-agent statistics

Usage:
    runner = DMTeamRunner()  # Dry-run mode with StubBackend
    result = runner.submit_task("Draft a post about EATP", target_agent="dm-content-creator")
    print(result.output)  # StubBackend response

    # Enable real LLM for one agent:
    runner.enable_real_llm(
        agent_id="dm-content-creator",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_budget_usd=1.00,
    )
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from pact_platform.build.config.schema import ConstraintEnvelopeConfig, VerificationLevel
from pact_platform.examples.foundation.dm_prompts import get_system_prompt
from pact_platform.examples.foundation.dm_team import (
    DM_ANALYTICS_ENVELOPE,
    DM_COMMUNITY_ENVELOPE,
    DM_CONTENT_ENVELOPE,
    DM_LEAD_ENVELOPE,
    DM_SEO_ENVELOPE,
    DM_VERIFICATION_GRADIENT,
    get_dm_team_config,
)
from pact_platform.trust.shadow_enforcer import ShadowEnforcer
from pact_platform.trust.shadow_enforcer_live import (
    ShadowEnforcerLive,
)  # restored with corrected imports
from pact_platform.use.execution.approval import ApprovalQueue
from pact_platform.use.execution.lifecycle import TaskLifecycle, TaskLifecycleState
from pact_platform.use.execution.llm_backend import (
    BackendRouter,
    LLMProvider,
    LLMRequest,
    StubBackend,
)
from pact_platform.use.execution.registry import AgentRecord, AgentRegistry
from pact_platform.use.execution.runtime import TaskResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Capability-to-agent routing table
# ---------------------------------------------------------------------------

# Each entry maps a set of keywords to an agent ID. The first matching
# keyword set wins. Order matters: more specific matches before general ones.
# Governance keywords that ALWAYS route to team lead regardless of other matches.
# These represent actions that require team lead authority (approval, scheduling,
# coordination, review). Checked before specialist routing.
_TEAM_LEAD_GOVERNANCE_KEYWORDS: list[str] = [
    "approve_publication",
    "approve",
    "schedule_content",
    "schedule the content",
    "schedule content calendar",
    "coordinate_team",
    "coordinate",
    "review_content",
    "review the content",
    "draft_strategy",
]

# Specialist routing rules: checked after governance keywords.
# Order: analytics -> community -> SEO -> content creator.
_SPECIALIST_ROUTING_RULES: list[tuple[list[str], str]] = [
    # Analytics Agent
    (
        [
            "read_metrics",
            "read metrics",
            "generate_report",
            "generate report",
            "track_engagement",
            "track engagement",
            "analyze_trends",
            "analyze trends",
            "engagement metrics",
            "performance report",
        ],
        "dm-analytics",
    ),
    # Community Manager (before content creator — "draft a response" is specific)
    (
        [
            "draft_response",
            "draft response",
            "draft a response",
            "moderate_content",
            "moderate",
            "track_community",
            "community question",
            "community feedback",
            "flag_issues",
        ],
        "dm-community-manager",
    ),
    # SEO Specialist
    (
        [
            "analyze_keywords",
            "analyze keywords",
            "suggest_structure",
            "audit_seo",
            "check seo",
            "seo",
            "research_topics",
            "keyword",
        ],
        "dm-seo-specialist",
    ),
    # Content Creator (broad "draft" matching — after community to avoid stealing
    # "draft a response"; catches "draft a post", "draft a blog", "draft a tweet")
    (
        [
            "draft_post",
            "draft a post",
            "draft post",
            "edit_content",
            "suggest_hashtags",
            "draft a blog",
            "draft a tweet",
            "draft a linkedin",
            "blog post",
            "blog article",
        ],
        "dm-content-creator",
    ),
]


# ---------------------------------------------------------------------------
# Synthetic actions for shadow calibration
# ---------------------------------------------------------------------------

_CALIBRATION_ACTIONS: list[dict[str, str]] = [
    # AUTO_APPROVED actions (read_*, draft_*, analyze_*)
    {"agent_id": "dm-team-lead", "action": "draft_strategy"},
    {"agent_id": "dm-team-lead", "action": "draft_strategy"},
    {"agent_id": "dm-team-lead", "action": "analyze_metrics"},
    {"agent_id": "dm-team-lead", "action": "analyze_metrics"},
    {"agent_id": "dm-team-lead", "action": "analyze_metrics"},
    {"agent_id": "dm-content-creator", "action": "draft_post"},
    {"agent_id": "dm-content-creator", "action": "draft_post"},
    {"agent_id": "dm-content-creator", "action": "draft_post"},
    {"agent_id": "dm-content-creator", "action": "draft_post"},
    {"agent_id": "dm-content-creator", "action": "draft_post"},
    {"agent_id": "dm-analytics", "action": "read_metrics"},
    {"agent_id": "dm-analytics", "action": "read_metrics"},
    {"agent_id": "dm-analytics", "action": "read_metrics"},
    {"agent_id": "dm-analytics", "action": "analyze_trends"},
    {"agent_id": "dm-analytics", "action": "analyze_trends"},
    {"agent_id": "dm-community-manager", "action": "draft_response"},
    {"agent_id": "dm-community-manager", "action": "draft_response"},
    {"agent_id": "dm-community-manager", "action": "draft_response"},
    {"agent_id": "dm-seo-specialist", "action": "analyze_keywords"},
    {"agent_id": "dm-seo-specialist", "action": "analyze_keywords"},
    {"agent_id": "dm-seo-specialist", "action": "analyze_keywords"},
    {"agent_id": "dm-seo-specialist", "action": "analyze_keywords"},
    # FLAGGED actions (no gradient pattern match -> default FLAGGED)
    {"agent_id": "dm-team-lead", "action": "schedule_content"},
    {"agent_id": "dm-team-lead", "action": "coordinate_team"},
    {"agent_id": "dm-team-lead", "action": "review_content"},
    {"agent_id": "dm-community-manager", "action": "moderate_content"},
    {"agent_id": "dm-community-manager", "action": "flag_issues"},
    {"agent_id": "dm-seo-specialist", "action": "suggest_structure"},
    {"agent_id": "dm-content-creator", "action": "suggest_hashtags"},
    {"agent_id": "dm-content-creator", "action": "edit_content"},
    # HELD actions (approve_* pattern)
    {"agent_id": "dm-team-lead", "action": "approve_publication"},
    {"agent_id": "dm-team-lead", "action": "approve_publication"},
    {"agent_id": "dm-team-lead", "action": "approve_publication"},
    # BLOCKED actions (delete_*, modify_constraints)
    {"agent_id": "dm-content-creator", "action": "delete_old_posts"},
    {"agent_id": "dm-analytics", "action": "delete_analytics_data"},
    {"agent_id": "dm-team-lead", "action": "modify_constraints"},
    {"agent_id": "dm-seo-specialist", "action": "delete_old_posts"},
    {"agent_id": "dm-community-manager", "action": "delete_old_posts"},
]


class _GovernanceVerdict:
    """Minimal verdict object for demo governance engine."""

    def __init__(self, level: str) -> None:
        self.level = level
        self.audit_details: dict = {}


class _DemoGovernanceEngine:
    """Minimal GovernanceEngine for demo/example use.

    Applies DM_VERIFICATION_GRADIENT rules to classify actions without
    requiring a full pact.governance.GovernanceEngine instance.
    """

    def __init__(self, gradient: object) -> None:
        self._gradient = gradient

    def verify_action(
        self,
        role_address: str,
        action: str,
        context: dict | None = None,
    ) -> _GovernanceVerdict:
        import fnmatch

        for rule in self._gradient.rules:
            if fnmatch.fnmatch(action, rule.pattern):
                return _GovernanceVerdict(rule.level.value.lower())
        return _GovernanceVerdict(self._gradient.default_level.value.lower())


class DMTeamRunner:
    """Orchestrator for the Digital Media team execution pipeline.

    Wires DM team config (agents, envelopes, gradient) with a LLM backend
    (StubBackend by default), approval queue, and shadow enforcement.

    The runner is the single entry point for DM task execution:
    1. Route task to the appropriate agent (by keyword or explicit target)
    2. Extract the action from the task description
    3. Evaluate through the constraint envelope and gradient
    4. Execute via LLM backend (if AUTO_APPROVED or FLAGGED)
    5. Queue for approval (if HELD)
    6. Reject (if BLOCKED)
    7. Record shadow comparison for posture upgrade evidence
    """

    def __init__(self) -> None:
        config = get_dm_team_config()

        # Agent registry
        self._registry = AgentRegistry()
        self._agent_configs = {}
        for agent in config["agents"]:
            self._registry.register(
                agent_id=agent.id,
                name=agent.name,
                role=agent.role,
                team_id="dm-team",
                capabilities=agent.capabilities,
                posture=agent.initial_posture.value,
            )
            self._agent_configs[agent.id] = agent

        # Constraint envelope configs (agent_id -> ConstraintEnvelopeConfig)
        _envelope_config_map = {
            "dm-team-lead": DM_LEAD_ENVELOPE,
            "dm-content-creator": DM_CONTENT_ENVELOPE,
            "dm-analytics": DM_ANALYTICS_ENVELOPE,
            "dm-community-manager": DM_COMMUNITY_ENVELOPE,
            "dm-seo-specialist": DM_SEO_ENVELOPE,
        }
        self._envelope_configs: dict[str, ConstraintEnvelopeConfig] = dict(_envelope_config_map)

        # Approval queue
        self._approval_queue = ApprovalQueue()

        # LLM backend (StubBackend by default)
        self._stub_backend = StubBackend(
            response_content="[DM Agent Response] Task completed successfully."
        )
        self._backend_router = BackendRouter()
        self._backend_router.register_backend(self._stub_backend)
        self._is_dry_run = True

        # Per-agent backend overrides (agent_id -> LLMProvider)
        self._agent_backend_overrides: dict[str, LLMProvider] = {}
        # Per-agent budget limits (agent_id -> max_budget_usd)
        self._agent_budgets: dict[str, float] = {}

        # Shadow enforcer (per-agent, for calibration)
        _mock_engine = _DemoGovernanceEngine(DM_VERIFICATION_GRADIENT)
        self._shadow_enforcers: dict[str, ShadowEnforcer] = {
            agent_id: ShadowEnforcer(
                governance_engine=_mock_engine,
                role_address="D1-R1",
            )
            for agent_id in self._envelope_configs
        }

        # Live shadow enforcer (M24: agreement/divergence tracking)
        self._shadow_enforcer_live = ShadowEnforcerLive(enabled=True)

        # Task statistics (agent_id -> stats dict)
        self._task_stats: dict[str, dict] = {
            agent_id: {
                "tasks_submitted": 0,
                "tasks_completed": 0,
                "tasks_held": 0,
                "tasks_blocked": 0,
            }
            for agent_id in self._envelope_configs
        }

        # Task results store (task_id -> TaskResult)
        self._task_results: dict[str, TaskResult] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_dry_run(self) -> bool:
        """Whether the runner is using StubBackend (dry-run mode)."""
        return self._is_dry_run

    @property
    def registered_agents(self) -> list[str]:
        """List of registered agent IDs."""
        return list(self._envelope_configs.keys())

    @property
    def approval_queue(self) -> ApprovalQueue:
        """The approval queue for HELD actions."""
        return self._approval_queue

    @property
    def envelopes(self) -> dict[str, ConstraintEnvelopeConfig]:
        """Constraint envelope configs indexed by agent ID."""
        return dict(self._envelope_configs)

    @property
    def shadow_enforcer_live(self) -> ShadowEnforcerLive:
        """The live shadow enforcer for agreement/divergence tracking."""
        return self._shadow_enforcer_live

    @property
    def supported_providers(self) -> list[str]:
        """List of supported LLM provider names."""
        return [p.value for p in LLMProvider]

    # ------------------------------------------------------------------
    # Task Routing (5051)
    # ------------------------------------------------------------------

    def route_task(self, description: str) -> str:
        """Route a task description to the most appropriate agent.

        Two-pass routing:
        1. Check governance keywords first (approve, schedule, coordinate,
           review). These always route to team lead.
        2. Check specialist routing rules (analytics, community, SEO,
           content creator).
        3. Ambiguous tasks with no match go to team lead.

        Args:
            description: The task description text.

        Returns:
            The agent_id of the best-matched agent.
        """
        desc_lower = description.lower()

        # Pass 1: Governance keywords always route to team lead
        for keyword in _TEAM_LEAD_GOVERNANCE_KEYWORDS:
            if keyword.lower() in desc_lower:
                return "dm-team-lead"

        # Pass 2: Specialist routing rules
        for keywords, agent_id in _SPECIALIST_ROUTING_RULES:
            for keyword in keywords:
                if keyword.lower() in desc_lower:
                    return agent_id

        # No match -> team lead handles ambiguous tasks
        return "dm-team-lead"

    # ------------------------------------------------------------------
    # Task Submission (5049)
    # ------------------------------------------------------------------

    def submit_task(
        self,
        description: str,
        target_agent: str | None = None,
    ) -> TaskResult:
        """Submit a task for execution through the DM governance pipeline.

        Args:
            description: The task description. The first token matching
                an action pattern (e.g., ``draft_post``, ``read_metrics``)
                is used as the action for gradient classification.
            target_agent: Explicit agent to route to. If None, auto-routes
                by keyword matching.

        Returns:
            TaskResult with output (success), error (blocked/held), and
            metadata including verification_level, lifecycle audit trail,
            and routing information.
        """
        if not description or not description.strip():
            return TaskResult(
                error="Task description cannot be empty",
                metadata={"error_type": "validation"},
            )

        # Determine target agent
        if target_agent is not None:
            if target_agent not in self._envelope_configs:
                return TaskResult(
                    error=(
                        f"Agent '{target_agent}' is not registered in the DM team. "
                        f"Available agents: {list(self._envelope_configs.keys())}"
                    ),
                    metadata={"error_type": "not_found"},
                )
            agent_id = target_agent
        else:
            agent_id = self.route_task(description)

        # Extract action from description
        action = self._extract_action(description, agent_id)

        # Create lifecycle tracker
        task_id = f"dm-task-{uuid.uuid4().hex[:12]}"
        lifecycle = TaskLifecycle(
            task_id=task_id,
            agent_id=agent_id,
            action=action,
        )

        # Classify through shadow enforcer (uses DM gradient rules)
        lifecycle.transition_to(TaskLifecycleState.VERIFYING)
        shadow_classify = self._shadow_enforcers[agent_id].evaluate(action, agent_id)
        verification_level = shadow_classify.verification_level

        # shadow_classify is reused as shadow_result for live comparison
        shadow_result = shadow_classify

        # Build metadata
        metadata: dict = {
            "task_id": task_id,
            "verification_level": verification_level.value,
            "routed_to": agent_id,
            "action": action,
        }

        # Track stats
        self._task_stats[agent_id]["tasks_submitted"] += 1

        # Route based on verification level
        if verification_level == VerificationLevel.BLOCKED:
            lifecycle.transition_to(
                TaskLifecycleState.REJECTED,
                reason=f"Action '{action}' is BLOCKED by constraint envelope",
            )
            metadata["lifecycle"] = lifecycle.to_audit_record()
            self._task_stats[agent_id]["tasks_blocked"] += 1

            # Record live shadow comparison
            self._shadow_enforcer_live.record(
                action=action,
                agent_id=agent_id,
                real_decision=VerificationLevel.BLOCKED,
                shadow_decision=shadow_result.verification_level,
            )

            result = TaskResult(
                error=f"Action '{action}' is BLOCKED by constraint envelope -- cannot execute",
                metadata=metadata,
            )
            self._task_results[task_id] = result
            return result

        if verification_level == VerificationLevel.HELD:
            lifecycle.transition_to(
                TaskLifecycleState.HELD,
                reason=f"Action '{action}' queued for human approval",
            )
            metadata["lifecycle"] = lifecycle.to_audit_record()
            metadata["held"] = True
            self._task_stats[agent_id]["tasks_held"] += 1

            # Submit to approval queue
            self._approval_queue.submit(
                agent_id=agent_id,
                action=action,
                reason=f"Action '{action}' requires human approval (verification level: HELD)",
                team_id="dm-team",
            )

            # Record live shadow comparison
            self._shadow_enforcer_live.record(
                action=action,
                agent_id=agent_id,
                real_decision=VerificationLevel.HELD,
                shadow_decision=shadow_result.verification_level,
            )

            result = TaskResult(
                error=f"Action '{action}' is HELD -- awaiting human approval",
                metadata=metadata,
            )
            self._task_results[task_id] = result
            return result

        # AUTO_APPROVED or FLAGGED: execute via LLM backend
        lifecycle.transition_to(
            TaskLifecycleState.EXECUTING,
            reason=f"Verification level: {verification_level.value}",
        )

        try:
            system_prompt = get_system_prompt(agent_id)
            llm_request = LLMRequest(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (f"--- BEGIN TASK ---\n{description}\n--- END TASK ---"),
                    },
                ],
            )

            # Route to the appropriate backend
            preferred = self._agent_backend_overrides.get(agent_id)
            llm_response = self._backend_router.route(llm_request, preferred=preferred)

            lifecycle.transition_to(
                TaskLifecycleState.COMPLETED,
                reason="LLM execution completed",
            )
            metadata["lifecycle"] = lifecycle.to_audit_record()
            metadata["llm_provider"] = llm_response.provider
            metadata["llm_model"] = llm_response.model
            self._task_stats[agent_id]["tasks_completed"] += 1

            # Record live shadow comparison
            self._shadow_enforcer_live.record(
                action=action,
                agent_id=agent_id,
                real_decision=verification_level,
                shadow_decision=shadow_result.verification_level,
            )

            result = TaskResult(
                output=llm_response.content,
                metadata=metadata,
            )
            self._task_results[task_id] = result
            return result

        except Exception as exc:
            lifecycle.transition_to(
                TaskLifecycleState.FAILED,
                reason=f"LLM execution failed: {exc}",
            )
            metadata["lifecycle"] = lifecycle.to_audit_record()
            logger.error("DMTeamRunner execution failed: %s", exc)
            result = TaskResult(
                error=f"Execution failed: {exc}",
                metadata=metadata,
            )
            self._task_results[task_id] = result
            return result

    # ------------------------------------------------------------------
    # Task Result Lookup
    # ------------------------------------------------------------------

    def get_task_result(self, task_id: str) -> TaskResult | None:
        """Get the result of a previously submitted task.

        Args:
            task_id: The task identifier returned from submit_task.

        Returns:
            The TaskResult, or None if the task_id is not found.
        """
        return self._task_results.get(task_id)

    # ------------------------------------------------------------------
    # Agent Information
    # ------------------------------------------------------------------

    def get_agent_record(self, agent_id: str) -> AgentRecord | None:
        """Get the registry record for an agent.

        Args:
            agent_id: The agent identifier.

        Returns:
            The AgentRecord, or None if not found.
        """
        return self._registry.get(agent_id)

    def get_agent_stats(self) -> dict[str, dict]:
        """Get task statistics for all agents.

        Returns:
            Dictionary mapping agent_id to stats dict with keys:
            tasks_submitted, tasks_completed, tasks_held, tasks_blocked.
        """
        return dict(self._task_stats)

    # ------------------------------------------------------------------
    # Shadow Calibration (5053)
    # ------------------------------------------------------------------

    def run_shadow_calibration(self) -> dict[str, dict]:
        """Run shadow calibration with synthetic DM actions.

        Feeds the predefined calibration action set through each agent's
        ShadowEnforcer to generate baseline metrics.

        Returns:
            Dictionary mapping agent_id to metrics dict with keys:
            total_evaluations, auto_approved_count, flagged_count,
            held_count, blocked_count, pass_rate.
        """
        fixed_time = datetime(2026, 3, 14, 12, 0, 0, tzinfo=UTC)

        for action_item in _CALIBRATION_ACTIONS:
            agent_id = action_item["agent_id"]
            action = action_item["action"]
            enforcer = self._shadow_enforcers[agent_id]
            enforcer.evaluate(action, agent_id, current_time=fixed_time)

        # Collect metrics
        results: dict[str, dict] = {}
        for agent_id, enforcer in self._shadow_enforcers.items():
            try:
                metrics = enforcer.get_metrics(agent_id)
                results[agent_id] = {
                    "total_evaluations": metrics.total_evaluations,
                    "auto_approved_count": metrics.auto_approved_count,
                    "flagged_count": metrics.flagged_count,
                    "held_count": metrics.held_count,
                    "blocked_count": metrics.blocked_count,
                    "pass_rate": metrics.pass_rate,
                }
            except KeyError:
                results[agent_id] = {
                    "total_evaluations": 0,
                    "auto_approved_count": 0,
                    "flagged_count": 0,
                    "held_count": 0,
                    "blocked_count": 0,
                    "pass_rate": 0.0,
                }

        return results

    # ------------------------------------------------------------------
    # Posture Upgrade Recommendation (5055)
    # ------------------------------------------------------------------

    def get_upgrade_recommendation(self, agent_id: str) -> dict:
        """Generate a posture upgrade recommendation for an agent.

        Uses the shadow enforcer's metrics and report generation to
        determine whether an agent is eligible for a posture upgrade.

        Args:
            agent_id: The agent to evaluate.

        Returns:
            Dictionary with recommendation details.

        Raises:
            KeyError: If agent_id is not a recognized DM team agent or
                has no shadow evaluation data.
        """
        if agent_id not in self._shadow_enforcers:
            raise KeyError(
                f"Agent '{agent_id}' is not a recognized DM team agent. "
                f"Available agents: {list(self._shadow_enforcers.keys())}"
            )

        enforcer = self._shadow_enforcers[agent_id]
        report = enforcer.generate_report(agent_id)

        return {
            "agent_id": report.agent_id,
            "eligible": report.upgrade_eligible,
            "recommendation": report.recommendation,
            "pass_rate": report.pass_rate,
            "total_evaluations": report.total_evaluations,
            "blocked_count": (
                report.total_evaluations
                - int(
                    report.total_evaluations
                    * (report.pass_rate + (report.hold_rate) + (report.flag_rate))
                )
                if report.total_evaluations > 0
                else 0
            ),
            "blockers": list(report.upgrade_blockers),
        }

    # ------------------------------------------------------------------
    # Real LLM Backend (5060)
    # ------------------------------------------------------------------

    def enable_real_llm(
        self,
        agent_id: str,
        provider: str,
        model: str,
        api_key: str,
        max_budget_usd: float,
    ) -> None:
        """Switch an agent from StubBackend to a real LLM provider.

        Args:
            agent_id: The agent to switch.
            provider: LLM provider name (e.g., "anthropic", "openai").
            model: Model identifier (e.g., "claude-sonnet-4-20250514").
            api_key: API key for the provider. Must not be empty.
            max_budget_usd: Maximum budget in USD. Must be positive.

        Raises:
            ValueError: If api_key is empty, budget is non-positive,
                agent is not registered, or provider is unsupported.
        """
        if not api_key:
            raise ValueError(
                "api_key must be a non-empty string when enabling real LLM. "
                "Set the appropriate environment variable (e.g., ANTHROPIC_API_KEY)."
            )

        if max_budget_usd <= 0:
            raise ValueError(
                f"max_budget_usd must be positive, got {max_budget_usd}. "
                "A budget limit is required for cost control."
            )

        if agent_id not in self._envelope_configs:
            raise ValueError(
                f"Agent '{agent_id}' is not registered in the DM team. "
                f"Available agents: {list(self._envelope_configs.keys())}"
            )

        # Validate provider
        try:
            llm_provider = LLMProvider(provider)
        except ValueError:
            raise ValueError(
                f"Unsupported LLM provider '{provider}'. "
                f"Supported providers: {[p.value for p in LLMProvider]}"
            ) from None

        # Create and register the real backend
        # For now, we store the configuration. Actual backend creation
        # happens when the provider SDK is available.
        self._agent_backend_overrides[agent_id] = llm_provider
        self._agent_budgets[agent_id] = max_budget_usd
        self._is_dry_run = False

        logger.info(
            "Enabled real LLM for agent '%s': provider=%s, model=%s, budget=$%.2f",
            agent_id,
            provider,
            model,
            max_budget_usd,
        )

    def get_agent_backend(self, agent_id: str) -> str:
        """Get the backend type for an agent.

        Returns:
            "stub" if using StubBackend, or the provider name if using a real backend.
        """
        if agent_id in self._agent_backend_overrides:
            return self._agent_backend_overrides[agent_id].value
        return "stub"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _extract_action(self, description: str, agent_id: str) -> str:
        """Extract the action identifier from a task description.

        Looks for known action patterns (e.g., draft_post, read_metrics)
        in the description. Falls back to the first capability of the agent
        if no pattern is found.

        Args:
            description: The task description text.
            agent_id: The target agent (for fallback capability lookup).

        Returns:
            The action string for gradient classification.
        """
        desc_lower = description.lower()

        # Known action patterns (underscore form)
        known_actions = [
            "draft_post",
            "draft_strategy",
            "draft_response",
            "edit_content",
            "research_topic",
            "suggest_hashtags",
            "read_metrics",
            "generate_report",
            "track_engagement",
            "analyze_trends",
            "moderate_content",
            "track_community",
            "flag_issues",
            "analyze_keywords",
            "suggest_structure",
            "audit_seo",
            "research_topics",
            "review_content",
            "approve_publication",
            "coordinate_team",
            "schedule_content",
            "analyze_metrics",
            "delete_old_posts",
            "delete_analytics_data",
            "modify_constraints",
            "publish_externally",
            "publish_linkedin_post",
            "publish_blog_article",
            "external_email",
            "external_outreach",
        ]

        for action in known_actions:
            if action in desc_lower:
                return action

        # Try to match "verb_noun" patterns in the description
        # e.g. "Draft a post" -> match draft_post via the agent's capabilities
        agent_config = self._agent_configs.get(agent_id)
        if agent_config:
            for cap in agent_config.capabilities:
                # Check if the description contains the capability words
                parts = cap.split("_")
                if all(part in desc_lower for part in parts):
                    return cap

        # Fallback: first capability of the agent
        if agent_config and agent_config.capabilities:
            return agent_config.capabilities[0]

        return description.strip()[:50]
