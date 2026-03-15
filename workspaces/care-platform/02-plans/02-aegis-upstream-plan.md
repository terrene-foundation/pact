# CARE Platform — Upstream Enhancements Plan

**Date**: 2026-03-15 (revalidated)
**Brief**: `workspaces/care-platform/briefs/02-aegis-foundational-strengths.md`
**Analysis**: `workspaces/care-platform/01-analysis/07-aegis-upstream-revalidation.md`

---

## Key Principles

1. **Capabilities belong where they belong**: Core EATP capabilities belong in kailash-py. CARE Platform adds governance orchestration on top.
2. **Consume, don't duplicate**: Where the EATP SDK already provides primitives (`@verified`, `@audited`, `@shadow`, `StrictEnforcer`), CARE wraps them with governance context.
3. **Intentional differences are NOT duplication**: CARE's scoring, circuit breaker, and ShadowEnforcer serve different purposes from their EATP counterparts (see `07-aegis-upstream-revalidation.md` for details).

### What moved to kailash-py EATP SDK

| Strength                                | Where It Belongs                                                           | Why                                                                                         |
| --------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| S9 — EATP Decorators                    | **Already in kailash-py** (`packages/eatp/src/eatp/enforce/decorators.py`) | `@verified`, `@audited`, `@shadow` already exist. CARE Platform just needs to consume them. |
| S4 — Proximity Thresholds               | **kailash-py EATP SDK** (gap G2)                                           | Core verification gradient capability, not governance-specific                              |
| S6 — Per-Agent Circuit Breaker Registry | **kailash-py EATP SDK** (gap G4)                                           | Core trust enforcement, not governance-specific                                             |
| S1 — Behavioral Scoring                 | **kailash-py EATP SDK** (gap G1)                                           | Complements structural scoring — protocol-level concern                                     |
| S3 — Dual-Signature / Key Management    | **kailash-py EATP SDK** (gaps G6, G7)                                      | Cryptographic infrastructure belongs in the SDK                                             |
| S10 — Posture Adapter                   | **kailash-py EATP SDK** (gap G10)                                          | Cross-implementation vocabulary mapping is protocol-level                                   |
| S11 — Dimension Adapter                 | **kailash-py EATP SDK** (gap G10)                                          | Same — canonical mappings are protocol infrastructure                                       |

**Workspace notes**: `~/repos/kailash/kailash-py/workspaces/eatp-gaps/` — 11 gaps (3 CRITICAL, 3 HIGH, 4 MEDIUM, 1 LOW)

### What stays in CARE Platform

The CARE Platform plan focuses on **CARE-specific governance extensions** — features that consume the EATP SDK and add organizational governance on top.

---

## Revised Scope: CARE Platform Only

### Tier 1 — Consume EATP SDK Better

#### 1.1 EATP Decorator Integration (S9) — CONSUME, NOT BUILD

**Deliverable**: Wire up existing EATP decorators into CARE Platform trust layer

The decorators already exist in `eatp.enforce.decorators`. The CARE Platform needs to:

- Import and re-export with CARE-specific defaults (e.g., `@care_verified` as a thin wrapper around `@verified` with CARE trust ops provider)
- Wire `CareTrustOpsProvider` to supply the trust operations context
- Document the migration path: `@care_shadow` → `@care_audited` → `@care_verified`

**Tests**: Integration tests verifying CARE trust ops work through EATP decorators.

#### 1.2 StrictEnforcer Integration (NEW)

**Deliverable**: Wire EATP's `StrictEnforcer` into CARE's verification pipeline

The EATP SDK has `StrictEnforcer` in `eatp.enforce` — a post-verification enforcement layer. GradientEngine (pre-verification) classifies action strings into verification levels. StrictEnforcer (post-verification) decides what to do with the verification result. These compose as sequential pipeline stages:

- Wire StrictEnforcer after VERIFY, consuming `VerificationResult → Verdict`
- CARE's GradientEngine feeds into StrictEnforcer (not replaces it)
- Map StrictEnforcer verdicts to CARE verification gradient levels

**Tests**: Integration tests verifying GradientEngine → StrictEnforcer pipeline.

#### 1.3 Verification Gradient — Proximity + Recommendations (S2 + S4)

**Deliverable**: Enhance `care_platform/constraint/gradient.py`

The EATP SDK already has `ProximityScanner` in `eatp.enforce.proximity` (flag at 80%, hold at 95%, per-dimension overrides, monotonic escalation). CARE needs to:

