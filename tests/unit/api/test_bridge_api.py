# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for M36 bridge management API endpoints.

Tests the bridge CRUD, approval, lifecycle, and audit handler methods
on PactAPI — same pattern as test_dashboard_endpoints.py.
"""

from __future__ import annotations

import pytest

from pact_platform.build.workspace.bridge import BridgeManager
from pact_platform.trust.store.cost_tracking import CostTracker
from pact_platform.use.api.endpoints import (
    PactAPI,
)
from pact_platform.use.execution.approval import ApprovalQueue
from pact_platform.use.execution.registry import AgentRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry():
    """Registry with agents in two teams, including lead approvers."""
    reg = AgentRegistry()
    reg.register(
        agent_id="agent-1",
        name="Agent One",
        role="Content Writer",
        team_id="team-alpha",
        capabilities=["read", "write"],
        posture="supervised",
    )
    # L1-FIX: Register approver agents so registry-based team membership
    # validation can verify them (replaces old substring-based check).
    reg.register(
        agent_id="team-alpha-lead-1",
        name="Alpha Lead",
        role="Lead",
        team_id="team-alpha",
        capabilities=["approve"],
        posture="delegated",
    )
    reg.register(
        agent_id="agent-3",
        name="Agent Three",
        role="Lead",
        team_id="team-beta",
        capabilities=["approve"],
        posture="delegated",
    )
    reg.register(
        agent_id="team-beta-lead-1",
        name="Beta Lead",
        role="Lead",
        team_id="team-beta",
        capabilities=["approve"],
        posture="delegated",
    )
    return reg


@pytest.fixture()
def approval_queue():
    """Empty approval queue."""
    return ApprovalQueue()


@pytest.fixture()
def cost_tracker():
    """Empty cost tracker."""
    return CostTracker()


@pytest.fixture()
def bridge_manager():
    """Fresh bridge manager."""
    return BridgeManager()


@pytest.fixture()
def api(registry, approval_queue, cost_tracker, bridge_manager):
    """PactAPI wired with bridge manager."""
    return PactAPI(
        registry=registry,
        approval_queue=approval_queue,
        cost_tracker=cost_tracker,
        bridge_manager=bridge_manager,
    )


# ---------------------------------------------------------------------------
# Test: create_bridge
# ---------------------------------------------------------------------------


class TestCreateBridge:
    """POST /api/v1/bridges — create a cross-functional bridge."""

    def test_create_standing_bridge(self, api):
        """Create a standing bridge returns bridge detail with PENDING status."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Content review pipeline",
                "permissions": {
                    "read_paths": ["workspaces/dm/*"],
                    "write_paths": [],
                    "message_types": ["review_request"],
                },
                "created_by": "agent-1",
            }
        )
        assert resp.status == "ok"
        data = resp.data
        assert data["bridge_type"] == "standing"
        assert data["source_team_id"] == "team-alpha"
        assert data["target_team_id"] == "team-beta"
        assert data["purpose"] == "Content review pipeline"
        assert data["status"] == "pending"
        assert data["bridge_id"]  # non-empty

    def test_create_scoped_bridge(self, api):
        """Create a scoped bridge with valid_days."""
        resp = api.create_bridge(
            {
                "bridge_type": "scoped",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "7-day analytics access",
                "permissions": {
                    "read_paths": ["workspaces/dm/analytics/*"],
                },
                "valid_days": 7,
                "created_by": "agent-1",
            }
        )
        assert resp.status == "ok"
        data = resp.data
        assert data["bridge_type"] == "scoped"
        assert data["valid_until"] is not None

    def test_create_adhoc_bridge(self, api):
        """Create an ad-hoc bridge with request payload."""
        resp = api.create_bridge(
            {
                "bridge_type": "ad_hoc",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "One-time governance review",
                "request_payload": {"document": "standards-v2.md", "review_type": "governance"},
                "created_by": "agent-1",
            }
        )
        assert resp.status == "ok"
        data = resp.data
        assert data["bridge_type"] == "ad_hoc"
        assert data["one_time_use"] is True
        # RT13-009: Payloads are redacted in bridge detail API
        assert data["has_request_payload"] is True

    def test_create_bridge_missing_fields(self, api):
        """Missing required fields returns error."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                # Missing source_team_id, target_team_id, purpose
            }
        )
        assert resp.status == "error"
        assert "required" in resp.error.lower()

    def test_create_bridge_invalid_type(self, api):
        """Invalid bridge_type returns error."""
        resp = api.create_bridge(
            {
                "bridge_type": "wormhole",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Test",
            }
        )
        assert resp.status == "error"
        assert "invalid" in resp.error.lower() or "wormhole" in resp.error.lower()

    def test_create_bridge_default_permissions(self, api):
        """Bridge created without explicit permissions gets defaults."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Default perms test",
                "created_by": "api",
            }
        )
        assert resp.status == "ok"
        assert "permissions" in resp.data

    def test_self_bridge_rejected(self, api):
        """RT13-001: Cannot create a bridge from a team to itself."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-alpha",
                "purpose": "Self-bridge attempt",
            }
        )
        assert resp.status == "error"
        assert "itself" in resp.error.lower()

    def test_long_team_id_rejected(self, api):
        """RT13-H7: Pathologically long identifiers are rejected."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "a" * 300,
                "target_team_id": "team-beta",
                "purpose": "Long ID test",
            }
        )
        assert resp.status == "error"
        assert "maximum length" in resp.error.lower()

    def test_bridge_detail_redacts_payloads(self, api):
        """RT13-009: Bridge detail API does not expose raw payloads."""
        resp = api.create_bridge(
            {
                "bridge_type": "ad_hoc",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Payload redaction test",
                "request_payload": {"secret": "data"},
            }
        )
        assert resp.status == "ok"
        data = resp.data
        assert "request_payload" not in data
        assert "response_payload" not in data
        assert data["has_request_payload"] is True
        assert data["has_response_payload"] is False


