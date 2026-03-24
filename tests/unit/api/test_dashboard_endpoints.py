# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for M18 dashboard API endpoints.

Tests the new dashboard-oriented handler methods on PactAPI:
- list_trust_chains / get_trust_chain_detail
- get_envelope
- list_workspaces
- list_bridges
- verification_stats
"""

from __future__ import annotations

import pytest

from pact_platform.build.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
    VerificationLevel,
    WorkspaceConfig,
)
from pact_platform.build.workspace.bridge import (
    BridgeManager,
    BridgePermission,
)
from pact_platform.build.workspace.models import (
    Workspace,
    WorkspacePhase,
    WorkspaceRegistry,
)
from pact_platform.trust.store.cost_tracking import CostTracker
from pact_platform.use.api.endpoints import (
    PactAPI,
)
from pact_platform.use.execution.approval import ApprovalQueue, UrgencyLevel
from pact_platform.use.execution.registry import AgentRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry():
    """Registry with agents in two teams."""
    reg = AgentRegistry()
    reg.register(
        agent_id="agent-1",
        name="Agent One",
        role="Content Writer",
        team_id="team-alpha",
        capabilities=["read", "write"],
        posture="supervised",
    )
    reg.register(
        agent_id="agent-2",
        name="Agent Two",
        role="Analytics",
        team_id="team-alpha",
        capabilities=["read"],
        posture="supervised",
    )
    reg.register(
        agent_id="agent-3",
        name="Agent Three",
        role="Lead",
        team_id="team-beta",
        capabilities=["approve"],
        posture="delegated",
    )
    return reg


@pytest.fixture()
def approval_queue():
    """Approval queue with one pending action."""
    q = ApprovalQueue()
    q.submit(
        agent_id="agent-1",
        action="publish_post",
        reason="External publication requires approval",
        team_id="team-alpha",
        urgency=UrgencyLevel.STANDARD,
    )
    return q


@pytest.fixture()
def cost_tracker():
    """Empty cost tracker."""
    return CostTracker()


@pytest.fixture()
def workspace_registry():
    """Workspace registry with two workspaces."""
    wr = WorkspaceRegistry()

    ws1_config = WorkspaceConfig(
        id="ws-dm",
        path="workspaces/dm",
        description="Digital Marketing workspace",
    )
    ws1 = Workspace(config=ws1_config, team_id="team-alpha")
    ws1.activate(reason="Test setup")
    ws1.transition_to(WorkspacePhase.PLAN, reason="Planning phase")
    wr.register(ws1)

    ws2_config = WorkspaceConfig(
        id="ws-standards",
        path="workspaces/standards",
        description="Standards workspace",
    )
    ws2 = Workspace(config=ws2_config, team_id="team-beta")
    # Leave in PROVISIONING state
    wr.register(ws2)

    return wr


@pytest.fixture()
def bridge_manager():
    """Bridge manager with bridges in various states."""
    bm = BridgeManager()
    perms = BridgePermission(
        read_paths=["workspaces/dm/content/*"],
        message_types=["review_request"],
    )
    # Create a standing bridge and activate it
    bridge1 = bm.create_standing_bridge(
        source_team="team-alpha",
        target_team="team-beta",
        purpose="Content review",
        permissions=perms,
        created_by="agent-1",
    )
    bridge1.approve_source("agent-1")
    bridge1.approve_target("agent-3")

    # Create a pending scoped bridge
    bm.create_scoped_bridge(
        source_team="team-beta",
        target_team="team-alpha",
        purpose="Analytics access",
        permissions=BridgePermission(read_paths=["workspaces/dm/analytics/*"]),
        created_by="agent-3",
        valid_days=7,
    )

    return bm


@pytest.fixture()
def envelope_registry():
    """Registry of constraint envelopes (dict mapping ID to ConstraintEnvelope)."""
    config1 = ConstraintEnvelopeConfig(
        id="env-writer",
        description="Content writer envelope",
        financial=FinancialConstraintConfig(max_spend_usd=50.0),
        operational=OperationalConstraintConfig(
            allowed_actions=["write_content", "publish_draft"],
            max_actions_per_day=100,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="09:00",
            active_hours_end="17:00",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/dm/*"],
            write_paths=["workspaces/dm/content/*"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )
    config2 = ConstraintEnvelopeConfig(
        id="env-lead",
        description="Team lead envelope",
        financial=FinancialConstraintConfig(max_spend_usd=500.0),
        operational=OperationalConstraintConfig(
            allowed_actions=["write_content", "publish_draft", "approve_content"],
            max_actions_per_day=200,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="08:00",
            active_hours_end="20:00",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/*"],
            write_paths=["workspaces/*"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=False,
            external_requires_approval=False,
        ),
    )

    return {"env-writer": config1, "env-lead": config2}


@pytest.fixture()
def verification_stats():
    """Pre-computed verification stats counts."""
    return {
        VerificationLevel.AUTO_APPROVED: 42,
        VerificationLevel.FLAGGED: 7,
        VerificationLevel.HELD: 3,
        VerificationLevel.BLOCKED: 1,
    }


@pytest.fixture()
def api(
    registry,
    approval_queue,
    cost_tracker,
    workspace_registry,
    bridge_manager,
    envelope_registry,
    verification_stats,
):
    """PactAPI wired with all dashboard components."""
    return PactAPI(
        registry=registry,
        approval_queue=approval_queue,
        cost_tracker=cost_tracker,
        workspace_registry=workspace_registry,
        bridge_manager=bridge_manager,
        envelope_registry=envelope_registry,
        verification_stats=verification_stats,
    )


# ---------------------------------------------------------------------------
# Test: list_trust_chains
# ---------------------------------------------------------------------------


class TestListTrustChains:
    """GET /api/v1/trust-chains — list all agents with trust chain status."""

    def test_list_trust_chains_returns_agents(self, api):
        """list_trust_chains() returns an entry per registered agent."""
        resp = api.list_trust_chains()
        assert resp.status == "ok"
        chains = resp.data["trust_chains"]
        assert isinstance(chains, list)
        assert len(chains) == 3  # 3 agents registered

    def test_list_trust_chains_entry_structure(self, api):
        """Each trust chain entry has agent_id, name, team_id, posture, status."""
        resp = api.list_trust_chains()
        chains = resp.data["trust_chains"]
        entry = next(c for c in chains if c["agent_id"] == "agent-1")
        assert entry["name"] == "Agent One"
        assert entry["team_id"] == "team-alpha"
        assert entry["posture"] == "supervised"
        assert "status" in entry

    def test_list_trust_chains_empty_registry(
        self,
        approval_queue,
        cost_tracker,
        workspace_registry,
        bridge_manager,
        envelope_registry,
        verification_stats,
    ):
        """list_trust_chains() returns empty list when no agents registered."""
        empty_reg = AgentRegistry()
        api = PactAPI(
            registry=empty_reg,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
            workspace_registry=workspace_registry,
            bridge_manager=bridge_manager,
            envelope_registry=envelope_registry,
            verification_stats=verification_stats,
        )
        resp = api.list_trust_chains()
        assert resp.status == "ok"
        assert resp.data["trust_chains"] == []


# ---------------------------------------------------------------------------
# Test: get_trust_chain_detail
# ---------------------------------------------------------------------------


class TestGetTrustChainDetail:
    """GET /api/v1/trust-chains/{agent_id} — single agent trust chain detail."""

    def test_trust_chain_detail_found(self, api):
        """get_trust_chain_detail() returns details for a known agent."""
        resp = api.get_trust_chain_detail("agent-1")
        assert resp.status == "ok"
        data = resp.data
        assert data["agent_id"] == "agent-1"
        assert data["name"] == "Agent One"
        assert data["role"] == "Content Writer"
        assert data["team_id"] == "team-alpha"
        assert data["posture"] == "supervised"
        assert "capabilities" in data
        assert "status" in data

    def test_trust_chain_detail_not_found(self, api):
        """get_trust_chain_detail() returns error for unknown agent."""
        resp = api.get_trust_chain_detail("nonexistent-agent")
        assert resp.status == "error"
        assert resp.error is not None
        assert "not found" in resp.error.lower()


# ---------------------------------------------------------------------------
# Test: get_envelope
# ---------------------------------------------------------------------------


class TestGetEnvelope:
    """GET /api/v1/envelopes/{envelope_id} — envelope detail with all 5 dimensions."""

    def test_get_envelope_found(self, api):
        """get_envelope() returns envelope with all five dimensions."""
        resp = api.get_envelope("env-writer")
        assert resp.status == "ok"
        data = resp.data
        assert data["envelope_id"] == "env-writer"
        assert data["description"] == "Content writer envelope"
        # All five dimensions must be present
        assert "financial" in data
        assert "operational" in data
        assert "temporal" in data
        assert "data_access" in data
        assert "communication" in data

    def test_get_envelope_financial_details(self, api):
        """Financial dimension includes max_spend_usd."""
        resp = api.get_envelope("env-writer")
        fin = resp.data["financial"]
        assert fin["max_spend_usd"] == 50.0

    def test_get_envelope_operational_details(self, api):
        """Operational dimension includes allowed_actions and max_actions_per_day."""
        resp = api.get_envelope("env-writer")
        ops = resp.data["operational"]
        assert "write_content" in ops["allowed_actions"]
        assert ops["max_actions_per_day"] == 100

    def test_get_envelope_temporal_details(self, api):
        """Temporal dimension includes active hours."""
        resp = api.get_envelope("env-writer")
        temp = resp.data["temporal"]
        assert temp["active_hours_start"] == "09:00"
        assert temp["active_hours_end"] == "17:00"

    def test_get_envelope_data_access_details(self, api):
        """Data access dimension includes read_paths and write_paths."""
        resp = api.get_envelope("env-writer")
        da = resp.data["data_access"]
        assert "workspaces/dm/*" in da["read_paths"]
        assert "workspaces/dm/content/*" in da["write_paths"]

    def test_get_envelope_communication_details(self, api):
        """Communication dimension includes internal_only and external_requires_approval."""
        resp = api.get_envelope("env-writer")
        comm = resp.data["communication"]
        assert comm["internal_only"] is True
        assert comm["external_requires_approval"] is True

    def test_get_envelope_not_found(self, api):
        """get_envelope() returns error for unknown envelope ID."""
        resp = api.get_envelope("env-nonexistent")
        assert resp.status == "error"
        assert resp.error is not None
        assert "not found" in resp.error.lower()


# ---------------------------------------------------------------------------
# Test: list_workspaces
# ---------------------------------------------------------------------------


class TestListWorkspaces:
    """GET /api/v1/workspaces — all workspaces with state and phase."""

    def test_list_workspaces_returns_all(self, api):
        """list_workspaces() returns all registered workspaces."""
        resp = api.list_workspaces()
        assert resp.status == "ok"
        workspaces = resp.data["workspaces"]
        assert isinstance(workspaces, list)
        assert len(workspaces) == 2

    def test_list_workspaces_entry_structure(self, api):
        """Each workspace entry has id, path, description, state, phase, team_id."""
        resp = api.list_workspaces()
        workspaces = resp.data["workspaces"]
        dm_ws = next(w for w in workspaces if w["id"] == "ws-dm")
        assert dm_ws["path"] == "workspaces/dm"
        assert dm_ws["description"] == "Digital Marketing workspace"
        assert dm_ws["state"] == "active"
        assert dm_ws["phase"] == "plan"
        assert dm_ws["team_id"] == "team-alpha"

    def test_list_workspaces_provisioning_state(self, api):
        """Workspace in PROVISIONING state is correctly reported."""
        resp = api.list_workspaces()
        workspaces = resp.data["workspaces"]
        std_ws = next(w for w in workspaces if w["id"] == "ws-standards")
        assert std_ws["state"] == "provisioning"
        assert std_ws["phase"] == "analyze"  # default phase

    def test_list_workspaces_empty(
        self,
        registry,
        approval_queue,
        cost_tracker,
        bridge_manager,
        envelope_registry,
        verification_stats,
    ):
        """list_workspaces() returns empty list when no workspaces registered."""
        api = PactAPI(
            registry=registry,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
            workspace_registry=WorkspaceRegistry(),
            bridge_manager=bridge_manager,
            envelope_registry=envelope_registry,
            verification_stats=verification_stats,
        )
        resp = api.list_workspaces()
        assert resp.status == "ok"
        assert resp.data["workspaces"] == []


# ---------------------------------------------------------------------------
# Test: list_bridges
# ---------------------------------------------------------------------------


class TestListBridges:
    """GET /api/v1/bridges — all bridges with status."""

    def test_list_bridges_returns_all(self, api):
        """list_bridges() returns all bridges from the manager."""
        resp = api.list_bridges()
        assert resp.status == "ok"
        bridges = resp.data["bridges"]
        assert isinstance(bridges, list)
        assert len(bridges) == 2

    def test_list_bridges_entry_structure(self, api):
        """Each bridge entry has bridge_id, type, source, target, purpose, status."""
        resp = api.list_bridges()
        bridges = resp.data["bridges"]
        # Find the active standing bridge
        active = next(b for b in bridges if b["status"] == "active")
        assert active["bridge_type"] == "standing"
        assert active["source_team_id"] == "team-alpha"
        assert active["target_team_id"] == "team-beta"
        assert active["purpose"] == "Content review"
        assert "bridge_id" in active

    def test_list_bridges_includes_pending(self, api):
        """Pending bridges are included in the list."""
        resp = api.list_bridges()
        bridges = resp.data["bridges"]
        pending = [b for b in bridges if b["status"] == "pending"]
        assert len(pending) == 1
        assert pending[0]["bridge_type"] == "scoped"

    def test_list_bridges_empty(
        self,
        registry,
        approval_queue,
        cost_tracker,
        workspace_registry,
        envelope_registry,
        verification_stats,
    ):
        """list_bridges() returns empty list when no bridges exist."""
        api = PactAPI(
            registry=registry,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
            workspace_registry=workspace_registry,
            bridge_manager=BridgeManager(),
            envelope_registry=envelope_registry,
            verification_stats=verification_stats,
        )
        resp = api.list_bridges()
        assert resp.status == "ok"
        assert resp.data["bridges"] == []


# ---------------------------------------------------------------------------
# Test: verification_stats_report
# ---------------------------------------------------------------------------


class TestVerificationStats:
    """GET /api/v1/verification/stats — gradient counts by level."""

    def test_verification_stats_returns_counts(self, api):
        """verification_stats_report() returns counts for all four levels."""
        resp = api.verification_stats_report()
        assert resp.status == "ok"
        data = resp.data
        assert data["AUTO_APPROVED"] == 42
        assert data["FLAGGED"] == 7
        assert data["HELD"] == 3
        assert data["BLOCKED"] == 1

    def test_verification_stats_total(self, api):
        """verification_stats_report() includes a total count."""
        resp = api.verification_stats_report()
        assert resp.data["total"] == 53

    def test_verification_stats_empty(
        self,
        registry,
        approval_queue,
        cost_tracker,
        workspace_registry,
        bridge_manager,
        envelope_registry,
    ):
        """verification_stats_report() returns zeros when no stats provided."""
        api = PactAPI(
            registry=registry,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
            workspace_registry=workspace_registry,
            bridge_manager=bridge_manager,
            envelope_registry=envelope_registry,
            verification_stats={},
        )
        resp = api.verification_stats_report()
        assert resp.status == "ok"
        assert resp.data["AUTO_APPROVED"] == 0
        assert resp.data["FLAGGED"] == 0
        assert resp.data["HELD"] == 0
        assert resp.data["BLOCKED"] == 0
        assert resp.data["total"] == 0


# ---------------------------------------------------------------------------
# Test: PactAPI backward compatibility
# ---------------------------------------------------------------------------


class TestPactAPIBackwardCompat:
    """PactAPI still works with only the original Phase 1 components."""

    def test_phase1_only_construction(self, registry, approval_queue, cost_tracker):
        """PactAPI works with just registry, approval_queue, cost_tracker."""
        api = PactAPI(
            registry=registry,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
        )
        # Phase 1 endpoints still work
        resp = api.list_teams()
        assert resp.status == "ok"

    def test_dashboard_endpoints_without_components_return_error(
        self, registry, approval_queue, cost_tracker
    ):
        """Dashboard endpoints return errors when optional components not provided."""
        api = PactAPI(
            registry=registry,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
        )
        # list_trust_chains uses registry so it still works
        resp = api.list_trust_chains()
        assert resp.status == "ok"

        # Workspace/bridge/envelope endpoints should return clear errors
        resp = api.list_workspaces()
        assert resp.status == "error"
        assert "workspace_registry" in resp.error.lower()

        resp = api.list_bridges()
        assert resp.status == "error"
        assert "bridge_manager" in resp.error.lower()

        resp = api.get_envelope("env-1")
        assert resp.status == "error"
        assert "envelope_registry" in resp.error.lower()

        resp = api.verification_stats_report()
        assert resp.status == "error"
        assert "verification_stats" in resp.error.lower()
