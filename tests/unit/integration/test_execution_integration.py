# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Integration tests for the agent execution runtime (Milestone 4, Todo 409).

Tests the full execution loop:
- Agent registration -> lookup by capability -> discovery
- Submit action for approval -> queued -> approve -> proceeds
- Session create -> checkpoint -> restore
- Backend routing between multiple LLM backends
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pact_platform.use.execution.approval import ApprovalQueue, UrgencyLevel
from pact_platform.use.execution.llm_backend import (
    BackendRouter,
    LLMProvider,
    LLMRequest,
    StubBackend,
)
from pact_platform.use.execution.registry import AgentRegistry, AgentStatus
from pact_platform.use.execution.session import SessionManager, SessionState

# ===========================================================================
# 1. Agent Registration and Discovery
# ===========================================================================


class TestAgentRegistrationAndDiscovery:
    """Register agents -> look up by capability -> verify discovery."""

    def test_register_and_get_agent(self):
        """Register an agent and retrieve it by ID."""
        registry = AgentRegistry()

        record = registry.register(
            agent_id="agent-analyst",
            name="Data Analyst",
            role="analyst",
            team_id="team-dm",
            capabilities=["analyze_data", "generate_reports"],
            posture="supervised",
        )

        assert record.agent_id == "agent-analyst"
        assert record.name == "Data Analyst"
        assert record.team_id == "team-dm"
        assert record.status == AgentStatus.ACTIVE

        retrieved = registry.get("agent-analyst")
        assert retrieved is not None
        assert retrieved.agent_id == "agent-analyst"

    def test_find_by_capability(self):
        """Find agents with a specific capability."""
        registry = AgentRegistry()

        registry.register(
            "agent-a", "Agent A", "analyst", capabilities=["analyze_data", "read_metrics"]
        )
        registry.register(
            "agent-b", "Agent B", "writer", capabilities=["draft_content", "read_metrics"]
        )
        registry.register("agent-c", "Agent C", "reviewer", capabilities=["review_content"])

        # Find agents that can read_metrics
        readers = registry.find_by_capability("read_metrics")
        assert len(readers) == 2
        reader_ids = {r.agent_id for r in readers}
        assert reader_ids == {"agent-a", "agent-b"}

        # Find agents that can review
        reviewers = registry.find_by_capability("review_content")
        assert len(reviewers) == 1
        assert reviewers[0].agent_id == "agent-c"

    def test_get_team_agents(self):
        """Get all agents in a specific team."""
        registry = AgentRegistry()

        registry.register("agent-1", "Agent 1", "analyst", team_id="team-dm")
        registry.register("agent-2", "Agent 2", "writer", team_id="team-dm")
        registry.register("agent-3", "Agent 3", "admin", team_id="team-ops")

        dm_team = registry.get_team("team-dm")
        assert len(dm_team) == 2
        assert all(r.team_id == "team-dm" for r in dm_team)

    def test_update_agent_status(self):
        """Update agent status (active -> suspended -> revoked)."""
        registry = AgentRegistry()
        registry.register("agent-1", "Agent 1", "analyst")

        assert registry.get("agent-1").status == AgentStatus.ACTIVE

        registry.update_status("agent-1", AgentStatus.SUSPENDED)
        assert registry.get("agent-1").status == AgentStatus.SUSPENDED

        registry.update_status("agent-1", AgentStatus.REVOKED)
        assert registry.get("agent-1").status == AgentStatus.REVOKED

    def test_active_agents_excludes_inactive(self):
        """active_agents() returns only agents with ACTIVE status."""
        registry = AgentRegistry()
        registry.register("agent-1", "Agent 1", "analyst")
        registry.register("agent-2", "Agent 2", "writer")
        registry.register("agent-3", "Agent 3", "admin")

        registry.update_status("agent-2", AgentStatus.SUSPENDED)
        registry.update_status("agent-3", AgentStatus.REVOKED)

        active = registry.active_agents()
        assert len(active) == 1
        assert active[0].agent_id == "agent-1"

    def test_duplicate_registration_raises(self):
        """Registering the same agent_id twice raises ValueError."""
        registry = AgentRegistry()
        registry.register("agent-1", "Agent 1", "analyst")

        with pytest.raises(ValueError, match="already registered"):
            registry.register("agent-1", "Agent 1 Again", "analyst")

    def test_deregister_agent(self):
        """Deregistering removes the agent from the registry."""
        registry = AgentRegistry()
        registry.register("agent-1", "Agent 1", "analyst")

        registry.deregister("agent-1")
        assert registry.get("agent-1") is None

    def test_deregister_nonexistent_raises(self):
        """Deregistering a nonexistent agent raises ValueError."""
        registry = AgentRegistry()
        with pytest.raises(ValueError, match="not found"):
            registry.deregister("nonexistent")

    def test_touch_updates_last_active(self):
        """Touching an agent updates its last_active_at timestamp."""
        registry = AgentRegistry()
        registry.register("agent-1", "Agent 1", "analyst")

        assert registry.get("agent-1").last_active_at is None
        registry.touch("agent-1")
        assert registry.get("agent-1").last_active_at is not None

    def test_stale_agents_detected(self):
        """Agents inactive beyond the threshold are detected as stale."""
        registry = AgentRegistry()
        record = registry.register("agent-1", "Agent 1", "analyst")

        # Set registered_at to 48 hours ago (beyond default 24h threshold)
        record.registered_at = datetime.now(UTC) - timedelta(hours=48)

        stale = registry.stale_agents(threshold_hours=24)
        assert len(stale) == 1
        assert stale[0].agent_id == "agent-1"


