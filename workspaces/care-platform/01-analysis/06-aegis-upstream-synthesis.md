# Aegis Foundational Strengths — Analysis Synthesis (Revised)

**Date**: 2026-03-14 (revised after ecosystem deep-dive)
**Superseded by**: `07-aegis-upstream-revalidation.md` (2026-03-15)
**Brief**: `workspaces/care-platform/briefs/02-aegis-foundational-strengths.md`
**Red-teamed by**: deep-analyst, care-expert, constitution-expert
**Deep-dived**: kailash-py EATP SDK, CARE Platform consumption patterns

---

## Initiative Summary

Evaluate 12 foundational strengths for upstream to the CARE Platform. After deep-diving the kailash-py EATP SDK, the initiative split into two tracks:

1. **Kailash Python SDK gaps** — 11 core EATP capabilities that belong at the SDK layer
2. **CARE Platform enhancements** — 7 CARE-specific governance improvements that consume the EATP SDK

**Note**: See `07-aegis-upstream-revalidation.md` for the final revalidated analysis with 3 material corrections.

---

## Key Discovery: The CARE Platform Already Consumes EATP Correctly

The audit confirmed that the CARE Platform is NOT duplicating the EATP SDK:

- **6 trust files** import from `eatp` (scoring, postures, constraints, etc.)
- **31 files** are CARE-specific governance extensions explicitly marked with `EATP-GAP` annotations where they fill gaps the SDK doesn't yet provide
- The architecture is sound: EATP = protocol layer, CARE = governance layer

---

## Ecosystem Gap Summary

### kailash-py EATP SDK — 11 Gaps

**Workspace**: `~/repos/kailash/kailash-py/workspaces/eatp-gaps/`

| Severity | Count | Key Gaps                                                                                 |
| -------- | ----- | ---------------------------------------------------------------------------------------- |
| CRITICAL | 3     | Behavioral scoring (G1), proximity thresholds (G2), lifecycle hooks (G3)                 |
| HIGH     | 3     | Per-agent circuit breaker registry (G4), shadow bounded memory (G5), dual-signature (G6) |
| MEDIUM   | 4     | KMS stub (G7), deprecated sync path (G8), threading model (G9), adapters (G10)           |
| LOW      | 1     | Dimension registry naming (G11)                                                          |

**Notable**: S9 (EATP decorators) — `@verified`, `@audited`, `@shadow` — already exist in `packages/eatp/src/eatp/enforce/decorators.py`. The CARE Platform analysis originally planned to build these from scratch. Not needed.

### CARE Platform — 7 Enhancements (Revalidated)

| ID  | Enhancement                                                         | Type             |
| --- | ------------------------------------------------------------------- | ---------------- |
| 1.1 | EATP decorator integration (consume, not build)                     | Wire-up          |
| 1.2 | StrictEnforcer integration (post-verification enforcement)          | Wire-up (NEW)    |
| 1.3 | Verification gradient proximity + recommendations                   | Enhancement      |
| 2.1 | Shadow enforcer bounded memory (maxlen cap, change_rate, fail-safe) | Enhancement      |
| 2.2 | Reasoning traces (signing payload, factories, size validation)      | Enhancement      |
| 2.3 | Posture history (trigger taxonomy reconciliation, reasoning traces) | Enhancement      |
| 3.1 | Fail-closed contract audit + CI enforcement                         | Systematic audit |

---

## What Changed from the Original Plan

| Original Plan                            | Revised Plan                              | Reason                                          |
| ---------------------------------------- | ----------------------------------------- | ----------------------------------------------- |
| Build EATP decorators in CARE Platform   | Consume existing decorators from EATP SDK | They already exist in kailash-py                |
| Build per-agent circuit breaker in CARE  | Move to kailash-py as EATP SDK gap        | Core trust enforcement, not governance-specific |
| Build proximity thresholds in CARE       | Move to kailash-py as EATP SDK gap        | Core verification gradient capability           |
| Build behavioral scoring in CARE         | Move to kailash-py as EATP SDK gap        | Scoring is protocol-level                       |
| Build posture/dimension adapters in CARE | Move to kailash-py as EATP SDK gap        | Vocabulary mapping is protocol infrastructure   |
| Build key management in CARE             | Move to kailash-py as EATP SDK gap        | Cryptographic infra belongs in SDK              |
| 12 items in CARE Platform                | 7 items in CARE + 11 gaps in kailash-py   | Capabilities go where they belong               |
| Constitutional governance Phase 0        | Removed                                   | Phase 1, sole Founder, no external stakeholders |

---

## Risks and Considerations

| Risk                           | Impact                         | Mitigation                                                                      |
| ------------------------------ | ------------------------------ | ------------------------------------------------------------------------------- |
| All 7 CARE items are unblocked | LOW — no external dependencies | ProximityScanner already exists in EATP SDK. All items can proceed immediately. |
