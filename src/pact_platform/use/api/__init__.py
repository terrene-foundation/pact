# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""PACT API layer — endpoint definitions, FastAPI server, and event bus.

Defines endpoint schemas and a PactAPI class that takes the core
components (registry, approval queue, cost tracker, workspace registry,
bridge manager, envelope registry, verification stats) and exposes
handler methods. The FastAPI server mounts these handlers as HTTP routes,
with a WebSocket endpoint for real-time event streaming.
"""

from pact_platform.use.api.endpoints import (
    ApiResponse,
    EndpointDefinition,
    PactAPI,
    PlatformAPI,
)
from pact_platform.use.api.events import EventBus, EventType, PlatformEvent, event_bus

__all__ = [
    "ApiResponse",
    "EndpointDefinition",
    "EventBus",
    "EventType",
    "PactAPI",
    "PlatformAPI",
    "PlatformEvent",
    "event_bus",
]