# ---------------------------------------------------------------------------
# Test: get_bridge
# ---------------------------------------------------------------------------


class TestGetBridge:
    """GET /api/v1/bridges/{bridge_id} — bridge detail."""

    def test_get_bridge_detail(self, api):
        """Get bridge by ID returns full detail."""
        # Create first
        create_resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Detail test",
                "created_by": "agent-1",
            }
        )
        bridge_id = create_resp.data["bridge_id"]

        resp = api.get_bridge(bridge_id)
        assert resp.status == "ok"
        data = resp.data
        assert data["bridge_id"] == bridge_id
        assert data["bridge_type"] == "standing"
        assert data["purpose"] == "Detail test"
        assert "permissions" in data
        assert "created_at" in data
        assert "created_by" in data
        assert "approved_by_source" in data
        assert "approved_by_target" in data

    def test_get_bridge_not_found(self, api):
        """Nonexistent bridge ID returns error."""
        resp = api.get_bridge("bridge-does-not-exist")
        assert resp.status == "error"
        assert "not found" in resp.error.lower()


# ---------------------------------------------------------------------------
# Test: approve_bridge
# ---------------------------------------------------------------------------


class TestApproveBridge:
    """PUT /api/v1/bridges/{bridge_id}/approve — bilateral approval."""

    def _create_bridge(self, api):
        """Helper: create a pending bridge and return its ID."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Approval test",
                "created_by": "agent-1",
            }
        )
        return resp.data["bridge_id"]

    def test_approve_source(self, api):
        """Approving source side records source approval."""
        bridge_id = self._create_bridge(api)
        # RT13-C1: approver_id must contain the team name for authorization
        resp = api.approve_bridge(bridge_id, "source", "team-alpha-lead-1")
        assert resp.status == "ok"
        assert resp.data["approved_by_source"] == "team-alpha-lead-1"
        assert resp.data["approved_by_target"] is None
        # Still pending until both sides approve
        assert resp.data["status"] == "pending"

    def test_approve_target(self, api):
        """Approving target side records target approval."""
        bridge_id = self._create_bridge(api)
        # RT13-C1: approver_id must contain the team name for authorization
        resp = api.approve_bridge(bridge_id, "target", "team-beta-lead-1")
        assert resp.status == "ok"
        assert resp.data["approved_by_target"] == "team-beta-lead-1"

    def test_approve_both_sides_activates(self, api):
        """Approving both sides transitions to ACTIVE."""
        bridge_id = self._create_bridge(api)
        api.approve_bridge(bridge_id, "source", "team-alpha-lead-1")
        resp = api.approve_bridge(bridge_id, "target", "team-beta-lead-1")
        assert resp.status == "ok"
        assert resp.data["status"] == "active"

    def test_approve_wrong_team_rejected(self, api):
        """RT13-C1: Approver from wrong team is rejected."""
        bridge_id = self._create_bridge(api)
        resp = api.approve_bridge(bridge_id, "source", "team-beta-intruder")
        assert resp.status == "error"
        assert "not authorized" in resp.error.lower()

    def test_approve_invalid_side(self, api):
        """Invalid side parameter returns error."""
        bridge_id = self._create_bridge(api)
        resp = api.approve_bridge(bridge_id, "middle", "team-alpha-lead-1")
        assert resp.status == "error"
        assert "invalid" in resp.error.lower() or "side" in resp.error.lower()

    def test_approve_nonexistent_bridge(self, api):
        """Approving nonexistent bridge returns error."""
        resp = api.approve_bridge("no-such-bridge", "source", "team-alpha-lead-1")
        assert resp.status == "error"


# ---------------------------------------------------------------------------
# Test: suspend_bridge_action
# ---------------------------------------------------------------------------


class TestSuspendBridge:
    """POST /api/v1/bridges/{bridge_id}/suspend — suspend active bridge."""

    def _create_active_bridge(self, api):
        """Helper: create and activate a bridge."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Suspend test",
                "created_by": "agent-1",
            }
        )
        bridge_id = resp.data["bridge_id"]
        api.approve_bridge(bridge_id, "source", "team-alpha-lead-1")
        api.approve_bridge(bridge_id, "target", "team-beta-lead-1")
        return bridge_id

    def test_suspend_active_bridge(self, api):
        """Suspending an active bridge sets status to SUSPENDED."""
        bridge_id = self._create_active_bridge(api)
        resp = api.suspend_bridge_action(bridge_id, "Security review required")
        assert resp.status == "ok"
        assert resp.data["status"] == "suspended"

    def test_suspend_no_reason(self, api):
        """Suspending without a reason returns error."""
        bridge_id = self._create_active_bridge(api)
        resp = api.suspend_bridge_action(bridge_id, "")
        assert resp.status == "error"
        assert "reason" in resp.error.lower()

    def test_suspend_nonexistent_bridge(self, api):
        """Suspending nonexistent bridge returns error."""
        resp = api.suspend_bridge_action("no-bridge", "test")
        assert resp.status == "error"


