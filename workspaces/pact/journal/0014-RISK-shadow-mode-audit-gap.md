---
type: RISK
date: 2026-04-02
created_at: 2026-04-02T16:55:00+08:00
author: agent
session_turn: 12
project: pact
topic: Shadow mode audit persistence requires correct AuditChain API usage
phase: redteam
tags: [shadow-mode, audit, enforcement-mode, security, RT30]
---

# Shadow Mode Audit Gap — API Contract Fragility

## Finding

During RT30 Round 1, the security reviewer flagged that `_ShadowDelegate` and `_PassthroughDelegate` produced no audit records (H1 — HIGH). The initial fix attempted to persist shadow verdicts via `AuditChain.append()` but used incorrect parameter names (`action_type`, `details` instead of `agent_id`, `action`, `verification_level`, `metadata`), causing silent failure under the `except Exception: pass` guard.

Round 2 caught this because the catch-all `except` that was designed as a safety net against infrastructure failure was instead masking a programming error. The fix was corrected to use the proper `AuditChain.append()` signature.

## Risk

The `except Exception: pass` pattern in shadow audit persistence is a double-edged sword:

- **Correct use**: Shadow mode must never fail due to audit infrastructure issues — the `pass` ensures this
- **Incorrect use**: A wrong API call silently fails forever, creating a false sense of observability

This pattern is specifically dangerous when:

1. `AuditChain.append()` signature changes in future L1 releases
2. The shadow delegate is tested only via "does it approve everything" (functional correctness) without verifying audit records are actually persisted

## Mitigation

1. The fix now uses the correct API: `append(agent_id=..., action="shadow:...", verification_level=AUTO_APPROVED, metadata={...})`
2. Future: Consider adding a dedicated test that verifies shadow audit records ARE persisted (not just that the delegate returns approved)
3. Consider narrowing the except clause to specific infrastructure exceptions rather than bare `Exception`

## For Discussion

1. Should the `except Exception: pass` be narrowed to `except (OSError, ConnectionError)` to catch only infrastructure failures while surfacing programming errors?
2. If `_PassthroughDelegate` (disabled mode) produces no audit trail at all, is this acceptable when `PACT_ALLOW_DISABLED_MODE=true` explicitly opts in?
3. Given that the initial fix was caught only by Round 2 of the red team, what does this say about the effectiveness of single-round reviews for API contract correctness?
