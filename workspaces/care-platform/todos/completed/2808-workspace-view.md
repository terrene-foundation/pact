# Todo 2808: Workspace Status View

**Milestone**: M28 — Dashboard Frontend
**Priority**: Medium
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2801, 2802

## What

Implement the Workspace Status view that lists all workspaces with their team assignments, active Cross-Functional Bridges, and health indicators. Each workspace row shows: workspace ID, team name, number of registered agents, number of active bridges (broken down by type: Standing, Scoped, Ad-Hoc), and an overall health status (Healthy / Degraded / Offline). Clicking a workspace row navigates to a workspace detail page showing: full workspace configuration, the agent roster with posture badges, and a bridge status table with each bridge's type, linked workspaces, and current state. Fetch data from the API via the typed client.

## Where

- `apps/web/src/app/workspaces/`

## Evidence

- [ ] Workspace list shows all workspaces with team name, agent count, bridge counts, and health status
- [ ] Bridge counts are broken down by type (Standing, Scoped, Ad-Hoc) using exact canonical names
- [ ] Clicking a workspace navigates to the workspace detail page
- [ ] Workspace detail shows full configuration, agent roster with posture badges, and bridge status table
- [ ] Data is fetched from the API via the typed client
- [ ] Component tests confirm list rendering, health status display, and navigation to detail page
