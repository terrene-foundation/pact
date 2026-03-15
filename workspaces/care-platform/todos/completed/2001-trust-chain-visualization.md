# M20-T01: Trust chain visualization page

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M20 — Frontend Dashboard Views
**Dependencies**: 1804, 1805

## What

Interactive visualization: genesis → delegation → agent trust chains. Nodes = trust entities, edges = delegations. Color-coded by state (ACTIVE=green, SUSPENDED=yellow, REVOKED=red). Click node for detail panel.

## Where

- `apps/web/app/trust-chains/page.tsx`
- `apps/web/components/trust/TrustChainGraph.tsx`

## Evidence

- Page renders; API data populates visualization; click shows detail
