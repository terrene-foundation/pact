# 1104: Log Swallowed Exception in EATPBridge.get_trust_chain()

**Priority**: High
**Effort**: Tiny
**Source**: RT3 R3-11
**Dependencies**: None

## Problem

`EATPBridge.get_trust_chain()` has `except Exception: return None` with no logging. A misconfigured trust store, network error, or serialization bug would be completely invisible. This violates the codebase's own `no-stubs.md` rule against silently swallowing errors.

The pattern used in `verify_action` (which logs at WARNING level before returning a failure result) should be followed.

## Implementation

### File: `care_platform/trust/eatp_bridge.py`

Add logging to the except block (~line 629):
```python
except Exception as exc:
    logger.warning(
        "Failed to retrieve trust chain for agent '%s': %s",
        agent_id,
        exc,
    )
    return None
```

## Acceptance Criteria

- [ ] Exception is logged at WARNING level with agent_id and exception message
- [ ] Behavior remains unchanged (still returns None)
- [ ] All existing tests pass
