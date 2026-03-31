# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for governance gate integration in work management routers.

Verifies that mutation endpoints (create_objective, submit_request,
update_objective) route through governance_gate() before persisting.

Tier 1 (Unit): Tests the gate in dev mode (no real GovernanceEngine).
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import Any

import httpx
import pytest

# Override DATABASE_URL before any model imports
_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_dir}/test_gov_gate.db"

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api import governance as gov_mod
from pact_platform.use.api.server import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dev_config() -> EnvConfig:
    return EnvConfig(pact_dev_mode=True, pact_api_token="")


@pytest.fixture()
def prod_config() -> EnvConfig:
    return EnvConfig(pact_dev_mode=False, pact_api_token="test-token-12345678")


@pytest.fixture()
def app(dev_config: EnvConfig):
    import pact_platform.use.api.server as server_module

    old_default = server_module._default_api
    server_module._default_api = None
    old_engine = gov_mod._engine
    old_dev = gov_mod._dev_mode
    old_dev_frozen = gov_mod._dev_mode_frozen
    application = create_app(env_config=dev_config)
    yield application
    server_module._default_api = old_default
    gov_mod._engine = old_engine
    gov_mod._dev_mode = old_dev
    gov_mod._dev_mode_frozen = old_dev_frozen


@pytest.fixture()
async def client(app) -> httpx.AsyncClient:  # type: ignore[misc]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Mock governance verdict
# ---------------------------------------------------------------------------


@dataclass
class MockVerdict:
    level: str
    reason: str
    envelope_version: int = 0


class MockEngine:
    """Mock GovernanceEngine that returns configurable verdicts."""

    def __init__(self, default_level: str = "auto_approved") -> None:
        self._default_level = default_level
        self._calls: list[dict[str, Any]] = []

    def verify_action(
        self,
        role_address: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> MockVerdict:
        self._calls.append({"role_address": role_address, "action": action, "context": context})
        return MockVerdict(level=self._default_level, reason=f"mock-{self._default_level}")


# ---------------------------------------------------------------------------
# Test: Dev mode allows without engine
# ---------------------------------------------------------------------------


class TestDevModeNoEngine:
    """In dev mode with no engine, mutations should proceed."""

    async def test_create_objective_allowed(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/objectives",
            json={
                "org_address": "D1-R1",
                "title": "Test Objective",
                "budget_usd": 100.0,
            },
        )
        assert resp.status_code == 201

    async def test_submit_request_allowed(self, client: httpx.AsyncClient) -> None:
        # Create an objective first
        obj_resp = await client.post(
            "/api/v1/objectives",
            json={"org_address": "D1-R1", "title": "Parent Obj"},
        )
        assert obj_resp.status_code == 201
        obj_id = obj_resp.json()["id"]

        resp = await client.post(
            "/api/v1/requests",
            json={"objective_id": obj_id, "title": "Test Request"},
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Test: Engine with AUTO_APPROVED allows
# ---------------------------------------------------------------------------


class TestEngineAutoApproved:
    """With an engine returning auto_approved, mutations succeed."""

    async def test_create_objective_approved(self, client: httpx.AsyncClient) -> None:
        engine = MockEngine("auto_approved")
        gov_mod.set_engine(engine)
        try:
            resp = await client.post(
                "/api/v1/objectives",
                json={
                    "org_address": "D1-R1",
                    "title": "Approved Objective",
                    "budget_usd": 50.0,
                },
            )
            assert resp.status_code == 201
            # Verify governance was called
            assert len(engine._calls) == 1
            assert engine._calls[0]["role_address"] == "D1-R1"
            assert engine._calls[0]["action"] == "create_objective"
            assert engine._calls[0]["context"]["cost"] == 50.0
        finally:
            gov_mod.set_engine(None)


# ---------------------------------------------------------------------------
# Test: Engine with BLOCKED rejects
# ---------------------------------------------------------------------------


class TestEngineBlocked:
    """With an engine returning blocked, mutations are rejected with 403."""

    async def test_create_objective_blocked(self, client: httpx.AsyncClient) -> None:
        engine = MockEngine("blocked")
        gov_mod.set_engine(engine)
        try:
            resp = await client.post(
                "/api/v1/objectives",
                json={
                    "org_address": "D1-R1",
                    "title": "Blocked Objective",
                },
            )
            assert resp.status_code == 403
            assert "blocked by governance" in resp.json()["detail"].lower()
        finally:
            gov_mod.set_engine(None)

    async def test_update_objective_blocked(self, client: httpx.AsyncClient) -> None:
        # First create in dev mode (no engine)
        gov_mod.set_engine(None)
        resp = await client.post(
            "/api/v1/objectives",
            json={"org_address": "D1-R1", "title": "To Update"},
        )
        assert resp.status_code == 201
        obj_id = resp.json()["id"]

        # Now block updates
        engine = MockEngine("blocked")
        gov_mod.set_engine(engine)
        try:
            resp = await client.put(
                f"/api/v1/objectives/{obj_id}",
                json={"budget_usd": 999.0},
            )
            assert resp.status_code == 403
        finally:
            gov_mod.set_engine(None)


# ---------------------------------------------------------------------------
# Test: Engine with HELD creates decision
# ---------------------------------------------------------------------------


class TestEngineHeld:
    """With an engine returning held, a decision record is created."""

    async def test_create_objective_held(self, client: httpx.AsyncClient) -> None:
        engine = MockEngine("held")
        gov_mod.set_engine(engine)
        try:
            resp = await client.post(
                "/api/v1/objectives",
                json={
                    "org_address": "D1-R1",
                    "title": "Held Objective",
                },
            )
            # HELD returns 202 Accepted with decision info (not 201 created)
            assert resp.status_code == 202
            data = resp.json()
            assert data["status"] == "held"
            assert "decision_id" in data
            assert data["decision_id"].startswith("dec-")

            # Verify the decision record was persisted
            dec_resp = await client.get(f"/api/v1/decisions/{data['decision_id']}")
            assert dec_resp.status_code == 200
            dec = dec_resp.json()
            assert dec["status"] == "pending"
            assert dec["agent_address"] == "D1-R1"
            assert dec["action"] == "create_objective"
        finally:
            gov_mod.set_engine(None)


# ---------------------------------------------------------------------------
# Test: Production mode without engine blocks
# ---------------------------------------------------------------------------


class TestProdModeNoEngine:
    """In production mode with no engine, mutations are blocked (503)."""

    async def test_create_objective_503(self, prod_config: EnvConfig) -> None:
        import pact_platform.use.api.server as server_module

        old_default = server_module._default_api
        server_module._default_api = None
        old_engine = gov_mod._engine
        old_dev = gov_mod._dev_mode
        old_dev_frozen = gov_mod._dev_mode_frozen

        try:
            application = create_app(env_config=prod_config)
            gov_mod.set_engine(None)  # Ensure no engine
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://test",
                headers={"Authorization": "Bearer test-token-12345678"},
            ) as c:
                resp = await c.post(
                    "/api/v1/objectives",
                    json={"org_address": "D1-R1", "title": "Should fail"},
                )
                assert resp.status_code == 503
                assert "not initialized" in resp.json()["detail"].lower()
        finally:
            server_module._default_api = old_default
            gov_mod._engine = old_engine
            gov_mod._dev_mode = old_dev
            gov_mod._dev_mode_frozen = old_dev_frozen
