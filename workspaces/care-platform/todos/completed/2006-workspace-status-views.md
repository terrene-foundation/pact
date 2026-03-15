# M20-T06: Workspace status views

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M20 — Frontend Dashboard Views
**Dependencies**: 1402, 1403, 1804, 1805

## What

All workspaces with state (PROVISIONING/ACTIVE/ARCHIVED) and CO phase (ANALYZE through CODIFY). Bridge connections shown as links between workspaces.

## Where

- `apps/web/app/workspaces/page.tsx`
- `apps/web/components/workspaces/WorkspaceCard.tsx`
- `apps/web/components/workspaces/BridgeConnections.tsx`

## Evidence

- Workspace cards with state/phase; bridge lines between connected workspaces
