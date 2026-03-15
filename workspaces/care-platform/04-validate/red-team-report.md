# CARE Platform Red Team Report

**Date**: 2026-03-12
**Agents deployed**: security-reviewer, care-expert, eatp-expert, intermediate-reviewer, gold-standards-validator, deep-analyst
**Test suite**: 1,217 tests passing (functional correctness confirmed)

---

## Executive Summary

The CARE Platform has strong foundational architecture — clean package separation, comprehensive test coverage, and correct CARE terminology throughout. However, the red team found a systemic pattern: **governance mechanisms are defined as data structures but not wired into the enforcement pipeline.** The platform has the right concepts in the right places, but several critical safety invariants exist as dead code.

**Totals (deduplicated)**: 10 CRITICAL, 12 HIGH, 11 MEDIUM, 6 LOW

---

## CRITICAL Findings (10)

### RT-01: LICENSE file attributes copyright to commercial entity with non-Apache restrictions

**Source**: Gold Standards Validator (V1, V2)
**File**: `LICENSE`

The LICENSE file says "Copyright 2025 Integrum Global Pte Ltd" and appends "ADDITIONAL TERMS AND CONDITIONS" that restrict commercial use. This means the CARE Platform is NOT Apache 2.0 as claimed everywhere else. Every source file header, README, CONTRIBUTING.md, and pyproject.toml says Apache 2.0, but the actual LICENSE file contradicts this.

**Impact**: Legal foundation of the project is incorrect. Any adopter reading the LICENSE file sees a commercial entity's copyright with additional restrictions.

**Fix**: Replace LICENSE with standard Apache 2.0 text. Copyright: "2026 Terrene Foundation". Remove all additional terms.

---

### RT-02: Monotonic tightening validation exists but is never called

**Source**: CARE Expert (F1), EATP Expert (F11)
**Files**: `trust/delegation.py`, `trust/eatp_bridge.py`, `constraint/envelope.py`

`DelegationManager.validate_tightening()` and `ConstraintEnvelope.is_tighter_than()` are implemented but never called in the delegation flow. `create_delegation()` delegates to the EATP SDK without checking whether the child envelope loosens any parent constraint. A child agent can be given a higher budget, more actions, or fewer restrictions than its parent.

**Impact**: The central safety invariant of CARE — "delegations can only reduce authority, never expand it" — is unenforced.

**Fix**: Call `validate_tightening()` in `DelegationManager.create_delegation()` before calling `bridge.delegate()`. Raise `ValueError` if tightening is violated.

---

### RT-03: NEVER_DELEGATED actions are not checked during action processing

**Source**: CARE Expert (F2)
**Files**: `trust/posture.py`, `constraint/middleware.py`, `constraint/gradient.py`

`NEVER_DELEGATED_ACTIONS` (modify_constraints, modify_governance, financial_decisions, etc.) and `is_action_always_held()` are defined but never consulted by the middleware, gradient engine, or hook enforcer. An agent at DELEGATED posture could execute `modify_constraints` and have it AUTO_APPROVED.

**Impact**: Actions permanently reserved for humans can be auto-approved by agents.

**Fix**: Add `TrustPosture.is_action_always_held()` check in `VerificationMiddleware.process_action()` — force HELD for any action in the NEVER_DELEGATED set regardless of gradient rules.

---

### RT-04: No verification that approvers are human (or authorized)

**Source**: CARE Expert (F3), Security Reviewer (H-5), Deep Analyst (AV1)
**Files**: `execution/approval.py`, `constraint/middleware.py`, `api/endpoints.py`

`approve()` and `approve_request()` accept any `approver_id` string with no authentication, authorization, or self-approval prevention. An agent could approve its own HELD actions.

**Impact**: The Trust Plane's primary human interaction point has no trust enforcement.

**Fix**: (1) Validate approver_id against a list of authorized human approvers. (2) Reject self-approval (approver_id != agent_id). (3) Add authentication to approval endpoints.

---

### RT-05: Two disconnected approval queues — middleware holds are invisible to API

**Source**: CARE Expert (F12), Deep Analyst (AV1), Code Quality (C2)
**Files**: `constraint/middleware.py` (own `_approval_queue`), `execution/approval.py` (separate `ApprovalQueue`)

The middleware creates `ApprovalRequest` objects in its internal list. The API reads from a separate `ApprovalQueue` in the execution layer. These never communicate. A human using the API sees an empty queue while the middleware silently holds actions.

**Impact**: Human-in-the-loop approval is architecturally broken. HELD actions cannot reach human approvers through the API.

**Fix**: Remove middleware's internal queue. When the middleware determines HELD, submit a `PendingAction` to the shared `ApprovalQueue`. Accept an `ApprovalQueue` in the middleware constructor.

---

### RT-06: Message authentication is forgeable — no HMAC, payload not covered

**Source**: Security Reviewer (C-1, C-2)
**File**: `trust/messaging.py`

`AgentMessage._compute_signature()` uses plain SHA-256 with no secret key (not HMAC). The payload dict is excluded from the hash. Any party can forge a message claiming to be from any agent, and message content can be modified without detection.

