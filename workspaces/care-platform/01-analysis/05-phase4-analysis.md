# Phase 4 Analysis: Cross-Functional Bridges + Security Hardening

**Date**: 2026-03-14
**Inputs**: CARE expert (bridge spec), EATP expert (cross-team delegation), codebase explorer
**Status**: Analysis complete — ready for planning

---

## What We're Doing

Phase 4 makes Cross-Functional Bridges real. The bridge scaffolding exists (871-line bridge.py, lifecycle state machine, 78 tests), but it's not connected to the EATP trust layer. When Team A's agent sends work to Team B via a bridge, there's no trust delegation, no constraint intersection, no cross-team audit trail. Phase 4 wires the bridge system into EATP governance so cross-team collaboration carries the same trust guarantees as within-team operations.

Additionally, Phase 4 resolves the security items deferred from RT11 (prompt injection hardening, keyword bypass fix, API rate limiting, security headers).

---

## Who It Affects

| Stakeholder               | Impact                                                                                                       | Concern                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| **Foundation teams**      | Teams can collaborate with trust — DM can request content from Research, Governance can request legal review | Trust must flow correctly; a bad bridge shouldn't compromise either team |
| **Adopters**              | Can model real organizations where departments collaborate                                                   | Bridges must be intuitive — they mirror how organizations actually work  |
| **Enterprise evaluators** | Cross-functional governance is the differentiator vs LangChain/CrewAI                                        | "Show me that Marketing can't access Finance data without a bridge"      |

---

## What Already Exists

### Bridge Layer (workspace/)

- **bridge.py** (871 lines): BridgeManager, Bridge class with Standing/Scoped/Ad-Hoc types, dual-side approval, path-level access control, audit logging, permission freezing, directionality enforcement
- **bridge_lifecycle.py** (188 lines): Lifecycle state machine (PROPOSED → NEGOTIATING → ACTIVE → SUSPENDED → CLOSED)
- **coordinator.py** (257 lines): WorkspaceCoordinator for team-bridge coordination
- **78 bridge tests** covering lifecycle, permissions, access control

### Trust Layer (trust/)

- **eatp_bridge.py**: ESTABLISH, DELEGATE, VERIFY, AUDIT operations
- **delegation.py**: DelegationManager with monotonic tightening validation
- **revocation.py**: RevocationManager with cascade revocation (already references BridgeManager)
- **posture.py**: Full posture lifecycle with 5 levels

### What's Missing (the gap)

1. No EATP trust delegation when crossing a bridge
2. No constraint envelope intersection for cross-team actions
3. No cross-team audit anchoring (dual-sided)
4. No posture resolution for cross-team actions
5. No bridge-level revocation (only agent-level exists)
6. No information sharing modes (auto-share, request-share, never-share)
7. No ad-hoc to standing promotion detection
8. No bridge management API endpoints (only GET /bridges exists)
9. No bridge management dashboard views

---

## Proposed Approach: Two Streams

### Stream A: Bridge Trust Integration (core)

Connect the existing bridge layer to EATP trust operations:

**A1. Bridge Delegation Records** — When a bridge activates, create EATP delegation records scoped to the bridge. The delegation chain flows: Genesis → Team authority → Bridge delegation → Target agent's bridge capabilities.

**A2. Constraint Envelope Intersection** — Compute the effective constraint envelope for bridge actions as the intersection (most restrictive) of: source agent's envelope, bridge rules, target agent's envelope. All five dimensions: min(financial), intersection(operational), intersection(temporal), intersection(data access), most-restrictive(communication).

**A3. Cross-Team Posture Resolution** — The effective posture for a bridge action is min(source_posture, target_posture). SUPERVISED source + CONTINUOUS_INSIGHT target = SUPERVISED bridge action. This routes through the existing verification gradient.

**A4. Cross-Team Audit** — Each team maintains its own audit chain. Bridge actions create dual-anchored audit records: Team A records "I delegated X via bridge Y" with a reference to Team B's corresponding anchor. Linked but separate chains preserve audit integrity.

**A5. Bridge-Level Revocation** — When a bridge is revoked or an agent's bridge delegation is revoked, revoke the specific capabilities granted through the bridge without revoking the agents themselves. This is delegation-level revocation, not agent-level.

**A6. Information Sharing Modes** — Per-field sharing rules on bridges: auto-share (flows automatically), request-share (requires explicit request), never-share (blocked). The spec says this is per-field, not per-bridge.

**A7. Bridge Verification Pipeline** — Integrate bridge validity checks into the verification gradient: Is the bridge ACTIVE? Is the action type allowed? Does the effective envelope permit it? What is the effective posture? Route accordingly.

### Stream B: Security Hardening (carry-forward)

Resolve the RT11 deferred items:

**B1. Prompt Injection Hardening** — Add system prompt to KaizenBridge that separates trusted instructions from untrusted task actions. Prevents prompt injection via task.action.

**B2. Posture Enforcer Keyword Normalization** — Normalize action strings before keyword matching: lowercase, unicode NFKD normalization, strip non-alphanumeric. Prevents bypass via CamelCase, hyphenation, or unicode homoglyphs.

**B3. API Rate Limiting** — Add slowapi middleware to FastAPI. Rate limit per-token on all endpoints, with stricter limits on mutating endpoints.

**B4. Security Response Headers** — Add CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy headers via middleware.

### Stream C: Bridge Management (API + Dashboard)

**C1. Bridge CRUD Endpoints** — POST /bridges (create), PUT /bridges/{id}/approve (approve), POST /bridges/{id}/suspend, POST /bridges/{id}/close. All require authentication.

**C2. Bridge Dashboard View** — Extend the existing /bridges page with bridge management: create bridge wizard, approval flow, lifecycle visualization, constraint intersection display.

---

## Risks and Considerations

### Risk 1: Constraint Intersection Complexity

Computing the intersection of three constraint envelopes (source, bridge, target) across five dimensions is non-trivial, especially for temporal (overlapping active hours) and data access (path intersection). The monotonic tightening validator exists but needs a new intersection computation.

**Mitigation**: Build on existing `ConstraintEnvelope.is_tighter_than()` which already validates all five dimensions. The intersection computation is a variant of tightening validation.

### Risk 2: Bridge Immutability vs Usability

The CARE spec says bridge terms are immutable once ACTIVE — modifications require a new bridge. This could be frustrating for operators who want to adjust a standing bridge.

**Mitigation**: The spec is correct — immutability preserves audit integrity. Provide a "modify" flow that suspends the old bridge and creates a new one with updated terms.

### Risk 3: Dual-Anchor Audit Complexity

Creating audit anchors on both sides of a bridge action requires coordinating between two teams' audit chains. If one side fails, the audit is incomplete.

**Mitigation**: Source-side anchor is created first (commit point). Target-side anchor is best-effort. The source-side anchor contains enough information for audit reconstruction even if the target-side anchor is missing.

---

## Not In Scope (Phase 5+)

| Item                                 | Reason                                                        |
| ------------------------------------ | ------------------------------------------------------------- |
| Cross-organization bridge federation | EATP spec defers federation governance; Phase 4 is single-org |
| Physical store isolation             | Enterprise feature — application-layer isolation sufficient   |
| HSM key management                   | Enterprise feature — software Ed25519 sufficient              |
| External hash chain anchoring        | Needs anchoring service selection                             |
| Multi-tenant isolation               | Commercial vendor territory                                   |
| EATP SDK gap closure                 | SDK team responsibility, not platform                         |
