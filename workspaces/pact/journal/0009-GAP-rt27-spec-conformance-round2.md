---
type: GAP
date: 2026-04-01
created_at: 2026-04-01T09:00:00+08:00
author: agent
session_id: rt27-spec-conformance
session_turn: 15
project: pact
topic: RT27 spec-conformance round 2 — 6 new findings, 10 RT26 fixes verified, 4 findings fixed
phase: redteam
tags:
  [
    spec-conformance,
    red-team,
    pact-thesis,
    emergency-bypass,
    temporal-dimension,
    shadow-mode,
    input-validation,
  ]
---

# RT27: Spec-Conformance Red Team Round 2

Follow-up to RT26 (journal 0007). Manual audit of PACT-Core-Thesis v0.1-WA against
L3 pact-platform v0.3.0 + L1 kailash-pact v0.5.0.

## Methodology

5 parallel red team agents were deployed but hit rate limits before producing their
analysis summaries (they completed file reading and code analysis but couldn't write
findings). The audit was completed manually, cross-referencing every normative spec
requirement against implementation code.

## Results

- **10 RT26 fixes verified**: All 10 implemented TODOs (01-04, 18, 21-25) passed verification
- **6 new findings**: 0 Critical, 1 High, 3 Medium, 2 Low (1 retracted)
- **4 findings fixed in this session**: F1, F3, F4 (F2 was retracted — false positive)

### Fixes Applied

| Finding     | Issue                                                            | Fix                                                       |
| ----------- | ---------------------------------------------------------------- | --------------------------------------------------------- |
| F1 (HIGH)   | Metrics router missing `validate_record_id()` on `agent_address` | Added validation                                          |
| F3 (MEDIUM) | Emergency bypass scope skipped Temporal dimension                | Added `active_hours` + `blackout_periods` validation      |
| F4 (MEDIUM) | `disabled` enforcement mode had no production guard              | Added `PACT_ALLOW_DISABLED_MODE=true` env var requirement |

### Remaining (tracked, not fixed)

| Finding                              | Severity | Status                 |
| ------------------------------------ | -------- | ---------------------- |
| F5: MCP tool_name format validation  | MEDIUM   | Track for next session |
| F6: YAML deploy endpoint size limit  | LOW      | Track                  |
| F7: Post-incident review enforcement | LOW      | Track                  |

## For Discussion

1. The temporal dimension gap (F3) was in code that already validated 4 of 5 EATP
   dimensions — was the omission deliberate (temporal bypass is acceptable in emergencies)
   or accidental? The spec says "approver's own envelope" without excluding any dimension.

2. If the `PACT_ALLOW_DISABLED_MODE` env guard had not been added (F4), what deployment
   scenarios could result in governance being silently disabled in production?

3. Given that 16 L1 TODOs remain blocked on upstream, should we prioritize contributing
   to kailash-py to unblock them, or continue hardening the L3 layer?
