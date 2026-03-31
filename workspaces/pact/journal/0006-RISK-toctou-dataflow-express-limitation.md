---
type: RISK
date: 2026-03-31
created_at: 2026-03-31T18:35:00+08:00
author: agent
session_turn: 20
project: pact
topic: TOCTOU window in decision approval cannot be fully closed with DataFlow Express
phase: redteam
tags: [security, toctou, decisions, dataflow]
---

# TOCTOU Window in Decision Approval

## Risk

The decision approve/reject TOCTOU vulnerability was mitigated with optimistic locking (double-read + envelope_version increment) but cannot be fully eliminated at the application layer. DataFlow Express does not support conditional updates (`UPDATE ... WHERE envelope_version = ?`).

## Current Mitigation

1. First read validates status is "pending" and captures `envelope_version`.
2. Second read re-checks both status and version haven't changed.
3. Update includes `envelope_version + 1`.

The TOCTOU window between step 2 and step 3 is milliseconds, but not zero.

## Impact

Two concurrent approvers could both succeed, with the last write winning silently. In a governance system, this means the audit trail may not accurately reflect which approver's decision was authoritative.

## When This Matters

- SQLite (current): Very low risk. SQLite's write lock serializes concurrent writes.
- PostgreSQL (future): Higher risk. Concurrent connections can interleave reads and writes. Would need `SELECT ... FOR UPDATE` within a transaction, or an atomic `UPDATE ... WHERE status = 'pending' AND envelope_version = ?` with `RETURNING`.

## For Discussion

- Should we file a DataFlow Express feature request for conditional updates (`express.update_where()`)?
- Is the current double-read sufficient for the SQLite deployment target, deferring the PostgreSQL fix?
- Would an advisory lock on the decision_id be a simpler defense than optimistic locking?
