# Trust Layer Patterns

Patterns for working with the CARE Platform trust and constraint layers. These patterns were established across Milestones 8-10 (EATP SDK integration, governance hardening, fail-closed audit) and validated through 3 red team rounds.

## EATP SDK Consumption Pattern

CARE wraps EATP SDK primitives — it never rebuilds them.

### Decorators (`trust/decorators.py`)

```python
from care_platform.trust.decorators import CareTrustOpsProvider, care_verified

provider = CareTrustOpsProvider(bridge)  # bridge must be initialized

@care_verified(action="read_data", provider=provider)
async def read_data(agent_id: str, path: str) -> dict:
    ...  # agent_id extracted dynamically from function args
```

- `CareTrustOpsProvider` lazily retrieves TrustOperations from EATPBridge
- Dynamic agent_id via `_extract_agent_id()` (cached signature resolution)
- Agent ID validated: alphanumeric + hyphens/underscores/dots, max 256 chars
- Migration path: `@care_shadow` → `@care_audited` → `@care_verified`

### Enforcement Pipeline (`constraint/enforcement.py`)

```python
from care_platform.constraint.enforcement import CareEnforcementPipeline

pipeline = CareEnforcementPipeline(gradient, on_held=HeldBehavior.CALLBACK, held_callback=callback)
result = pipeline.classify_and_enforce(action="draft_content", agent_id="agent-001")
# result.verdict: Verdict (AUTO_APPROVED, FLAGGED, HELD, BLOCKED)
# result.classification: CARE VerificationResult (preserved)
# result.enforced_level: CARE VerificationLevel (mapped back)
```

Key: `CARE_FLAG_THRESHOLD = 2` → 0 violations=AUTO, 1=FLAGGED, 2=HELD, valid=False=BLOCKED

### Verification Result Adapter

| CARE Field          | EATP Field           | Mapping          |
| ------------------- | -------------------- | ---------------- |
| level=BLOCKED       | valid=False          | Direct           |
| level=HELD          | violations=[2 items] | flag_threshold=2 |
| level=FLAGGED       | violations=[1 item]  | < flag_threshold |
| level=AUTO_APPROVED | violations=[]        | Clean            |

See `care_result_to_eatp_result()` in `constraint/enforcement.py` for the full mapping table.

## Fail-Closed Contract

**Rule**: Every error path in trust/constraint must deny, not allow.

- `scripts/lint_fail_closed.py` — CI enforcement (43 files scanned)
- `docs/architecture/fail-closed-contract.md` — Contract documentation
- **Exempt**: `shadow_enforcer.py`, `shadow_enforcer_live.py`, `decorators.py` shadow mode

**What the lint catches**: bare `except: pass`, `return True` in except blocks.
**Manual review**: `return None` in except blocks (too many false positives in queries).

## ShadowEnforcer Patterns

- **Bounded memory**: `maxlen=10_000`, oldest 10% trimmed when exceeded
- **Thread safety**: `threading.Lock` around `_results` and `_metrics`
- **Fail-safe**: `evaluate()` catches all exceptions, returns safe AUTO_APPROVED result
- **Change rate**: `previous_pass_rate` tracks delta between windows
- **Lifetime vs window**: `get_metrics()` = cumulative lifetime; `get_metrics_window()` = accurate windowed

## Reasoning Trace Patterns

- **Size limits**: decision 10K, rationale 50K, alternatives 100 items, evidence 100 items
- **Signing**: `to_signing_payload()` → canonical JSON bytes via JCS (RFC 8785)
- **Factories**: `create_delegation_trace()`, `create_posture_trace()`, `create_verification_trace()`
- **Store bounded**: `ReasoningTraceStore(maxlen=10_000)` with oldest-10% trimming

## Posture History Patterns

- **10 trigger types**: INCIDENT, REVIEW, SCHEDULED, CASCADE_REVOCATION, MANUAL, TRUST_SCORE, ESCALATION, DOWNGRADE, DRIFT, APPROVAL
- **Append-only**: `__setattr__` guard blocks `_records` reassignment; monotonic sequence numbers
- **Thread safety**: `threading.Lock` on `record_change()`
- **Immutable returns**: `get_history()` returns `model_copy()` deep copies
