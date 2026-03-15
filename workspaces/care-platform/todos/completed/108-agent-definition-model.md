# 108: Create Agent Definition Model

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (bridges COC agent definitions to platform)
**Estimated effort**: Medium

## Description

Create the agent definition model — the structured representation of an agent's identity, role, capabilities, constraint envelope, and team membership. This is the abstraction layer between COC-style markdown agent definitions and runtime execution.

## Tasks

- [ ] Define `care_platform/config/agent.py`:
  - `AgentDefinition` model:
    - Agent ID (unique, immutable)
    - Name, description, role
    - Team ID (which team this agent belongs to)
    - Constraint envelope ID (reference to envelope definition)
    - Capability attestation reference
    - Trust posture (current level)
    - Allowed tools (list of tool/action names)
    - LLM backend preference (optional — Claude, GPT, Gemini, local)
    - Model preference (optional — specific model within backend)
  - `TeamDefinition` model:
    - Team ID
    - Team name, description
    - Workspace path
    - Team Lead agent ID
    - Specialist agent IDs
    - Universal agent IDs (Knowledge Curator, Cross-Team Coordinator)
- [ ] Create markdown-to-model parser:
  - Parse existing `.claude/agents/*.md` format into AgentDefinition
  - Extract role, allowed-tools, description
  - Map to constraint envelope (derived from agent rules/scope)
- [ ] Create model-to-markdown generator:
  - Generate Claude Code compatible agent definitions from AgentDefinition
  - Preserve compatibility with COC setup pattern
- [ ] Write unit tests for:
  - AgentDefinition creation and validation
  - TeamDefinition creation and validation
  - Markdown parsing round-trip (parse → generate → parse = identical)

## Acceptance Criteria

- Agent and team definition models complete
- Markdown parser handles existing COC agent format
- Round-trip (parse → generate → parse) produces identical results
- Unit tests passing

## References

- `.claude/agents/` — Existing agent definitions (COC format)
- DM team agents: `01-analysis/01-research/03-eatp-trust-model-dm-team.md`
