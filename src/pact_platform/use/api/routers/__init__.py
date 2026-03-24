# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""Work management API routers.

Seven routers covering objectives, requests, sessions, decisions,
pools, reviews, and platform metrics.
"""

from __future__ import annotations

from pact_platform.use.api.routers.decisions import router as decisions_router
from pact_platform.use.api.routers.metrics import router as metrics_router
from pact_platform.use.api.routers.objectives import router as objectives_router
from pact_platform.use.api.routers.pools import router as pools_router
from pact_platform.use.api.routers.requests import router as requests_router
from pact_platform.use.api.routers.reviews import router as reviews_router
from pact_platform.use.api.routers.sessions import router as sessions_router

__all__ = [
    "objectives_router",
    "requests_router",
    "sessions_router",
    "decisions_router",
    "pools_router",
    "reviews_router",
    "metrics_router",
]
