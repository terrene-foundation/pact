---
type: DECISION
date: 2026-03-30
project: pact
topic: Keep FastAPI server, do not migrate to NexusEngine
phase: analyze
tags: [nexus, fastapi, architecture, api]
---

# Decision: Keep FastAPI, Not NexusEngine

**Choice**: Keep the current FastAPI server (`server.py`).

**Alternatives considered**: NexusEngine with Preset.ENTERPRISE (gives CSRF, audit, metrics, security headers, rate limiting in one builder call).

**Rationale**: Pact has 62+ custom endpoints with governance engine integration, WebSocket auth, custom middleware (BodySizeLimit, SecurityHeaders), and complex business logic. Nexus is designed for exposing Kailash workflows as multi-channel APIs, not custom API servers.

**Consequence**: Pact manually configures middleware. This is acceptable — it's 1 file (server.py), not a recurring cost.
