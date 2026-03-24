# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for work management API routers.

Tests the 7 new routers: objectives, requests, sessions, decisions,
pools, reviews, and metrics.
"""

from __future__ import annotations

import os
import tempfile

import httpx
import pytest

# Override DATABASE_URL before any model imports
_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_dir}/test_api.db"

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api.server import create_app


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


class TestObjectivesRouter:
    async def test_create_objective(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
                "title": "Test Objective",
                "budget_usd": 1000.0,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Objective"
        assert "id" in data

    async def test_list_objectives(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/objectives")
        assert resp.status_code == 200

    async def test_create_requires_title(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
            },
        )
        assert resp.status_code == 400


class TestRequestsRouter:
    async def test_submit_request(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/requests",
            json={
                "objective_id": "obj-1",
                "title": "Test Request",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Test Request"

    async def test_list_requests(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/requests")
        assert resp.status_code == 200


class TestDecisionsRouter:
    async def test_list_decisions(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/decisions")
        assert resp.status_code == 200

    async def test_get_decision_stats(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/decisions/stats")
        assert resp.status_code == 200
        assert "stats" in resp.json()


class TestPoolsRouter:
    async def test_create_pool(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/pools",
            json={
                "org_id": "org-1",
                "name": "Test Pool",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Test Pool"

    async def test_list_pools(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/pools")
        assert resp.status_code == 200


class TestSessionsRouter:
    async def test_list_sessions(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/sessions")
        assert resp.status_code == 200


class TestReviewsRouter:
    async def test_list_reviews(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/reviews")
        assert resp.status_code == 200


class TestMetricsRouter:
    async def test_cost_metrics(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/platform/metrics/cost")
        assert resp.status_code == 200

    async def test_throughput_metrics(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/platform/metrics/throughput")
        assert resp.status_code == 200

    async def test_governance_metrics(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/platform/metrics/governance")
        assert resp.status_code == 200

    async def test_budget_metrics(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/platform/metrics/budget")
        assert resp.status_code == 200
