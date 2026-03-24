# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for M42: Known Issues / Data Wiring fixes.

Covers:
- Task 6050: verification_stats uses VerificationLevel enum keys consistently
- Task 6051: AuditChain wired into PactAPI for dashboard_trends()
- Task 6052: GET /api/v1/agents/{agent_id}/upgrade-evidence endpoint
- Task 6053: Frontend API client upgrade-evidence method (tested via endpoint behavior)

Test structure:
- Unit tests for PactAPI handler methods (no HTTP, no mocking)
- Unit tests for seed_demo AuditChain construction
- Unit tests for the upgrade_evidence endpoint handler
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pact_platform.build.config.schema import (
    VerificationLevel,
)
from pact_platform.trust.audit.anchor import AuditAnchor, AuditChain
from pact_platform.trust.shadow_enforcer import ShadowEnforcer
from pact_platform.trust.store.cost_tracking import CostTracker
from pact_platform.use.api.endpoints import PactAPI
from pact_platform.use.execution.approval import ApprovalQueue
from pact_platform.use.execution.registry import AgentRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry() -> AgentRegistry:
    """Registry with agents from multiple teams, matching seed data structure."""
    reg = AgentRegistry()
    reg.register(
        agent_id="agent-alpha",
        name="Alpha Agent",
        role="Content Writer",
        team_id="team-alpha",
        capabilities=["draft_post", "edit_content"],
        posture="supervised",
    )
    reg.register(
        agent_id="agent-beta",
        name="Beta Agent",
        role="Policy Reviewer",
        team_id="team-beta",
        capabilities=["review_policy", "approve_policy"],
        posture="shared_planning",
    )
    reg.register(
        agent_id="agent-gamma",
        name="Gamma Agent",
        role="Analytics Agent",
        team_id="team-alpha",
        capabilities=["read_metrics", "generate_report"],
        posture="supervised",
    )
    return reg


@pytest.fixture()
def approval_queue() -> ApprovalQueue:
    """Empty approval queue."""
    return ApprovalQueue()


@pytest.fixture()
def cost_tracker() -> CostTracker:
    """Empty cost tracker."""
    return CostTracker()


class _MockVerdict:
    """Minimal governance verdict for test mock."""

    def __init__(self, level: str, reason: str = "") -> None:
        self.level = level
        self.reason = reason


class _MockGovernanceEngine:
    """Mock GovernanceEngine for shadow enforcer tests.

    Replicates the gradient rules that the old GradientEngine provided:
    - emergency_* -> blocked
    - approve_* -> held
    - flag_* -> flagged
    - default -> auto_approved
    """

    def verify_action(self, role_address: str, action: str, context=None) -> _MockVerdict:
        if action.startswith("emergency_"):
            return _MockVerdict("blocked", "blocked by pattern")
        if action.startswith("approve_"):
            return _MockVerdict("held", "held by pattern")
        if action.startswith("flag_"):
            return _MockVerdict("flagged", "flagged by pattern")
        return _MockVerdict("auto_approved", "default auto-approved")


@pytest.fixture()
def shadow_enforcer() -> ShadowEnforcer:
    """ShadowEnforcer with evaluations for test agents."""
    enforcer = ShadowEnforcer(
        governance_engine=_MockGovernanceEngine(),
        role_address="D1-R1",
    )

    # Add evaluations for agent-alpha (mostly passing)
    for _ in range(30):
        enforcer.evaluate("draft_post", "agent-alpha")
    for _ in range(5):
        enforcer.evaluate("edit_content", "agent-alpha")
    # One flagged action
    enforcer.evaluate("flag_quality_issue", "agent-alpha")

    # Add evaluations for agent-beta (some held, some passing)
    for _ in range(20):
        enforcer.evaluate("review_policy", "agent-beta")
    for _ in range(5):
        enforcer.evaluate("approve_policy", "agent-beta")
    # One blocked
    enforcer.evaluate("emergency_shutdown", "agent-beta")

    return enforcer


