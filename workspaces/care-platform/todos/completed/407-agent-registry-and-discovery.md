# 407: Agent Registry and Discovery

**Milestone**: 4 — Agent Execution Runtime
**Priority**: Medium (enables multi-team coordination)
**Estimated effort**: Small
**Completed**: 2026-03-12
**Verified by**: AgentRegistry + AgentRecord + AgentStatus + find_by_capability + staleness detection in `care_platform/execution/registry.py`; 25 unit tests pass in `tests/unit/execution/test_registry.py`

## Description

Implement the agent registry — a queryable directory of all active agents, their current state, capabilities, and trust posture. Required for cross-team communication (teams need to find and verify each other's agents) and for the human operator to understand the current state of all agent activity.

## Tasks

- [ ] Implement `care_platform/execution/registry.py`:
  - `AgentRegistry.register(agent, team, posture, envelope)` — add agent to registry
  - `AgentRegistry.deregister(agent_id)` — remove agent (on revocation or team shutdown)
  - `AgentRegistry.get(agent_id) -> AgentRecord` — lookup agent details
  - `AgentRegistry.get_team(team_id) -> list[AgentRecord]` — all agents in team
  - `AgentRegistry.find_by_capability(capability) -> list[AgentRecord]` — discovery by role
  - `AgentRegistry.get_status(agent_id) -> AgentStatus` — ACTIVE/SUSPENDED/REVOKED
- [ ] Implement `AgentRecord`:
  - agent_id, name, role, team_id, current_posture, envelope_expires_at, last_verified_at, status
  - Capability list (for discovery)
  - Public verification endpoint (for cross-team verification)
- [ ] Integrate with EATP ESA (Enterprise Service Agent) registry if applicable:
  - Check EATP SDK `src/eatp/esa/` — may already have agent discovery
  - Compose from EATP ESA if it covers this use case
- [ ] Implement registry health monitor:
  - Periodic check: are registered agents still active?
  - Auto-deregister agents that have been revoked
  - Alert if agent fails health check
- [ ] Implement `care-platform agents list [--team dm] [--status active]` CLI command
- [ ] Write integration tests for registry operations

## Acceptance Criteria

- Agents register and deregister correctly
- Discovery by capability works
- Registry reflects real-time status (revoked agents removed promptly)
- CLI list command works
- Integration tests passing

## Dependencies

- 207: Cascade revocation (deregister on revoke)
- 303: Workspace persistence (registry backed by DataFlow)
- 401: Kaizen agent bridge (agents registered when launched)

## References

- EATP SDK: `src/eatp/esa/` — ESA registry (check for reuse)
- EATP SDK: `src/eatp/registry/agent_registry.py` — existing agent registry
