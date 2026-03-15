# M20-T03: Audit trail viewer

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M20 — Frontend Dashboard Views
**Dependencies**: 1804, 1805

## What

Searchable, filterable table of audit anchors. Filters: agent, time range, verification level, action type. Shows chain integrity status.

## Where

- `apps/web/app/audit/page.tsx`
- `apps/web/components/audit/AuditTable.tsx`
- `apps/web/components/audit/AuditFilters.tsx`

## Evidence

- Table populates from API; filters work; chain integrity indicator visible