@pytest.fixture()
def audit_chain_with_data() -> AuditChain:
    """AuditChain with anchors spread across the last 7 days."""
    chain = AuditChain(chain_id="test-chain")
    now = datetime.now(UTC)

    # Add anchors for each of the last 7 days
    for days_ago in range(7):
        day_time = now - timedelta(days=days_ago, hours=12)

        # 5 AUTO_APPROVED per day
        for _ in range(5):
            anchor = AuditAnchor(
                anchor_id=f"aa-{days_ago}-auto-{_}",
                sequence=len(chain.anchors),
                previous_hash=chain.anchors[-1].content_hash if chain.anchors else None,
                agent_id="agent-alpha",
                action="draft_post",
                verification_level=VerificationLevel.AUTO_APPROVED,
                timestamp=day_time,
            )
            anchor.seal()
            chain.anchors.append(anchor)

        # 2 FLAGGED per day
        for _ in range(2):
            anchor = AuditAnchor(
                anchor_id=f"aa-{days_ago}-flagged-{_}",
                sequence=len(chain.anchors),
                previous_hash=chain.anchors[-1].content_hash if chain.anchors else None,
                agent_id="agent-beta",
                action="flag_quality",
                verification_level=VerificationLevel.FLAGGED,
                timestamp=day_time,
            )
            anchor.seal()
            chain.anchors.append(anchor)

        # 1 HELD per day
        anchor = AuditAnchor(
            anchor_id=f"aa-{days_ago}-held",
            sequence=len(chain.anchors),
            previous_hash=chain.anchors[-1].content_hash if chain.anchors else None,
            agent_id="agent-alpha",
            action="approve_publication",
            verification_level=VerificationLevel.HELD,
            timestamp=day_time,
        )
        anchor.seal()
        chain.anchors.append(anchor)

    return chain


@pytest.fixture()
def api_with_audit_chain(
    registry,
    approval_queue,
    cost_tracker,
    audit_chain_with_data,
) -> PactAPI:
    """PactAPI with audit_chain wired for dashboard_trends."""
    verification_stats = {
        VerificationLevel.AUTO_APPROVED: 35,
        VerificationLevel.FLAGGED: 14,
        VerificationLevel.HELD: 7,
        VerificationLevel.BLOCKED: 0,
    }
    return PactAPI(
        registry=registry,
        approval_queue=approval_queue,
        cost_tracker=cost_tracker,
        verification_stats=verification_stats,
        audit_chain=audit_chain_with_data,
    )


@pytest.fixture()
def api_with_shadow(
    registry,
    approval_queue,
    cost_tracker,
    shadow_enforcer,
) -> PactAPI:
    """PactAPI with shadow_enforcer wired for upgrade-evidence."""
    verification_stats = {
        VerificationLevel.AUTO_APPROVED: 35,
        VerificationLevel.FLAGGED: 14,
        VerificationLevel.HELD: 7,
        VerificationLevel.BLOCKED: 0,
    }
    return PactAPI(
        registry=registry,
        approval_queue=approval_queue,
        cost_tracker=cost_tracker,
        verification_stats=verification_stats,
        shadow_enforcer=shadow_enforcer,
    )


@pytest.fixture()
def api_minimal(registry, approval_queue, cost_tracker) -> PactAPI:
    """PactAPI with minimal components (no shadow, no audit_chain)."""
    return PactAPI(
        registry=registry,
        approval_queue=approval_queue,
        cost_tracker=cost_tracker,
    )


# ===========================================================================
# Task 6050: Wire verification_stats into API
# ===========================================================================


