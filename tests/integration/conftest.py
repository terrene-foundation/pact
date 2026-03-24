# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Integration test fixtures for the PACT API server.

Provides a fully seeded PactAPI instance and an httpx.AsyncClient
configured with ASGITransport for testing FastAPI endpoints against
real seed data (no mocks).
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio

# Ensure scripts/ is importable for seed_demo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from pact_platform.build.config.env import EnvConfig
from pact_platform.build.workspace.bridge import BridgeManager
from pact_platform.build.workspace.models import WorkspaceRegistry
from pact_platform.trust.store.cost_tracking import CostTracker
from pact_platform.trust.store.posture_history import PostureHistoryStore
from pact_platform.use.api.endpoints import PactAPI
from pact_platform.use.api.server import create_app
from pact_platform.use.execution.approval import ApprovalQueue
from pact_platform.use.execution.registry import AgentRegistry
from scripts.seed_demo import (
    build_audit_chain,
    convert_verification_stats_to_enum_keys,
    seed_agents,
    seed_audit_anchors,
    seed_bridges,
    seed_cost_tracking,
    seed_envelopes,
    seed_held_actions,
    seed_posture_history,
    seed_shadow_evaluations,
    seed_verification_stats,
    seed_workspaces,
)

# Test API token used across all auth tests
TEST_API_TOKEN = "test-integration-token-2026"

# Module-level cache for seeded components (avoids re-seeding per test)
_seeded_components_cache: dict | None = None


def _build_seeded_components() -> dict:
    """Build all PACT components with demo seed data.

    Uses the same seed functions as the production seed_demo script
    to ensure realistic, consistent data. Cached at module level for
    efficiency since the seed data is read-only during tests.
    """
    global _seeded_components_cache
    if _seeded_components_cache is not None:
        return _seeded_components_cache

    registry = AgentRegistry()
    approval_queue = ApprovalQueue()
    cost_tracker = CostTracker()
    workspace_registry = WorkspaceRegistry()
    bridge_manager = BridgeManager()
    posture_store = PostureHistoryStore()

    seed_agents(registry)
    seed_workspaces(workspace_registry)
    envelope_registry = seed_envelopes()
    verification_stats_raw, audit_records = seed_audit_anchors()
    verification_stats_str = seed_verification_stats(audit_records)
    verification_stats = convert_verification_stats_to_enum_keys(verification_stats_str)
    audit_chain = build_audit_chain(audit_records)
    seed_held_actions(approval_queue)
    seed_bridges(bridge_manager)
    seed_posture_history(posture_store)
    seed_cost_tracking(cost_tracker)
    shadow_enforcer = seed_shadow_evaluations()

    _seeded_components_cache = {
        "registry": registry,
        "approval_queue": approval_queue,
        "cost_tracker": cost_tracker,
        "workspace_registry": workspace_registry,
        "bridge_manager": bridge_manager,
        "posture_store": posture_store,
        "envelope_registry": envelope_registry,
        "verification_stats": verification_stats,
        "audit_records": audit_records,
        "audit_chain": audit_chain,
        "shadow_enforcer": shadow_enforcer,
    }
    return _seeded_components_cache


@pytest.fixture()
def seeded_components() -> dict:
    """Provide seeded platform components (cached, not re-created per test)."""
    return _build_seeded_components()


@pytest.fixture()
def platform_api(seeded_components: dict) -> PactAPI:
    """Create a PactAPI wired with real seeded components."""
    return PactAPI(
        registry=seeded_components["registry"],
        approval_queue=seeded_components["approval_queue"],
        cost_tracker=seeded_components["cost_tracker"],
        workspace_registry=seeded_components["workspace_registry"],
        bridge_manager=seeded_components["bridge_manager"],
        envelope_registry=seeded_components["envelope_registry"],
        verification_stats=seeded_components["verification_stats"],
        posture_store=seeded_components["posture_store"],
        audit_chain=seeded_components.get("audit_chain"),
        shadow_enforcer=seeded_components.get("shadow_enforcer"),
    )


@pytest.fixture()
def dev_env_config() -> EnvConfig:
    """EnvConfig in dev mode with no API token (auth disabled)."""
    return EnvConfig(pact_dev_mode=True, pact_api_token="")


@pytest.fixture()
def auth_env_config() -> EnvConfig:
    """EnvConfig with API token enabled for auth testing."""
    return EnvConfig(pact_dev_mode=False, pact_api_token=TEST_API_TOKEN)


@pytest_asyncio.fixture()
async def client(platform_api: PactAPI, dev_env_config: EnvConfig) -> AsyncGenerator:
    """Async HTTP client for the seeded PACT API (no auth required).

    Uses httpx.AsyncClient with ASGITransport to test FastAPI endpoints
    without running a real server.
    """
    import pact_platform.use.api.server as server_module

    old_default = server_module._default_api
    server_module._default_api = None

    app = create_app(platform_api=platform_api, env_config=dev_env_config)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    server_module._default_api = old_default


@pytest_asyncio.fixture()
async def auth_client(platform_api: PactAPI, auth_env_config: EnvConfig) -> AsyncGenerator:
    """Async HTTP client for the seeded PACT API (auth required).

    Uses httpx.AsyncClient with ASGITransport. Requests must include
    a valid Bearer token to access protected endpoints.
    """
    import pact_platform.use.api.server as server_module

    old_default = server_module._default_api
    server_module._default_api = None

    app = create_app(platform_api=platform_api, env_config=auth_env_config)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    server_module._default_api = old_default
