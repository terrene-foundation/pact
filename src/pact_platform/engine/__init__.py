# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""PACT Engine — Dual Plane bridge connecting governance to execution.

Components:
- SupervisorOrchestrator: End-to-end request execution (composes PactEngine)
- ApprovalBridge: Creates AgenticDecisions from HELD verdicts
- EventBridge: Pipes supervisor events to platform EventBus
- EmergencyBypass: 3-tier bypass with rate limiting
- seed_demo_data / seed_if_empty: Auto-seeding for first boot
"""

from __future__ import annotations

from pact_platform.engine.approval_bridge import ApprovalBridge
from pact_platform.engine.emergency_bypass import (
    AuthorityLevel,
    BypassRecord,
    BypassTier,
    EmergencyBypass,
    MemoryRateLimitStore,
    RateLimitStore,
    SqliteRateLimitStore,
)
from pact_platform.engine.event_bridge import EventBridge
from pact_platform.engine.orchestrator import SupervisorOrchestrator
from pact_platform.engine.seed import seed_demo_data, seed_if_empty
from pact_platform.engine.settings import (
    EnforcementMode,
    PlatformSettings,
    get_platform_settings,
    set_platform_settings,
)

__all__ = [
    "ApprovalBridge",
    "AuthorityLevel",
    "BypassRecord",
    "BypassTier",
    "EmergencyBypass",
    "EnforcementMode",
    "EventBridge",
    "MemoryRateLimitStore",
    "PlatformSettings",
    "RateLimitStore",
    "SqliteRateLimitStore",
    "SupervisorOrchestrator",
    "get_platform_settings",
    "seed_demo_data",
    "seed_if_empty",
    "set_platform_settings",
]
