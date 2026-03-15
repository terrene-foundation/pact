# 103: Create Constraint Envelope Data Model

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (core CARE concept)
**Estimated effort**: Medium

## Description

Implement the constraint envelope data model — the five-dimension boundary definition that governs what each agent can and cannot do. This is the core CARE governance primitive.

## Tasks

- [ ] Define `care_platform/constraint/envelope.py` — Pydantic model:
  - `ConstraintEnvelope` with five dimensions:
    1. **Financial** — spending limits, budget allocation authority
    2. **Operational** — allowed actions, blocked actions, scope boundaries
    3. **Temporal** — operating hours, blackout periods, rate limits, review windows
    4. **Data Access** — read scope, write scope, PII access, classification levels
    5. **Communication** — internal/external channels, publication authority, audience
  - Each dimension has: allowed actions, blocked actions, flagged conditions, rate limits
  - Envelope metadata: ID, version, created_by, expires_at (90-day default), parent_envelope_id
- [ ] Define `care_platform/constraint/dimension.py` — Per-dimension models
- [ ] Implement envelope composition (child envelope must be subset of parent — monotonic tightening)
- [ ] Implement `validate_tightening(parent, child)` — verifies child only narrows, never expands
- [ ] Implement envelope expiry logic (90-day default, renewal required)
- [ ] Implement `evaluate(action, envelope)` — returns verification gradient level
- [ ] Write unit tests for:
  - Valid envelope creation
  - Monotonic tightening validation (valid and invalid cases)
  - Dimension-level evaluation
  - Expiry logic
  - Edge cases (empty dimensions, conflicting rules)

## Acceptance Criteria

- All five constraint dimensions modeled with structured types
- Monotonic tightening validation works correctly
- Envelope evaluation correctly classifies actions into gradient levels
- 90-day expiry enforced with clear renewal path
- Comprehensive unit tests passing

## Standards Alignment

- CARE specification: Constraint envelopes are the Execution Plane's boundary definition
- EATP specification: Constraint Envelope is Element 3 of the Trust Lineage Chain
- EATP SDK: `to_schema_dict()` / `from_schema_dict()` compatibility with canonical JSON Schema

## References

- EATP SDK Phase 1 (`packages/eatp/`) — Existing ConstraintEnvelope model
- `~/repos/terrene/terrene/docs/02-standards/interoperability/schemas/constraint-envelope.schema.json`
- DM team constraint envelopes in analysis: `01-analysis/01-research/03-eatp-trust-model-dm-team.md`
