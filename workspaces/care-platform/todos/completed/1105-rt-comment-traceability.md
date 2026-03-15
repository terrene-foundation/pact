# 1105: RT Comment Traceability Gaps

**Priority**: Medium
**Effort**: Tiny
**Source**: RT3 R3-05, R3-12
**Dependencies**: None

## Problem

Three traceability gaps where RT fixes exist in code but aren't discoverable via grep:

1. **RT2-04** (channel HMAC): Code in `messaging.py:124-130,176-178` has no `RT2-04` comment. Test `TestRT2_04_MessagingChannelHMAC` exists.

2. **RT2-20** (real delegation ID): Code in `eatp_bridge.py:413` (`delegation_id=delegation.id`) has no `RT2-20` comment. Test `TestRT2_20_RealDelegationId` exists.

3. **RT-30** (emergency halt): Referenced at lines 140,149,174,211,222 of middleware.py but not listed in the module-level docstring.

## Implementation

1. Add `# RT2-04: Channel-level HMAC-SHA256 MAC` near the channel_secret logic in `messaging.py`
2. Add `# RT2-20: Use real delegation record ID, not synthetic` near line 413 in `eatp_bridge.py`
3. Add `RT-30: Emergency halt mechanism blocks all actions until resumed.` to the middleware module docstring

## Acceptance Criteria

- [ ] `grep -r "RT2-04" care_platform/` finds the production code
- [ ] `grep -r "RT2-20" care_platform/` finds the production code
- [ ] `grep -r "RT-30" care_platform/constraint/middleware.py` includes the module docstring
