# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for enum field validation in server.py endpoints (H5 from R1).

Validates that string fields constrained to known values are rejected
when arbitrary strings are passed. Covers the ``side`` query parameter
in approve_bridge (server.py) and write-path enum fields in router
endpoints.

Tier 1 (Unit): Uses httpx.AsyncClient with ASGITransport. No external
dependencies.
"""

from __future__ import annotations

import httpx
import pytest

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


# ---------------------------------------------------------------------------
# approve_bridge side validation
# ---------------------------------------------------------------------------


class TestApproveBridgeSideValidation:
    """Validate 'side' query parameter in PUT /api/v1/bridges/{id}/approve."""

    async def test_approve_bridge_invalid_side_rejected(self, client: httpx.AsyncClient):
        """Invalid side value must be rejected with 400."""
        resp = await client.put("/api/v1/bridges/bridge-001/approve?side=INVALID&approver_id=admin")
        assert resp.status_code == 400

    async def test_approve_bridge_empty_side_rejected(self, client: httpx.AsyncClient):
        """Empty side value must be rejected with 400."""
        resp = await client.put("/api/v1/bridges/bridge-001/approve?side=&approver_id=admin")
        assert resp.status_code == 400

    async def test_approve_bridge_sql_injection_side(self, client: httpx.AsyncClient):
        """SQL injection in side must be rejected with 400."""
        resp = await client.put(
            "/api/v1/bridges/bridge-001/approve?side=source' OR '1'='1&approver_id=admin"
        )
        assert resp.status_code == 400

    async def test_approve_bridge_source_side_accepted(self, client: httpx.AsyncClient):
        """Valid side='source' passes validation (may fail downstream for other reasons)."""
        resp = await client.put("/api/v1/bridges/bridge-001/approve?side=source&approver_id=admin")
        # Should not be 400 -- may be a different error from downstream
        assert resp.status_code != 400

    async def test_approve_bridge_target_side_accepted(self, client: httpx.AsyncClient):
        """Valid side='target' passes validation (may fail downstream for other reasons)."""
        resp = await client.put("/api/v1/bridges/bridge-001/approve?side=target&approver_id=admin")
        assert resp.status_code != 400

    async def test_approve_bridge_case_sensitive(self, client: httpx.AsyncClient):
        """Side values are case-sensitive -- 'Source' is not valid."""
        resp = await client.put("/api/v1/bridges/bridge-001/approve?side=Source&approver_id=admin")
        assert resp.status_code == 400

    async def test_approve_bridge_side_both_rejected(self, client: httpx.AsyncClient):
        """'both' is not a valid side value."""
        resp = await client.put("/api/v1/bridges/bridge-001/approve?side=both&approver_id=admin")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# pool_type validation (create pool)
# ---------------------------------------------------------------------------


class TestPoolTypeValidation:
    """Validate pool_type field in POST /api/v1/pools."""

    async def test_create_pool_invalid_pool_type_rejected(self, client: httpx.AsyncClient):
        """Invalid pool_type must be rejected with 400."""
        resp = await client.post(
            "/api/v1/pools",
            json={
                "org_id": "org-1",
                "name": "Test Pool",
                "pool_type": "INVALID_TYPE",
            },
        )
        assert resp.status_code == 400

    async def test_create_pool_agent_type_accepted(self, client: httpx.AsyncClient):
        """pool_type='agent' is valid."""
        resp = await client.post(
            "/api/v1/pools",
            json={
                "org_id": "org-1",
                "name": "Agent Pool",
                "pool_type": "agent",
            },
        )
        assert resp.status_code in (201, 200)

    async def test_create_pool_human_type_accepted(self, client: httpx.AsyncClient):
        """pool_type='human' is valid."""
        resp = await client.post(
            "/api/v1/pools",
            json={
                "org_id": "org-1",
                "name": "Human Pool",
                "pool_type": "human",
            },
        )
        assert resp.status_code in (201, 200)

    async def test_create_pool_mixed_type_accepted(self, client: httpx.AsyncClient):
        """pool_type='mixed' is valid."""
        resp = await client.post(
            "/api/v1/pools",
            json={
                "org_id": "org-1",
                "name": "Mixed Pool",
                "pool_type": "mixed",
            },
        )
        assert resp.status_code in (201, 200)


# ---------------------------------------------------------------------------
# routing_strategy validation (create pool)
# ---------------------------------------------------------------------------


class TestRoutingStrategyValidation:
    """Validate routing_strategy field in POST /api/v1/pools."""

    async def test_create_pool_invalid_strategy_rejected(self, client: httpx.AsyncClient):
        """Invalid routing_strategy must be rejected with 400."""
        resp = await client.post(
            "/api/v1/pools",
            json={
                "org_id": "org-1",
                "name": "Test Pool",
                "routing_strategy": "random_chaos",
            },
        )
        assert resp.status_code == 400

    async def test_create_pool_round_robin_accepted(self, client: httpx.AsyncClient):
        """routing_strategy='round_robin' is valid."""
        resp = await client.post(
            "/api/v1/pools",
            json={
                "org_id": "org-1",
                "name": "RR Pool",
                "routing_strategy": "round_robin",
            },
        )
        assert resp.status_code in (201, 200)

    async def test_create_pool_least_busy_accepted(self, client: httpx.AsyncClient):
        """routing_strategy='least_busy' is valid."""
        resp = await client.post(
            "/api/v1/pools",
            json={
                "org_id": "org-1",
                "name": "LB Pool",
                "routing_strategy": "least_busy",
            },
        )
        assert resp.status_code in (201, 200)

    async def test_create_pool_capability_match_accepted(self, client: httpx.AsyncClient):
        """routing_strategy='capability_match' is valid."""
        resp = await client.post(
            "/api/v1/pools",
            json={
                "org_id": "org-1",
                "name": "CM Pool",
                "routing_strategy": "capability_match",
            },
        )
        assert resp.status_code in (201, 200)


# ---------------------------------------------------------------------------
# priority validation (create objective)
# ---------------------------------------------------------------------------


class TestPriorityValidation:
    """Validate priority field in POST /api/v1/objectives."""

    async def test_create_objective_invalid_priority_rejected(self, client: httpx.AsyncClient):
        """Invalid priority must be rejected with 400."""
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
                "title": "Test Objective",
                "priority": "ULTRA_MEGA_HIGH",
            },
        )
        assert resp.status_code == 400

    async def test_create_objective_low_priority_accepted(self, client: httpx.AsyncClient):
        """priority='low' is valid."""
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
                "title": "Low Priority Obj",
                "priority": "low",
            },
        )
        assert resp.status_code in (201, 200)

    async def test_create_objective_normal_priority_accepted(self, client: httpx.AsyncClient):
        """priority='normal' is valid."""
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
                "title": "Normal Priority Obj",
                "priority": "normal",
            },
        )
        assert resp.status_code in (201, 200)

    async def test_create_objective_high_priority_accepted(self, client: httpx.AsyncClient):
        """priority='high' is valid."""
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
                "title": "High Priority Obj",
                "priority": "high",
            },
        )
        assert resp.status_code in (201, 200)

    async def test_create_objective_critical_priority_accepted(self, client: httpx.AsyncClient):
        """priority='critical' is valid."""
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
                "title": "Critical Priority Obj",
                "priority": "critical",
            },
        )
        assert resp.status_code in (201, 200)


# ---------------------------------------------------------------------------
# status validation (create objective)
# ---------------------------------------------------------------------------


class TestObjectiveStatusValidation:
    """Validate status field in POST /api/v1/objectives."""

    async def test_create_objective_invalid_status_rejected(self, client: httpx.AsyncClient):
        """Invalid status must be rejected with 400."""
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
                "title": "Test Objective",
                "status": "SUPERDRAFT",
            },
        )
        assert resp.status_code == 400

    async def test_create_objective_draft_status_accepted(self, client: httpx.AsyncClient):
        """status='draft' is valid."""
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
                "title": "Draft Obj",
                "status": "draft",
            },
        )
        assert resp.status_code in (201, 200)