# ---------------------------------------------------------------------------
# Test: close_bridge_action
# ---------------------------------------------------------------------------


class TestCloseBridge:
    """POST /api/v1/bridges/{bridge_id}/close — close a bridge."""

    def _create_active_bridge(self, api):
        """Helper: create and activate a bridge."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Close test",
                "created_by": "agent-1",
            }
        )
        bridge_id = resp.data["bridge_id"]
        api.approve_bridge(bridge_id, "source", "team-alpha-lead-1")
        api.approve_bridge(bridge_id, "target", "team-beta-lead-1")
        return bridge_id

    def test_close_active_bridge(self, api):
        """Closing an active bridge sets status to CLOSED."""
        bridge_id = self._create_active_bridge(api)
        resp = api.close_bridge_action(bridge_id, "Project complete")
        assert resp.status == "ok"
        assert resp.data["status"] == "closed"

    def test_close_no_reason(self, api):
        """Closing without a reason returns error."""
        bridge_id = self._create_active_bridge(api)
        resp = api.close_bridge_action(bridge_id, "")
        assert resp.status == "error"
        assert "reason" in resp.error.lower()

    def test_close_nonexistent_bridge(self, api):
        """Closing nonexistent bridge returns error."""
        resp = api.close_bridge_action("no-bridge", "test")
        assert resp.status == "error"


# ---------------------------------------------------------------------------
# Test: list_bridges_by_team
# ---------------------------------------------------------------------------


class TestListBridgesByTeam:
    """GET /api/v1/bridges/team/{team_id} — team bridges."""

    def test_list_bridges_for_source_team(self, api):
        """Lists bridges where team is the source."""
        api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Alpha to Beta",
                "created_by": "agent-1",
            }
        )
        resp = api.list_bridges_by_team("team-alpha")
        assert resp.status == "ok"
        bridges = resp.data["bridges"]
        assert len(bridges) >= 1
        assert any(b["source_team_id"] == "team-alpha" for b in bridges)

    def test_list_bridges_for_target_team(self, api):
        """Lists bridges where team is the target."""
        api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Alpha to Beta",
                "created_by": "agent-1",
            }
        )
        resp = api.list_bridges_by_team("team-beta")
        assert resp.status == "ok"
        bridges = resp.data["bridges"]
        assert len(bridges) >= 1
        assert any(b["target_team_id"] == "team-beta" for b in bridges)

    def test_list_bridges_empty_team(self, api):
        """Returns empty list for team with no bridges."""
        resp = api.list_bridges_by_team("team-nonexistent")
        assert resp.status == "ok"
        assert resp.data["bridges"] == []


# ---------------------------------------------------------------------------
# Test: bridge_audit
# ---------------------------------------------------------------------------


class TestBridgeAudit:
    """GET /api/v1/bridges/{bridge_id}/audit — audit trail."""

    def test_bridge_audit_empty(self, api):
        """New bridge has empty audit trail."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Audit test",
                "created_by": "agent-1",
            }
        )
        bridge_id = resp.data["bridge_id"]

        audit_resp = api.bridge_audit(bridge_id)
        assert audit_resp.status == "ok"
        assert audit_resp.data["bridge_id"] == bridge_id
        assert isinstance(audit_resp.data["entries"], list)
        assert audit_resp.data["total"] == 0

    def test_bridge_audit_not_found(self, api):
        """Audit for nonexistent bridge returns error."""
        resp = api.bridge_audit("no-such-bridge")
        assert resp.status == "error"
        assert "not found" in resp.error.lower()

    def test_bridge_audit_pagination(self, api):
        """Audit respects limit and offset parameters."""
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Pagination test",
                "created_by": "agent-1",
            }
        )
        bridge_id = resp.data["bridge_id"]

        audit_resp = api.bridge_audit(bridge_id, limit=5, offset=0)
        assert audit_resp.status == "ok"
        assert audit_resp.data["limit"] == 5
        assert audit_resp.data["offset"] == 0