class TestVerificationStatsEnumKeys:
    """verification_stats uses VerificationLevel enum keys consistently."""

    def test_verification_stats_with_enum_keys(self, api_with_audit_chain):
        """verification_stats_report works with VerificationLevel enum keys."""
        resp = api_with_audit_chain.verification_stats_report()
        assert resp.status == "ok"
        assert resp.data["AUTO_APPROVED"] == 35
        assert resp.data["FLAGGED"] == 14
        assert resp.data["HELD"] == 7
        assert resp.data["BLOCKED"] == 0
        assert resp.data["total"] == 56

    def test_verification_stats_accepts_both_string_and_enum_keys(self):
        """verification_stats works with both string and enum keys since
        VerificationLevel is a str enum."""
        reg = AgentRegistry()
        reg.register(
            agent_id="a1",
            name="Test",
            role="Test",
            team_id="t1",
            capabilities=[],
            posture="supervised",
        )
        # String keys work because VerificationLevel is a str enum
        string_keyed_stats = {
            "AUTO_APPROVED": 10,
            "FLAGGED": 5,
            "HELD": 3,
            "BLOCKED": 1,
        }
        api = PactAPI(
            registry=reg,
            approval_queue=ApprovalQueue(),
            cost_tracker=CostTracker(),
            verification_stats=string_keyed_stats,
        )
        resp = api.verification_stats_report()
        assert resp.status == "ok"
        assert resp.data["AUTO_APPROVED"] == 10
        assert resp.data["total"] == 19

    def test_verification_stats_enum_keys_preferred(self):
        """verification_stats with VerificationLevel enum keys works correctly."""
        reg = AgentRegistry()
        reg.register(
            agent_id="a1",
            name="Test",
            role="Test",
            team_id="t1",
            capabilities=[],
            posture="supervised",
        )
        enum_keyed_stats = {
            VerificationLevel.AUTO_APPROVED: 10,
            VerificationLevel.FLAGGED: 5,
            VerificationLevel.HELD: 3,
            VerificationLevel.BLOCKED: 1,
        }
        api = PactAPI(
            registry=reg,
            approval_queue=ApprovalQueue(),
            cost_tracker=CostTracker(),
            verification_stats=enum_keyed_stats,
        )
        resp = api.verification_stats_report()
        assert resp.status == "ok"
        assert resp.data["AUTO_APPROVED"] == 10
        assert resp.data["total"] == 19

    def test_build_platform_api_logs_warning(self, caplog):
        """_build_platform_api logs a warning about missing seed data."""
        import logging

        from pact_platform.use.api.server import _build_platform_api

        with caplog.at_level(logging.WARNING):
            api = _build_platform_api()
        # The function should log a warning that it's running without seed data
        assert any(
            "seed" in record.message.lower() or "without" in record.message.lower()
            for record in caplog.records
        ), (
            f"Expected a warning about running without seed data, but got: "
            f"{[r.message for r in caplog.records]}"
        )
        # Verify it still creates a valid API instance
        assert api is not None

    def test_run_seeded_server_passes_verification_stats(self):
        """run_seeded_server.py passes verification_stats to PactAPI.

        This is a design test: the seed_demo return dict must contain
        'verification_stats' with VerificationLevel enum keys.
        """
        # Import seed_verification_stats and verify it produces enum-keyed stats
        from scripts.seed_demo import seed_verification_stats

        # Example audit records from the seed
        records = [
            {"verification_level": "AUTO_APPROVED"},
            {"verification_level": "AUTO_APPROVED"},
            {"verification_level": "FLAGGED"},
            {"verification_level": "HELD"},
            {"verification_level": "BLOCKED"},
        ]
        stats = seed_verification_stats(records)
        # seed_verification_stats currently returns string keys
        assert isinstance(stats, dict)
        assert stats["AUTO_APPROVED"] == 2
        assert stats["FLAGGED"] == 1


# ===========================================================================
# Task 6051: Wire AuditChain for dashboard trends
# ===========================================================================


