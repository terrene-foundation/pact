# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for governance API routers: clearance, KSP, envelopes, access.

Tier 1 (Unit): Tests in dev mode (no real GovernanceEngine) verify that
endpoints accept valid input, reject invalid input, and return 503 when
no engine is configured.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

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
# Clearance Router
# ---------------------------------------------------------------------------


class TestClearanceRouter:
    """Tests for /api/v1/clearance endpoints."""

    async def test_grant_requires_role_address(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/clearance/grant",
            json={"level": "confidential"},
        )
        assert resp.status_code == 400
        assert "role_address" in resp.json()["detail"]

    async def test_grant_requires_level(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/clearance/grant",
            json={"role_address": "D1-R1"},
        )
        assert resp.status_code == 400
        assert "level" in resp.json()["detail"]

    async def test_grant_rejects_invalid_level(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/clearance/grant",
            json={"role_address": "D1-R1", "level": "mega_secret"},
        )
        assert resp.status_code == 400
        assert "Invalid clearance level" in resp.json()["detail"]

    async def test_grant_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        # In dev mode, governance_gate passes through, but the engine
        # call itself will fail since _engine is None.
        resp = await client.post(
            "/api/v1/clearance/grant",
            json={"role_address": "D1-R1", "level": "public"},
        )
        assert resp.status_code == 503

    async def test_revoke_requires_role_address(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/clearance/revoke",
            json={},
        )
        assert resp.status_code == 400

    async def test_revoke_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/clearance/revoke",
            json={"role_address": "D1-R1"},
        )
        assert resp.status_code == 503

    async def test_get_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/clearance/D1-R1")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# KSP Router
# ---------------------------------------------------------------------------


class TestKspRouter:
    """Tests for /api/v1/ksp endpoints."""

    async def test_create_requires_id(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/ksp",
            json={
                "source_address": "D1-R1",
                "target_address": "D2-R1",
                "max_classification": "restricted",
            },
        )
        assert resp.status_code == 400
        assert "id" in resp.json()["detail"]

    async def test_create_requires_addresses(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/ksp",
            json={"id": "ksp-1", "max_classification": "restricted"},
        )
        assert resp.status_code == 400

    async def test_create_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/ksp",
            json={
                "id": "ksp-test",
                "source_address": "D1-R1",
                "target_address": "D2-R1",
                "max_classification": "restricted",
            },
        )
        assert resp.status_code == 503

    async def test_list_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/ksp")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Envelopes Router
# ---------------------------------------------------------------------------


class TestEnvelopesRouter:
    """Tests for /api/v1/governance/envelopes endpoints."""

    async def test_get_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/governance/envelopes/D1-R1")
        assert resp.status_code == 503

    async def test_set_role_requires_defining_role(self, client: httpx.AsyncClient) -> None:
        resp = await client.put(
            "/api/v1/governance/envelopes/D1-R1/role",
            json={"envelope": {"id": "env-1"}},
        )
        assert resp.status_code == 400
        assert "defining_role_address" in resp.json()["detail"]

    async def test_set_role_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        resp = await client.put(
            "/api/v1/governance/envelopes/D1-R1/role",
            json={
                "defining_role_address": "D1-R1",
                "envelope": {"id": "env-1", "financial": {"max_spend_usd": 100.0}},
            },
        )
        assert resp.status_code == 503

    async def test_set_task_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        resp = await client.put(
            "/api/v1/governance/envelopes/D1-R1/task",
            json={
                "task_id": "task-001",
                "envelope": {"id": "env-1", "financial": {"max_spend_usd": 50.0}},
            },
        )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Access Router
# ---------------------------------------------------------------------------


class TestAccessRouter:
    """Tests for /api/v1/access endpoints."""

    async def test_check_requires_role_address(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/access/check",
            json={"item_id": "doc-1", "classification": "public", "owning_unit_address": "D1"},
        )
        assert resp.status_code == 400
        assert "role_address" in resp.json()["detail"]

    async def test_check_requires_item_id(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/access/check",
            json={"role_address": "D1-R1", "classification": "public", "owning_unit_address": "D1"},
        )
        assert resp.status_code == 400
        assert "item_id" in resp.json()["detail"]

    async def test_check_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/access/check",
            json={
                "role_address": "D1-R1",
                "item_id": "doc-finance-q4",
                "classification": "confidential",
                "owning_unit_address": "D2",
            },
        )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Bridge Consent (org router extension)
# ---------------------------------------------------------------------------


class TestBridgeConsent:
    """Tests for POST /api/v1/org/bridges/consent."""

    async def test_consent_requires_bridge_id(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/org/bridges/consent",
            json={"consenting_address": "D1-R1"},
        )
        assert resp.status_code == 400

    async def test_consent_requires_consenting_address(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/org/bridges/consent",
            json={"bridge_id": "br-123"},
        )
        assert resp.status_code == 400

    async def test_consent_returns_503_without_engine(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/org/bridges/consent",
            json={"bridge_id": "br-123", "consenting_address": "D1-R1"},
        )
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Validation edge cases (from RT30 testing-specialist review)
# ---------------------------------------------------------------------------


class TestValidationEdgeCases:
    """Cover validation branches not hit by basic happy-path tests."""

    async def test_clearance_grant_rejects_invalid_address(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/clearance/grant",
            json={"role_address": "not a valid address!!", "level": "public"},
        )
        assert resp.status_code == 400
        assert "address" in resp.json()["detail"].lower()

    async def test_ksp_create_rejects_invalid_classification(
        self, client: httpx.AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/v1/ksp",
            json={
                "id": "ksp-test",
                "source_address": "D1-R1",
                "target_address": "D2-R1",
                "max_classification": "ultra_secret",
            },
        )
        assert resp.status_code == 400
        assert "Invalid" in resp.json()["detail"]

    async def test_access_check_requires_classification(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/access/check",
            json={
                "role_address": "D1-R1",
                "item_id": "doc-1",
                "owning_unit_address": "D1",
            },
        )
        assert resp.status_code == 400
        assert "classification" in resp.json()["detail"]

    async def test_access_check_requires_owning_unit(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/access/check",
            json={
                "role_address": "D1-R1",
                "item_id": "doc-1",
                "classification": "public",
            },
        )
        assert resp.status_code == 400
        assert "owning_unit_address" in resp.json()["detail"]

    async def test_envelope_set_task_requires_task_id(self, client: httpx.AsyncClient) -> None:
        resp = await client.put(
            "/api/v1/governance/envelopes/D1-R1/task",
            json={"envelope": {"id": "e1"}},
        )
        assert resp.status_code == 400
        assert "task_id" in resp.json()["detail"]

    async def test_consent_bridge_validates_bridge_id_format(
        self, client: httpx.AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/v1/org/bridges/consent",
            json={"bridge_id": "../etc/passwd", "consenting_address": "D1-R1"},
        )
        assert resp.status_code == 400