**Impact**: Inter-agent messaging provides no actual authentication or integrity.

**Fix**: Use Ed25519 per-agent signatures (infrastructure already exists in `signing.py`). Include `json.dumps(self.payload, sort_keys=True)` in the signed content.

---

### RT-07: Reasoning traces incompatible with EATP specification

**Source**: EATP Expert (F1, F2, F3)
**File**: `trust/reasoning.py`

Three deviations: (1) Confidentiality levels are wrong — implementation has PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED/SEALED; spec requires PUBLIC/RESTRICTED/CONFIDENTIAL/SECRET/TOP_SECRET with different ordering. (2) Trace structure uses a single `reasoning` string; spec requires structured `decision`/`rationale`/`alternatives_considered`/`evidence`/`confidence` fields. (3) No dual-binding cryptographic signing; hash is truncated to 64 bits.

**Impact**: Reasoning traces cannot interoperate with any EATP-compliant system.

**Fix**: Align confidentiality levels with EATP spec. Add structured fields. Use full SHA-256 and bind trace hash into parent record signing payload.

---

### RT-08: Unsigned envelopes accepted in evaluation pipeline

**Source**: Deep Analyst (AV3a)
**Files**: `constraint/middleware.py`, `execution/hook_enforcer.py`

`VerificationMiddleware` and `HookEnforcer` accept raw `ConstraintEnvelope` objects — no `SignedEnvelope` wrapper required. Ed25519 signing infrastructure exists but is never enforced during evaluation. An agent with memory access could construct a permissive envelope.

**Impact**: Constraint envelope signing is available but optional — the trust guarantee is decorative.

**Fix**: Require `SignedEnvelope` in middleware/hook_enforcer constructors. Verify signature on each evaluation cycle (or cache with TTL).

---

### RT-09: Trust posture level is never consulted during action processing

**Source**: CARE Expert (F10)
**Files**: `constraint/middleware.py`, `constraint/gradient.py`

The five trust postures (PSEUDO_AGENT through DELEGATED) govern how much autonomy an agent should have, but the middleware, gradient engine, and hook enforcer never check posture. A PSEUDO_AGENT (interface-only, no autonomy) is treated identically to a DELEGATED agent.

**Impact**: Trust postures are metadata with no enforcement effect. An agent at SUPERVISED posture ("human approves") can have actions AUTO_APPROVED.

**Fix**: Add posture check in middleware: at PSEUDO_AGENT, all actions BLOCKED; at SUPERVISED, all non-trivial actions HELD; at higher postures, defer to gradient rules.

---

### RT-10: Approval queue has no automatic expiry, escalation, or dead-man's-switch

**Source**: Deep Analyst (AV1a), CARE Expert (F11)
**Files**: `execution/approval.py`, `constraint/middleware.py`

`ApprovalQueue.expire_old()` exists but must be explicitly called — no scheduler or background task invokes it. If the sole approver is unavailable, HELD actions accumulate forever with no timeout, escalation, or safety halt.

**Impact**: Solo founder bottleneck can deadlock the entire platform.

**Fix**: (1) Implement automatic expiry via background task. (2) Add queue depth threshold that triggers safety halt. (3) Define escalation path for Phase 2+ governance.

---

## HIGH Findings (12)

| ID    | Finding                                                                                              | Source            | Fix Complexity                                |
| ----- | ---------------------------------------------------------------------------------------------------- | ----------------- | --------------------------------------------- |
| RT-11 | Wildcard capabilities (`*`) defeat EATP Element 4 (Capability Attestation)                           | EATP F4, CARE F8  | Medium — map agent capabilities explicitly    |
| RT-12 | Constraint mapping to EATP is lossy — drops blackout_periods, blocked_data_types, api_cost_budget    | EATP F5           | Medium — add typed constraint mappings        |
| RT-13 | Audit chain unsigned, no lineage hash, no witnesses, no external anchoring                           | EATP F6, CARE F18 | High — requires signing infrastructure        |
| RT-14 | Cascade revocation doesn't touch EATP SDK trust chains                                               | EATP F7           | Low — call SDK revocation in cascade flow     |
| RT-15 | Temporal dimension substantially weaker — blackout_periods ignored, timezone not applied             | CARE F4           | Low — implement existing fields               |
| RT-16 | Data Access dimension — read_paths/write_paths not enforced, only blocked_data_types substring check | CARE F5, F6       | Medium — enforce path-based access            |
| RT-17 | `external_requires_approval` not enforced during evaluation                                          | CARE F7           | Low — add check in envelope evaluation        |
| RT-18 | Expired envelopes still evaluate actions (no expiry check in evaluate_action)                        | CARE F9           | Low — add `is_expired` check                  |
| RT-19 | FilesystemStore path traversal — crafted IDs can escape base directory                               | Security H-2      | Low — validate/sanitize IDs                   |
| RT-20 | EnvelopeVersionHistory mutates SignedEnvelope after signing, invalidating signature                  | Security H-3      | Low — re-sign after mutation                  |
| RT-21 | Timing-variable string comparison for hash verification                                              | Security H-1      | Low — use `hmac.compare_digest()`             |
| RT-22 | Bridge permissions mutable after activation; approver identity not verified                          | Deep Analyst AV5  | Medium — freeze permissions, verify approvers |

