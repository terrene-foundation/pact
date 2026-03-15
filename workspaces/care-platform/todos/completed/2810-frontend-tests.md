# Todo 2810: Frontend Tests

**Milestone**: M28 — Dashboard Frontend
**Priority**: High
**Effort**: Large
**Source**: Phase 3 requirement
**Dependencies**: 2801, 2802, 2803, 2804, 2805, 2806, 2807, 2808, 2809

## What

Write a comprehensive frontend test suite covering all views and the API client. Use Vitest for unit tests and React Testing Library for component/view integration tests. Mock the API client at the module boundary so tests do not require a running backend. Cover: all 9 views render without errors with mock data, interactive elements behave correctly (filters, navigation, approve/reject flows), the WebSocket client reconnection logic, and the TypeScript API client method signatures. Run accessibility checks (using `jest-axe` or equivalent) on every view to catch missing ARIA attributes, contrast issues, and keyboard navigation gaps.

## Where

- `apps/web/src/**/*.test.tsx`

## Evidence

- [ ] All 9 views (Trust Chain, Constraints, Audit, Agents, Gradient, Workspaces, Approvals, Layout, API client) have test files
- [ ] Every view renders without errors with mock API data
- [ ] Interactive elements (filters, buttons, navigation) are tested in each view
- [ ] Approve and reject flows in the Approval Queue view are tested end-to-end within the component
- [ ] WebSocket reconnection logic unit tests pass
- [ ] Accessibility checks pass for all views (no critical axe violations)
- [ ] All tests pass via `pnpm test` or equivalent
