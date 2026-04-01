---
type: GAP
date: 2026-03-31
created_at: 2026-03-31T22:00:00+08:00
author: agent
session_id: rt26-spec-conformance
session_turn: 1
project: pact
topic: Spec-conformance red team — 5 parallel agents against PACT-Core-Thesis.md
phase: redteam
tags:
  [
    spec-conformance,
    red-team,
    pact-thesis,
    eatp,
    governance,
    envelopes,
    clearance,
    bridges,
    mcp,
  ]
---

# Spec-Conformance Red Team: PACT-Core-Thesis.md vs Implementation

Five parallel red team agents audited the full PACT implementation (L1 kailash-pact v0.5.0 + L3 pact-platform v0.3.0) against the authoritative spec at `foundation/docs/02-standards/publications/PACT-Core-Thesis.md` (v0.1-WA, March 2026).

## Methodology

Each agent was assigned a non-overlapping spec section and independently read both the spec and the implementation source. Findings were cross-validated where agents covered adjacent requirements.

| Agent                 | Spec Sections                                                    | Files Audited                                              |
| --------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------- |
| rt-grammar-addressing | 4.1-4.4 (D/T/R, addressing, bridges)                             | addressing.py, compilation.py, access.py, engine.py        |
| rt-envelopes          | 5.2-5.7 (envelopes, tightening, gradient, vacancy, EATP mapping) | envelopes.py, engine.py, config.py, gradient.py            |
| rt-clearance          | 6.1-6.3, 9, 10, 12.9 (clearance, bypass, inversion, threats)     | clearance.py, access.py, emergency_bypass.py, runtime.py   |
| rt-eatp-integration   | 5.7 (EATP records), 5.4/5.6 (gradient), MCP                      | audit.py, engine.py, bootstrap.py, pact.mcp/\*             |
| rt-constraint-theater | 12.1-12.9, Disclosure (limitations, mitigations, MCP, shadow)    | envelopes.py, shadow_enforcer.py, dm_runner.py, builder.py |

## Consolidated Findings (26 total, deduplicated)

### CRITICAL (2)

**C1. EATP Record Mapping — Structural Divergence (Spec 5.7)**
The spec states: "This mapping is normative; implementations claiming PACT conformance must produce these records." The L1 GovernanceEngine produces PACT-specific `AuditAnchor` records in a tamper-evident hash chain, but does NOT produce the EATP record types the spec mandates:

- No `GenesisRecord` on org creation (L3 bootstrap creates one; L1 engine does not)
- No `DelegationRecord` on envelope definition/modification (audit anchor only)
- No `CapabilityAttestation` on clearance grant (audit anchor only)
- No bilateral `DelegationRecord` pair on bridge creation (single audit anchor)
- `ENVELOPE_MODIFIED` and `BARRIER_ENFORCED` action types defined in enum but never emitted

Root cause: two parallel audit systems exist — L3 bootstrap creates real EATP types at init; L1 engine creates PACT-specific anchors at runtime. The spec requires EATP types at runtime too.

**C2. Emergency Bypass Tier 4 — Spec Violation (Spec 9)**
The spec says >72h is "Not emergency — Not permitted via bypass." The implementation treats Tier 4 as an open-ended bypass with COMPLIANCE approval and no auto-expiry. This directly contradicts the spec.

### HIGH (7)

**H1. Auto-Creation of Vacant Head Roles Missing (Spec 4.2)**
Spec: "When a D or T is created without an R, the system auto-creates a vacant head role." Implementation: `compile_org()` silently drops headless units from the compiled org. No auto-creation occurs.

**H2. Emergency Bypass Scope Not Validated (Spec 9)**
Spec: "Bypass cannot widen beyond approver's own envelope." Implementation: `create_bypass()` accepts arbitrary `expanded_envelope` without comparing against the approver's governance envelope.

**H3. Emergency Bypass Authority Not Structurally Validated (Spec 9)**
Spec requires "Immediate supervisor" / "Two levels up" / "C-Suite" relative to the target role's D/T/R position. Implementation uses abstract `AuthorityLevel` enum without verifying actual D/T/R relationship.

**H4. Write-Time Tightening Incomplete for 3 of 5 Dimensions (Spec 5.3)**
`validate_tightening()` enforces Financial, Confidentiality, Operational, and delegation depth. Does NOT enforce Temporal, Data Access, or Communication at write time. Spec says "for every dimension d" and "enforced at write time."

**H5. Posture Gaming — No Independent Assessor (Spec 12.9.4)**
Posture is a caller-supplied parameter at every layer. No conflict-of-interest check exists. A supervisor benefiting from higher agent autonomy can initiate posture upgrades unilaterally.

**H6. Per-Dimension Gradient Configuration Missing (Spec 5.6)**
Spec envisions per-dimension, per-role gradient thresholds (e.g., Financial: auto-approve up to $20K, flag $20K-$50K, hold $50K-$100K, block >$100K). Implementation has only a single `requires_approval_above_usd` threshold and action-pattern-based gradient rules. The `RoleEnvelope` has no gradient field.

**H7. Bridge Bilateral Consent Missing at L1 (Spec 4.4 property 3)**
Spec: "requires bilateral establishment (both roles must agree)." L1 `create_bridge()` requires only LCA approval, not consent from both endpoint roles. L3 correctly implements dual-side approval, but L1 does not enforce it.

### MEDIUM (8)

