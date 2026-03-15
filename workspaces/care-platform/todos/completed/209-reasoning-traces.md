# 209: Implement Reasoning Traces (EATP v2.2)

**Milestone**: 2 — EATP Trust Integration
**Priority**: Medium (regulatory traceability)
**Estimated effort**: Medium
**Status**: COMPLETED — 2026-03-12

## Completion Summary

`ReasoningTrace` and `ReasoningTraceStore` implemented in `care_platform/trust/reasoning.py`.

- `care_platform/trust/reasoning.py` — `ReasoningTrace`, `ReasoningTraceStore`, `ConfidentialityLevel`
- Five-level confidentiality: PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED, SEALED
- Content hash automatically computed on creation (dual-binding signature pattern)
- Selective disclosure: `get_traces_for_audience(max_level)` returns only accessible traces
- `REASONING_REQUIRED` constraint pattern supported
- `tests/unit/trust/test_reasoning.py` — trace creation, confidentiality enforcement, selective disclosure

## Description

Implement EATP v2.2 reasoning traces — structured records of WHY trust decisions were made.

## Tasks

- [x] `care_platform/trust/reasoning.py` with `ReasoningTrace` model
- [x] Five-level confidentiality classification
- [x] Dual-binding via content hash
- [x] `REASONING_REQUIRED` constraint type
- [x] Selective disclosure (full vs redacted for external review)
- [x] Traces attach to delegation records and audit anchors
- [x] Unit tests (trace creation, confidentiality, selective disclosure)

## Acceptance Criteria

- [x] Reasoning traces attach to delegation records and audit anchors
- [x] Confidentiality levels enforced
- [x] Selective disclosure works for different audience levels
- [x] Unit tests passing

## References

- `care_platform/trust/reasoning.py`
- `tests/unit/trust/test_reasoning.py`
