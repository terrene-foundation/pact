# Aegis Upstream — Revalidation with EATP SDK + trust-plane

**Date**: 2026-03-15
**Context**: Re-analysis after syncing EATP SDK skills, trust-plane 0.2.0 dependency, and correcting scope boundaries.

---

## Scope Correction

The CARE Platform is open-source (Apache 2.0). This analysis covers ONLY:

- **CARE Platform** (`~/repos/terrene/care`) — governance orchestration
- **Kailash Python SDK** (`~/repos/kailash/kailash-py`) — EATP SDK, trust-plane

All references to proprietary repositories have been removed.

---

## Red Team Corrections to Previous Analysis

The previous analysis (06-aegis-upstream-synthesis.md) contained 3 material errors:

### Correction 1: scoring.py is NOT duplicated

The codebase audit flagged `care_platform/trust/scoring.py` as duplicating `eatp.scoring`. This is **wrong**. The two have intentionally different semantics:

| Dimension       | CARE scoring.py                                | EATP scoring.py                                  |
| --------------- | ---------------------------------------------- | ------------------------------------------------ |
| Posture mapping | DELEGATED = 1.0 (more autonomous = more trust) | DELEGATED = 20/100 (more autonomous = more risk) |
| Grade levels    | 7 (A+, A, B+, B, C, D, F)                      | 5 (A, B, C, D, F)                                |
| Output scale    | 0.0–1.0                                        | 0–100                                            |
| Sync model      | Synchronous                                    | Async                                            |

The posture mapping reflects a **design philosophy difference**: CARE's governance model treats higher autonomy as evidence of earned trust. EATP's scoring model treats higher autonomy as higher risk. Both are valid — they answer different questions.

**Decision**: Keep CARE's scoring. Do not delegate to EATP.

### Correction 2: circuit_breaker.py is NOT replaceable

The audit recommended consuming EATP's `PostureCircuitBreaker`. This would remove CARE's verification-pipeline fail-safe:

| Dimension  | CARE circuit_breaker.py                | EATP PostureCircuitBreaker          |
| ---------- | -------------------------------------- | ----------------------------------- |
| Purpose    | Protect the verification system itself | Downgrade agent postures on failure |
| Lock model | threading.Lock (sync)                  | asyncio.Lock (async)                |
| On open    | Raises CircuitBreakerOpen → BLOCKED    | Downgrades posture                  |
| Scope      | Global (verification pipeline)         | Per-agent (behavioral)              |

These solve different problems. CARE's breaker says "if the verifier is down, deny everything." EATP's breaker says "if an agent keeps failing, reduce its autonomy." Both are needed.

**Decision**: Keep CARE's circuit breaker. Consider adding EATP's PostureCircuitBreaker as a complementary per-agent behavior layer in a future milestone.

### Correction 3: ShadowEnforcer is NOT replaceable by trust-plane

The audit suggested trust-plane's `shadow_store` could replace CARE's ShadowEnforcer. This conflates a governance evaluation engine with a persistence layer:

| Dimension  | CARE ShadowEnforcer                                                                       | trust-plane ShadowStore                              |
| ---------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Purpose    | Governance evaluation — 7-step middleware pipeline, posture upgrade evidence              | Persistence — SQLite storage with retention policies |
| Key output | PostureEvidence, upgrade eligibility                                                      | ShadowSession, tool call records                     |
| Evaluation | Constraint envelopes, gradient classification, posture escalation, never-delegated checks | Simple pattern matching                              |

**Decision**: Keep CARE's ShadowEnforcer for evaluation logic. Use trust-plane for persistence if needed. The bounded memory fix (item 2.1) is still needed.

---

## Validated CARE Platform Enhancements

After re-analysis, the following 6 items are confirmed for CARE Platform scope:

### Tier 1 — Consume EATP SDK Better

**1.1 EATP Decorator Integration (S9)**

