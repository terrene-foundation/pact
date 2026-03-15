# 501: Implement Standing Bridge (Permanent Cross-Team)

**Milestone**: 5 — Cross-Functional Bridges
**Priority**: High (most common bridge type)
**Estimated effort**: Medium
**Depends on**: Milestone 4, 210
**Completed**: 2026-03-12
**Verified by**: Bridge + BridgeManager + BridgePermission + standing bridge establishment + dual-side approval in `care_platform/workspace/bridge.py`; 26 unit tests pass in `tests/unit/workspace/test_bridge.py`

## Description

Implement Standing Bridges — permanent relationships between agent teams that allow ongoing coordination. Example: DM team has a standing bridge to Standards team for content access.

## Tasks

- [ ] Implement `care_platform/workspace/bridge.py`:
  - `StandingBridge` model:
    - Bridge ID
    - Source team / workspace
    - Target team / workspace
    - Purpose (human-readable description)
    - Data access permissions (what can be shared)
    - Communication channels (which message types allowed)
    - Created by (delegator who authorized the bridge)
    - Constraint envelope (bridge-specific constraints)
  - Bridge is bidirectional (both sides must agree)
- [ ] Implement bridge establishment:
  - Both team leads approve the bridge
  - Bridge has its own constraint envelope (what can flow between teams)
  - Bridge creates audit anchors on both sides
- [ ] Implement bridge-scoped data access:
  - Source team can read specific target workspace areas
  - Read-only by default (write requires explicit grant)
  - Access scope defined in bridge constraint envelope
- [ ] Implement bridge monitoring:
  - Track data flow across bridge
  - Alert on unusual patterns
  - Regular review cycle (who reviewed when)
- [ ] Write integration tests:
  - Bridge establishment between two teams
  - Data access through bridge (valid and denied)
  - Audit trail on both sides

## Acceptance Criteria

- Standing bridges connect teams with defined permissions
- Both sides produce audit anchors for bridge interactions
- Access scope enforced
- Integration tests passing
