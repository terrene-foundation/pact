# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for decision approve/reject TOCTOU defense via optimistic locking.

Verifies that the envelope_version field on AgenticDecision is used for
optimistic-locking concurrency control: approve and reject increment the
version, and concurrent modifications are detected via 409 Conflict.
"""

from __future__ import annotations

import httpx
import pytest

from pact_platform.build.config.env import EnvConfig
from pact_platform.use.api.server import create_app


@pytest.fixture()
def dev_config() -> EnvConfig:
    return EnvConfig(pact_dev_mode=True, pact_api_token="")


@pytest.fixture()
def app(dev_config: EnvConfig):
    import pact_platform.use.api.governance as gov_mod
    import pact_platform.use.api.server as server_module

    old_default = server_module._default_api
    server_module._default_api = None
    old_dev_frozen = gov_mod._dev_mode_frozen
    application = create_app(env_config=dev_config)
    yield application
    server_module._default_api = old_default
    gov_mod._dev_mode_frozen = old_dev_frozen


@pytest.fixture()
async def client(app) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


async def _create_pending_decision(client: httpx.AsyncClient) -> dict:
    """Helper: create an AgenticDecision record in pending status via db.express."""
    import uuid

    from pact_platform.models import db

    decision_id = f"dec-{uuid.uuid4().hex[:12]}"
    record = await db.express.create(
        "AgenticDecision",
        {
            "id": decision_id,
            "agent_address": "D1-R1",
            "action": "execute_trade",
            "decision_type": "governance_hold",
            "status": "pending",
            "reason_held": "Budget exceeds threshold",
            "constraint_dimension": "financial",
            "urgency": "high",
            "envelope_version": 0,
        },
    )
    return record


class TestApproveOptimisticLocking:
    """Approve endpoint uses envelope_version for optimistic locking."""

    async def test_approve_increments_envelope_version(self, client: httpx.AsyncClient):
        """Normal approve sets status to approved and increments envelope_version.

        State persistence verification: read back the record after approve to
        confirm the update was persisted correctly.
        """
        decision = await _create_pending_decision(client)
        decision_id = decision["id"]
        assert decision["envelope_version"] == 0

        resp = await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={"decided_by": "admin-1", "reason": "Within budget"},
        )
        assert resp.status_code == 200

        # State persistence: read back via GET to verify the update persisted
        get_resp = await client.get(f"/api/v1/decisions/{decision_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["status"] == "approved"
        assert data["envelope_version"] == 1
        assert data["decided_by"] == "admin-1"
        assert data["decision_reason"] == "Within budget"
        assert data["decided_at"] is not None

    async def test_approve_already_approved_returns_409(self, client: httpx.AsyncClient):
        """Approving a decision that was already approved returns 409 Conflict."""
        decision = await _create_pending_decision(client)
        decision_id = decision["id"]

        # First approve succeeds
        resp1 = await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={"decided_by": "admin-1", "reason": "OK"},
        )
        assert resp1.status_code == 200

        # Second approve hits 409 because status is no longer pending
        resp2 = await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={"decided_by": "admin-2", "reason": "Also OK"},
        )
        assert resp2.status_code == 409

    async def test_approve_already_rejected_returns_409(self, client: httpx.AsyncClient):
        """Approving a decision that was already rejected returns 409 Conflict."""
        decision = await _create_pending_decision(client)
        decision_id = decision["id"]

        # Reject first
        resp1 = await client.post(
            f"/api/v1/decisions/{decision_id}/reject",
            json={"decided_by": "admin-1", "reason": "Denied"},
        )
        assert resp1.status_code == 200

        # Approve attempt returns 409
        resp2 = await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={"decided_by": "admin-2", "reason": "Changed mind"},
        )
        assert resp2.status_code == 409

    async def test_approve_missing_decided_by_returns_400(self, client: httpx.AsyncClient):
        """Approve with missing decided_by still returns 400."""
        decision = await _create_pending_decision(client)
        decision_id = decision["id"]

        resp = await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={"reason": "OK"},
        )
        assert resp.status_code == 400


class TestRejectOptimisticLocking:
    """Reject endpoint uses envelope_version for optimistic locking."""

    async def test_reject_increments_envelope_version(self, client: httpx.AsyncClient):
        """Normal reject sets status to rejected and increments envelope_version.

        State persistence verification: read back the record after reject to
        confirm the update was persisted correctly.
        """
        decision = await _create_pending_decision(client)
        decision_id = decision["id"]
        assert decision["envelope_version"] == 0

        resp = await client.post(
            f"/api/v1/decisions/{decision_id}/reject",
            json={"decided_by": "admin-1", "reason": "Too risky"},
        )
        assert resp.status_code == 200

        # State persistence: read back via GET to verify the update persisted
        get_resp = await client.get(f"/api/v1/decisions/{decision_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["status"] == "rejected"
        assert data["envelope_version"] == 1
        assert data["decided_by"] == "admin-1"
        assert data["decision_reason"] == "Too risky"
        assert data["decided_at"] is not None

    async def test_reject_already_rejected_returns_409(self, client: httpx.AsyncClient):
        """Rejecting a decision that was already rejected returns 409 Conflict."""
        decision = await _create_pending_decision(client)
        decision_id = decision["id"]

        # First reject succeeds
        resp1 = await client.post(
            f"/api/v1/decisions/{decision_id}/reject",
            json={"decided_by": "admin-1", "reason": "Denied"},
        )
        assert resp1.status_code == 200

        # Second reject hits 409
        resp2 = await client.post(
            f"/api/v1/decisions/{decision_id}/reject",
            json={"decided_by": "admin-2", "reason": "Also denied"},
        )
        assert resp2.status_code == 409

    async def test_reject_already_approved_returns_409(self, client: httpx.AsyncClient):
        """Rejecting a decision that was already approved returns 409 Conflict."""
        decision = await _create_pending_decision(client)
        decision_id = decision["id"]

        # Approve first
        resp1 = await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={"decided_by": "admin-1", "reason": "OK"},
        )
        assert resp1.status_code == 200

        # Reject attempt returns 409
        resp2 = await client.post(
            f"/api/v1/decisions/{decision_id}/reject",
            json={"decided_by": "admin-2", "reason": "Changed mind"},
        )
        assert resp2.status_code == 409

    async def test_reject_missing_decided_by_returns_400(self, client: httpx.AsyncClient):
        """Reject with missing decided_by still returns 400."""
        decision = await _create_pending_decision(client)
        decision_id = decision["id"]

        resp = await client.post(
            f"/api/v1/decisions/{decision_id}/reject",
            json={"reason": "Denied"},
        )
        assert resp.status_code == 400


class TestNonexistentDecision:
    """404 for non-existent decision IDs."""

    async def test_approve_nonexistent_returns_404(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/decisions/does-not-exist/approve",
            json={"decided_by": "admin-1", "reason": "OK"},
        )
        assert resp.status_code == 404

    async def test_reject_nonexistent_returns_404(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/decisions/does-not-exist/reject",
            json={"decided_by": "admin-1", "reason": "Denied"},
        )
        assert resp.status_code == 404
