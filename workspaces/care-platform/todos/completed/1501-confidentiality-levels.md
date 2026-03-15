# M15-T01: Confidentiality levels — promote to first-class constraint

**Status**: ACTIVE
**Priority**: High
**Milestone**: M15 — EATP v2.2 Alignment
**Dependencies**: 1301-1304

## What

Five confidentiality levels (PUBLIC, RESTRICTED, CONFIDENTIAL, SECRET, TOP_SECRET) already exist in `trust/reasoning.py` as `ConfidentialityLevel`. Promote to platform-wide concept: add to `config/schema.py` as a config option, integrate with constraint envelope (each envelope can have a confidentiality classification), enforce in data access evaluation.

## Where

- Modify: `src/care_platform/config/schema.py`, `src/care_platform/constraint/envelope.py`, `src/care_platform/trust/reasoning.py`

## Evidence

- Tests: envelope evaluation denies access to data above the envelope's confidentiality clearance