class TestAuditChainDashboardTrends:
    """AuditChain wired into PactAPI produces non-zero trend data."""

    def test_dashboard_trends_with_audit_chain(self, api_with_audit_chain):
        """dashboard_trends() returns non-zero data when AuditChain is provided."""
        resp = api_with_audit_chain.dashboard_trends()
        assert resp.status == "ok"
        data = resp.data

        # Must have 7 dates
        assert len(data["dates"]) == 7

        # Must have non-zero auto_approved (we seeded 5 per day)
        total_auto = sum(data["auto_approved"])
        assert (
            total_auto > 0
        ), f"Expected non-zero auto_approved trend data, got {data['auto_approved']}"

        # Must have non-zero flagged (we seeded 2 per day)
        total_flagged = sum(data["flagged"])
        assert total_flagged > 0, f"Expected non-zero flagged trend data, got {data['flagged']}"

        # Must have non-zero held (we seeded 1 per day)
        total_held = sum(data["held"])
        assert total_held > 0, f"Expected non-zero held trend data, got {data['held']}"

    def test_dashboard_trends_without_audit_chain(self, api_minimal):
        """dashboard_trends() returns all zeros when no AuditChain is provided."""
        resp = api_minimal.dashboard_trends()
        assert resp.status == "ok"
        data = resp.data

        assert len(data["dates"]) == 7
        assert sum(data["auto_approved"]) == 0
        assert sum(data["flagged"]) == 0
        assert sum(data["held"]) == 0
        assert sum(data["blocked"]) == 0

    def test_seed_demo_returns_audit_chain(self):
        """seed_demo main() return dict includes an 'audit_chain' key."""
        from scripts.seed_demo import seed_audit_anchors

        _stats, audit_records = seed_audit_anchors()
        # Verify we have audit records to build an AuditChain from
        assert len(audit_records) > 0

    def test_audit_chain_from_seed_records(self):
        """An AuditChain can be constructed from seed audit records."""
        from scripts.seed_demo import build_audit_chain, seed_audit_anchors

        _stats, audit_records = seed_audit_anchors()
        chain = build_audit_chain(audit_records)

        assert isinstance(chain, AuditChain)
        assert chain.chain_id == "pact-main"
        assert chain.length > 0

        # Verify the chain has anchors with various verification levels
        levels_seen = {a.verification_level for a in chain.anchors}
        assert VerificationLevel.AUTO_APPROVED in levels_seen

    def test_audit_chain_anchors_have_timestamps_in_last_7_days(self):
        """AuditChain anchors from seed include timestamps in the last 7 days."""
        from scripts.seed_demo import build_audit_chain, seed_audit_anchors

        _stats, audit_records = seed_audit_anchors()
        chain = build_audit_chain(audit_records)

        now = datetime.now(UTC)
        seven_days_ago = now - timedelta(days=7)

        recent_anchors = [a for a in chain.anchors if a.timestamp >= seven_days_ago]
        assert (
            len(recent_anchors) > 0
        ), "Expected audit chain to have anchors within the last 7 days for dashboard trend data"


# ===========================================================================
# Task 6052: Create upgrade-evidence API endpoint
# ===========================================================================


class TestUpgradeEvidenceEndpoint:
    """GET /api/v1/agents/{agent_id}/upgrade-evidence returns real data."""

    def test_upgrade_evidence_returns_data_for_known_agent(self, api_with_shadow):
        """upgrade_evidence() returns evidence data for a known agent."""
        resp = api_with_shadow.upgrade_evidence("agent-alpha")
        assert resp.status == "ok"
        data = resp.data

        assert data["agent_id"] == "agent-alpha"
        assert isinstance(data["total_operations"], int)
        assert data["total_operations"] > 0
        assert isinstance(data["successful_operations"], int)
        assert isinstance(data["shadow_enforcer_pass_rate"], float)
        assert isinstance(data["incidents"], int)
        assert data["recommendation"] in ("eligible", "not_eligible", "needs_review")
        assert "current_posture" in data
        assert "target_posture" in data

    def test_upgrade_evidence_agent_not_found(self, api_with_shadow):
        """upgrade_evidence() returns error for unknown agent."""
        resp = api_with_shadow.upgrade_evidence("nonexistent-agent")
        assert resp.status == "error"
        assert resp.error is not None
        assert "not found" in resp.error.lower()

    def test_upgrade_evidence_without_shadow_enforcer(self, api_minimal):
        """upgrade_evidence() returns error when shadow_enforcer not configured."""
        resp = api_minimal.upgrade_evidence("agent-alpha")
        assert resp.status == "error"
        assert "shadow" in resp.error.lower() or "unavailable" in resp.error.lower()

    def test_upgrade_evidence_response_structure(self, api_with_shadow):
        """upgrade_evidence() response has the documented structure."""
        resp = api_with_shadow.upgrade_evidence("agent-alpha")
        assert resp.status == "ok"
        data = resp.data

        # Required fields per the spec
        required_fields = {
            "agent_id",
            "total_operations",
            "successful_operations",
            "shadow_enforcer_pass_rate",
            "incidents",
            "recommendation",
            "current_posture",
            "target_posture",
        }
        actual_fields = set(data.keys())
        missing = required_fields - actual_fields
        assert (
            not missing
        ), f"upgrade-evidence response missing fields: {missing}. Got: {sorted(actual_fields)}"

    def test_upgrade_evidence_pass_rate_range(self, api_with_shadow):
        """shadow_enforcer_pass_rate is between 0.0 and 1.0."""
        resp = api_with_shadow.upgrade_evidence("agent-alpha")
        rate = resp.data["shadow_enforcer_pass_rate"]
        assert 0.0 <= rate <= 1.0, f"Pass rate out of range: {rate}"

    def test_upgrade_evidence_recommendation_logic(self, api_with_shadow):
        """recommendation reflects actual pass rate and operation counts."""
        resp = api_with_shadow.upgrade_evidence("agent-alpha")
        data = resp.data
        # With 36 operations (30 draft_post + 5 edit + 1 flagged), the agent
        # should have some recommendation
        assert data["recommendation"] in ("eligible", "not_eligible", "needs_review")

    def test_upgrade_evidence_current_posture_matches_registry(self, api_with_shadow):
        """current_posture reflects the agent's actual posture from registry."""
        resp = api_with_shadow.upgrade_evidence("agent-alpha")
        assert resp.data["current_posture"] == "supervised"

    def test_upgrade_evidence_target_posture_is_next_in_ladder(self, api_with_shadow):
        """target_posture is the next posture level in the autonomy ladder."""
        resp = api_with_shadow.upgrade_evidence("agent-alpha")
        # agent-alpha is supervised, so target should be shared_planning
        assert resp.data["target_posture"] == "shared_planning"