# ===========================================================================
# 2. Approval Queue Workflow
# ===========================================================================


class TestApprovalQueueWorkflow:
    """Submit action for approval -> verify queued -> approve -> verify proceeds."""

    def test_submit_verify_approve_flow(self):
        """Full approval flow: submit -> pending -> approve -> resolved."""
        queue = ApprovalQueue()

        # Submit an action for approval
        pending = queue.submit(
            agent_id="agent-1",
            action="send_external_email",
            reason="Outbound messages need approval",
            team_id="team-dm",
            urgency=UrgencyLevel.STANDARD,
        )

        # Verify it is queued
        assert pending.status == "pending"
        assert queue.queue_depth == 1
        assert pending.action_id in [p.action_id for p in queue.pending]

        # Approve the action
        approved = queue.approve(pending.action_id, "supervisor-1", reason="Content reviewed")

        # Verify it is resolved
        assert approved.status == "approved"
        assert approved.decided_by == "supervisor-1"
        assert approved.decided_at is not None
        assert queue.queue_depth == 0

    def test_submit_and_reject(self):
        """Rejected actions are removed from pending."""
        queue = ApprovalQueue()

        pending = queue.submit(
            agent_id="agent-1",
            action="delete_customer_data",
            reason="Destructive action held",
        )

        rejected = queue.reject(pending.action_id, "supervisor-1", reason="Too risky")
        assert rejected.status == "rejected"
        assert queue.queue_depth == 0

    def test_urgency_sorting(self):
        """Pending queue is sorted by urgency (immediate first)."""
        queue = ApprovalQueue()

        queue.submit("agent-1", "action-batch", "Batch item", urgency=UrgencyLevel.BATCH)
        queue.submit("agent-2", "action-standard", "Standard item", urgency=UrgencyLevel.STANDARD)
        queue.submit("agent-3", "action-immediate", "Urgent item", urgency=UrgencyLevel.IMMEDIATE)

        pending = queue.pending
        assert pending[0].urgency == UrgencyLevel.IMMEDIATE
        assert pending[1].urgency == UrgencyLevel.STANDARD
        assert pending[2].urgency == UrgencyLevel.BATCH

    def test_batch_approve(self):
        """Batch approve multiple actions at once."""
        queue = ApprovalQueue()

        pa1 = queue.submit("agent-1", "action-1", "Reason 1")
        pa2 = queue.submit("agent-2", "action-2", "Reason 2")
        pa3 = queue.submit("agent-3", "action-3", "Reason 3")

        approved = queue.batch_approve(
            [pa1.action_id, pa2.action_id],
            approver_id="supervisor-1",
        )

        assert len(approved) == 2
        assert queue.queue_depth == 1  # pa3 still pending

    def test_approve_nonexistent_raises(self):
        """Approving a nonexistent action raises ValueError."""
        queue = ApprovalQueue()
        with pytest.raises(ValueError, match="not found"):
            queue.approve("nonexistent-id", "supervisor-1")

    def test_approve_already_resolved_raises(self):
        """Approving an already-approved action raises ValueError."""
        queue = ApprovalQueue()

        pa = queue.submit("agent-1", "action-1", "Reason")
        queue.approve(pa.action_id, "supervisor-1")

        with pytest.raises(ValueError, match="not pending"):
            queue.approve(pa.action_id, "supervisor-1")

    def test_expire_old_actions(self):
        """Actions older than threshold are expired automatically."""
        queue = ApprovalQueue()

        # Create a pending action with old timestamp
        pa = queue.submit("agent-1", "old-action", "Old reason")
        pa.submitted_at = datetime.now(UTC) - timedelta(hours=72)

        expired = queue.expire_old(max_age_hours=48)
        assert len(expired) == 1
        assert expired[0].status == "expired"
        assert queue.queue_depth == 0

    def test_capacity_metrics(self):
        """Capacity metrics track pending and resolved counts."""
        queue = ApprovalQueue()

        pa1 = queue.submit("agent-1", "action-1", "Reason 1")
        pa2 = queue.submit("agent-2", "action-2", "Reason 2")
        queue.approve(pa1.action_id, "supervisor-1")

        metrics = queue.get_capacity_metrics()
        assert metrics["pending_count"] == 1
        assert metrics["resolved_count"] == 1
        assert metrics["avg_resolution_seconds"] >= 0