---

## MEDIUM Findings (11)

| ID    | Finding                                                                                | Source            |
| ----- | -------------------------------------------------------------------------------------- | ----------------- |
| RT-23 | Nonce set in MessageChannel grows unbounded (memory exhaustion)                        | Security H-4      |
| RT-24 | No HELD result from envelope evaluation (soft limits not implemented)                  | EATP F8           |
| RT-25 | PSEUDO_AGENT is dead end — no upgrade path, never used as default                      | EATP F9           |
| RT-26 | CapabilityAttestation defined but never connected to bridge                            | EATP F10          |
| RT-27 | Financial checks per-action only, no cumulative budget tracking in envelope            | CARE F13          |
| RT-28 | Overnight temporal windows broken (string comparison fails for wrap-around)            | CARE F14          |
| RT-29 | ShadowEnforcer maps shadow-blocked to "incidents" (conflates hypothetical with actual) | CARE F15          |
| RT-30 | No runtime human intervention mechanism (emergency halt/pause)                         | CARE F16          |
| RT-31 | Two incompatible `VerificationLevel` enums with same name                              | Code Quality C1   |
| RT-32 | Missing license headers on 4 Python files                                              | Gold Standards V6 |
| RT-33 | Government body references (IMDA, MAS) in public red-team docs                         | Gold Standards V5 |

---

## LOW Findings (6)

| ID    | Finding                                                                           | Source                 |
| ----- | --------------------------------------------------------------------------------- | ---------------------- |
| RT-34 | Audit chain export doesn't redact sensitive metadata                              | Security L-4           |
| RT-35 | Temporal evaluation ignores timezone configuration                                | EATP F12, Security L-3 |
| RT-36 | Genesis validation checks signature presence, not cryptographic validity          | EATP F13               |
| RT-37 | Circuit breaker resets on process restart                                         | Security L-2           |
| RT-38 | Mutable default arguments on Pydantic fields (inconsistent with codebase pattern) | Code Quality C3        |
| RT-39 | Timestamp field naming varies without convention                                  | Code Quality M7        |

---

## Systemic Patterns

Three root causes explain the majority of findings:

### Pattern A: "Defined but not wired" (RT-02, RT-03, RT-08, RT-09, RT-26)

Governance mechanisms are implemented as standalone methods and models but never called in the enforcement pipeline. The code has the right architecture but missing integration wiring.

### Pattern B: "Dual systems, no bridge" (RT-05, RT-14, RT-31)

Parallel implementations of the same concept (two approval queues, two verification level enums, CARE audit chain + EATP audit) with no integration between them.

### Pattern C: "Trust boundary without enforcement" (RT-04, RT-06, RT-11, RT-22)

Security-critical boundaries (message authentication, approval authorization, capability attestation, bridge permissions) accept any input without validation.

---

## Defenses That Held

| Defense                                                                    | Tested By                | Result |
| -------------------------------------------------------------------------- | ------------------------ | ------ |
| YAML safe_load (no deserialization attacks)                                | Security                 | PASS   |
| No hardcoded secrets in codebase                                           | Security, Gold Standards | PASS   |
| Circuit breaker fail-safe (BLOCKED when verification unavailable)          | Security, Deep Analyst   | PASS   |
| Hook enforcer fail-safe (BLOCKED when unconfigured)                        | Security                 | PASS   |
| Ed25519 signing implementation (constant-time, correct library usage)      | Security                 | PASS   |
| CARE terminology consistency (Trust Plane, five dimensions, posture names) | Gold Standards           | PASS   |
| No charity/IPC language                                                    | Gold Standards           | PASS   |
| Foundation independence language in all public docs                        | Gold Standards           | PASS   |
| Dual-side bridge approval required for activation                          | Deep Analyst             | PASS   |
| Bridge revocation immediately prevents access                              | Deep Analyst             | PASS   |
| Pydantic validation catches type/format errors in config                   | Deep Analyst             | PASS   |
| Cost tracking uses Decimal (no float precision errors)                     | Security                 | PASS   |
| No eval/exec on user input                                                 | Security                 | PASS   |

---

## Recommended Fix Priority

### Immediate (before first commit)

1. **RT-01**: Fix LICENSE file (legal foundation)
2. **RT-02**: Wire monotonic tightening into delegation flow
3. **RT-03**: Wire NEVER_DELEGATED check into middleware
4. **RT-05**: Unify approval queues
5. **RT-09**: Wire posture level into middleware

### Before merge/release

6. **RT-04**: Add approver authorization
7. **RT-06**: Fix message authentication
8. **RT-08**: Enforce signed envelopes
9. **RT-10**: Add automatic queue expiry
10. **RT-19**: Add path traversal protection

### Next iteration

11. RT-07: Align reasoning traces with EATP spec
12. RT-11: Replace wildcard capabilities
13. RT-13: Sign audit anchors
14. RT-15-18: Complete temporal, data access, financial dimensions
