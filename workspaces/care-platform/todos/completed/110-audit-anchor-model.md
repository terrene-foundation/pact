# 110: Create Audit Anchor Model

**Milestone**: 1 — Project Foundation & Core Models
**Priority**: High (EATP Element 5 — tamper-evident records)
**Estimated effort**: Medium

## Description

Implement the audit anchor model — the tamper-evident record of every agent action. Each anchor hashes the previous, forming a chain that proves no records have been altered or removed.

## Tasks

- [ ] Define `care_platform/audit/anchor.py`:
  - `AuditAnchor` model:
    - Anchor ID
    - Previous anchor hash (forms chain)
    - Agent ID (who acted)
    - Action description (what was done)
    - Constraint envelope reference (what was allowed)
    - Verification result (gradient level: auto/flagged/held/blocked)
    - Timestamp
    - Hash (SHA-256 of all fields + previous anchor hash)
    - Optional: reasoning trace reference (v2.2 extension)
  - `AuditChain` — Ordered sequence of anchors with integrity verification
- [ ] Implement chain integrity verification:
  - Walk the chain, verify each anchor's hash against its content + previous hash
  - Detect gaps (missing anchors), tampering (hash mismatch), ordering violations
- [ ] Implement anchor creation:
  - Auto-create anchor for every agent action
  - Include verification gradient result
  - Chain to previous anchor
- [ ] Implement chain export (for external audit):
  - Export as JSON with integrity proofs
  - Support selective export (time range, agent, team)
- [ ] Write unit tests for:
  - Anchor creation and hashing
  - Chain integrity verification (valid chain, tampered chain, gap detection)
  - Export format

## Acceptance Criteria

- Audit anchors capture every action with full context
- Chain integrity verification detects tampering
- Export produces auditable records
- Unit tests cover chain integrity edge cases

## References

- EATP specification: Audit Anchor (Element 5)
- EATP SDK Phase 1: Existing audit models
