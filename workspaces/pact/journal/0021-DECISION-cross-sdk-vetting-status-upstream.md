---
type: DECISION
date: 2026-04-06
created_at: 2026-04-06T16:00:00+08:00
author: co-authored
session_id: gh-issues-implementation
session_turn: 40
project: pact
topic: Filed cross-SDK issues for VettingStatus.SUSPENDED upstream
phase: implement
tags: [cross-sdk, kailash-py, kailash-rs, vetting, upstream, l1-change]
---

# Cross-SDK VettingStatus.SUSPENDED Filed Upstream

## Decision

Filed kailash-py#309 and kailash-rs#220 for adding SUSPENDED to VettingStatus enum + FSM transition validation. L3 implementation at pact-platform is complete — FSM enforcement, multi-approver by clearance level, all endpoints — but the L1 enum extension requires a kailash-pact release.

## Rationale

The L3 vetting router enforces the FSM at the application layer, which works for the PACT platform. But FSM transition validation should ultimately live in L1 (GovernanceEngine) where it cannot be bypassed by other L1 consumers. The approach is:

1. L1 adds SUSPENDED to the enum (backward-compatible — `can_access()` already denies anything != ACTIVE)
2. L1 adds `_VALID_TRANSITIONS` table and validates in `grant_clearance()`/`transition_clearance()`
3. L1 changes `revoke_clearance()` to status transition instead of record deletion
4. L3 already enforces this — it will align with L1 once the release lands

## Alternatives Considered

- **L3-only FSM forever**: Rejected — other L1 consumers could bypass the FSM
- **Wait for L1 before implementing L3**: Rejected — L3 work is independent and delivers value now
- **Implement in L1 ourselves**: Rejected — this is a USE repo, not a BUILD repo. Filed upstream per artifact-flow rules.

## For Discussion

1. The L1 change is ~60 lines and backward-compatible. Should it be a patch (0.7.1) or minor (0.8.0) release, given it adds a new public method (`transition_clearance`)?

2. Once kailash-pact releases with the SUSPENDED enum, the L3 vetting router should delegate FSM validation to L1 rather than maintaining its own `_VALID_TRANSITIONS` table. Is this a one-line change (call `engine.transition_clearance()` instead of local validation), or does the L3 workflow logic need restructuring?

3. The kailash-rs issue (#220) was filed for cross-SDK alignment per EATP D6. The Rust SDK may not have a PACT platform consumer yet. Should the Rust issue be prioritized, or deferred until a Rust vertical needs vetting?
