# 1102: ShadowEnforcer Envelope Expiry Check

**Priority**: High
**Effort**: Small
**Source**: RT3 R3-01
**Dependencies**: None

## Problem

The ShadowEnforcer is observational — it doesn't enforce. But when the envelope is expired, it still runs the full evaluation pipeline and records metrics as if the envelope were valid. This produces misleading shadow metrics and incorrect upgrade recommendations.

## Implementation

### File: `care_platform/trust/shadow_enforcer.py`

1. Add envelope expiry check in `evaluate()` after the PSEUDO_AGENT check:
   ```python
   # RT3-01: Check envelope expiry for accurate shadow metrics
   if self._envelope.is_expired:
       return ShadowResult(
           action=action,
           agent_id=agent_id,
           shadow_verdict="BLOCKED",
           reason="Constraint envelope has expired",
           dimension_results={"expiry": "blocked"},
       )
   ```

2. Update the docstring to include the expiry check step.

## Acceptance Criteria

- [ ] ShadowEnforcer returns BLOCKED shadow result when envelope is expired
- [ ] Tests verify the behavior
- [ ] All existing tests still pass
