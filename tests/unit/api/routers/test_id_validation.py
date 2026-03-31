# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Tests for path parameter ID validation across all API routers.

Validates that validate_record_id() rejects malicious or malformed IDs
at the API boundary (defense-in-depth per rules/security.md Rule 3).

Tier 1 (Unit): Tests the validation function directly and via HTTP
endpoints. No external dependencies.
"""

from __future__ import annotations

import os
import tempfile

import httpx
import pytest

# Override DATABASE_URL before any model imports
_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_dir}/test_id_validation.db"

from pact_platform.models import MAX_SHORT_STRING, validate_record_id
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
# Direct unit tests for validate_record_id()
# ---------------------------------------------------------------------------


class TestValidateRecordIdDirect:
    """Direct tests for the validate_record_id function."""

    def test_valid_uuid_hex(self):
        """12-char hex from uuid4().hex[:12] is valid."""
        validate_record_id("a1b2c3d4e5f6")

    def test_valid_alphanumeric(self):
        """Pure alphanumeric strings are valid."""
        validate_record_id("abc123XYZ")

    def test_valid_with_hyphens(self):
        """Hyphens are allowed in IDs."""
        validate_record_id("obj-123-abc")

    def test_valid_with_underscores(self):
        """Underscores are allowed in IDs."""
        validate_record_id("session_42_final")

    def test_valid_with_dots(self):
        """Dots are allowed in IDs."""
        validate_record_id("v1.2.3")

    def test_valid_single_char(self):
        """Single character IDs are valid."""
        validate_record_id("x")

    def test_valid_full_uuid(self):
        """Full UUID format with hyphens is valid."""
        validate_record_id("550e8400-e29b-41d4-a716-446655440000")

    def test_reject_empty_string(self):
        """Empty string must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id("")
        assert exc_info.value.status_code == 400

    def test_reject_path_traversal_dotdotslash(self):
        """Path traversal with ../ must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id("../../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_reject_path_traversal_slash(self):
        """Forward slash must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id("path/to/file")
        assert exc_info.value.status_code == 400

    def test_reject_null_bytes(self):
        """Null bytes must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id("id\x00injected")
        assert exc_info.value.status_code == 400

    def test_reject_sql_single_quote(self):
        """Single quote (SQL injection) must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id("'; DROP TABLE users;--")
        assert exc_info.value.status_code == 400

    def test_reject_sql_double_quote(self):
        """Double quote must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id('id"injected')
        assert exc_info.value.status_code == 400

    def test_reject_semicolon(self):
        """Semicolons must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id("id;malicious")
        assert exc_info.value.status_code == 400

    def test_reject_sql_comment(self):
        """SQL comment markers (--) within unsafe strings must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id("id' --comment")
        assert exc_info.value.status_code == 400

    def test_reject_backslash(self):
        """Backslash must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id("path\\to\\file")
        assert exc_info.value.status_code == 400

    def test_reject_spaces(self):
        """Spaces must be rejected."""
        with pytest.raises(Exception) as exc_info:
            validate_record_id("id with spaces")
        assert exc_info.value.status_code == 400

    def test_reject_too_long(self):
        """IDs exceeding MAX_SHORT_STRING must be rejected."""
        long_id = "a" * (MAX_SHORT_STRING + 1)
        with pytest.raises(Exception) as exc_info:
            validate_record_id(long_id)
        assert exc_info.value.status_code == 400

    def test_accept_max_length(self):
        """ID at exactly MAX_SHORT_STRING length is valid."""
        max_id = "a" * MAX_SHORT_STRING
        validate_record_id(max_id)


# ---------------------------------------------------------------------------
# Integration via HTTP endpoints -- decisions router
# ---------------------------------------------------------------------------