**M1. Bridge Scope Not Validated Against Envelopes (Spec 4.4)**
Spec: "A bridge cannot grant access broader than either party's own envelope permits." `create_bridge()` does not validate bridge scope against either role's effective envelope.

**M2. Vacancy Interim Envelope Missing (Spec 5.5 Rule 2)**
Spec: between vacancy and deadline, affected agents operate under more restrictive of own or parent's envelope. Implementation skips directly to full block — no degraded-but-operational middle state.

**M3. Vacancy Deadline Not Configurable (Spec 5.5)**
Hardcoded to 24h. Spec says "configurable deadline (default: 24 hours)."

**M4. Emergency Bypass Rate Limiting Missing (Spec 9)**
Spec: "Rate limiting prevents bypass from becoming governance workaround." No per-role bypass frequency limit, cooling-off period, or escalation trigger exists.

**M5. Gradient Dereliction Detection Missing (Spec 5.4)**
No monitoring of auto-approved to held action ratios per supervisor. No mechanism to detect supervisors who effectively rubber-stamp everything.

**M6. `check_degenerate_envelope()` Not Wired in L3 (Spec 12.3)**
The function exists and is tested in L1, but L3 never calls it. Deep hierarchies can produce near-zero envelopes without warning.

**M7. PACT for MCP Not Wired in L3 (Disclosure)**
`pact.mcp` sub-module exists in L1 with enforcer, middleware, and audit trail. Zero imports from L3. Operators cannot enable MCP governance through the platform.

**M8. Pass-Through Envelope Detection Missing (Spec 12.1, 12.9.1)**
No code detects when a child envelope is identical to its parent. Explicitly documented as a gap in `test_adversarial.py`.

### LOW (5)

**L1. Bridge EATP Atomicity Pattern Missing (Spec 4.4)**
No `BilateralDelegation` transactional wrapper for bilateral delegation records (moot since bilateral records themselves are missing — see C1).

**L2. Designated Compliance Role as Alternative Bridge Approver (Spec 4.4)**
Only LCA approval supported. Spec also allows designated compliance role as alternative.

**L3. Shadow Mode Platform Toggle Missing (Disclosure)**
Per-agent `ShadowEnforcer` exists. No platform-level `enforcement_mode: shadow` toggle.

**L4. Gradient Calibration Tooling Missing (Spec 12.1)**
No `pact calibrate` CLI command or framework-level calibration runner for the 10% held-event target.

**L5. Post-Execution TOCTOU Comparison Missing (Spec 12.9.5)**
Envelope version hash is recorded in audit but never re-checked post-execution. Forensic-only, not automated.

### CONFIRMED WORKING (not exhaustive)

- D/T/R grammar constraint with state machine validation
- Positional addressing (globally unique, deterministic, prefix-containment)
- Three-layer envelope architecture (Role/Task/Effective — computed, never stored)
- Per-dimension intersection rules (all 5 dimensions correct)
- Deny-overrides combining
- Five classification levels (PUBLIC through TOP_SECRET)
- Posture-gated effective clearance (`min(role.max_clearance, posture_ceiling)`)
- 5-step access enforcement algorithm
- Containment boundaries as module boundaries
- LCA approval for bridge creation
- Vacancy suspension (all ancestors checked)
- Thread safety throughout
- Fail-closed on all error paths
- NaN/Inf guards on all numeric fields
- Frozen dataclasses for all governance state
- TOCTOU defense with versioned envelope snapshots
- Compilation limits (depth 50, children 500, total 100K)
- Envelope templates and defaults (11 builtin templates)
- PACT for MCP sub-module (L1 — enforcer, middleware, audit)

## Severity Distribution

| Severity  | Count  | L1 (kailash-pact) | L3 (pact-platform) | Both      |
| --------- | ------ | ----------------- | ------------------ | --------- |
| CRITICAL  | 2      | 1 (C1)            | 1 (C2)             | —         |
| HIGH      | 7      | 4 (H1,H4,H6,H7)   | 1 (H2,H3)          | 1 (H5)    |
| MEDIUM    | 8      | 2 (M1,M5)         | 4 (M4,M6,M7,M8)    | 2 (M2,M3) |
| LOW       | 5      | 1 (L1)            | 3 (L3,L4,L5)       | 1 (L2)    |
| **Total** | **22** | **8**             | **9**              | **5**     |

## For Discussion

1. The EATP record mapping (C1) is the largest structural gap. The L1 engine has its own tamper-evident audit chain that provides integrity guarantees, but the record types don't match the spec's normative mapping. Is the PACT-specific audit chain a deliberate architectural decision (pragmatic — EATP types require Ed25519 signing infrastructure at runtime) or an oversight? If the spec's EATP mapping is non-negotiable, what is the cost of wiring EATP type creation into every `GovernanceEngine` mutation?

2. If the emergency bypass Tier 4 had been spec-compliant (>72h = not permitted), what would an organization do when an emergency genuinely lasts more than 72 hours? Would they need to re-authorize through normal governance every 72 hours — and is that actually the safer design?

3. The gradient system (H6) is the widest gap between spec vision and implementation reality. The spec describes rich per-dimension, per-role threshold arrays; the implementation has a single financial threshold. Given that per-dimension gradient configuration adds significant complexity (5 dimensions x N roles x 4 zones = large configuration matrix), is the current simplified model actually more practical for early adopters?
