# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for path parameter ID validation in server.py endpoints (H3 from R1).

Validates that validate_record_id() is called at the top of every server.py
handler that accepts a path parameter. The routers already have this coverage
-- these tests fill the gap for the server.py endpoints defined directly in
create_app().

Tier 1 (Unit): Uses httpx.AsyncClient with ASGITransport. No external
dependencies.
"""

from __future__ import annotations

import os
import tempfile

import httpx
import pytest

# Override DATABASE_URL before any model imports
_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_dir}/test_server_id_val.db"

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api.server import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dev_config() -> EnvConfig:
    return EnvConfig(pact_dev_mode=True, pact_api_token="")


@pytest.fixture()
def app(dev_config: EnvConfig):
    import pact_platform.use.api.server as server_module

    old_default = server_module._default_api
    server_module._default_api = None
    application = create_app(env_config=dev_config)
    yield application
    server_module._default_api = old_default


@pytest.fixture()
async def client(app) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


# Malicious IDs that must be rejected with 400.
# NOTE: IDs containing slashes (e.g. "../../../etc/passwd", "path/traversal")
# are omitted because Starlette interprets slashes as path separators BEFORE
# the handler runs, resulting in a framework-level 404. Null bytes are omitted
# because httpx rejects them at the client level (InvalidURL). Both are safe
# -- the request never reaches the DB layer. We test handler-level rejection
# with characters that pass through the URL path but fail our regex.
MALICIOUS_IDS = [
    "'; DROP TABLE users;--",
    "id with spaces",
    'id"double_quote',
    "id;semicolon",
    "back\\slash",
]


# ---------------------------------------------------------------------------
# team_id validation
# ---------------------------------------------------------------------------


class TestTeamIdValidation:
    """Validate team_id path parameters in server.py endpoints."""

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_list_agents_rejects_invalid_team_id(
        self, client: httpx.AsyncClient, bad_id: str
    ):
        """GET /api/v1/teams/{team_id}/agents rejects invalid team_id."""
        resp = await client.get(f"/api/v1/teams/{bad_id}/agents")
        assert (
            resp.status_code == 400
        ), f"Expected 400 for team_id={bad_id!r}, got {resp.status_code}"

    async def test_list_agents_accepts_valid_team_id(self, client: httpx.AsyncClient):
        """GET /api/v1/teams/{team_id}/agents with valid ID gets past validation."""
        resp = await client.get("/api/v1/teams/valid-team-1/agents")
        # Should not be 400 -- may be 200 (empty list) or other non-400 status
        assert resp.status_code != 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_list_bridges_by_team_rejects_invalid_team_id(
        self, client: httpx.AsyncClient, bad_id: str
    ):
        """GET /api/v1/bridges/team/{team_id} rejects invalid team_id."""
        resp = await client.get(f"/api/v1/bridges/team/{bad_id}")
        assert (
            resp.status_code == 400
        ), f"Expected 400 for team_id={bad_id!r}, got {resp.status_code}"

    async def test_list_bridges_by_team_accepts_valid(self, client: httpx.AsyncClient):
        """GET /api/v1/bridges/team/{team_id} with valid ID passes validation."""
        resp = await client.get("/api/v1/bridges/team/team-alpha")
        assert resp.status_code != 400


# ---------------------------------------------------------------------------
# agent_id validation
# ---------------------------------------------------------------------------


class TestAgentIdValidation:
    """Validate agent_id path parameters in server.py endpoints."""

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_agent_status_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """GET /api/v1/agents/{agent_id}/status rejects invalid agent_id."""
        resp = await client.get(f"/api/v1/agents/{bad_id}/status")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_approve_action_rejects_invalid_agent_id(
        self, client: httpx.AsyncClient, bad_id: str
    ):
        """POST /api/v1/agents/{agent_id}/approve/{action_id} rejects invalid agent_id."""
        resp = await client.post(f"/api/v1/agents/{bad_id}/approve/valid-action?approver_id=admin")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_reject_action_rejects_invalid_agent_id(
        self, client: httpx.AsyncClient, bad_id: str
    ):
        """POST /api/v1/agents/{agent_id}/reject/{action_id} rejects invalid agent_id."""
        resp = await client.post(f"/api/v1/agents/{bad_id}/reject/valid-action?approver_id=admin")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_posture_history_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """GET /api/v1/agents/{agent_id}/posture-history rejects invalid agent_id."""
        resp = await client.get(f"/api/v1/agents/{bad_id}/posture-history")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_upgrade_evidence_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """GET /api/v1/agents/{agent_id}/upgrade-evidence rejects invalid agent_id."""
        resp = await client.get(f"/api/v1/agents/{bad_id}/upgrade-evidence")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_shadow_metrics_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """GET /api/v1/shadow/{agent_id}/metrics rejects invalid agent_id."""
        resp = await client.get(f"/api/v1/shadow/{bad_id}/metrics")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_shadow_report_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """GET /api/v1/shadow/{agent_id}/report rejects invalid agent_id."""
        resp = await client.get(f"/api/v1/shadow/{bad_id}/report")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_trust_chain_detail_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """GET /api/v1/trust-chains/{agent_id} rejects invalid agent_id."""
        resp = await client.get(f"/api/v1/trust-chains/{bad_id}")
        assert resp.status_code == 400

    async def test_agent_status_accepts_valid(self, client: httpx.AsyncClient):
        """GET /api/v1/agents/{agent_id}/status with valid ID passes validation."""
        resp = await client.get("/api/v1/agents/agent-001/status")
        assert resp.status_code != 400


# ---------------------------------------------------------------------------
# action_id validation
# ---------------------------------------------------------------------------


class TestActionIdValidation:
    """Validate action_id path parameters in server.py endpoints."""

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_approve_action_rejects_invalid_action_id(
        self, client: httpx.AsyncClient, bad_id: str
    ):
        """POST /api/v1/agents/{agent_id}/approve/{action_id} rejects invalid action_id."""
        resp = await client.post(f"/api/v1/agents/valid-agent/approve/{bad_id}?approver_id=admin")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_reject_action_rejects_invalid_action_id(
        self, client: httpx.AsyncClient, bad_id: str
    ):
        """POST /api/v1/agents/{agent_id}/reject/{action_id} rejects invalid action_id."""
        resp = await client.post(f"/api/v1/agents/valid-agent/reject/{bad_id}?approver_id=admin")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# bridge_id validation
# ---------------------------------------------------------------------------


class TestBridgeIdValidation:
    """Validate bridge_id path parameters in server.py endpoints."""

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_bridge_audit_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """GET /api/v1/bridges/{bridge_id}/audit rejects invalid bridge_id."""
        resp = await client.get(f"/api/v1/bridges/{bad_id}/audit")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_get_bridge_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """GET /api/v1/bridges/{bridge_id} rejects invalid bridge_id."""
        resp = await client.get(f"/api/v1/bridges/{bad_id}")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_approve_bridge_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """PUT /api/v1/bridges/{bridge_id}/approve rejects invalid bridge_id."""
        resp = await client.put(f"/api/v1/bridges/{bad_id}/approve?side=source&approver_id=admin")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_suspend_bridge_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """POST /api/v1/bridges/{bridge_id}/suspend rejects invalid bridge_id."""
        resp = await client.post(f"/api/v1/bridges/{bad_id}/suspend?reason=test")
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_close_bridge_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """POST /api/v1/bridges/{bridge_id}/close rejects invalid bridge_id."""
        resp = await client.post(f"/api/v1/bridges/{bad_id}/close?reason=test")
        assert resp.status_code == 400

    async def test_get_bridge_accepts_valid(self, client: httpx.AsyncClient):
        """GET /api/v1/bridges/{bridge_id} with valid ID passes validation."""
        resp = await client.get("/api/v1/bridges/bridge-001")
        assert resp.status_code != 400


# ---------------------------------------------------------------------------
# envelope_id validation
# ---------------------------------------------------------------------------


class TestEnvelopeIdValidation:
    """Validate envelope_id path parameters in server.py endpoints."""

    @pytest.mark.parametrize("bad_id", MALICIOUS_IDS)
    async def test_get_envelope_rejects_invalid(self, client: httpx.AsyncClient, bad_id: str):
        """GET /api/v1/envelopes/{envelope_id} rejects invalid envelope_id."""
        resp = await client.get(f"/api/v1/envelopes/{bad_id}")
        assert resp.status_code == 400

    async def test_get_envelope_accepts_valid(self, client: httpx.AsyncClient):
        """GET /api/v1/envelopes/{envelope_id} with valid ID passes validation."""
        resp = await client.get("/api/v1/envelopes/env-001")
        assert resp.status_code != 400
