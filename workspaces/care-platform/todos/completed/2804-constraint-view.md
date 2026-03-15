# Todo 2804: Constraint Envelope Dashboard View

**Milestone**: M28 — Dashboard Frontend
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2801, 2802

## What

Implement the Constraint Envelope view that displays all active constraint envelopes with all five constraint dimensions: Financial, Operational, Temporal, Data Access, and Communication. For each dimension show the configured limit and the current utilization as a percentage (for example, "$47.20 of $100.00 — 47%"). Display visual indicators for near-boundary states: yellow warning when utilization exceeds 80%, red alert when utilization exceeds 95%. Select an agent from a dropdown to view their specific envelope. Fetch envelope and utilization data from the API via the typed client.

## Where

- `apps/web/src/app/constraints/`

## Evidence

- [ ] All five constraint dimensions are displayed for the selected agent's envelope
- [ ] Utilization percentage is shown for each dimension
- [ ] Yellow warning indicator appears when utilization exceeds 80%
- [ ] Red alert indicator appears when utilization exceeds 95%
- [ ] Agent selector dropdown changes the displayed envelope correctly
- [ ] Data is fetched from the API via the typed client
- [ ] Component tests confirm all five dimensions render and threshold indicators trigger correctly
