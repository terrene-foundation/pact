# Todo 2801: TypeScript API Client (from Pydantic Models)

**Milestone**: M28 — Dashboard Frontend
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2103

## What

Generate TypeScript types and a fully typed API client from the FastAPI/Pydantic models. Use `openapi-typescript-codegen` or an equivalent tool to produce types from the OpenAPI schema exported by the FastAPI app. The generated client must provide typed methods for all 15+ REST endpoints. Add a WebSocket client (hand-written or generated) that connects to the event stream endpoint, handles reconnection with exponential backoff, and types the incoming event payloads using the generated types. Place all generated and hand-written client code under `apps/web/src/lib/api/`.

## Where

- `apps/web/src/lib/api/`

## Evidence

- [ ] TypeScript types are generated from the OpenAPI schema exported by the FastAPI app
- [ ] Every REST endpoint has a corresponding typed method in the client
- [ ] TypeScript types match the Pydantic model field names and types exactly
- [ ] WebSocket client connects to the event stream endpoint successfully
- [ ] WebSocket client reconnects automatically after a disconnect
- [ ] Incoming WebSocket event payloads are typed using the generated event types
- [ ] Client compiles without TypeScript errors
- [ ] Unit tests cover the WebSocket reconnection logic