# ---------------------------------------------------------------------------
# Test: full bridge lifecycle
# ---------------------------------------------------------------------------


class TestBridgeLifecycle:
    """Integration test: full bridge lifecycle through API."""

    def test_full_lifecycle(self, api):
        """Create → approve both sides → active → suspend → close."""
        # Step 1: Create
        create_resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Full lifecycle test",
                "permissions": {
                    "read_paths": ["workspaces/dm/*"],
                    "message_types": ["review_request"],
                },
                "created_by": "agent-1",
            }
        )
        assert create_resp.status == "ok"
        bridge_id = create_resp.data["bridge_id"]
        assert create_resp.data["status"] == "pending"

        # Step 2: Approve source
        src_resp = api.approve_bridge(bridge_id, "source", "team-alpha-lead-1")
        assert src_resp.status == "ok"
        assert src_resp.data["approved_by_source"] == "team-alpha-lead-1"
        assert src_resp.data["status"] == "pending"

        # Step 3: Approve target → ACTIVE
        tgt_resp = api.approve_bridge(bridge_id, "target", "team-beta-lead-1")
        assert tgt_resp.status == "ok"
        assert tgt_resp.data["status"] == "active"

        # Step 4: Verify detail
        detail_resp = api.get_bridge(bridge_id)
        assert detail_resp.status == "ok"
        assert detail_resp.data["status"] == "active"
        assert detail_resp.data["approved_by_source"] == "team-alpha-lead-1"
        assert detail_resp.data["approved_by_target"] == "team-beta-lead-1"

        # Step 5: Suspend
        susp_resp = api.suspend_bridge_action(bridge_id, "Security audit")
        assert susp_resp.status == "ok"
        assert susp_resp.data["status"] == "suspended"

        # Step 6: Close
        close_resp = api.close_bridge_action(bridge_id, "Audit complete")
        assert close_resp.status == "ok"
        assert close_resp.data["status"] == "closed"

        # Step 7: Verify final state
        final_resp = api.get_bridge(bridge_id)
        assert final_resp.status == "ok"
        assert final_resp.data["status"] == "closed"

    def test_bridge_appears_in_team_list(self, api):
        """Created bridge appears in both teams' bridge lists."""
        api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "team-alpha",
                "target_team_id": "team-beta",
                "purpose": "Team list test",
                "created_by": "agent-1",
            }
        )

        alpha_resp = api.list_bridges_by_team("team-alpha")
        beta_resp = api.list_bridges_by_team("team-beta")
        assert alpha_resp.status == "ok"
        assert beta_resp.status == "ok"
        assert len(alpha_resp.data["bridges"]) >= 1
        assert len(beta_resp.data["bridges"]) >= 1