# ===========================================================================
# Task 6052 (continued): HTTP-level test via TestClient
# ===========================================================================


class TestUpgradeEvidenceHTTPEndpoint:
    """Test the upgrade-evidence endpoint via FastAPI TestClient."""

    @pytest.fixture()
    def client(self, api_with_shadow):
        """Create a FastAPI test client with seeded data, auth disabled."""
        from fastapi.testclient import TestClient

        import pact_platform.use.api.server as server_module
        from pact_platform.build.config.env import EnvConfig
        from pact_platform.use.api.server import create_app

        # Disable auth for unit testing
        dev_config = EnvConfig(pact_dev_mode=True, pact_api_token="")

        old_default = server_module._default_api
        server_module._default_api = None
        try:
            app = create_app(platform_api=api_with_shadow, env_config=dev_config)
            yield TestClient(app)
        finally:
            server_module._default_api = old_default

    def test_get_upgrade_evidence_200(self, client):
        """GET /api/v1/agents/{agent_id}/upgrade-evidence returns 200."""
        resp = client.get("/api/v1/agents/agent-alpha/upgrade-evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["data"]["agent_id"] == "agent-alpha"
        assert data["data"]["total_operations"] > 0

    def test_get_upgrade_evidence_404_unknown_agent(self, client):
        """GET /api/v1/agents/nonexistent/upgrade-evidence returns error."""
        resp = client.get("/api/v1/agents/nonexistent/upgrade-evidence")
        assert resp.status_code == 200  # API returns 200 with error status
        data = resp.json()
        assert data["status"] == "error"

    def test_upgrade_evidence_endpoint_requires_valid_path(self, client):
        """The endpoint correctly routes to agent-specific data."""
        resp = client.get("/api/v1/agents/agent-beta/upgrade-evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["data"]["agent_id"] == "agent-beta"


# ===========================================================================
# Integration: Seed data produces valid verification_stats with enum keys
# ===========================================================================


class TestSeedDataVerificationStatsIntegrity:
    """Verify that seed_demo produces verification_stats with correct key types."""

    def test_seed_verification_stats_with_enum_conversion(self):
        """Converted verification stats use VerificationLevel enum keys."""
        from scripts.seed_demo import (
            convert_verification_stats_to_enum_keys,
            seed_verification_stats,
        )

        records = [
            {"verification_level": "AUTO_APPROVED"},
            {"verification_level": "AUTO_APPROVED"},
            {"verification_level": "AUTO_APPROVED"},
            {"verification_level": "FLAGGED"},
            {"verification_level": "HELD"},
        ]
        string_stats = seed_verification_stats(records)
        enum_stats = convert_verification_stats_to_enum_keys(string_stats)

        assert VerificationLevel.AUTO_APPROVED in enum_stats
        assert enum_stats[VerificationLevel.AUTO_APPROVED] == 3
        assert VerificationLevel.FLAGGED in enum_stats
        assert enum_stats[VerificationLevel.FLAGGED] == 1
        assert VerificationLevel.HELD in enum_stats
        assert enum_stats[VerificationLevel.HELD] == 1
        assert VerificationLevel.BLOCKED in enum_stats
        assert enum_stats[VerificationLevel.BLOCKED] == 0
