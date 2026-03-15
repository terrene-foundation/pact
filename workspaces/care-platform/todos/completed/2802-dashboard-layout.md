# Todo 2802: Dashboard Layout and Navigation

**Milestone**: M28 — Dashboard Frontend
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2801

## What

Implement the main dashboard layout with three structural zones: a sidebar with navigation links to all 7 views (Trust Chain, Constraints, Audit, Agents, Verification Gradient, Workspaces, Approvals), a header displaying the current workspace name and authentication status (authenticated / unauthenticated), and a content area that renders the active route. Set up client-side routing between all 7 views. Layout must be responsive (desktop and tablet breakpoints). Implement dark and light mode toggle persisted to `localStorage`.

## Where

- `apps/web/src/app/`
- `apps/web/src/components/layout/`

## Evidence

- [ ] Sidebar is present on all 7 routes and links navigate correctly
- [ ] Header displays the workspace name and auth status
- [ ] Content area renders the correct view for each route
- [ ] Layout is usable at 1280px (desktop) and 768px (tablet) screen widths
- [ ] Dark mode is applied when toggled and preference is persisted across page refreshes
- [ ] Light mode is applied when toggled and preference is persisted across page refreshes
- [ ] All 7 routes return a non-error render (even if the view content is a placeholder pending later todos)
- [ ] Component tests confirm navigation and theme toggle behaviour
