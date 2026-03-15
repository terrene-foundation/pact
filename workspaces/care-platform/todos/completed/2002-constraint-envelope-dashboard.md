# M20-T02: Constraint envelope dashboard

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M20 — Frontend Dashboard Views
**Dependencies**: 1804, 1805

## What

Dashboard showing all five constraint dimensions for selected agent/envelope. Each dimension shows current utilization as gauge (0-100%), limits, boundary proximity.

## Where

- `apps/web/app/envelopes/page.tsx`
- `apps/web/app/envelopes/[id]/page.tsx`
- `apps/web/components/constraints/DimensionGauge.tsx`

## Evidence

- Five dimension gauges display; utilization data from API
