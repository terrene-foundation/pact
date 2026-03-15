# 109: Create Workspace-as-Knowledge-Base Model

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (core CARE architecture concept)
**Estimated effort**: Medium

## Description

Implement the workspace-as-knowledge-base abstraction — each workspace is an agent team's institutional memory, containing briefs, analysis, plans, todos, and operational artifacts.

## Tasks

- [ ] Define `care_platform/workspace/model.py`:
  - `Workspace` model:
    - Workspace ID
    - Name, description
    - Path (filesystem location)
    - Team ID (assigned team)
    - Lifecycle phase (analyze → plan → implement → validate → codify)
    - Knowledge structure (briefs/, analysis/, plans/, todos/, etc.)
  - `WorkspaceRegistry` — Track all active workspaces
- [ ] Define `care_platform/workspace/lifecycle.py`:
  - Workspace creation (initialize directory structure)
  - Phase transitions (with validation gates)
  - Session management (session notes, context preservation)
- [ ] Define standard workspace directory structure:
  ```
  workspaces/<name>/
    briefs/          — User input surface
    01-analysis/     — Research and findings
    02-plans/        — Approved plans
    03-user-flows/   — User flow definitions
    04-validate/     — Red team and review
    05-codify/       — Captured knowledge
    todos/active/    — Active work items
    todos/completed/ — Completed work items
  ```
- [ ] Implement workspace discovery (scan for existing workspaces)
- [ ] Write unit tests for:
  - Workspace creation with correct directory structure
  - Lifecycle phase transitions
  - Registry operations (add, list, find)

## Acceptance Criteria

- Workspace model captures all institutional memory concepts
- Directory structure creation produces correct layout
- Lifecycle phases track correctly
- Unit tests passing

## References

- Existing workspace structure in this repo (`workspaces/care-platform/`)
- Analysis synthesis: workspace-as-knowledge-base concept