# ---------------------------------------------------------------------------
# Test: backward compatibility
# ---------------------------------------------------------------------------


class TestBridgeAPIBackwardCompat:
    """Bridge endpoints return errors when bridge_manager not provided."""

    def test_create_bridge_no_manager(self, registry, approval_queue, cost_tracker):
        """create_bridge returns error when no bridge_manager."""
        api = PactAPI(
            registry=registry,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
        )
        resp = api.create_bridge(
            {
                "bridge_type": "standing",
                "source_team_id": "a",
                "target_team_id": "b",
                "purpose": "test",
            }
        )
        assert resp.status == "error"
        assert "bridge_manager" in resp.error.lower()

    def test_get_bridge_no_manager(self, registry, approval_queue, cost_tracker):
        """get_bridge returns error when no bridge_manager."""
        api = PactAPI(
            registry=registry,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
        )
        resp = api.get_bridge("any-id")
        assert resp.status == "error"
        assert "bridge_manager" in resp.error.lower()

    def test_list_bridges_by_team_no_manager(self, registry, approval_queue, cost_tracker):
        """list_bridges_by_team returns error when no bridge_manager."""
        api = PactAPI(
            registry=registry,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
        )
        resp = api.list_bridges_by_team("team-alpha")
        assert resp.status == "error"
        assert "bridge_manager" in resp.error.lower()

    def test_bridge_audit_no_manager(self, registry, approval_queue, cost_tracker):
        """bridge_audit returns error when no bridge_manager."""
        api = PactAPI(
            registry=registry,
            approval_queue=approval_queue,
            cost_tracker=cost_tracker,
        )
        resp = api.bridge_audit("any-id")
        assert resp.status == "error"
        assert "bridge_manager" in resp.error.lower()
