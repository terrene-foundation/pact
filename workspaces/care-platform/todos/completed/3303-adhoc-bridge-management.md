# Todo 3303: Ad-Hoc Bridge Management

**Milestone**: M33 — Cross-Team Execution
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3101

## What

Extend `BridgeManager` with ad-hoc bridge lifecycle automation and pattern-based promotion detection.

Add `request_adhoc_bridge(source_team, target_team, action, data)` — this creates an ad-hoc bridge, submits the cross-team request, and automatically closes the bridge after the response is received. The caller does not need to manage bridge lifecycle; the method handles open, use, and close atomically.

Add an `_adhoc_history` internal tracking dict with type `dict[tuple[str, str], list[datetime]]`. Each successful ad-hoc bridge between a team pair appends a timestamp entry to the list for that pair.

Add `check_promotion_threshold(source_team, target_team, threshold=5, window_days=30)` — if there are more than `threshold` ad-hoc bridge completions between the same two teams within the last `window_days`, return a suggestion object recommending the creation of a Standing bridge. The suggestion must include the team pair, the observed count, the window, and a human-readable recommendation message.

When the promotion threshold is reached, emit a FLAGGED platform event of type `bridge_status` carrying the suggestion. The FLAGGED status signals that human attention is warranted without blocking execution.

## Where

- `src/care_platform/workspace/bridge.py` (extend `BridgeManager`)

## Evidence

- [ ] `request_adhoc_bridge(source_team, target_team, action, data)` implemented
- [ ] Ad-hoc bridge auto-closes after response is received (no manual close required)
- [ ] `_adhoc_history` tracking dict maintained per team pair
- [ ] Each completed ad-hoc bridge appends a timestamp to the appropriate pair entry
- [ ] `check_promotion_threshold()` implemented with configurable threshold and window
- [ ] Returns suggestion when count exceeds threshold within window
- [ ] Returns no suggestion when count is below threshold
- [ ] Suggestion includes team pair, count, window, and recommendation message
- [ ] FLAGGED platform event emitted when promotion threshold is reached
- [ ] Team pairs are order-normalised (A→B and B→A count as the same pair) — or consistently directional, whichever matches the bridge model
- [ ] All unit tests pass
