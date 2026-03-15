# 3805: Reasoning Traces Enhancement

**Milestone**: 9 — Governance Hardening (Tier 2)
**Item**: 2.2
**Priority**: Can run in parallel with 3804 and 3806

## What

Enhance `care_platform/trust/reasoning.py` (186 lines) with signing payload, factory functions, and size validation.

### Current state

- `ReasoningTrace` model with trace_id, decision, rationale, alternatives, evidence, confidence, confidentiality, trace_hash, genesis_binding_hash
- `compute_hash()` — SHA-256 content hash
- `verify_integrity()` — timing-safe comparison
- `redact()` — confidentiality-aware redaction
- `ReasoningTraceStore` — append-only with add(), get_for_record(), get_with_clearance(), export()
- **No `to_signing_payload()`** — can't independently sign traces with Ed25519
- **No factory functions** — each trace created manually with all fields
- **No size validation** — unbounded decision/rationale strings (DoS vector)

### Changes needed

#### 1. `to_signing_payload()` method on ReasoningTrace

- Serialize trace to canonical JSON (sorted keys, no whitespace) for Ed25519 signing
- Include: trace_id, parent_record_type, parent_record_id, decision, rationale, confidentiality, created_at, genesis_binding_hash
- Exclude: trace_hash (derived), mutable display fields
- Use `jcs` (RFC 8785) for canonical serialization — already in pyproject.toml dependencies
- Return `bytes` suitable for `cryptography` Ed25519 signing

#### 2. Factory functions (class methods on ReasoningTrace)

- `create_delegation_trace(delegator_id, delegatee_id, capabilities, constraints, rationale)` — for DELEGATE operations
- `create_posture_trace(agent_id, from_posture, to_posture, trigger, evidence)` — for posture transitions
- `create_verification_trace(agent_id, action, result, level)` — for VERIFY operations
- Each factory pre-fills: parent_record_type, confidence level, methodology, and generates trace_id

#### 3. Size validation (in `__post_init__` or validator)

- `decision`: max 10,000 characters
- `rationale`: max 50,000 characters
- `alternatives_considered`: max 100 items
- `evidence`: max 100 items
- Raise `ValueError` with clear message on violation
- These limits prevent DoS through unbounded trace payloads

## Where

- **Modified**: `src/care_platform/trust/reasoning.py`
- **Tests**: `tests/unit/trust/test_reasoning.py` (enhance existing)

## Evidence

- [ ] `to_signing_payload()` returns canonical JSON bytes via jcs
- [ ] Signing payload is deterministic (same trace → same bytes)
- [ ] `create_delegation_trace()` factory works with correct pre-fills
- [ ] `create_posture_trace()` factory works with correct pre-fills
- [ ] `create_verification_trace()` factory works with correct pre-fills
- [ ] Size validation rejects oversized decision (>10K chars)
- [ ] Size validation rejects oversized rationale (>50K chars)
- [ ] Size validation rejects oversized alternatives/evidence (>100 items)
- [ ] Existing tests still pass (no regression)
- [ ] Standards review (eatp-expert): signing payload format compatible with EATP signing
- [ ] Security review: canonical serialization prevents signing ambiguity attacks

## Dependencies

- None (independent of Tier 1 work)
