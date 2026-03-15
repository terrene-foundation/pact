# Todo 2805: Audit Trail Viewer

**Milestone**: M28 — Dashboard Frontend
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2801, 2802

## What

Implement the Audit Trail view that displays the complete audit history in reverse-chronological order. Provide filter controls for: agent (dropdown), action type (dropdown), verification level (AUTO_APPROVED / FLAGGED / HELD / BLOCKED), and time range (date-from / date-to). Each row shows: timestamp, agent ID, action summary, verification level (colour-coded badge), and a hash chain integrity indicator (checkmark if the anchor's hash chain is intact, warning icon if broken). Clicking a row expands the full audit anchor record. Add an export button that downloads the filtered results as JSON. Fetch audit data from the API via the typed client.

## Where

- `apps/web/src/app/audit/`

## Evidence

- [ ] Audit entries are displayed in reverse-chronological order
- [ ] Filter by agent narrows the displayed entries correctly
- [ ] Filter by verification level narrows the displayed entries correctly
- [ ] Filter by time range narrows the displayed entries correctly
- [ ] Hash chain integrity indicator is shown on each row
- [ ] Clicking a row expands the full audit anchor record
- [ ] Export button downloads the currently filtered results as a JSON file
- [ ] Data is fetched from the API via the typed client
- [ ] Component tests confirm filters, row expansion, and export behaviour
