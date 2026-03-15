# Todo 3203: Bridge Tightening Validation

**Milestone**: M32 — Constraint Intersection
**Priority**: High
**Effort**: Small
**Source**: Phase 4 plan
**Dependencies**: 3201

## What

Implement a validation function that confirms the computed bridge envelope is no wider than either team's individual constraint envelope. This is the safety check that prevents a bridge from accidentally granting broader access than either party actually holds.

### `validate_bridge_tightening`

```python
def validate_bridge_tightening(
    bridge_envelope: ConstraintEnvelopeConfig,
    source_envelope: ConstraintEnvelopeConfig,
    target_envelope: ConstraintEnvelopeConfig,
) -> list[str]:
```

Returns an empty list if the bridge envelope is a valid tightening of both source and target. Returns a list of violation description strings if the bridge envelope is wider than either source or target on any dimension.

### Violations to detect (check against both source and target)

For each of the five CARE constraint dimensions, check that the bridge envelope is not wider:

- **Financial**: `bridge.max_spend_usd > source.max_spend_usd` or `bridge.max_spend_usd > target.max_spend_usd` (if the bridge has a financial limit and an input has None, that is a violation — bridge should have None too)
- **Operational**: any action in `bridge.allowed_actions` that is not in `source.allowed_actions` or `target.allowed_actions`; any action in `source.blocked_actions` or `target.blocked_actions` that is not in `bridge.blocked_actions`
- **Temporal**: bridge window must be contained within both source and target windows (bridge start >= max(source_start, target_start) and bridge end <= min(source_end, target_end))
- **Data Access**: any path in `bridge.read_paths` not covered by `source.read_paths` or `target.read_paths`; similar for `write_paths`; any data type in `source.blocked_data_types` or `target.blocked_data_types` not in `bridge.blocked_data_types`
- **Communication**: if `source.internal_only` or `target.internal_only` is True but `bridge.internal_only` is False, that is a violation

Each violation is described as a human-readable string, e.g.: `"Financial: bridge allows $500 but source only allows $200"`.

Use existing `_is_time_window_tighter` and `_paths_covered_by` helper functions from `src/care_platform/constraint/envelope.py` where applicable.

### Call site

Call `validate_bridge_tightening()` during bridge activation. Specifically, in `Bridge._activate()` (which 3102 extends), call this validator on the computed bridge envelope before committing the trust records. If violations are returned, raise `ValueError` with the violation list rather than activating the bridge.

## Where

- `src/care_platform/constraint/bridge_envelope.py` (add `validate_bridge_tightening()`)
- `src/care_platform/workspace/bridge.py` (call validator in `_activate()`)

## Evidence

- [ ] `validate_bridge_tightening()` function implemented in `bridge_envelope.py`
- [ ] Returns empty list when bridge envelope is validly tighter than both source and target
- [ ] Detects financial dimension violations (bridge wider than source or target budget)
- [ ] Detects operational dimension violations (extra allowed actions, missing blocked actions)
- [ ] Detects temporal dimension violations (bridge window exceeds source or target window)
- [ ] Detects data access dimension violations (extra read/write paths, missing blocked types)
- [ ] Detects communication dimension violations (internal_only bypassed on bridge)
- [ ] Returns clear, human-readable violation messages for each violation
- [ ] `Bridge._activate()` calls `validate_bridge_tightening()` and raises `ValueError` on violations
- [ ] All unit tests pass
