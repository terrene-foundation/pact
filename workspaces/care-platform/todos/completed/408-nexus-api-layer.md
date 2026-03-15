# 408: Nexus API Layer — REST, CLI, MCP

**Milestone**: 4 — Agent Execution Runtime
**Priority**: Medium (multi-channel access to platform)
**Estimated effort**: Medium

## Description

Deploy the CARE Platform as a Nexus multi-channel application, exposing REST API, CLI, and MCP interfaces. Consult the nexus-specialist before implementing — Nexus handles the deployment topology; the task is defining what endpoints the CARE Platform needs. This enables multiple humans and external integrations to interact with the platform concurrently.

## Tasks

- [ ] Consult nexus-specialist to design API topology for CARE Platform
- [ ] Define REST API endpoints:
  - `GET /api/v1/teams` — list all active teams
  - `GET /api/v1/teams/{team_id}/agents` — list team agents
  - `GET /api/v1/agents/{agent_id}/status` — agent status and posture
  - `POST /api/v1/agents/{agent_id}/approve/{action_id}` — approve held action
  - `POST /api/v1/agents/{agent_id}/reject/{action_id}` — reject held action
  - `GET /api/v1/audit/team/{team_id}` — team audit report
  - `GET /api/v1/held-actions` — list pending approvals
  - `GET /api/v1/cost/report` — API cost report
- [ ] Implement authentication:
  - API key authentication for all endpoints (key from `.env`)
  - No unauthenticated endpoints (all platform data is sensitive)
- [ ] Implement rate limiting:
  - Per-key rate limits
  - Protect against enumeration attacks on agent/action IDs
- [ ] Implement MCP integration:
  - CARE Platform as an MCP server (agents can query it)
  - MCP tools: `approve_action`, `list_held`, `get_agent_status`
  - Consult mcp-specialist for MCP server implementation patterns
- [ ] Write integration tests for REST API endpoints
- [ ] Write E2E test: human approves held action via REST API → action executes

## Acceptance Criteria

- REST API serves all defined endpoints
- Authentication enforced on all endpoints
- MCP integration allows agent-to-platform queries
- Integration tests and one E2E test passing

## Dependencies

- 403: Human-in-the-loop approval (endpoints to expose)
- 407: Agent registry (query endpoints)
- 304: Audit query interface (report endpoints)
- Nexus: `kailash-nexus>=1.4.2`

## References

- Nexus deployment: consult nexus-specialist
- MCP: consult mcp-specialist
- `pyproject.toml`: `kailash-nexus>=1.4.2`
