# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Work management and governance API routers.

Seventeen routers covering objectives, requests, sessions, decisions,
pools, reviews, platform metrics, org management, clearance, vetting,
knowledge share policies, envelopes, task envelopes, access checks,
knowledge records, emergency bypass, and bootstrap mode.
"""

from __future__ import annotations

from pact_platform.use.api.routers.access import router as access_router
from pact_platform.use.api.routers.bootstrap import router as bootstrap_router
from pact_platform.use.api.routers.clearance import router as clearance_router
from pact_platform.use.api.routers.decisions import router as decisions_router
from pact_platform.use.api.routers.emergency_bypass import router as emergency_bypass_router
from pact_platform.use.api.routers.envelopes import router as envelopes_router
from pact_platform.use.api.routers.knowledge import router as knowledge_router
from pact_platform.use.api.routers.ksp import router as ksp_router
from pact_platform.use.api.routers.metrics import router as metrics_router
from pact_platform.use.api.routers.objectives import router as objectives_router
from pact_platform.use.api.routers.org import router as org_router
from pact_platform.use.api.routers.pools import router as pools_router
from pact_platform.use.api.routers.requests import router as requests_router
from pact_platform.use.api.routers.reviews import router as reviews_router
from pact_platform.use.api.routers.sessions import router as sessions_router
from pact_platform.use.api.routers.task_envelopes import router as task_envelopes_router
from pact_platform.use.api.routers.vetting import router as vetting_router

__all__ = [
    "objectives_router",
    "requests_router",
    "sessions_router",
    "decisions_router",
    "pools_router",
    "reviews_router",
    "metrics_router",
    "org_router",
    "clearance_router",
    "ksp_router",
    "envelopes_router",
    "access_router",
    "emergency_bypass_router",
    "knowledge_router",
    "vetting_router",
    "bootstrap_router",
    "task_envelopes_router",
]
