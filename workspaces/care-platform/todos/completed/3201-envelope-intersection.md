# Todo 3201: Envelope Intersection

**Milestone**: M32 — Constraint Intersection
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: None

## What

Implement `compute_bridge_envelope(source_envelope, bridge_constraints, target_envelope) -> ConstraintEnvelopeConfig` in a new `src/care_platform/constraint/bridge_envelope.py` module. This function takes three `ConstraintEnvelopeConfig` objects and returns the most restrictive combination across all five CARE constraint dimensions.

### Financial dimension

`max_spend_usd` = minimum of all three non-None values. If any input has `max_spend_usd = None`, the result is `None` (no financial capability — the tightest possible). Rationale: a None budget means no budget authority at all.

### Operational dimension

- `allowed_actions` = intersection of all three lists (only actions permitted by all three)
- `blocked_actions` = union of all three lists (if blocked anywhere, blocked everywhere)
- `max_actions_per_hour` = minimum of all three non-None values (None means no limit; treat None as infinity when computing min, so only finite values reduce the cap)
- `reasoning_required_actions` = union of all three lists (if reasoning required anywhere, required on the bridge)

### Temporal dimension

- `active_hours_start` and `active_hours_end` define a window. Compute the overlapping window: `latest_start = max(all start times)`, `earliest_end = min(all end times)`
- Handle overnight windows (e.g., 22:00–06:00) by converting to comparable ranges
- If there is no temporal overlap (latest_start >= earliest_end in the same-day sense), set a sentinel that marks the bridge as temporally blocked (e.g., `active_hours_start == active_hours_end`)
- If any envelope has no temporal restriction, treat it as fully permissive (does not constrain the overlap)

### Data Access dimension

- `read_paths` = intersection of glob patterns from all three (a path is readable only if it matches a pattern in all three lists)
- `write_paths` = intersection of glob patterns from all three
- `blocked_data_types` = union of all three lists

For glob pattern intersection: a glob pattern `p` from envelope A is in the intersection result only if it is also present in envelopes B and C. Use exact string matching on the pattern strings themselves (not path expansion). This is the conservative approach — if the exact pattern is not shared across all three, exclude it.

### Communication dimension

- `internal_only` = `True` if ANY of the three has it `True`
- `external_requires_approval` = `True` if ANY has it `True`
- `allowed_channels` = intersection of all three lists

## Where

- `src/care_platform/constraint/bridge_envelope.py` (new file — primary implementation)

## Evidence

- [ ] `src/care_platform/constraint/bridge_envelope.py` exists with `compute_bridge_envelope()` function
- [ ] Financial: min of non-None values returned; None input produces None result
- [ ] Operational: allowed_actions is intersection, blocked_actions is union
- [ ] Operational: max_actions_per_hour is min of finite values (None treated as infinity)
- [ ] Operational: reasoning_required_actions is union
- [ ] Temporal: overlapping window computed correctly (latest start, earliest end)
- [ ] Temporal: overnight windows handled without producing incorrect overlaps
- [ ] Temporal: no-overlap case produces a temporally-blocked sentinel
- [ ] Data Access: read_paths and write_paths use exact-pattern intersection
- [ ] Data Access: blocked_data_types is union
- [ ] Communication: internal_only is True if any source has True
- [ ] Communication: allowed_channels is intersection
- [ ] All unit tests pass
