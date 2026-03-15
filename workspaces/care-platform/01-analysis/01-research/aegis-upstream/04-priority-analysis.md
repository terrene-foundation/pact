# Aegis Upstream — Priority and Dependency Analysis

**Date**: 2026-03-14

---

## Priority Tiers

### Tier 1 — Correctness Gaps (implement first)

These are issues where the current CARE Platform behavior is incorrect or incomplete relative to spec requirements.

| Priority | ID  | Strength                  | Rationale                                                                                                                                                                                |
| -------- | --- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1       | S9  | EATP Decorators           | **Completely missing.** Spec-defined operations (VERIFY, AUDIT, shadow) lack their natural programmatic interface. Every trust-sensitive function currently requires manual boilerplate. |
| P2       | S6  | Per-Agent Circuit Breaker | **Critical correctness gap.** Global circuit breaker means one failing agent can deny service to all agents. Violates CARE isolation principle.                                          |
| P3       | S4  | Proximity Thresholds      | **Missing as standalone.** The verification gradient cannot properly escalate actions near constraint boundaries without configurable proximity thresholds.                              |

### Tier 2 — Interoperability (implement second)

These prevent vocabulary drift and ensure multiple CARE implementations can interoperate.

| Priority | ID  | Strength           | Rationale                                                                                                             |
| -------- | --- | ------------------ | --------------------------------------------------------------------------------------------------------------------- |
| P4       | S10 | Posture Adapter    | Bidirectional CARE/EATP posture mapping with fail-closed defaults. Prevents vocabulary divergence as ecosystem grows. |
| P5       | S11 | Dimension Adapter  | Canonical dimension mapping between implementation field names and spec identifiers. Same rationale as S10.           |
| P6       | S1  | Behavioral Scoring | Complementary to existing structural scoring. Requires spec definition first (medium IP risk).                        |

### Tier 3 — Hardening (implement third)

These improve existing implementations to match Aegis quality levels.

| Priority | ID  | Strength              | Rationale                                                                     |
| -------- | --- | --------------------- | ----------------------------------------------------------------------------- |
| P7       | S5  | Shadow Enforcer       | Add memory cap, metrics aggregation, fail-safe error handling.                |
| P8       | S7  | Reasoning Traces      | Add signing payload, factory functions, size validation.                      |
| P9       | S12 | Posture History       | Add full trigger taxonomy, reasoning trace storage, strict append-only.       |
| P10      | S3  | Ed25519 Signing       | Add key management service, dual-signature, multi-sig, revoked-key semantics. |
| P11      | S2  | Verification Gradient | Add proximity integration, recommendations, timing metrics.                   |
| P12      | S8  | Fail-Closed Audit     | Systematic audit + CI lint rule for trust layer error paths.                  |

---

## Dependency Map

```
S9 (EATP Decorators)
  └── depends on: existing trust operations infrastructure (exists)

S6 (Per-Agent Circuit Breaker)
  └── depends on: existing circuit breaker (exists, needs refactor)

S4 (Proximity Thresholds)
  └── depends on: S2 (Verification Gradient) — proximity feeds into gradient
  └── but S4 can be implemented standalone first

S10 (Posture Adapter)
  └── depends on: existing posture definitions (exists)

S11 (Dimension Adapter)
  └── depends on: existing constraint definitions (exists)

S1 (Behavioral Scoring)
  └── depends on: CARE spec update (must define scoring factors first)
  └── depends on: existing structural scoring (exists, complementary)

S5/S7/S12/S3/S2 (Hardening)
  └── independent of each other
  └── each depends only on its own existing implementation

S8 (Fail-Closed Audit)
  └── depends on: all other trust layer work being complete
  └── should run LAST as a systematic audit
```

---

## Effort Estimates (Relative)

| Tier      | Strengths               | Estimated Scope  | Notes                                              |
| --------- | ----------------------- | ---------------- | -------------------------------------------------- |
| Tier 1    | S9, S6, S4              | ~15-20 tasks     | S9 is new module; S6 is refactor; S4 is extraction |
| Tier 2    | S10, S11, S1            | ~10-15 tasks     | S1 requires spec work first                        |
| Tier 3    | S5, S7, S12, S3, S2, S8 | ~20-25 tasks     | Many small enhancements to existing modules        |
| **Total** | **12 strengths**        | **~45-60 tasks** | Across 3 tiers                                     |

---

## Risk Assessment

| Risk                   | Impact                                                                         | Mitigation                                                               |
| ---------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| S1 IP boundary         | Medium — could appear to favor Founder's commercial entity                     | Define in CARE spec first with independent factor weights                |
| S10 vocabulary lock-in | Medium — Aegis display labels could become canonical                           | Use only CARE/EATP canonical names                                       |
| S6 refactor scope      | Medium — changing from global to per-agent circuit breaker affects all callers | Create registry wrapper preserving existing API                          |
| S9 decorator adoption  | Low — developers must learn new pattern                                        | Migration path (shadow -> audited -> verified) provides gradual adoption |
| Test coverage          | Low — each new module needs comprehensive tests                                | RT13 established 2914-test baseline; maintain coverage                   |
