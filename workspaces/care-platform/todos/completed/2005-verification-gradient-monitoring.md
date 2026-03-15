# M20-T05: Verification gradient monitoring

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M20 — Frontend Dashboard Views
**Dependencies**: 1803, 1804, 1805

## What

Real-time display of AUTO_APPROVED / FLAGGED / HELD / BLOCKED counts with trend charts over time. Connects to WebSocket for live updates.

## Where

- `apps/web/app/verification/page.tsx`
- `apps/web/components/verification/GradientChart.tsx`

## Evidence

- Counts update via WebSocket; chart shows trend
