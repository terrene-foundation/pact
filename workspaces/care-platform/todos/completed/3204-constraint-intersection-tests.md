# Todo 3204: Constraint Intersection Tests

**Milestone**: M32 — Constraint Intersection
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3201, 3202, 3203

## What

TDD test file covering all M32 deliverables. Verify the envelope intersection logic, information sharing modes, and bridge tightening validation across all five CARE constraint dimensions and their edge cases.

### Test groups to cover

**Envelope intersection — per-dimension tests (3201)**

Financial:

- Three envelopes with explicit budgets: result is the minimum
- One envelope with `None` budget: result is `None`
- All envelopes with `None` budget: result is `None`

Operational:

- `allowed_actions` intersection: actions in all three are kept; actions in only two are excluded
- `allowed_actions` where no common actions exist: result is empty list (all actions blocked)
- `blocked_actions` union: action blocked in any one envelope appears in result
- `max_actions_per_hour` min: test with explicit values; test with one `None` (treated as infinity, finite values win)
- `reasoning_required_actions` union

Temporal:

- Three non-overlapping windows: result is temporally blocked sentinel
- Three overlapping windows: result is the tightest overlap
- One envelope with no temporal restriction: other two windows determine the result
- Overnight window handling (e.g., 22:00–06:00 overlapping with 20:00–08:00)

Data Access:

- `read_paths` exact-pattern intersection: only patterns shared by all three are kept
- `read_paths` with no shared patterns: empty list result
- `blocked_data_types` union

Communication:

- `internal_only` is False in all three: result is False
- `internal_only` is True in one of three: result is True
- `allowed_channels` intersection

**Full 5-dimension intersection (3201)**

- Single test with realistic envelopes across all five dimensions to confirm the composed result is correct

**Information sharing modes (3202)**

- `check_field("budget.annual")` matches `"budget.*"` rule and returns that rule's mode
- `check_field("content.public")` matches `"*.public"` rule
- `check_field("unmatched.path")` returns `default_mode`
- Most specific rule wins: `"budget.annual"` matches `"budget.annual"` before `"budget.*"` if both are in rules list
- Rules tried in order (first match wins)
- AUTO_SHARE access: action passes through with AUTO_APPROVED verification level
- REQUEST_SHARE access: action returns HELD verification level
- NEVER_SHARE access: action returns BLOCKED verification level

**Bridge tightening validation (3203)**

- Valid intersection passes (empty list returned)
- Financial violation: bridge allows more than source
- Operational violation: bridge allows action not in source
- Operational violation: source blocks action not blocked on bridge
- Temporal violation: bridge window wider than source window
- Data access violation: bridge has extra read path not in source
- Communication violation: source is internal_only but bridge is not
- Multiple violations returned in a single call (all violations detected, not just first)

## Where

- `tests/unit/constraint/test_bridge_envelope.py` (new file)

## Evidence

- [ ] `tests/unit/constraint/test_bridge_envelope.py` exists
- [ ] All financial dimension tests pass (min value, None propagation)
- [ ] All operational dimension tests pass (intersection, union, min rate)
- [ ] All temporal dimension tests pass (overlap, no-overlap, overnight)
- [ ] All data access dimension tests pass (pattern intersection, union blocked types)
- [ ] All communication dimension tests pass
- [ ] Full 5-dimension integration test passes
- [ ] All sharing mode tests pass (glob matching, ordering, three modes)
- [ ] All bridge tightening validation tests pass (valid and 5 violation types)
- [ ] Multiple-violations test passes
- [ ] `pytest tests/unit/constraint/test_bridge_envelope.py` exits with code 0
