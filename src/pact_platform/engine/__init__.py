# Copyright 2026 Terrene Foundation
# SPDX-License-Identifier: Apache-2.0
"""PACT Engine — Dual Plane bridge connecting governance to execution.

Components:
- PlatformEnvelopeAdapter: Converts governance envelopes to supervisor params
- GovernedDelegate: execute_node callback enforcing governance before execution
- ApprovalBridge: Creates AgenticDecisions from HELD verdicts
- EventBridge: Pipes supervisor events to platform EventBus
- SupervisorOrchestrator: End-to-end request execution
- seed_demo_data / seed_if_empty: Auto-seeding for first boot
"""

from __future__ import annotations

from pact_platform.engine.approval_bridge import ApprovalBridge
from pact_platform.engine.delegate import GovernedDelegate
from pact_platform.engine.envelope_adapter import PlatformEnvelopeAdapter
from pact_platform.engine.event_bridge import EventBridge
from pact_platform.engine.orchestrator import SupervisorOrchestrator
from pact_platform.engine.seed import seed_demo_data, seed_if_empty

__all__ = [
    "PlatformEnvelopeAdapter",
    "GovernedDelegate",
    "ApprovalBridge",
    "EventBridge",
    "SupervisorOrchestrator",
    "seed_demo_data",
    "seed_if_empty",
]
