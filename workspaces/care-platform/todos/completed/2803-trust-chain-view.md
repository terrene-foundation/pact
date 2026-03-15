# Todo 2803: Trust Chain Visualization View

**Milestone**: M28 — Dashboard Frontend
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2801, 2802

## What

Implement the Trust Chain view that visualizes the trust hierarchy as a directed tree or graph. The root node is the genesis record; child nodes are delegation records; leaf nodes are active agents. Each node is colour-coded by status: green for active, amber for near-expiry, red for revoked, grey for expired. Clicking any node opens a detail panel displaying the full record fields (ID, issuer, subject, constraints, timestamps, signature hash). Fetch data from the API using the typed client from 2801. The graph must re-render when the underlying data changes (polling or WebSocket push).

## Where

- `apps/web/src/app/trust/`

## Evidence

- [ ] Trust chain is rendered as a tree/graph with genesis record at the root
- [ ] Active nodes are green, near-expiry nodes are amber, revoked nodes are red, expired nodes are grey
- [ ] Clicking a node opens a detail panel with full record fields
- [ ] Detail panel closes when clicking outside it or pressing Escape
- [ ] Data is fetched from the API via the typed client
- [ ] Graph updates when the data changes (poll interval or WebSocket event)
- [ ] Component tests confirm node rendering, colour coding, and detail panel behaviour
