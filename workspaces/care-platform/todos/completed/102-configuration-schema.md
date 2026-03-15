# 102: Define Platform Configuration Schema

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (foundation for all platform configuration)
**Estimated effort**: Medium

## Description

Define the configuration schema for the CARE Platform — how organizations describe their structure, teams, agents, constraint envelopes, and workspace layout. This is the entry point for platform configuration.

## Tasks

- [ ] Design configuration file format (YAML recommended — readable, editable, version-controllable)
- [ ] Define `care_platform/config/schema.py` — Pydantic models for:
  - Platform-level config (name, genesis authority, default trust posture)
  - Team definitions (name, workspace path, team lead, specialist agents)
  - Agent definitions (name, role, capabilities, constraint envelope reference)
  - Workspace definitions (path, team assignment, knowledge base structure)
- [ ] Create `care_platform/config/loader.py` — Load and validate YAML config files
- [ ] Create `care_platform/config/defaults.py` — Sensible defaults for optional fields
- [ ] Support `.env` for secrets (API keys, signing keys) — never in config files
- [ ] Write unit tests for schema validation (valid configs, invalid configs, edge cases)
- [ ] Create example configuration file (`examples/care-config.yaml`)

## Acceptance Criteria

- Configuration schema defined as Pydantic models with full validation
- YAML config files load, validate, and produce typed Python objects
- Invalid configs raise clear, actionable error messages
- Example config file demonstrates all features
- Unit tests cover schema validation edge cases

## Design Notes

- Configuration should be composable — teams can be defined in separate files and imported
- Constraint envelopes are referenced by ID, not inlined (they're first-class objects)
- Agent definitions reference their constraint envelope and trust posture
- The config schema is the bridge between "configuration + methodology" and runtime execution

## References

- `.env.example` — Environment variable template
- `care_platform/config/__init__.py` — Module entry point
