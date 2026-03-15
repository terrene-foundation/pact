# Todo 2201: WebSocket Authentication

**Milestone**: M22 — API Hardening
**Priority**: High
**Effort**: Small
**Source**: RT10-A4
**Dependencies**: 2101, 2102, 2103

## What

Add token-based authentication to the WebSocket connection upgrade. When a client attempts to open a WebSocket connection, the server must verify a `CARE_API_TOKEN` value presented by the client (via query parameter or `Authorization` header, consistent with how the REST endpoints accept tokens) before completing the upgrade handshake. Connections that omit or present an incorrect token must be rejected with HTTP 401 before the WebSocket protocol is established. Authenticated connections proceed normally and receive event stream messages.

The implementation should reuse the same token-verification logic already used for REST endpoints rather than introducing a parallel authentication path.

## Where

- `src/care_platform/api/server.py` — WebSocket endpoint handler (connection upgrade check)
- `src/care_platform/api/events.py` — event delivery logic (if authentication state needs to be threaded through)

## Evidence

- [ ] WebSocket connection without a token is rejected before upgrade (HTTP 401 or WebSocket close with policy violation code)
- [ ] WebSocket connection with a correct token completes upgrade and receives events
- [ ] WebSocket connection with an incorrect token is rejected
- [ ] Authentication uses the same token as the REST layer (no separate credential)
- [ ] Unit/integration tests cover: unauthenticated rejection, incorrect token rejection, authenticated success, event delivery to authenticated client
- [ ] Existing tests continue to pass
