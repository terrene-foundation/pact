# Todo 2807: Verification Gradient Monitoring View

**Milestone**: M28 — Dashboard Frontend
**Priority**: Medium
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2801, 2802

## What

Implement the Verification Gradient Monitoring view that shows the real-time distribution of verification outcomes across all agents. The top section displays aggregate counts and percentages for each level: AUTO_APPROVED, FLAGGED, HELD, BLOCKED. A bar or pie chart visualizes the distribution. A per-agent breakdown table shows each agent's outcome counts for the selected time window (last hour, last 24 hours, last 7 days, selectable via a toggle). A trend chart shows how the distribution has changed over time (time series with one data point per hour). Fetch data from the API via the typed client; update on a polling interval.

## Where

- `apps/web/src/app/verification/`

## Evidence

- [ ] Aggregate counts and percentages for all four gradient levels are displayed
- [ ] Distribution chart renders correctly with real API data
- [ ] Per-agent breakdown table shows individual outcome counts
- [ ] Time window toggle (1h / 24h / 7d) changes the data range displayed
- [ ] Trend chart shows a time series of outcome distribution
- [ ] Data is fetched from the API via the typed client and refreshes on a polling interval
- [ ] Component tests confirm aggregate display, per-agent table, and time window toggle
