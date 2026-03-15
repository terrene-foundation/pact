# 3901: Red Team Deferred Fixes

**Milestone**: 10.1 — Red Team Remediation
**Priority**: Immediate (blocks /codify)

## Items

### C4: eatp_bridge.py None financial guard

- `map_envelope_to_constraints()` crashes on `config.financial=None`
- Add None guard matching envelope.py's existing pattern
- File: `src/care_platform/trust/eatp_bridge.py`

### M1: Circular import gradient ↔ enforcement

- `gradient.py._apply_proximity()` does deferred import of `enforcement.py`
- Move the shared mapping dicts to a shared constants module or inline them
- Files: `src/care_platform/constraint/gradient.py`, `src/care_platform/constraint/enforcement.py`

### M4: Fail-open on unparseable envelope dates

- `select_active_envelope` treats unparseable `expires_at` as non-expired (fail-open)
- Change to treat as expired (fail-closed)
- File: `src/care_platform/constraint/envelope.py`

### M5: ReasoningTraceStore unbounded memory

- Add `maxlen` parameter with default 10,000 (match ShadowEnforcer pattern)
- File: `src/care_platform/trust/reasoning.py`

### M7: Fail-closed lint ↔ contract inconsistency

- Contract document says `return None` is a violation but lint doesn't enforce it
- Update contract document to note it's a manual review item
- File: `docs/architecture/fail-closed-contract.md`

### L2: Windowed metrics don't track previous_pass_rate

- `_compute_metrics_from_results` doesn't set `previous_pass_rate`
- Fix to compute from the preceding window
- File: `src/care_platform/trust/shadow_enforcer.py`

### L3: PostureHistoryStore returns mutable records

- `get_history()` returns shallow copies — records themselves are mutable
- Use `model_copy()` for deep immutability
- File: `src/care_platform/persistence/posture_history.py`

### L4: Delegation trace semantic error

- `create_delegation_trace` puts constraints in `alternatives_considered`
- Move to `evidence` field (more semantically correct)
- File: `src/care_platform/trust/reasoning.py`

### H2: PostureHistoryStore thread safety

- Add `threading.Lock` for concurrent access (Phase 3 preparation)
- File: `src/care_platform/persistence/posture_history.py`