- Integrate `ProximityScanner` into CARE's verification gradient pipeline
- Add `_build_recommendations()` for actionable suggestions per verification result
- `duration_ms` timing already exists — no work needed there

**Tests**: Unit tests for recommendation generation, integration tests for proximity integration.

---

### Tier 2 — CARE Governance Extensions

#### 2.1 Shadow Enforcer Hardening (S5)

**Deliverable**: Enhance `care_platform/trust/shadow_enforcer.py`

- Bounded memory: 10,000 record cap, trim oldest 10% when exceeded
- `change_rate` metric (pass_rate and block_rate already exist)
- Fail-safe: shadow check errors caught, never block actual execution
- Thread safety for concurrent access

**Note**: ShadowEnforcer is CARE's governance evaluation engine (7-step middleware pipeline). Do NOT replace it with trust-plane's ShadowStore, which is a persistence layer. Add bounded memory pattern only.

#### 2.2 Reasoning Traces Enhancement (S7)

**Deliverable**: Enhance `care_platform/trust/reasoning.py`

- `to_signing_payload()` for independent cryptographic signing
- Factory functions: `create_delegation_trace()`, `create_posture_trace()`, `create_verification_trace()`
- Size validation: decision 10K max, rationale 50K, max 100 alternatives/evidence

#### 2.3 Posture History Enhancement (S12)

**Deliverable**: Enhance `care_platform/persistence/posture_history.py`

- Reconcile trigger type taxonomy: CARE Platform has 4 types (INCIDENT, REVIEW, SCHEDULED, CASCADE_REVOCATION), Aegis has 9. This is a taxonomy reconciliation, not a simple addition — some types overlap, some are unique to each.
- Reasoning trace JSON storage per transition
- Strict append-only guarantee (no update/delete methods)

---

### Tier 3 — Systematic Quality

#### 3.1 Fail-Closed Contract Audit (S8)

**Deliverable**: Systematic audit + CI enforcement

- Audit all trust layer files for fail-closed compliance
- CI lint rule flagging `except` blocks that return True/allowed in trust layer
- Document fail-closed contract as CARE Platform specification requirement

---

## Removed from CARE Platform Scope

These items are core EATP capabilities tracked in kailash-py workspace notes:

| Item                                 | Now Where                    | Kailash Gap ID |
| ------------------------------------ | ---------------------------- | -------------- |
| EATP Decorators (build from scratch) | Already exists in kailash-py | N/A            |
| Per-Agent Circuit Breaker Registry   | kailash-py                   | G4             |
| Constraint Proximity Thresholds      | kailash-py                   | G2             |
| Behavioral Trust Scoring             | kailash-py                   | G1             |
| EATP Lifecycle Hooks                 | kailash-py                   | G3             |
| Dual-Signature Pattern               | kailash-py                   | G6             |
| Key Management Service               | kailash-py                   | G7             |
| Posture/Dimension Adapters           | kailash-py                   | G10            |

### What Was Kept (and Why) — Red Team Corrections

| Item                   | Previous Recommendation  | Why It Stays in CARE                                                                         |
| ---------------------- | ------------------------ | -------------------------------------------------------------------------------------------- |
| Scoring (`scoring.py`) | Delegate to EATP         | Posture mapping is intentionally inverted (CARE: autonomous=trusted, EATP: autonomous=risky) |
| Circuit breaker        | Replace with EATP        | Different purpose: CARE protects verification pipeline, EATP downgrades agent postures       |
| ShadowEnforcer         | Replace with trust-plane | Governance evaluation engine, not a persistence layer                                        |

---

## Implementation Order

```
Tier 1 (unblocked):  1.1 (decorators) → 1.2 (StrictEnforcer) → 1.3 (proximity + recommendations)
Tier 2 (parallel):   2.1 (shadow bounded memory) | 2.2 (reasoning traces) | 2.3 (posture history)
Tier 3 (after T2):   3.1 (fail-closed audit)
```

Tier 1 items are sequential. Tier 2 items are independent and can run in parallel. Tier 3 runs after Tier 2 since the audit should cover the newly enhanced modules.

---

## Quality Gates

Each enhancement must pass:

1. Unit tests (all new/changed code)
2. Integration tests (CARE trust ops through EATP SDK)
3. Standards review (care-expert or eatp-expert)
4. Security review (for crypto and trust-sensitive code)
5. Gold standards validation (naming, licensing, terminology)
