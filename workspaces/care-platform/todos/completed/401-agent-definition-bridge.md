# 401: Bridge Agent Definitions to Kaizen Execution

**Milestone**: 4 — Agent Execution Runtime
**Priority**: High (enables multi-agent execution)
**Estimated effort**: Large
**Depends on**: 108, Milestones 1-3

## Description

Bridge COC-style agent definitions (markdown) to Kaizen multi-agent execution. The agent definition format (todo 108) is the abstraction layer; Kaizen is the runtime.

## Tasks

- [ ] Implement `care_platform/execution/bridge.py`:
  - `AgentDefinition` → Kaizen `BaseAgent` conversion
  - Map agent role/description to system prompt
  - Map allowed tools to Kaizen tool definitions
  - Map constraint envelope to runtime enforcement hooks
  - Map LLM backend preference to Kaizen provider config
- [ ] Implement `care_platform/execution/runtime.py`:
  - `CareRuntime` — Manages multiple agent instances
  - Start/stop agent teams
  - Agent lifecycle: create, configure, execute, pause, revoke
  - Team-scoped execution contexts (agents share team workspace)
- [ ] Implement trust-aware execution:
  - Every agent action passes through verification middleware (todo 212)
  - Constraint envelope attached to agent runtime context
  - Trust posture determines verification strictness
  - ShadowEnforcer runs in parallel (when enabled)
- [ ] Implement agent communication within team:
  - Team Lead can coordinate specialist agents
  - Specialists report to Team Lead
  - Internal messaging (same workspace, no cross-team delegation needed)
- [ ] Write integration tests:
  - Agent definition → Kaizen execution → action → verification → audit
  - Multi-agent team execution
  - Trust enforcement during execution

## Acceptance Criteria

- Agent definitions correctly translated to Kaizen agents
- Multi-agent teams execute concurrently
- Trust enforcement active during execution
- Integration tests verify full execution loop
