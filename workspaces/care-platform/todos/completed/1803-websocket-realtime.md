# M18-T03: WebSocket endpoint for real-time updates

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M18 — Frontend Scaffold & API Layer
**Dependencies**: 1802

## What

WebSocket endpoint pushing real-time events (new audit anchors, held actions, posture changes) to connected dashboard clients.

## Where

- Modify: `src/care_platform/api/server.py` (add WebSocket route)
- New: `src/care_platform/api/events.py` (event bus)

## Evidence

- Test: connect via WebSocket, trigger audit event, verify event received
