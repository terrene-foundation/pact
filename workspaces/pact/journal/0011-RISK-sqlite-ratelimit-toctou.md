---
type: RISK
date: 2026-04-01
created_at: 2026-04-01T15:45:00+08:00
author: agent
session_id: rt29-outstanding-items
session_turn: 45
project: pact
topic: Cross-process TOCTOU in SqliteRateLimitStore — BEGIN IMMEDIATE transaction fix
phase: redteam
tags: [emergency-bypass, rate-limiting, toctou, sqlite, multi-process, security]
---

# Cross-Process TOCTOU in SqliteRateLimitStore

## Finding

When `SqliteRateLimitStore` was first implemented, the rate limit check and record were separate
operations:

1. `_check_rate_limits()` called `store.get_history()` to count recent bypasses
2. `_record_bypass_creation()` called `store.record_creation()` to insert a row

While `EmergencyBypass._lock` (a `threading.Lock`) made this atomic within a single process, it
provided no protection across Gunicorn workers. Each worker has its own `EmergencyBypass` instance
with its own `_lock`. Two workers could both pass the rate limit check before either recorded,
allowing `MAX_BYPASSES_PER_WEEK + 1` (or more) bypasses for the same role.

## Fix

Added `atomic_check_and_record()` to the `RateLimitStore` ABC:

- **Default implementation** (in ABC): sequential `cleanup_stale()` + `get_history()` + check + `record_creation()`. Suitable for `MemoryRateLimitStore` where the outer `EmergencyBypass._lock` already provides atomicity.

- **SQLite override**: Uses `BEGIN IMMEDIATE` to acquire the SQLite write lock before reading. The entire check-and-record sequence runs within a single transaction. If the rate limit is violated, the transaction rolls back — no row is inserted. `BEGIN IMMEDIATE` ensures that a second process attempting the same operation will block on the write lock until the first completes.

## Regression Tests

Two tests verify rollback behavior:

- `test_atomic_check_and_record_rolls_back_on_violation`: fills rate limit, verifies rejection does not insert
- `test_atomic_check_and_record_cooldown_rollback`: verifies cooldown violation rolls back

## Impact

Without the fix, a multi-process deployment could exceed the 3-per-week bypass rate limit for the
same role. This undermines the PACT spec requirement that "rate limiting prevents bypass from
becoming a governance workaround."

## For Discussion

1. The `BEGIN IMMEDIATE` approach uses SQLite's file-level write lock. Under high contention (many
   workers simultaneously creating bypasses for different roles), all workers serialize on the same
   lock. Would a PostgreSQL-backed store with row-level locking perform better at scale?

2. If the `record_creation` INSERT succeeds but the `COMMIT` fails (e.g., disk full), the bypass
   record is stored in `EmergencyBypass._bypasses` (in-memory) but not in the rate limit DB. On
   the next process restart, the rate limit count resets. Should `create_bypass` catch commit
   failures and remove the in-memory record?
