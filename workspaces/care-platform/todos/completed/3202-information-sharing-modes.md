# Todo 3202: Information Sharing Modes

**Milestone**: M32 — Constraint Intersection
**Priority**: High
**Effort**: Medium
**Source**: Phase 4 plan
**Dependencies**: 3201

## What

Implement a field-level information sharing policy system. Not all data accessible through a bridge should flow with equal ease — some fields auto-share, some require explicit approval before crossing, and some must never cross the bridge boundary at all.

### `SharingMode` enum

```python
class SharingMode(str, Enum):
    AUTO_SHARE = "auto_share"      # field passes through automatically
    REQUEST_SHARE = "request_share"  # field queued for approval (HELD)
    NEVER_SHARE = "never_share"    # field is BLOCKED, never crosses bridge
```

### `FieldSharingRule` dataclass

A Pydantic model with:

- `field_pattern: str` — glob pattern matching field paths (e.g., `"*.public"`, `"budget.*"`, `"**"`)
- `sharing_mode: SharingMode`
- `justification: str` — human-readable reason for this rule

### `BridgeSharingPolicy` model

A Pydantic model with:

- `rules: list[FieldSharingRule]` — ordered from most specific to least specific
- `default_mode: SharingMode = SharingMode.REQUEST_SHARE` — applied when no rule matches
- `check_field(field_path: str) -> SharingMode` method: matches `field_path` against `rules` using `fnmatch.fnmatch()`. Most specific match wins — this means the first rule in the list that matches is used (rules are tried in order). Returns `default_mode` if no rule matches.

### Integration with bridge access control

Add a `sharing_policy: BridgeSharingPolicy | None = None` field to the `Bridge` model in `src/care_platform/workspace/bridge.py`.

When a field access is evaluated on a bridge (in whatever access-control method exists on `Bridge`):

- `AUTO_SHARE` fields pass through immediately
- `REQUEST_SHARE` fields are queued as HELD items (return `VerificationLevel.HELD` for the action involving that field)
- `NEVER_SHARE` fields are BLOCKED (return `VerificationLevel.BLOCKED`)

`SharingMode` and `FieldSharingRule` live in `bridge_envelope.py` since they are part of the constraint intersection system. `BridgeSharingPolicy` also lives there. Integration (the `sharing_policy` field and the `check_field` call site) lives in `bridge.py`.

## Where

- `src/care_platform/constraint/bridge_envelope.py` (add `SharingMode`, `FieldSharingRule`, `BridgeSharingPolicy`)
- `src/care_platform/workspace/bridge.py` (add `sharing_policy` field, integrate `check_field` into access control)

## Evidence

- [ ] `SharingMode` enum defined with AUTO_SHARE, REQUEST_SHARE, NEVER_SHARE values
- [ ] `FieldSharingRule` model defined with `field_pattern`, `sharing_mode`, `justification` fields
- [ ] `BridgeSharingPolicy` model defined with `rules`, `default_mode`, `check_field()` method
- [ ] `check_field()` uses `fnmatch.fnmatch()` for glob matching
- [ ] `check_field()` returns the first matching rule's mode (most specific wins by list order)
- [ ] `check_field()` returns `default_mode` when no rule matches
- [ ] `Bridge` model has `sharing_policy: BridgeSharingPolicy | None` field
- [ ] Bridge access control enforces AUTO_SHARE, REQUEST_SHARE (HELD), NEVER_SHARE (BLOCKED) correctly
- [ ] All unit tests pass