class TestDecisionsIdValidation:
    """Validate ID rejection via the decisions router."""

    async def test_get_decision_valid_id(self, client: httpx.AsyncClient):
        """Valid ID format passes validation (may return 404 if not found)."""
        resp = await client.get("/api/v1/decisions/abc123def456")
        # 404 is expected (record does not exist) -- NOT 400
        assert resp.status_code in (200, 404)

    async def test_get_decision_path_traversal(self, client: httpx.AsyncClient):
        """Path traversal characters in decision_id are rejected.

        Note: Encoded slashes (%2F) are interpreted as path separators by
        Starlette before the handler runs, resulting in a framework-level
        404. This is also safe -- the request never reaches the db layer.
        We test with a single quote instead to verify our handler rejects it.
        """
        # Single-quote: our handler catches this
        resp = await client.get("/api/v1/decisions/test'inject")
        assert resp.status_code == 400

    async def test_approve_decision_invalid_id(self, client: httpx.AsyncClient):
        """Semicolons in decision_id are rejected with 400."""
        resp = await client.post(
            "/api/v1/decisions/id;malicious/approve",
            json={"decided_by": "admin", "reason": "test"},
        )
        assert resp.status_code == 400

    async def test_reject_decision_invalid_id(self, client: httpx.AsyncClient):
        """Spaces in decision_id are rejected with 400."""
        resp = await client.post(
            "/api/v1/decisions/id with spaces/reject",
            json={"decided_by": "admin", "reason": "test"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Integration via HTTP endpoints -- objectives router
# ---------------------------------------------------------------------------


class TestObjectivesIdValidation:
    """Validate ID rejection via the objectives router."""

    async def test_get_objective_valid_id(self, client: httpx.AsyncClient):
        """Valid ID passes validation."""
        resp = await client.get("/api/v1/objectives/obj-123")
        assert resp.status_code in (200, 404)

    async def test_get_objective_with_spaces(self, client: httpx.AsyncClient):
        """Spaces in objective_id are rejected with 400."""
        resp = await client.get("/api/v1/objectives/id with spaces")
        assert resp.status_code == 400

    async def test_update_objective_sql_injection(self, client: httpx.AsyncClient):
        """SQL injection in objective_id is rejected with 400."""
        resp = await client.put(
            "/api/v1/objectives/id;DELETE FROM",
            json={"title": "hacked"},
        )
        assert resp.status_code == 400

    async def test_cancel_objective_backslash(self, client: httpx.AsyncClient):
        """Backslash in objective_id is rejected with 400."""
        resp = await client.post("/api/v1/objectives/path\\to\\file/cancel")
        assert resp.status_code == 400

    async def test_get_objective_requests_invalid(self, client: httpx.AsyncClient):
        """Single quote in nested route is rejected with 400."""
        resp = await client.get("/api/v1/objectives/id'quote/requests")
        assert resp.status_code == 400

    async def test_get_objective_cost_invalid(self, client: httpx.AsyncClient):
        """Double quote in cost endpoint is rejected with 400."""
        resp = await client.get('/api/v1/objectives/id"quote/cost')
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Integration via HTTP endpoints -- pools router (including member_id)
# ---------------------------------------------------------------------------


class TestPoolsIdValidation:
    """Validate ID rejection via the pools router."""

    async def test_get_pool_valid_id(self, client: httpx.AsyncClient):
        """Valid ID passes validation."""
        resp = await client.get("/api/v1/pools/pool-abc123")
        assert resp.status_code in (200, 404)

    async def test_get_pool_invalid_id(self, client: httpx.AsyncClient):
        """Semicolon in pool_id is rejected with 400."""
        resp = await client.get("/api/v1/pools/id;SELECT 1")
        assert resp.status_code == 400

    async def test_add_member_invalid_pool_id(self, client: httpx.AsyncClient):
        """Single quote in pool_id in add_member is rejected with 400."""
        resp = await client.post(
            "/api/v1/pools/pool'inject/members",
            json={"member_address": "D1-R1"},
        )
        assert resp.status_code == 400

    async def test_remove_member_invalid_pool_id(self, client: httpx.AsyncClient):
        """Space in pool_id in remove_member is rejected with 400."""
        resp = await client.delete("/api/v1/pools/pool bad/members/member1")
        assert resp.status_code == 400

    async def test_remove_member_invalid_member_id(self, client: httpx.AsyncClient):
        """Single quote in member_id in remove_member is rejected with 400."""
        resp = await client.delete("/api/v1/pools/valid-pool/members/m'inject")
        assert resp.status_code == 400

    async def test_get_pool_capacity_invalid(self, client: httpx.AsyncClient):
        """Double quote in pool_id in capacity endpoint is rejected with 400."""
        resp = await client.get('/api/v1/pools/id"quote/capacity')
        assert resp.status_code == 400
