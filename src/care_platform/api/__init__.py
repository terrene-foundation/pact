# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""CARE Platform API layer — endpoint definitions, FastAPI server, and event bus.

Defines endpoint schemas and a PlatformAPI class that takes the core
components (registry, approval queue, cost tracker, workspace registry,
bridge manager, envelope registry, verification stats) and exposes
handler methods. The FastAPI server mounts these handlers as HTTP routes,
with a WebSocket endpoint for real-time event streaming.
"""

from care_platform.api.endpoints import (
    ApiResponse,
    EndpointDefinition,
    PlatformAPI,
)
from care_platform.api.events import EventBus, EventType, PlatformEvent, event_bus

__all__ = [
    "ApiResponse",
    "EndpointDefinition",
    "EventBus",
    "EventType",
    "PlatformAPI",
    "PlatformEvent",
    "event_bus",
]