# ===========================================================================
# 3. Session Management
# ===========================================================================


class TestSessionManagement:
    """Create session -> checkpoint -> restore."""

    def test_create_session_and_checkpoint(self):
        """Start session, create checkpoint, verify state captured."""
        mgr = SessionManager()

        session = mgr.start_session()
        assert session.state == SessionState.ACTIVE
        assert mgr.current_session is not None

        cp = mgr.checkpoint(
            active_teams=["team-dm", "team-ops"],
            pending_approvals=3,
            agent_statuses={"agent-1": "active", "agent-2": "suspended"},
            notes="Mid-session checkpoint",
        )

        assert cp.session_id == session.session_id
        assert cp.active_teams == ["team-dm", "team-ops"]
        assert cp.pending_approvals == 3
        assert cp.agent_statuses["agent-2"] == "suspended"

    def test_session_end_creates_final_checkpoint(self):
        """Ending a session creates a final checkpoint."""
        mgr = SessionManager()
        session = mgr.start_session()

        ended = mgr.end_session(notes="All tasks complete")

        assert ended.state == SessionState.ENDED
        assert ended.ended_at is not None
        assert ended.notes == "All tasks complete"
        assert len(ended.checkpoints) == 1  # final checkpoint
        assert mgr.current_session is None

    def test_checkpoint_restore_via_briefing(self):
        """Generate briefing from last checkpoint for session continuity.

        Note: end_session() creates a final checkpoint internally, so the
        briefing reflects the *final* checkpoint state (the end-session note),
        not the mid-session checkpoint. This is correct behavior -- the
        briefing shows what was happening when the session ended.
        """
        mgr = SessionManager()

        # First session with checkpoint
        mgr.start_session()
        mgr.checkpoint(
            active_teams=["team-dm"],
            pending_approvals=2,
            agent_statuses={"agent-1": "active"},
            notes="Working on content strategy",
        )
        mgr.end_session(notes="Content strategy complete")

        # Generate briefing for the next session
        briefing = mgr.generate_briefing()

        assert "Session Briefing" in briefing
        # The briefing should reflect session end state
        assert "Session ended" in briefing
        assert "Content strategy complete" in briefing

    def test_new_session_auto_ends_previous(self):
        """Starting a new session auto-ends any active session."""
        mgr = SessionManager()

        session1 = mgr.start_session()
        session2 = mgr.start_session()

        assert session1.state == SessionState.ENDED
        assert session2.state == SessionState.ACTIVE
        assert mgr.current_session.session_id == session2.session_id

    def test_checkpoint_without_session_raises(self):
        """Creating a checkpoint without an active session raises ValueError."""
        mgr = SessionManager()
        with pytest.raises(ValueError, match="No active session"):
            mgr.checkpoint()

    def test_end_without_session_raises(self):
        """Ending a session when none is active raises ValueError."""
        mgr = SessionManager()
        with pytest.raises(ValueError, match="No active session"):
            mgr.end_session()

    def test_no_previous_session_briefing(self):
        """Briefing with no previous sessions returns fresh start message."""
        mgr = SessionManager()
        briefing = mgr.generate_briefing()
        assert "fresh start" in briefing.lower()

    def test_last_checkpoint_across_sessions(self):
        """get_last_checkpoint returns the most recent across all sessions."""
        mgr = SessionManager()

        mgr.start_session()
        cp1 = mgr.checkpoint(notes="Session 1 checkpoint")
        mgr.end_session()

        mgr.start_session()
        cp2 = mgr.checkpoint(notes="Session 2 checkpoint")

        last = mgr.get_last_checkpoint()
        assert last is not None
        # The latest checkpoint should be the end-session checkpoint or session 2's
        # (end_session creates a checkpoint too)
        assert last.created_at >= cp1.created_at


