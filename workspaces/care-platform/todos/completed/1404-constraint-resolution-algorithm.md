# M14-T04: Constraint resolution algorithm

**Status**: ACTIVE
**Priority**: High
**Milestone**: M14 — CARE Formal Specifications
**Dependencies**: 1301-1304

## What

Implement formal constraint resolution when multiple envelopes apply (agent + team + org). Resolution rule: most restrictive wins per dimension.

- Financial: min of max_spend_usd
- Operational: intersection of allowed_actions, union of blocked_actions
- Temporal: intersection of active windows
- Data Access: intersection of read/write paths, union of blocked types
- Communication: most restrictive (internal_only if any says so)

## Where

- New: `src/care_platform/constraint/resolution.py`

## Evidence

- Unit tests: single envelope pass-through, two envelopes pick tightest per dimension, three-level hierarchy (org→team→agent)
