---
type: RISK
date: 2026-04-01
created_at: 2026-04-01T14:00:00+08:00
author: agent
session_id: rt28-convergence
session_turn: 40
project: pact
topic: Race condition in emergency bypass rate limiting — check and record in separate locks
phase: redteam
tags: [emergency-bypass, race-condition, thread-safety, rate-limiting]
---

# Race Condition in Emergency Bypass Rate Limiting

## Finding

`EmergencyBypass.create_bypass()` performed the rate limit check (`_check_rate_limits`) and
the rate limit recording (`_record_bypass_creation`) in **separate** `self._lock` acquisitions.
Between the two, another thread could pass the rate limit check before either recorded its
creation, allowing more bypasses than `MAX_BYPASSES_PER_WEEK` (3) for the same role.

## Fix

Combined rate limit check, bypass storage, and rate limit recording into a single `self._lock`
acquisition block. The audit callback (which may do I/O) remains outside the lock to avoid
holding it during potentially slow operations.

## Impact

In a multi-threaded deployment (e.g., Gunicorn workers sharing state), concurrent emergency
bypass requests for the same role could exceed the 3-per-week rate limit. This undermines
the spec's requirement that "rate limiting prevents bypass from becoming a governance workaround."

## For Discussion

1. The fix moves the rate limit check inside the same lock as storage — could this cause
   deadlocks if the audit callback (called outside the lock) itself tries to acquire the lock?

2. If the PACT platform transitions to multi-process deployment (multiple Gunicorn workers
   with separate memory), the in-memory rate limit store would not be shared. Should rate
   limiting use a persistent store (e.g., DataFlow) instead?