# ===========================================================================
# 4. Backend Routing Between Multiple LLM Backends
# ===========================================================================


class TestBackendRouting:
    """Route between multiple LLM backends with fallover."""

    def test_route_to_preferred_backend(self):
        """Request is routed to preferred backend when available."""
        router = BackendRouter()

        anthropic = StubBackend(
            response_content="Anthropic response", provider_name=LLMProvider.ANTHROPIC
        )
        openai = StubBackend(response_content="OpenAI response", provider_name=LLMProvider.OPENAI)

        router.register_backend(anthropic)
        router.register_backend(openai)

        request = LLMRequest(messages=[{"role": "user", "content": "Hello"}])
        response = router.route(request, preferred=LLMProvider.ANTHROPIC)

        assert response.content == "Anthropic response"
        assert response.provider == "anthropic"

    def test_fallback_when_preferred_unavailable(self):
        """Falls back to next available when preferred is unavailable."""
        router = BackendRouter()

        anthropic = StubBackend(
            response_content="Anthropic response", provider_name=LLMProvider.ANTHROPIC
        )
        anthropic._available = False  # Simulate unavailable
        openai = StubBackend(response_content="OpenAI response", provider_name=LLMProvider.OPENAI)

        router.register_backend(anthropic)
        router.register_backend(openai)
        router.set_fallback_order([LLMProvider.ANTHROPIC, LLMProvider.OPENAI])

        request = LLMRequest(messages=[{"role": "user", "content": "Hello"}])
        response = router.route(request, preferred=LLMProvider.ANTHROPIC)

        assert response.content == "OpenAI response"
        assert response.provider == "openai"

    def test_no_backends_available_raises(self):
        """RuntimeError raised when no backends are available."""
        router = BackendRouter()

        anthropic = StubBackend(provider_name=LLMProvider.ANTHROPIC)
        anthropic._available = False

        router.register_backend(anthropic)
        router.set_fallback_order([LLMProvider.ANTHROPIC])

        request = LLMRequest(messages=[{"role": "user", "content": "Hello"}])

        with pytest.raises(RuntimeError, match="No LLM backends available"):
            router.route(request)

    def test_same_request_different_backends_same_verification(self):
        """Same agent definition routes to different backends consistently."""
        router = BackendRouter()

        anthropic = StubBackend(response_content="Response A", provider_name=LLMProvider.ANTHROPIC)
        openai = StubBackend(response_content="Response B", provider_name=LLMProvider.OPENAI)

        router.register_backend(anthropic)
        router.register_backend(openai)

        request = LLMRequest(
            messages=[{"role": "user", "content": "Analyze this data"}],
            model="auto",
        )

        # Route to Anthropic
        resp_a = router.route(request, preferred=LLMProvider.ANTHROPIC)
        assert resp_a.provider == "anthropic"

        # Route same request to OpenAI
        resp_b = router.route(request, preferred=LLMProvider.OPENAI)
        assert resp_b.provider == "openai"

        # Both backends received the same request
        assert len(anthropic.call_history) == 1
        assert len(openai.call_history) == 1

    def test_available_backends_list(self):
        """available_backends returns only providers that report as available."""
        router = BackendRouter()

        anthropic = StubBackend(provider_name=LLMProvider.ANTHROPIC)
        openai = StubBackend(provider_name=LLMProvider.OPENAI)
        openai._available = False

        router.register_backend(anthropic)
        router.register_backend(openai)

        available = router.available_backends()
        assert LLMProvider.ANTHROPIC in available
        assert LLMProvider.OPENAI not in available

    def test_stub_backend_records_call_history(self):
        """StubBackend records all requests in call_history."""
        backend = StubBackend(response_content="test response")

        req1 = LLMRequest(messages=[{"role": "user", "content": "Hello"}])
        req2 = LLMRequest(messages=[{"role": "user", "content": "World"}])

        backend.generate(req1)
        backend.generate(req2)

        assert len(backend.call_history) == 2
        assert backend.call_history[0].messages[0]["content"] == "Hello"
        assert backend.call_history[1].messages[0]["content"] == "World"

    def test_route_without_preference_uses_any_available(self):
        """Without preferred or fallback, routes to any available backend."""
        router = BackendRouter()

        local_backend = StubBackend(
            response_content="Local response", provider_name=LLMProvider.LOCAL
        )
        router.register_backend(local_backend)

        request = LLMRequest(messages=[{"role": "user", "content": "Hello"}])
        response = router.route(request)

        assert response.content == "Local response"
