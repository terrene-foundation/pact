# M17-T02: Knowledge policy enforcement

**Status**: ACTIVE
**Priority**: Medium
**Milestone**: M17 — Gap Closure: Integrity & Resilience
**Dependencies**: 1601-1605

## What

Knowledge policies are generated during workspace setup but never enforced at query time. Implement `KnowledgePolicyEnforcer` that checks data access against workspace knowledge policies before allowing reads.

## Where

- New: `src/care_platform/workspace/knowledge_policy.py`
- Modify: `src/care_platform/workspace/bridge.py` (integrate into `access_through_bridge()`)

## Evidence

- Test: access via bridge violating knowledge policy → denied
- Test: access complying with policy → allowed