- Status: **VALID — start immediately**
- The EATP SDK has `@verified`, `@audited`, `@shadow` decorators in `eatp.enforce.decorators`
- CARE needs thin wrappers (`@care_verified`, etc.) that supply CareTrustOpsProvider
- Wire the migration path: shadow → audited → verified

**1.2 StrictEnforcer Integration (NEW)**

- Status: **NEW FINDING — complements GradientEngine**
- GradientEngine is pre-verification (classifies action strings into verification levels)
- StrictEnforcer is post-verification (decides what to do with the verification result)
- These compose as sequential pipeline stages, not replacements
- CARE should wire StrictEnforcer after VERIFY, consuming VerificationResult → Verdict

**1.3 Verification Gradient — Proximity + Recommendations (S2 + S4)**

- Status: **VALID — EATP SDK already has ProximityScanner, ready to integrate**
- EATP SDK has `ProximityScanner` in `eatp.enforce.proximity` (flag at 80%, hold at 95%, per-dimension overrides, monotonic escalation)
- Integrate ProximityScanner into CARE's verification gradient pipeline
- Add `_build_recommendations()` for actionable suggestions per verification result
- `duration_ms` timing already exists — confirmed, no work needed there

### Tier 2 — CARE Governance Hardening

**2.1 Shadow Enforcer Bounded Memory (S5)**

- Status: **VALID — straightforward fix**
- Add maxlen cap (10,000) with oldest-10% trimming
- Add `change_rate` metric (pass_rate and block_rate already exist)
- Add fail-safe error handling around shadow evaluation
- Do NOT replace ShadowEnforcer with trust-plane — add bounded memory pattern only

**2.2 Reasoning Traces Enhancement (S7)**

- Status: **VALID**
- Add `to_signing_payload()` for independent cryptographic signing
- Add factory functions: `create_delegation_trace()`, `create_posture_trace()`, `create_verification_trace()`
- Add size validation: decision 10K max, rationale 50K, max 100 alternatives/evidence

**2.3 Posture History Enhancement (S12)**

- Status: **VALID — taxonomy reconciliation**
- CARE has 4 trigger types (INCIDENT, REVIEW, SCHEDULED, CASCADE_REVOCATION)
- Brief describes 9 types. Some overlap, some are unique to each.
- Reconcile into a unified taxonomy for CARE Platform
- Add reasoning trace JSON storage per transition
- Enforce strict append-only (no update/delete)

### Tier 3 — Systematic Quality

**3.1 Fail-Closed Contract Audit (S8)**

- Status: **VALID**
- Audit all trust layer files for fail-closed compliance
- CI lint rule flagging unsafe exception handling in trust layer
- Document fail-closed contract as specification requirement

---

## What Was Removed (and Why)

| Item                        | Previous Status       | Why Removed                                                           |
| --------------------------- | --------------------- | --------------------------------------------------------------------- |
| Scoring delegation to EATP  | Was "HIGH priority"   | Posture mapping is intentionally inverted — not duplication           |
| Circuit breaker replacement | Was "HIGH priority"   | Different purpose (verification fail-safe vs agent posture downgrade) |
| ShadowEnforcer replacement  | Was recommended       | Governance engine, not a persistence layer                            |
| ConfidentialityLevel import | Was "MEDIUM priority" | Circular import workaround; low value, low risk                       |
| All kailash-rs references   | Was in plan           | Out of scope — proprietary                                            |

---

## Implementation Order

```
Tier 1 (unblocked):  1.1 (decorators) → 1.2 (StrictEnforcer) → 1.3 (proximity + recommendations)
Tier 2 (parallel):   2.1 (shadow bounded memory) | 2.2 (reasoning traces) | 2.3 (posture history)
Tier 3 (after T2):   3.1 (fail-closed audit)
```

Tier 2 items are independent and can run in parallel. Tier 3 runs after Tier 2 since the audit should cover the newly enhanced modules.
