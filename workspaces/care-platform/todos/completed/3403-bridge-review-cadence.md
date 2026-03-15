# Todo 3403: Bridge Review Cadence

**Milestone**: M34 — Bridge Lifecycle Operations
**Priority**: High
**Effort**: Small
**Source**: Phase 4 plan
**Dependencies**: None

## What

Add review tracking to bridges so that Standing and Scoped bridges are periodically reviewed rather than silently running indefinitely.

Add a `reviews: list[dict]` field to the `Bridge` model. Each review entry is a dict with keys: `reviewer_id`, `timestamp`, and `notes`.

Add a `next_review_date` computed property to `Bridge`:

- Standing bridge: 90 days after the most recent review's timestamp, or 90 days after activation if no reviews have been recorded yet
- Scoped bridge: at the next initiative milestone date (configurable per bridge at creation time; if not configured, default to 90 days like Standing)
- Ad-Hoc bridge: no individual review date — reviewed in aggregate via `get_adhoc_summary()`

Add `Bridge.mark_reviewed(reviewer_id, notes)` — appends a review entry with the current timestamp, resets the `next_review_date` calculation, and returns the review entry.

Add `BridgeManager.get_bridges_due_for_review()` — returns a list of all ACTIVE bridges whose `next_review_date` is in the past.

Add `BridgeManager.get_adhoc_summary(days=30)` — returns aggregate statistics for all Ad-Hoc bridges completed in the last `days` days: total count, count grouped by team pair, the most frequent team pairs, and average response time (time from bridge creation to auto-close).

## Where

- `src/care_platform/workspace/bridge.py` (extend `Bridge` model and `BridgeManager`)

## Evidence

- [ ] `Bridge.reviews` field added as `list[dict]` with correct schema
- [ ] `Bridge.next_review_date` computed property implemented for Standing bridges (90 days after last review or activation)
- [ ] `Bridge.next_review_date` computed property returns `None` for Ad-Hoc bridges
- [ ] `Bridge.mark_reviewed(reviewer_id, notes)` appends to `reviews` and returns the entry
- [ ] `mark_reviewed()` calling again resets the `next_review_date` window from the new timestamp
- [ ] `BridgeManager.get_bridges_due_for_review()` returns bridges past their review date
- [ ] `get_bridges_due_for_review()` does not include Ad-Hoc bridges
- [ ] `get_bridges_due_for_review()` does not include SUSPENDED or CLOSED bridges
- [ ] `BridgeManager.get_adhoc_summary(days=30)` implemented
- [ ] Summary includes: total count, count by team pair, most frequent pairs, average response time
- [ ] `days` parameter correctly filters to the specified window
- [ ] All unit tests pass
