# M18-T04: Frontend shared components and layout

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M18 — Frontend Scaffold & API Layer
**Dependencies**: 1305, 1802

## What

Shared React component library and layout: navigation sidebar, header, content area, status indicators, data tables.

Components: Sidebar (navigation), Header (breadcrumbs), StatusBadge (verification levels, posture levels, bridge status), DataTable (sortable, filterable), ConstraintGauge (dimension utilization visualization).

## Where

- `apps/web/components/layout/`
- `apps/web/components/ui/`
- `apps/web/lib/api.ts`

## Evidence

- `cd apps/web && npm run build` succeeds; layout renders in browser
