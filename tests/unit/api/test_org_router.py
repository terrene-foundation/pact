# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Tests for the org API router (TODO-16).

Covers: GET /api/v1/org/structure, POST /api/v1/org/deploy,
error handling, and engine lifecycle.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pact_platform.use.api.routers.org import router, set_engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app() -> FastAPI:
    """Create a minimal FastAPI app with the org router."""
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _make_mock_node(
    address: str = "D1-R1",
    node_type: str = "role",
    name: str = "Test Role",
    parent_address: str | None = "D1",
    role_id: str | None = "role-1",
) -> MagicMock:
    node = MagicMock()
    node.address = address
    node.type = node_type
    node.name = name
    node.parent_address = parent_address
    node.role_id = role_id
    return node


def _make_mock_org(org_id: str = "test-org", nodes: dict | None = None) -> MagicMock:
    org = MagicMock()
    org.org_id = org_id
    # CompiledOrg.nodes is dict[str, OrgNode]
    if nodes is None:
        n1 = _make_mock_node("D1-R1", "role", "Dean")
        n2 = _make_mock_node("D1-R1-T1-R1", "role", "Chair")
        nodes = {"D1-R1": n1, "D1-R1-T1-R1": n2}
    org.nodes = nodes
    return org


def _make_mock_engine(org: MagicMock | None = None) -> MagicMock:
    engine = MagicMock()
    engine.get_org.return_value = org or _make_mock_org()
    return engine


# ---------------------------------------------------------------------------
# GET /api/v1/org/structure
# ---------------------------------------------------------------------------


class TestGetOrgStructure:
    def test_returns_org_tree(self, client: TestClient) -> None:
        engine = _make_mock_engine()
        set_engine(engine)
        try:
            resp = client.get("/api/v1/org/structure")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["data"]["org_name"] == "test-org"
            assert data["data"]["node_count"] == 2
            assert len(data["data"]["nodes"]) == 2
            assert data["data"]["nodes"][0]["address"] == "D1-R1"
        finally:
            set_engine(None)

    def test_503_when_no_engine(self, client: TestClient) -> None:
        set_engine(None)
        resp = client.get("/api/v1/org/structure")
        assert resp.status_code == 503

    def test_500_on_engine_error(self, client: TestClient) -> None:
        engine = MagicMock()
        engine.get_org.side_effect = RuntimeError("boom")
        set_engine(engine)
        try:
            resp = client.get("/api/v1/org/structure")
            assert resp.status_code == 500
        finally:
            set_engine(None)


# ---------------------------------------------------------------------------
# POST /api/v1/org/deploy
# ---------------------------------------------------------------------------


class TestDeployOrg:
    def test_rejects_missing_yaml(self, client: TestClient) -> None:
        resp = client.post("/api/v1/org/deploy", json={})
        assert resp.status_code == 400
        assert "yaml" in resp.json()["detail"].lower()

    def test_rejects_non_string_yaml(self, client: TestClient) -> None:
        resp = client.post("/api/v1/org/deploy", json={"yaml": 123})
        assert resp.status_code == 400

    def test_rejects_invalid_yaml(self, client: TestClient) -> None:
        resp = client.post("/api/v1/org/deploy", json={"yaml": "{{invalid"})
        # YAML parsing of "{{invalid" may succeed (as string) or fail,
        # but the endpoint should not crash
        assert resp.status_code in (400, 501)

    def test_rejects_oversized_yaml(self, client: TestClient) -> None:
        big_yaml = "x: " + "a" * 2_000_000
        resp = client.post("/api/v1/org/deploy", json={"yaml": big_yaml})
        assert resp.status_code == 413

    def test_successful_deploy_with_minimal_yaml(self, client: TestClient) -> None:
        """Integration test with a minimal valid org YAML."""
        try:
            from pact.governance import GovernanceEngine  # noqa: F401
        except ImportError:
            pytest.skip("kailash-pact not available")

        yaml_str = (
            "org_id: test-deploy\n"
            "name: Test Deploy Org\n"
            "departments:\n"
            "  - id: dept-eng\n"
            "    name: Engineering\n"
            "roles:\n"
            "  - id: eng-lead\n"
            "    name: Engineering Lead\n"
            "    heads: dept-eng\n"
        )

        resp = client.post("/api/v1/org/deploy", json={"yaml": yaml_str})
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["status"] == "ok"
        assert data["data"]["compiled_nodes"] > 0
        assert data["data"]["org_id"] == "test-deploy"

        # Subsequent GET /structure should return the deployed org
        resp2 = client.get("/api/v1/org/structure")
        assert resp2.status_code == 200
        assert resp2.json()["data"]["org_name"] == "test-deploy"

        # Clean up
        set_engine(None)


# ---------------------------------------------------------------------------
# POST /api/v1/org/bridges/approve (TODO-10 L3 wiring)
# ---------------------------------------------------------------------------


