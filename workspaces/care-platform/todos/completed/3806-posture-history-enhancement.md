# 3806: Posture History Enhancement

**Milestone**: 9 — Governance Hardening (Tier 2)
**Item**: 2.3
**Priority**: Can run in parallel with 3804 and 3805

## What

Enhance `care_platform/persistence/posture_history.py` (231 lines) with trigger taxonomy reconciliation, reasoning trace storage, and strict append-only enforcement.

### Current state

- `PostureChangeTrigger` enum: 4 types (INCIDENT, REVIEW, SCHEDULED, CASCADE_REVOCATION)
- `PostureChangeRecord` with record_id, agent_id, from/to posture, direction, trigger, changed_by, changed_at, reason, evidence_ref
- `PostureHistoryStore` — append-only with record_change(), get_history(), current_posture(), get_duration_at_posture()
- `PostureEligibilityChecker` — checks cooldown, time-at-posture, operations, shadow_pass_rate
- **Only 4 trigger types** — brief describes 9 (manual, trust_score, escalation, downgrade, drift, incident, evaluation, system, approval)
- **No reasoning trace storage** — evidence_ref is just a string, no structured ReasoningTrace linkage
- **Append-only is implicit** — no explicit enforcement or protection

### Changes needed

#### 1. Trigger taxonomy reconciliation

Current CARE 4 types vs brief's 9 types — reconcile into unified taxonomy:

| Current CARE       | Brief       | Reconciled         | Notes                                          |
| ------------------ | ----------- | ------------------ | ---------------------------------------------- |
| INCIDENT           | incident    | INCIDENT           | Keep                                           |
| REVIEW             | evaluation  | REVIEW             | Rename brief's "evaluation" to CARE's "REVIEW" |
| SCHEDULED          | system      | SCHEDULED          | System-initiated scheduled reviews             |
| CASCADE_REVOCATION | —           | CASCADE_REVOCATION | Keep (CARE-specific)                           |
| —                  | manual      | MANUAL             | Add: human-initiated posture change            |
| —                  | trust_score | TRUST_SCORE        | Add: triggered by scoring threshold            |
| —                  | escalation  | ESCALATION         | Add: upward posture change                     |
| —                  | downgrade   | DOWNGRADE          | Add: downward posture change (not incident)    |
| —                  | drift       | DRIFT              | Add: detected behavioral drift                 |
| —                  | approval    | APPROVAL           | Add: human approval of pending change          |

Result: 10 trigger types (4 existing + 6 new). The `direction` field already tracks upgrade/downgrade, so ESCALATION and DOWNGRADE triggers capture the _reason_ for the change, not the direction.

#### 2. Reasoning trace storage per transition

- Add optional `reasoning_trace: Optional[ReasoningTrace]` field to `PostureChangeRecord`
- When present, the trace is stored inline with the record (not just a string reference)
- Use `create_posture_trace()` factory from 3805 to generate traces
- Keep `evidence_ref` for backward compatibility (can reference external evidence)

#### 3. Strict append-only enforcement

- Make `PostureHistoryStore._records` a private attribute
- Override `__setattr__` or use `@property` to prevent direct mutation after initialization
- Add explicit `_validate_append_only()` check — any attempt to modify or delete raises `PostureHistoryError`
- Add monotonic sequence number validation — each new record's sequence must be exactly previous + 1
- Log attempts to modify history as security events

## Where

- **Modified**: `src/care_platform/persistence/posture_history.py`
- **Tests**: `tests/unit/persistence/test_posture_history.py` (enhance existing)

## Evidence

- [ ] PostureChangeTrigger enum has all 10 reconciled types
- [ ] Existing code using 4 original triggers still works (backward compatible)
- [ ] PostureChangeRecord accepts optional ReasoningTrace
- [ ] Reasoning traces stored and retrievable with posture history records
- [ ] Append-only: mutation attempts raise PostureHistoryError
- [ ] Append-only: delete attempts raise PostureHistoryError
- [ ] Monotonic sequence numbers validated on append
- [ ] Unit tests: all 10 trigger types work correctly
- [ ] Unit tests: reasoning trace round-trips through storage
- [ ] Unit tests: append-only violation raises error
- [ ] Standards review (care-expert): trigger taxonomy aligns with CARE specification
- [ ] Security review: append-only enforcement is robust

## Dependencies

- 3805 recommended (for create_posture_trace() factory), but can proceed independently using manual trace creation
