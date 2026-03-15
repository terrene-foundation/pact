# 3804: Shadow Enforcer Bounded Memory

**Milestone**: 9 — Governance Hardening (Tier 2)
**Item**: 2.1
**Priority**: Can run in parallel with 3805 and 3806

## What

Enhance `care_platform/trust/shadow_enforcer.py` (503 lines) with bounded memory, change rate tracking, and fail-safe error handling.

### Current state

- `ShadowEnforcer` has a full 7-step evaluation pipeline
- `ShadowMetrics` has pass_rate and block_rate properties
- `get_metrics_window()` supports 30-day windowed queries
- **No per-agent result buffer limits** — grows unbounded
- **No change_rate metric** — can't detect behavioral volatility
- **No fail-safe error handling** — corrupt envelope/gradient data could crash evaluation

### Changes needed

#### 1. Bounded memory (maxlen cap with oldest-10% trimming)

- Add `maxlen: int = 10_000` parameter to `ShadowEnforcer.__init__()`
- Per-agent result storage: when an agent's results exceed `maxlen`, trim the oldest 10% (1,000 records)
- Use `collections.deque(maxlen=...)` or manual trimming on the internal results dict
- Log when trimming occurs (structlog warning with agent_id, trimmed_count)

#### 2. Change rate metric

- Add `change_rate` property to `ShadowMetrics`
- Definition: rate of pass/block transitions over a sliding window
- Implementation: compare current window pass_rate to previous window pass_rate
- `change_rate = abs(current_pass_rate - previous_pass_rate)`
- High change_rate indicates behavioral instability (useful for upgrade eligibility checks)

#### 3. Fail-safe error handling

- Wrap the 7-step evaluate() pipeline in try/except
- On ANY exception during shadow evaluation: log the error, return a safe `ShadowResult` with `would_be_blocked=False`
- Shadow evaluation must NEVER block actual execution — this is the fundamental contract
- Add specific handling for: corrupt EnvelopeEvaluation, missing gradient rules, malformed agent_id

### Design constraint

ShadowEnforcer is CARE's governance evaluation engine — NOT a persistence layer. Do NOT replace with trust-plane's ShadowStore. Only add the bounded memory pattern.

## Where

- **Modified**: `src/care_platform/trust/shadow_enforcer.py`
- **Tests**: `tests/unit/trust/test_shadow_enforcer.py` (enhance existing)

## Evidence

- [ ] maxlen parameter added with default 10,000
- [ ] Oldest 10% trimming triggers when buffer exceeds maxlen
- [ ] change_rate metric computed and accessible via ShadowMetrics
- [ ] Fail-safe: evaluate() never raises — always returns ShadowResult
- [ ] Fail-safe: corrupt input logged but doesn't block execution
- [ ] Unit tests: bounded memory trims at threshold
- [ ] Unit tests: change_rate computed correctly across windows
- [ ] Unit tests: evaluate() handles corrupt envelopes gracefully
- [ ] Thread safety added for concurrent access (threading.Lock around \_results mutation)
- [ ] Security review: no information leakage through error messages

## Dependencies

- None (independent of Tier 1 work)