class TestBridgeLCAApproval:
    def test_approve_bridge_503_when_no_engine(self, client: TestClient) -> None:
        set_engine(None)
        resp = client.post(
            "/api/v1/org/bridges/approve",
            json={
                "source_address": "D1-R1",
                "target_address": "D1-R1-T1-R1",
                "approver_address": "D1-R1",
            },
        )
        assert resp.status_code == 503

    def test_approve_bridge_400_missing_fields(self, client: TestClient) -> None:
        engine = _make_mock_engine()
        set_engine(engine)
        try:
            resp = client.post("/api/v1/org/bridges/approve", json={"source_address": "D1-R1"})
            assert resp.status_code == 400
        finally:
            set_engine(None)

    def test_approve_bridge_success(self, client: TestClient) -> None:
        engine = _make_mock_engine()
        mock_approval = MagicMock()
        mock_approval.source_address = "D1-R1"
        mock_approval.target_address = "D1-R1-T1-R1"
        mock_approval.approved_by = "D1-R1"
        mock_approval.approved_at = "2026-03-31T00:00:00"
        mock_approval.expires_at = "2026-04-01T00:00:00"
        engine.approve_bridge.return_value = mock_approval
        set_engine(engine)
        try:
            resp = client.post(
                "/api/v1/org/bridges/approve",
                json={
                    "source_address": "D1-R1",
                    "target_address": "D1-R1-T1-R1",
                    "approver_address": "D1-R1",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["data"]["source_address"] == "D1-R1"
            assert data["data"]["approved_by"] == "D1-R1"
            engine.approve_bridge.assert_called_once_with("D1-R1", "D1-R1-T1-R1", "D1-R1")
        finally:
            set_engine(None)


# ---------------------------------------------------------------------------
# POST /api/v1/org/roles/{role_address}/designate-acting (TODO-11)
# ---------------------------------------------------------------------------


class TestVacancyDesignation:
    def test_designate_acting_503_when_no_engine(self, client: TestClient) -> None:
        set_engine(None)
        resp = client.post(
            "/api/v1/org/roles/D1-R1/designate-acting",
            json={"acting_role_address": "D1-R1-T1-R1", "designated_by": "D1-R1"},
        )
        assert resp.status_code == 503

    def test_designate_acting_400_missing_fields(self, client: TestClient) -> None:
        engine = _make_mock_engine()
        set_engine(engine)
        try:
            resp = client.post(
                "/api/v1/org/roles/D1-R1/designate-acting",
                json={"acting_role_address": "D1-R1-T1-R1"},
            )
            assert resp.status_code == 400
        finally:
            set_engine(None)

    def test_designate_acting_success(self, client: TestClient) -> None:
        engine = _make_mock_engine()
        mock_designation = MagicMock()
        mock_designation.vacant_role_address = "D1-R1"
        mock_designation.acting_role_address = "D1-R1-T1-R1"
        mock_designation.designated_by = "D1-R1"
        mock_designation.designated_at = "2026-03-31T00:00:00"
        mock_designation.expires_at = "2026-04-01T00:00:00"
        engine.designate_acting_occupant.return_value = mock_designation
        set_engine(engine)
        try:
            resp = client.post(
                "/api/v1/org/roles/D1-R1/designate-acting",
                json={"acting_role_address": "D1-R1-T1-R1", "designated_by": "D1-R1"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["data"]["vacant_role_address"] == "D1-R1"
            assert data["data"]["acting_role_address"] == "D1-R1-T1-R1"
        finally:
            set_engine(None)


# ---------------------------------------------------------------------------
# GET /api/v1/org/roles/{role_address}/vacancy (TODO-11)
# ---------------------------------------------------------------------------


class TestVacancyStatus:
    def test_vacancy_status_503_when_no_engine(self, client: TestClient) -> None:
        set_engine(None)
        resp = client.get("/api/v1/org/roles/D1-R1/vacancy")
        assert resp.status_code == 503

    def test_vacancy_status_404_no_designation(self, client: TestClient) -> None:
        engine = _make_mock_engine()
        engine.get_vacancy_designation.return_value = None
        set_engine(engine)
        try:
            resp = client.get("/api/v1/org/roles/D1-R1/vacancy")
            assert resp.status_code == 404
        finally:
            set_engine(None)

    def test_vacancy_status_success(self, client: TestClient) -> None:
        engine = _make_mock_engine()
        mock_designation = MagicMock()
        mock_designation.vacant_role_address = "D1-R1"
        mock_designation.acting_role_address = "D1-R1-T1-R1"
        mock_designation.designated_by = "D1-R1"
        mock_designation.designated_at = "2026-03-31T00:00:00"
        mock_designation.expires_at = "2026-04-01T00:00:00"
        engine.get_vacancy_designation.return_value = mock_designation
        set_engine(engine)
        try:
            resp = client.get("/api/v1/org/roles/D1-R1/vacancy")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["data"]["acting_role_address"] == "D1-R1-T1-R1"
        finally:
            set_engine(None)
