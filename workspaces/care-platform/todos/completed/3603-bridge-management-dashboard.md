# Todo 3603: Bridge Management Dashboard

**Milestone**: M36 — Bridge API + Dashboard
**Priority**: High
**Effort**: Large
**Source**: Phase 4 plan
**Dependencies**: 3601

## What

Extend the web frontend with a dedicated bridge management section. Currently bridges appear as a subcomponent on the `/workspaces` page; this work promotes them to a first-class section.

Bridge list page at `/bridges`:

- Lists all bridges the authenticated user can see, grouped or sortable by lifecycle status
- Status badges color-coded by lifecycle state: PENDING (yellow), ACTIVE (green), SUSPENDED (orange), CLOSED (grey)
- Bridge type labels: Standing, Scoped, Ad-Hoc (using canonical terminology)
- Visual source → target team flow indicator per row
- Link from each row to the bridge detail page

Bridge detail page at `/bridges/[id]`:

- Full bridge information: bridge ID, type, purpose, source team, target team, created date
- Lifecycle status with transition history
- Permissions list: paths, access types, message types
- Sharing policy: field-level sharing modes per path pattern
- Effective constraint envelope visualization using the existing `DimensionGauge` component from the envelopes page — shows the intersection envelope that governs cross-team actions
- Recent access log: last 10 entries from the audit trail (links to full audit view)
- Approval status panel: who has approved from each side, pending approvals highlighted
- Action buttons contextual to current lifecycle state:
  - PENDING: Approve (source side), Approve (target side)
  - ACTIVE: Suspend, Close
  - SUSPENDED: Resume, Close
  - CLOSED: no actions available

Add `CareApiClient` methods in `apps/web/lib/api.ts` for all bridge operations:

- `createBridge(data)`, `getBridge(id)`, `approveBridge(id, side, approverId)`, `suspendBridge(id, reason)`, `closeBridge(id, reason)`, `getTeamBridges(teamId)`, `getBridgeAudit(id, params)`

## Where

- `apps/web/app/bridges/page.tsx` (extend or replace bridge list view)
- `apps/web/app/bridges/[id]/page.tsx` (new bridge detail page)
- `apps/web/lib/api.ts` (add `CareApiClient` bridge methods)

## Evidence

- [ ] `/bridges` page renders a list of bridges with status badges, type labels, and source/target indicators
- [ ] Bridge status badges use the correct color for each lifecycle state
- [ ] Bridge type labels use canonical names: Standing, Scoped, Ad-Hoc
- [ ] `/bridges/[id]` page renders full bridge detail including permissions and sharing policy
- [ ] Effective constraint envelope visualization renders using `DimensionGauge` components
- [ ] Approval status panel shows per-side approval state
- [ ] Action buttons match current lifecycle state (correct buttons visible for each state)
- [ ] Lifecycle action buttons call the correct API endpoints and refresh page state on success
- [ ] Recent access log section displays with link to full audit
- [ ] All `CareApiClient` bridge methods added to `apps/web/lib/api.ts`
- [ ] No console errors on page load for any bridge lifecycle state
