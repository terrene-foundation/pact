# 1103: Missing RT2 Test Coverage (RT2-16, RT2-19, RT2-21)

**Priority**: High
**Effort**: Small
**Source**: RT3 R3-04
**Dependencies**: None

## Problem

Three RT2 fixes exist in production code but have zero test coverage:

1. **RT2-16** (`bridge.py:554-566`): `access_through_bridge` rejects agents whose `agent_team_id` does not match the bridge's source or target team. No test verifies this.

2. **RT2-19** (`middleware.py:541,576,613,726`): Resource is included in audit anchor metadata across all handler methods. No test asserts that resource appears in the metadata.

3. **RT2-21** (`eatp_bridge.py:672-688`): `get_delegation_tree()` inverts the `_delegation_parents` map into a parent-to-children tree. No test verifies the tree structure.

## Implementation

### File: `tests/unit/test_redteam_round2.py`

Add three test classes:

1. `TestRT2_16_BridgeTeamMembership` — Create a bridge between teams A and B. Verify agent from team A can access. Verify agent from team C is rejected.

2. `TestRT2_19_ResourceInAuditMetadata` — Process an action through middleware with a resource parameter. Verify the audit anchor metadata contains the resource.

3. `TestRT2_21_DelegationTreeSync` — Create a parent delegation with two children. Call `get_delegation_tree()`. Verify the tree structure maps parent → [child1, child2].

## Acceptance Criteria

- [ ] Three new test classes added
- [ ] Each test class has at least 2 test methods (positive + negative/edge case)
- [ ] All tests pass
