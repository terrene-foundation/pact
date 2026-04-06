---
type: RISK
date: 2026-04-06
created_at: 2026-04-06T14:35:00+08:00
author: agent
session_id: gh-issues-analysis
session_turn: 15
project: pact
topic: Bootstrap mode directly tensions with PACT fail-closed and monotonic tightening
phase: analyze
tags: [bootstrap, monotonic-tightening, fail-closed, security, pact-spec]
---

# Bootstrap Mode vs Monotonic Tightening

## Risk

Issue #23 proposes temporary permissive envelopes for new orgs. All three independent analysts flagged this as the highest-risk issue because it directly tensions with two PACT core invariants:

1. **Fail-closed**: L1's `compute_effective_envelope()` returns `None` when no envelopes exist, which `verify_action()` treats as maximally restrictive. Bootstrap mode would override this to be permissive.

2. **Monotonic tightening**: PACT guarantees child envelopes can only narrow, never widen. A bootstrap envelope substitutes for a missing parent, creating a permissive baseline that real envelopes later tighten from. This isn't technically a violation (no parent exists to widen beyond), but it creates a governance gap: actions under bootstrap are ungoverned.

## Three Specific Attack Vectors

1. **Permanent escape hatch**: If bootstrap can be re-enabled after real envelopes are configured, it effectively widens governance by reverting to permissive defaults.
2. **Ungoverned actions**: Everything done during bootstrap operates outside the intended hierarchy. Retroactive constraints don't apply.
3. **Expiry race**: If bootstrap expires mid-execution, the agent's next governance check suddenly fails (maximally restrictive).

## Resolution

All three analysts converge on: **L3 only, never L1**. The PACT specification layer must not contain a permissive-default path. Bootstrap is an operational convenience, not a governance primitive.

Mitigations:

- Explicit opt-in (`PACT_ALLOW_BOOTSTRAP_MODE=true`)
- Max TTL (72 hours), single-use per org
- Bootstrap envelopes cap at CONFIDENTIAL (no SECRET/TOP_SECRET access)
- Bounded financial/operational limits (not unlimited)
- Full audit marking on every bootstrap-mode action
- Post-bootstrap compliance review workflow

## For Discussion

1. The gap analyst initially recommended L1 engine support (Option B), arguing audit trail integrity. The PACT specialist overruled on principle: L1 must never contain a permissive-default path. If L3's audit marking of bootstrap actions were later found to be insufficient (e.g., gaps in the EATP chain), would that change the L1/L3 decision?

2. Bootstrap mode is functionally similar to emergency bypass (time-limited permission elevation). Could bootstrap be modeled as a special case of emergency bypass rather than a new feature, reusing the existing bypass infrastructure?

3. If bootstrap envelopes cap at CONFIDENTIAL and the org's first real use case requires SECRET access, the org is blocked during bootstrap. Is this the right tradeoff, or should bootstrap allow configurable classification caps?
