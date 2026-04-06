# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for governance hardening features (Issues #21-#25).

Tier 1 (Unit): Tests in dev mode verify endpoints accept valid input,
reject invalid input, and exercise the new models and services.

Covers:
- #21: Knowledge records (compartment persistence)
- #22: Clearance vetting FSM
- #23: Bootstrap mode
- #24: Task envelope lifecycle
- #25: Multi-approver decisions
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


# ===========================================================================
# Issue #21: Knowledge Records
# ===========================================================================


class TestKnowledgeRecordCRUD:
    """Test the knowledge record API endpoints."""

    @pytest.mark.anyio
    async def test_create_knowledge_record(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/knowledge",
            json={
                "item_id": "doc-finance-q4",
                "classification": "confidential",
                "owning_unit_address": "D1-R1",
                "compartments": ["finance", "audit"],
                "title": "Q4 Financial Report",
                "created_by": "admin",
            },
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        # Router returns the raw record or wraps it in {"status":"ok","data":{...}}
        record = data.get("data", data)
        assert record.get("item_id") == "doc-finance-q4"
        assert record.get("classification") == "confidential"

    @pytest.mark.anyio
    async def test_create_knowledge_record_invalid_classification(
        self, client: httpx.AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/v1/knowledge",
            json={
                "item_id": "doc-test",
                "classification": "ultra_secret",
                "owning_unit_address": "D1-R1",
            },
        )
        assert resp.status_code == 400
        assert "Invalid classification" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_list_knowledge_records(self, client: httpx.AsyncClient) -> None:
        # Create one first
        await client.post(
            "/api/v1/knowledge",
            json={
                "item_id": "doc-list-test",
                "classification": "public",
                "owning_unit_address": "D1-R1",
            },
        )
        resp = await client.get("/api/v1/knowledge")
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data

    @pytest.mark.anyio
    async def test_get_knowledge_record_by_item_id(self, client: httpx.AsyncClient) -> None:
        await client.post(
            "/api/v1/knowledge",
            json={
                "item_id": "doc-get-test",
                "classification": "restricted",
                "owning_unit_address": "D1-R1",
            },
        )
        resp = await client.get("/api/v1/knowledge/doc-get-test")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_missing_item_id(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/knowledge",
            json={
                "classification": "public",
                "owning_unit_address": "D1-R1",
            },
        )
        assert resp.status_code == 400


# ===========================================================================
# Issue #25: Multi-Approver Decisions
# ===========================================================================


class TestMultiApproverService:
    """Test the MultiApproverService independently."""

    @pytest.mark.anyio
    async def test_record_approval_and_count(self) -> None:
        from pact_platform.models import db
        from pact_platform.use.services.multi_approver import MultiApproverService

        service = MultiApproverService(db)

        # Create a decision first
        decision_id = "dec-test-multi-001"
        await db.express.create(
            "AgenticDecision",
            {
                "id": decision_id,
                "agent_address": "D1-R1",
                "action": "test_action",
                "status": "pending",
                "required_approvals": 2,
                "current_approvals": 0,
            },
        )

        # First approval
        result1 = await service.record_approval(
            decision_id=decision_id,
            approver_address="D1-R1-T1-R1",
            approver_identity="Approver 1",
            reason="Looks good",
        )
        assert result1["current_approvals"] == 1

        # Second approval (different approver)
        result2 = await service.record_approval(
            decision_id=decision_id,
            approver_address="D1-R1-T1-R2",
            approver_identity="Approver 2",
            reason="Approved",
        )
        assert result2["current_approvals"] == 2

    @pytest.mark.anyio
    async def test_duplicate_approval_rejected(self) -> None:
        from pact_platform.models import db
        from pact_platform.use.services.multi_approver import MultiApproverService

        service = MultiApproverService(db)

        decision_id = "dec-test-dup-001"
        await db.express.create(
            "AgenticDecision",
            {
                "id": decision_id,
                "agent_address": "D1-R1",
                "action": "test_action",
                "status": "pending",
                "required_approvals": 2,
            },
        )

        await service.record_approval(
            decision_id=decision_id,
            approver_address="D1-R1-T1-R1",
        )

        with pytest.raises(ValueError, match="already voted"):
            await service.record_approval(
                decision_id=decision_id,
                approver_address="D1-R1-T1-R1",
            )

    @pytest.mark.anyio
    async def test_list_approvals(self) -> None:
        from pact_platform.models import db
        from pact_platform.use.services.multi_approver import MultiApproverService

        service = MultiApproverService(db)

        decision_id = "dec-test-list-001"
        await db.express.create(
            "AgenticDecision",
            {
                "id": decision_id,
                "agent_address": "D1-R1",
                "action": "test_action",
                "status": "pending",
                "required_approvals": 3,
            },
        )

        await service.record_approval(
            decision_id=decision_id,
            approver_address="D1-R1-T1-R1",
        )
        await service.record_approval(
            decision_id=decision_id,
            approver_address="D1-R1-T1-R2",
        )

        records = await service.list_approvals(decision_id)
        assert len(records) == 2


class TestDecisionMultiApproverAPI:
    """Test the decisions API with multi-approver support."""

    @pytest.mark.anyio
    async def test_approve_single_approver(self, client: httpx.AsyncClient) -> None:
        """Single-approver decisions still work unchanged."""
        from pact_platform.models import db

        decision_id = "dec-single-001"
        await db.express.create(
            "AgenticDecision",
            {
                "id": decision_id,
                "agent_address": "D1-R1",
                "action": "test",
                "status": "pending",
                "reason_held": "test",
                "required_approvals": 1,
                "current_approvals": 0,
            },
        )

        resp = await client.post(
            f"/api/v1/decisions/{decision_id}/approve",
            json={"decided_by": "admin", "reason": "OK"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "approved"

    @pytest.mark.anyio
    async def test_list_decision_approvals_endpoint(self, client: httpx.AsyncClient) -> None:
        from pact_platform.models import db

        decision_id = "dec-listappr-001"
        await db.express.create(
            "AgenticDecision",
            {
                "id": decision_id,
                "agent_address": "D1-R1",
                "action": "test",
                "status": "pending",
                "required_approvals": 1,
            },
        )

        resp = await client.get(f"/api/v1/decisions/{decision_id}/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data
        assert data["decision_id"] == decision_id


# ===========================================================================
# Issue #22: Clearance Vetting FSM
# ===========================================================================


class TestClearanceVettingFSM:
    """Test the vetting workflow FSM endpoints."""

    @pytest.mark.anyio
    async def test_submit_vetting_request(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/vetting/submit",
            json={
                "role_address": "D1-R1",
                "level": "confidential",
                "requested_by": "admin",
            },
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["status"] == "ok"
        assert data["data"]["current_status"] == "pending"
        assert data["data"]["required_approvals"] == 1  # confidential = 1 approver

    @pytest.mark.anyio
    async def test_submit_secret_requires_2_approvers(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/vetting/submit",
            json={
                "role_address": "D1-R1",
                "level": "secret",
                "requested_by": "admin",
                "nda_signed": True,
            },
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["data"]["required_approvals"] == 2

    @pytest.mark.anyio
    async def test_submit_top_secret_requires_3_approvers(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/vetting/submit",
            json={
                "role_address": "D1-R1",
                "level": "top_secret",
                "requested_by": "admin",
                "nda_signed": True,
            },
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["data"]["required_approvals"] == 3

    @pytest.mark.anyio
    async def test_submit_invalid_level(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/vetting/submit",
            json={
                "role_address": "D1-R1",
                "level": "ultra_secret",
                "requested_by": "admin",
            },
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_reject_pending_vetting(self, client: httpx.AsyncClient) -> None:
        # Submit
        submit_resp = await client.post(
            "/api/v1/vetting/submit",
            json={
                "role_address": "D1-R1",
                "level": "restricted",
                "requested_by": "admin",
            },
        )
        vetting_id = submit_resp.json()["data"]["vetting_id"]

        # Reject
        resp = await client.post(
            f"/api/v1/vetting/{vetting_id}/reject",
            json={"rejector_address": "D1-R1-T1-R1", "reason": "Denied"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["current_status"] == "rejected"

    @pytest.mark.anyio
    async def test_list_vetting_requests(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/vetting")
        assert resp.status_code == 200
        assert "records" in resp.json()


# ===========================================================================
# Issue #24: Task Envelope Lifecycle
# ===========================================================================


class TestTaskEnvelopeLifecycle:
    """Test the task envelope lifecycle endpoints."""

    @pytest.mark.anyio
    async def test_create_task_envelope(self, client: httpx.AsyncClient) -> None:
        from datetime import UTC, datetime, timedelta

        expires = (datetime.now(UTC) + timedelta(hours=4)).isoformat()

        resp = await client.post(
            "/api/v1/governance/task-envelopes/create",
            json={
                "task_id": "task-001",
                "role_address": "D1-R1",
                "envelope_config": {
                    "id": "te-001",
                    "financial": {"max_budget": 500.0},
                },
                "expires_at": expires,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.anyio
    async def test_create_task_envelope_missing_expires(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/governance/task-envelopes/create",
            json={
                "task_id": "task-002",
                "role_address": "D1-R1",
                "envelope_config": {"id": "te-002"},
            },
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_task_envelope_past_expires(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/governance/task-envelopes/create",
            json={
                "task_id": "task-003",
                "role_address": "D1-R1",
                "envelope_config": {"id": "te-003"},
                "expires_at": "2020-01-01T00:00:00+00:00",
            },
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_acknowledge_task_envelope(self, client: httpx.AsyncClient) -> None:
        from datetime import UTC, datetime, timedelta

        from pact_platform.models import db

        record_id = "ter-ack-001"
        await db.express.create(
            "TaskEnvelopeRecord",
            {
                "id": record_id,
                "task_id": "task-ack",
                "role_address": "D1-R1",
                "status": "active",
                "expires_at": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
            },
        )

        resp = await client.post(
            "/api/v1/governance/task-envelopes/D1-R1/task-ack/acknowledge",
            json={"acknowledged_by": "agent-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "acknowledged"

    @pytest.mark.anyio
    async def test_reject_task_envelope(self, client: httpx.AsyncClient) -> None:
        from datetime import UTC, datetime, timedelta

        from pact_platform.models import db

        record_id = "ter-rej-001"
        await db.express.create(
            "TaskEnvelopeRecord",
            {
                "id": record_id,
                "task_id": "task-rej",
                "role_address": "D1-R1",
                "status": "active",
                "expires_at": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
            },
        )

        resp = await client.post(
            "/api/v1/governance/task-envelopes/D1-R1/task-rej/reject",
            json={"rejected_by": "agent-001", "reason": "Too restrictive"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "rejected"

    @pytest.mark.anyio
    async def test_list_active_task_envelopes(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/governance/task-envelopes/D1-R1/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data or "records" in data


# ===========================================================================
# Issue #23: Bootstrap Mode
# ===========================================================================


class TestBootstrapMode:
    """Test the bootstrap mode endpoints."""

    @pytest.mark.anyio
    async def test_bootstrap_not_allowed_by_default(self, client: httpx.AsyncClient) -> None:
        """Bootstrap requires PACT_ALLOW_BOOTSTRAP_MODE=true."""
        resp = await client.post(
            "/api/v1/org/bootstrap/activate",
            json={"org_id": "test-org"},
        )
        # Should be 403 since env var is not set
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_bootstrap_status_no_active(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/v1/org/bootstrap/status/test-org")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] is None

    @pytest.mark.anyio
    async def test_bootstrap_activate_when_allowed(self, client: httpx.AsyncClient) -> None:
        """Test bootstrap activation with the env var set."""
        import pact_platform.use.api.routers.bootstrap as bootstrap_mod

        original = bootstrap_mod._BOOTSTRAP_ALLOWED
        bootstrap_mod._BOOTSTRAP_ALLOWED = True
        try:
            resp = await client.post(
                "/api/v1/org/bootstrap/activate",
                json={
                    "org_id": "test-org-bootstrap",
                    "duration_hours": 2,
                    "max_budget": 500.0,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["data"]["status"] == "active"
            assert data["data"]["org_id"] == "test-org-bootstrap"
        finally:
            bootstrap_mod._BOOTSTRAP_ALLOWED = original

    @pytest.mark.anyio
    async def test_bootstrap_end_early(self, client: httpx.AsyncClient) -> None:
        """Test ending bootstrap early."""
        import pact_platform.use.api.routers.bootstrap as bootstrap_mod
        from datetime import UTC, datetime, timedelta

        from pact_platform.models import db

        bootstrap_mod._BOOTSTRAP_ALLOWED = True
        try:
            # Create active bootstrap record directly
            await db.express.create(
                "BootstrapRecord",
                {
                    "id": "bs-end-001",
                    "org_id": "test-org-end",
                    "status": "active",
                    "started_at": datetime.now(UTC).isoformat(),
                    "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
                },
            )

            resp = await client.post(
                "/api/v1/org/bootstrap/end",
                json={"org_id": "test-org-end", "ended_by": "admin"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["status"] == "ended_early"
        finally:
            bootstrap_mod._BOOTSTRAP_ALLOWED = False

    @pytest.mark.anyio
    async def test_bootstrap_invalid_budget_negative(self, client: httpx.AsyncClient) -> None:
        """Negative budget should be handled gracefully."""
        import pact_platform.use.api.routers.bootstrap as bootstrap_mod

        original = bootstrap_mod._BOOTSTRAP_ALLOWED
        bootstrap_mod._BOOTSTRAP_ALLOWED = True
        try:
            resp = await client.post(
                "/api/v1/org/bootstrap/activate",
                json={
                    "org_id": "test-org-neg",
                    "max_budget": -100.0,
                    "duration_hours": 1,
                },
            )
            # Negative budget -- either accepted (clamped) or rejected
            assert resp.status_code in (200, 400)
        finally:
            bootstrap_mod._BOOTSTRAP_ALLOWED = original


# ===========================================================================
# Expiry Scheduler
# ===========================================================================


class TestExpiryScheduler:
    """Test the shared expiry scheduler."""

    @pytest.mark.anyio
    async def test_scheduler_registers_handler(self) -> None:
        from pact_platform.use.services.expiry_scheduler import ExpiryScheduler

        from pact_platform.models import db

        scheduler = ExpiryScheduler(db)
        scheduler.register_handler(
            model_name="TaskEnvelopeRecord",
            status_field="status",
            expires_field="expires_at",
            active_status="active",
            expired_status="expired",
        )
        assert len(scheduler._handlers) == 1

    @pytest.mark.anyio
    async def test_scheduler_expires_records(self) -> None:
        from datetime import UTC, datetime, timedelta

        from pact_platform.models import db
        from pact_platform.use.services.expiry_scheduler import ExpiryScheduler

        scheduler = ExpiryScheduler(db)
        scheduler.register_handler(
            model_name="TaskEnvelopeRecord",
            status_field="status",
            expires_field="expires_at",
            active_status="active",
            expired_status="expired",
        )

        # Create an expired record
        record_id = "ter-exp-001"
        await db.express.create(
            "TaskEnvelopeRecord",
            {
                "id": record_id,
                "task_id": "task-exp",
                "role_address": "D1-R1",
                "status": "active",
                "expires_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            },
        )

        result = await scheduler.poll()
        assert result.total_expired >= 1

        # Verify record was updated
        record = await db.express.read("TaskEnvelopeRecord", record_id)
        assert record["status"] == "expired"

    @pytest.mark.anyio
    async def test_scheduler_ignores_non_expired(self) -> None:
        from datetime import UTC, datetime, timedelta

        from pact_platform.models import db
        from pact_platform.use.services.expiry_scheduler import ExpiryScheduler

        scheduler = ExpiryScheduler(db)
        scheduler.register_handler(
            model_name="TaskEnvelopeRecord",
            status_field="status",
            expires_field="expires_at",
            active_status="active",
            expired_status="expired",
        )

        # Create a non-expired record
        record_id = "ter-noexp-001"
        await db.express.create(
            "TaskEnvelopeRecord",
            {
                "id": record_id,
                "task_id": "task-noexp",
                "role_address": "D1-R1",
                "status": "active",
                "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            },
        )

        await scheduler.poll()

        # Verify record was NOT updated
        record = await db.express.read("TaskEnvelopeRecord", record_id)
        assert record["status"] == "active"


# ===========================================================================
# Governance Gate Multi-Approver Integration
# ===========================================================================


class TestGovernanceGateApprovalConfig:
    """Test that governance_gate reads ApprovalConfig for required_approvals."""

    @pytest.mark.anyio
    async def test_approval_config_model_crud(self) -> None:
        """Verify ApprovalConfig can be created and queried."""
        from pact_platform.models import db

        config_id = "ac-test-001"
        await db.express.create(
            "ApprovalConfig",
            {
                "id": config_id,
                "operation_type": "grant_clearance_secret",
                "required_approvals": 2,
                "timeout_hours": 48,
            },
        )

        # Read back
        result = await db.express.read("ApprovalConfig", config_id)
        assert result["operation_type"] == "grant_clearance_secret"
        assert result["required_approvals"] == 2
        assert result["timeout_hours"] == 48

        # List by operation type
        configs = await db.express.list(
            "ApprovalConfig",
            {"operation_type": "grant_clearance_secret"},
            limit=10,
        )
        assert len(configs) >= 1
