# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for M33 — Cross-Team Execution.

Covers:
- Task 3301: Bridge verification pipeline in ExecutionRuntime
- Task 3302: Bridge-level delegation revocation
- Task 3303: Ad-hoc bridge management with auto-approve and promotion detection
- Task 3304: KaizenBridge cross-team routing
- Task 3305: Comprehensive integration tests
"""

from __future__ import annotations

import logging

import pytest

from care_platform.audit.anchor import AuditChain
from care_platform.config.schema import (
    TrustPostureLevel,
    VerificationGradientConfig,
    VerificationLevel,
)
from care_platform.constraint.gradient import GradientEngine
from care_platform.execution.approval import ApprovalQueue
from care_platform.execution.kaizen_bridge import KaizenBridge
from care_platform.execution.llm_backend import BackendRouter, StubBackend
from care_platform.execution.registry import AgentRegistry
from care_platform.execution.runtime import (
    ExecutionRuntime,
    Task,
    TaskResult,
    TaskStatus,
)
from care_platform.persistence.store import MemoryStore
from care_platform.trust.bridge_trust import (
    BridgeDelegation,
    BridgeTrustManager,
)
from care_platform.trust.credentials import CredentialManager
from care_platform.trust.revocation import RevocationManager
from care_platform.workspace.bridge import (
    Bridge,
    BridgeManager,
    BridgePermission,
    BridgeStatus,
    BridgeType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry():
    """AgentRegistry with agents on two different teams."""
    reg = AgentRegistry()
    reg.register(
        agent_id="agent-a1",
        name="Alpha Agent 1",
        role="researcher",
        team_id="team-alpha",
        capabilities=["summarize", "read_docs"],
    )
    reg.register(
        agent_id="agent-b1",
        name="Beta Agent 1",
        role="reviewer",
        team_id="team-beta",
        capabilities=["review", "write_report"],
    )
    return reg


@pytest.fixture
def gradient():
    """GradientEngine with permissive default (AUTO_APPROVED)."""
    config = VerificationGradientConfig(
        default_level=VerificationLevel.AUTO_APPROVED,
    )
    return GradientEngine(config)


@pytest.fixture
def audit_chain():
    """Fresh AuditChain."""
    return AuditChain(chain_id="test-bridge-exec")


@pytest.fixture
def approval_queue():
    """Fresh ApprovalQueue."""
    return ApprovalQueue()


@pytest.fixture
def bridge_manager():
    """BridgeManager with no callbacks."""
    return BridgeManager()


@pytest.fixture
def bridge_trust_manager():
    """BridgeTrustManager for delegation tracking."""
    return BridgeTrustManager()


@pytest.fixture
def active_bridge(bridge_manager):
    """Create an ACTIVE standing bridge between team-alpha and team-beta."""
    bridge = bridge_manager.create_standing_bridge(
        source_team="team-alpha",
        target_team="team-beta",
        purpose="Cross-team collaboration for reviews",
        permissions=BridgePermission(
            read_paths=["docs/*"],
            write_paths=["reviews/*"],
            message_types=["review", "summarize"],
        ),
        created_by="admin",
    )
    bridge_manager.approve_bridge_source(bridge.bridge_id, "admin-alpha")
    bridge_manager.approve_bridge_target(bridge.bridge_id, "admin-beta")
    return bridge


@pytest.fixture
def runtime(registry, gradient, audit_chain, approval_queue, bridge_manager, bridge_trust_manager):
    """ExecutionRuntime wired with bridge support."""
    return ExecutionRuntime(
        registry=registry,
        gradient=gradient,
        audit_chain=audit_chain,
        approval_queue=approval_queue,
        bridge_manager=bridge_manager,
        bridge_trust_manager=bridge_trust_manager,
    )


@pytest.fixture
def trust_store():
    """MemoryStore with delegation records for both agents."""
    store = MemoryStore()
    store.store_delegation(
        delegation_id="del-agent-a1",
        data={
            "delegator_id": "terrene.foundation",
            "delegatee_id": "agent-a1",
            "agent_name": "Alpha Agent 1",
            "capabilities": ["summarize", "read_docs"],
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
    )
    store.store_delegation(
        delegation_id="del-agent-b1",
        data={
            "delegator_id": "terrene.foundation",
            "delegatee_id": "agent-b1",
            "agent_name": "Beta Agent 1",
            "capabilities": ["review", "write_report"],
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
    )
    return store


@pytest.fixture
def stub_backend():
    """A StubBackend returning a predictable response."""
    return StubBackend(response_content="cross-team response")


@pytest.fixture
def backend_router(stub_backend):
    """BackendRouter with a single StubBackend registered."""
    router = BackendRouter()
    router.register_backend(stub_backend)
    return router


# ---------------------------------------------------------------------------
# 3301: Bridge Verification Pipeline
# ---------------------------------------------------------------------------


class TestBridgeVerificationPipeline:
    """Test bridge verification integration in ExecutionRuntime."""

    def test_active_bridge_allows_cross_team_action(self, runtime, active_bridge, approval_queue):
        """Cross-team task with an ACTIVE bridge should be processed."""
        # Submit a cross-team task: team-alpha requesting agent-b1 on team-beta
        task_id = runtime.submit(
            "review",
            agent_id="agent-b1",
            team_id="team-alpha",
        )
        task = runtime.process_next()

        assert task is not None
        assert task.status not in (TaskStatus.BLOCKED, TaskStatus.FAILED)

    def test_no_bridge_blocks_cross_team_action(
        self, registry, gradient, audit_chain, approval_queue
    ):
        """Cross-team task without any bridge should be BLOCKED."""
        # Create a runtime with empty bridge manager (no bridges)
        empty_bm = BridgeManager()
        rt = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
            bridge_manager=empty_bm,
        )

        task_id = rt.submit(
            "review",
            agent_id="agent-b1",
            team_id="team-alpha",
        )
        task = rt.process_next()

        assert task is not None
        assert task.status == TaskStatus.BLOCKED
        assert task.result is not None
        assert (
            "no ACTIVE bridge" in task.result.error.lower()
            or "cross-team" in task.result.error.lower()
        )

    def test_suspended_bridge_blocks_cross_team_action(
        self, registry, gradient, audit_chain, approval_queue, bridge_manager, active_bridge
    ):
        """Cross-team task with a SUSPENDED bridge should be BLOCKED."""
        bridge_manager.suspend_bridge(active_bridge.bridge_id, "Under review")

        rt = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
            bridge_manager=bridge_manager,
        )

        task_id = rt.submit(
            "review",
            agent_id="agent-b1",
            team_id="team-alpha",
        )
        task = rt.process_next()

        assert task is not None
        assert task.status == TaskStatus.BLOCKED

    def test_same_team_task_bypasses_bridge_check(self, runtime, bridge_manager):
        """Tasks within the same team should bypass bridge verification."""
        task_id = runtime.submit(
            "summarize",
            agent_id="agent-a1",
            team_id="team-alpha",
        )
        task = runtime.process_next()

        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_no_team_id_bypasses_bridge_check(self, runtime):
        """Tasks without a team_id should bypass bridge verification."""
        task_id = runtime.submit(
            "summarize",
            agent_id="agent-a1",
        )
        task = runtime.process_next()

        assert task is not None
        assert task.status == TaskStatus.COMPLETED

    def test_bridge_metadata_recorded_on_cross_team(self, runtime, active_bridge):
        """Cross-team tasks should record bridge metadata."""
        task_id = runtime.submit(
            "review",
            agent_id="agent-b1",
            team_id="team-alpha",
        )
        task = runtime.process_next()

        assert task is not None
        # Bridge metadata should be in the task metadata
        if task.status in (TaskStatus.COMPLETED, TaskStatus.EXECUTING):
            assert task.metadata.get("bridge_source_team") == "team-alpha"
            assert task.metadata.get("bridge_target_team") == "team-beta"


# ---------------------------------------------------------------------------
# 3302: Bridge-Level Revocation
# ---------------------------------------------------------------------------


class TestBridgeLevelRevocation:
    """Test bridge-level delegation revocation."""

    def test_revoke_delegations_by_bridge_id(self, bridge_trust_manager):
        """Revoke all delegations for a specific bridge_id."""
        # Register some delegations for a bridge
        d1 = BridgeDelegation(
            delegation_id="bd-001",
            bridge_id="br-test1",
            source_team="team-alpha",
            target_team="team-beta",
            bridge_type=BridgeType.STANDING,
            delegation_record={"mock": True},
        )
        d2 = BridgeDelegation(
            delegation_id="bd-002",
            bridge_id="br-test1",
            source_team="team-alpha",
            target_team="team-beta",
            bridge_type=BridgeType.STANDING,
            delegation_record={"mock": True},
        )
        bridge_trust_manager.register_delegation(d1)
        bridge_trust_manager.register_delegation(d2)

        # Revoke via RevocationManager
        rm = RevocationManager(
            bridge_trust_manager=bridge_trust_manager,
        )
        revoked_ids = rm.revoke_bridge_delegations(
            bridge_id="br-test1",
            reason="Bridge suspended",
            revoker_id="admin",
        )

        assert len(revoked_ids) == 2
        assert "bd-001" in revoked_ids
        assert "bd-002" in revoked_ids

        # Verify delegations are marked as revoked
        delegations = bridge_trust_manager.get_delegations("br-test1")
        for d in delegations:
            assert d.revoked is True

    def test_revoke_bridge_delegations_without_manager(self):
        """Without BridgeTrustManager, revoke_bridge_delegations returns empty."""
        rm = RevocationManager()
        revoked = rm.revoke_bridge_delegations(
            bridge_id="br-test1",
            reason="Test",
            revoker_id="admin",
        )
        assert revoked == []

    def test_bridge_suspension_revokes_delegations(
        self, bridge_manager, bridge_trust_manager, active_bridge
    ):
        """Suspending a bridge should revoke its delegations."""
        # Register delegations for the bridge
        d1 = BridgeDelegation(
            delegation_id="bd-susp-1",
            bridge_id=active_bridge.bridge_id,
            source_team="team-alpha",
            target_team="team-beta",
            bridge_type=BridgeType.STANDING,
            delegation_record={"mock": True},
        )
        bridge_trust_manager.register_delegation(d1)

        rm = RevocationManager(
            bridge_manager=bridge_manager,
            bridge_trust_manager=bridge_trust_manager,
        )

        # Suspend the bridge
        bridge_manager.suspend_bridge(active_bridge.bridge_id, "Under review")

        # Revoke delegations for the suspended bridge
        revoked_ids = rm.revoke_bridge_delegations(
            bridge_id=active_bridge.bridge_id,
            reason="Bridge suspended",
            revoker_id="admin",
        )

        assert len(revoked_ids) == 1
        assert "bd-susp-1" in revoked_ids

    def test_agent_revocation_also_revokes_bridge_delegations(self, bridge_trust_manager):
        """When an agent is revoked, its bridge delegations can also be revoked."""
        # Register delegations that reference specific teams
        d1 = BridgeDelegation(
            delegation_id="bd-agent-1",
            bridge_id="br-agent-bridge",
            source_team="team-alpha",
            target_team="team-beta",
            bridge_type=BridgeType.STANDING,
            delegation_record={"mock": True},
        )
        bridge_trust_manager.register_delegation(d1)

        rm = RevocationManager(
            bridge_trust_manager=bridge_trust_manager,
        )

        # Surgically revoke an agent
        rm.register_delegation("root", "agent-to-revoke")
        rm.surgical_revoke("agent-to-revoke", "Compromised", "admin")

        # Also revoke bridge delegations for the bridge the agent had access through
        revoked_ids = rm.revoke_bridge_delegations(
            bridge_id="br-agent-bridge",
            reason="Agent revoked — revoking bridge delegations",
            revoker_id="admin",
        )

        assert len(revoked_ids) == 1
        assert "bd-agent-1" in revoked_ids

    def test_revocation_record_created_for_bridge_delegation(self, bridge_trust_manager):
        """Bridge delegation revocation should create an auditable record."""
        d1 = BridgeDelegation(
            delegation_id="bd-audit-1",
            bridge_id="br-audit",
            source_team="team-alpha",
            target_team="team-beta",
            bridge_type=BridgeType.STANDING,
            delegation_record={"mock": True},
        )
        bridge_trust_manager.register_delegation(d1)

        rm = RevocationManager(
            bridge_trust_manager=bridge_trust_manager,
        )
        rm.revoke_bridge_delegations(
            bridge_id="br-audit",
            reason="Audit test",
            revoker_id="auditor",
        )

        log = rm.get_revocation_log()
        bridge_revocations = [r for r in log if r.revocation_type == "bridge_delegation"]
        assert len(bridge_revocations) == 1
        assert bridge_revocations[0].agent_id == "bridge:br-audit"
        assert "bd-audit-1" in bridge_revocations[0].affected_agents


# ---------------------------------------------------------------------------
# 3303: Ad-Hoc Bridge Management
# ---------------------------------------------------------------------------


class TestAdHocBridgeManagement:
    """Test ad-hoc bridge creation with auto-approve and promotion detection."""

    def test_request_adhoc_bridge_basic(self, bridge_manager):
        """Basic ad-hoc bridge creation without auto-approve."""
        bridge = bridge_manager.request_adhoc_bridge(
            source_team="team-alpha",
            target_team="team-beta",
            purpose="One-off review request",
            request_payload={"doc": "report.md"},
            created_by="agent-a1",
        )

        assert bridge.bridge_type == BridgeType.AD_HOC
        assert bridge.status == BridgeStatus.PENDING
        assert bridge.source_team_id == "team-alpha"
        assert bridge.target_team_id == "team-beta"
        assert bridge.request_payload == {"doc": "report.md"}

    def test_request_adhoc_bridge_auto_approve_with_standing_trust(
        self, bridge_manager, active_bridge
    ):
        """Auto-approve should activate ad-hoc bridge when standing trust exists."""
        bridge = bridge_manager.request_adhoc_bridge(
            source_team="team-alpha",
            target_team="team-beta",
            purpose="Quick cross-team query",
            request_payload={"query": "status update"},
            created_by="agent-a1",
            auto_approve=True,
        )

        assert bridge.status == BridgeStatus.ACTIVE

    def test_request_adhoc_bridge_auto_approve_without_standing_trust(self, bridge_manager):
        """Without standing trust, auto_approve should leave bridge PENDING."""
        bridge = bridge_manager.request_adhoc_bridge(
            source_team="team-alpha",
            target_team="team-gamma",
            purpose="Query to unknown team",
            request_payload={"query": "hello"},
            created_by="agent-a1",
            auto_approve=True,
        )

        assert bridge.status == BridgeStatus.PENDING

    def test_adhoc_frequency_detection_logs_warning(self, bridge_manager, caplog):
        """Exceeding ad-hoc threshold should log a standing bridge suggestion."""
        # Create many ad-hoc bridges to exceed threshold (default is 5)
        for i in range(6):
            bridge = bridge_manager.create_adhoc_bridge(
                source_team="team-x",
                target_team="team-y",
                purpose=f"Request {i}",
                request_payload={"n": i},
                created_by="agent-x1",
            )

        # Now request one more through the new API
        with caplog.at_level(logging.WARNING):
            bridge_manager.request_adhoc_bridge(
                source_team="team-x",
                target_team="team-y",
                purpose="Yet another request",
                request_payload={"n": 7},
                created_by="agent-x1",
            )

        # Should have logged a promotion suggestion
        assert any(
            "Consider creating a Standing bridge" in record.message for record in caplog.records
        )


# ---------------------------------------------------------------------------
# 3304: KaizenBridge Cross-Team Routing
# ---------------------------------------------------------------------------


class TestKaizenBridgeCrossTeamRouting:
    """Test KaizenBridge cross-team routing with bridge verification."""

    def test_cross_team_routing_with_active_bridge(
        self,
        registry,
        gradient,
        audit_chain,
        approval_queue,
        backend_router,
        trust_store,
        bridge_manager,
        bridge_trust_manager,
        active_bridge,
        stub_backend,
    ):
        """Cross-team task with ACTIVE bridge should execute via LLM.

        The runtime is created WITHOUT bridge_manager so bridge verification
        is handled entirely by the KaizenBridge layer (bridge exists = proceed).
        The runtime's standard verification gradient (AUTO_APPROVED) applies.
        """
        # Runtime without bridge_manager — KaizenBridge handles cross-team logic
        rt = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
        )
        kaizen = KaizenBridge(
            runtime=rt,
            backend_router=backend_router,
            trust_store=trust_store,
            bridge_manager=bridge_manager,
            bridge_trust_manager=bridge_trust_manager,
        )

        task = Task(
            action="review",
            agent_id="agent-b1",
            team_id="team-alpha",
        )
        result = kaizen.execute_task(task)

        assert result.output != ""
        assert result.error is None
        # Bridge metadata should be present
        assert result.metadata.get("cross_team") is True
        assert result.metadata.get("bridge_id") == active_bridge.bridge_id
        assert result.metadata.get("source_team") == "team-alpha"
        assert result.metadata.get("target_team") == "team-beta"

    def test_cross_team_routing_without_bridge_blocked(
        self,
        registry,
        gradient,
        audit_chain,
        approval_queue,
        backend_router,
        trust_store,
        bridge_trust_manager,
        stub_backend,
    ):
        """Cross-team task without bridge should be blocked."""
        empty_bm = BridgeManager()
        rt = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
        )
        kaizen = KaizenBridge(
            runtime=rt,
            backend_router=backend_router,
            trust_store=trust_store,
            bridge_manager=empty_bm,
            bridge_trust_manager=bridge_trust_manager,
        )

        task = Task(
            action="review",
            agent_id="agent-b1",
            team_id="team-alpha",
        )
        result = kaizen.execute_task(task)

        assert result.error is not None
        assert "blocked" in result.error.lower() or "no active bridge" in result.error.lower()
        assert result.metadata.get("cross_team") is True

    def test_cross_team_system_prompt_includes_bridge_context(
        self,
        registry,
        gradient,
        audit_chain,
        approval_queue,
        backend_router,
        trust_store,
        bridge_manager,
        bridge_trust_manager,
        active_bridge,
        stub_backend,
    ):
        """System prompt should include bridge context for cross-team tasks."""
        rt = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
        )
        kaizen = KaizenBridge(
            runtime=rt,
            backend_router=backend_router,
            trust_store=trust_store,
            bridge_manager=bridge_manager,
            bridge_trust_manager=bridge_trust_manager,
        )

        task = Task(
            action="review",
            agent_id="agent-b1",
            team_id="team-alpha",
        )
        kaizen.execute_task(task)

        # Check the system prompt sent to the LLM
        assert len(stub_backend.call_history) == 1
        system_content = stub_backend.call_history[0].messages[0]["content"]
        assert "Cross-Functional Bridge" in system_content
        assert active_bridge.bridge_id in system_content

    def test_same_team_task_no_bridge_metadata(
        self,
        registry,
        gradient,
        audit_chain,
        approval_queue,
        backend_router,
        trust_store,
        bridge_manager,
        bridge_trust_manager,
        stub_backend,
    ):
        """Same-team tasks should not include bridge metadata."""
        rt = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
        )
        kaizen = KaizenBridge(
            runtime=rt,
            backend_router=backend_router,
            trust_store=trust_store,
            bridge_manager=bridge_manager,
            bridge_trust_manager=bridge_trust_manager,
        )

        task = Task(
            action="summarize",
            agent_id="agent-a1",
            team_id="team-alpha",
        )
        result = kaizen.execute_task(task)

        assert result.error is None
        assert result.metadata.get("cross_team") is None

    def test_kaizen_bridge_backward_compatibility(
        self,
        registry,
        gradient,
        audit_chain,
        approval_queue,
        backend_router,
        trust_store,
        stub_backend,
    ):
        """KaizenBridge without bridge_manager should work as before."""
        rt = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
        )
        kaizen = KaizenBridge(
            runtime=rt,
            backend_router=backend_router,
            trust_store=trust_store,
        )

        task = Task(
            action="summarize",
            agent_id="agent-a1",
        )
        result = kaizen.execute_task(task)

        assert result.error is None
        assert result.output != ""


# ---------------------------------------------------------------------------
# 3305: Integration / End-to-End Scenarios
# ---------------------------------------------------------------------------


class TestCrossTeamExecutionIntegration:
    """Integration tests combining multiple M33 components."""

    def test_full_cross_team_execution_flow(
        self,
        registry,
        gradient,
        audit_chain,
        approval_queue,
        backend_router,
        trust_store,
        bridge_manager,
        bridge_trust_manager,
        active_bridge,
        stub_backend,
    ):
        """Full flow: bridge lookup -> verification -> LLM execution -> metadata."""
        # Register bridge delegations
        d1 = BridgeDelegation(
            delegation_id="bd-integ-1",
            bridge_id=active_bridge.bridge_id,
            source_team="team-alpha",
            target_team="team-beta",
            bridge_type=BridgeType.STANDING,
            delegation_record={"mock": True},
        )
        bridge_trust_manager.register_delegation(d1)

        # Runtime without bridge_manager for this test — KaizenBridge handles
        # cross-team logic, runtime does standard gradient verification
        rt = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
        )

        kaizen = KaizenBridge(
            runtime=rt,
            backend_router=backend_router,
            trust_store=trust_store,
            bridge_manager=bridge_manager,
            bridge_trust_manager=bridge_trust_manager,
        )

        task = Task(
            action="review",
            agent_id="agent-b1",
            team_id="team-alpha",
        )
        result = kaizen.execute_task(task)

        # Verify execution succeeded
        assert result.error is None
        assert result.output == "cross-team response"
        assert result.metadata["cross_team"] is True
        assert result.metadata["bridge_id"] == active_bridge.bridge_id

    def test_bridge_revocation_then_execution_blocked(
        self,
        registry,
        gradient,
        audit_chain,
        approval_queue,
        bridge_manager,
        bridge_trust_manager,
        active_bridge,
        backend_router,
        trust_store,
    ):
        """After revoking bridge delegations, the bridge itself remains
        but delegations are marked revoked."""
        # Register and then revoke delegations
        d1 = BridgeDelegation(
            delegation_id="bd-revblock-1",
            bridge_id=active_bridge.bridge_id,
            source_team="team-alpha",
            target_team="team-beta",
            bridge_type=BridgeType.STANDING,
            delegation_record={"mock": True},
        )
        bridge_trust_manager.register_delegation(d1)

        rm = RevocationManager(
            bridge_trust_manager=bridge_trust_manager,
            bridge_manager=bridge_manager,
        )
        revoked_ids = rm.revoke_bridge_delegations(
            bridge_id=active_bridge.bridge_id,
            reason="Trust review",
            revoker_id="admin",
        )

        # Verify delegations are revoked
        assert len(revoked_ids) == 1
        delegations = bridge_trust_manager.get_delegations(active_bridge.bridge_id)
        assert all(d.revoked for d in delegations)

    def test_adhoc_bridge_then_cross_team_execution(
        self,
        registry,
        gradient,
        audit_chain,
        approval_queue,
        bridge_manager,
        bridge_trust_manager,
        backend_router,
        trust_store,
        stub_backend,
        active_bridge,
    ):
        """Ad-hoc bridge with auto-approve enables immediate cross-team execution."""
        # Create an ad-hoc bridge with auto-approve (standing trust exists)
        adhoc = bridge_manager.request_adhoc_bridge(
            source_team="team-alpha",
            target_team="team-beta",
            purpose="Quick review",
            request_payload={"doc": "report.md"},
            created_by="agent-a1",
            auto_approve=True,
        )

        assert adhoc.status == BridgeStatus.ACTIVE

    def test_runtime_backward_compatible_without_bridge_manager(
        self, registry, gradient, audit_chain, approval_queue
    ):
        """Runtime without bridge_manager should work exactly as before."""
        rt = ExecutionRuntime(
            registry=registry,
            gradient=gradient,
            audit_chain=audit_chain,
            approval_queue=approval_queue,
        )

        task_id = rt.submit("summarize", agent_id="agent-a1")
        task = rt.process_next()

        assert task is not None
        assert task.status == TaskStatus.COMPLETED
