# RT25 Spec Compliance Gaps — Implementation Todos

Based on RT25 Quartet compliance audit. 7 MISSING + 9 PARTIAL findings.
Organized by priority (dependency order), estimated in autonomous sessions.

---

## M0: Dimension Enforcement (L1 — kailash-pact engine)

The single highest-impact fix: 3 of 5 constraint dimensions are defined in schema but not enforced at runtime. This is an L1 fix in `GovernanceEngine._evaluate_against_envelope()`.

### TODO-01: Enforce Temporal dimension in verify_action()

- **File**: `kailash-py/src/kailash/trust/pact/engine.py` → `_evaluate_against_envelope()`
- **What**: Check `active_hours_start/end` against current time. Check `blackout_periods`. BLOCK outside hours, FLAG near boundary.
- **Schema**: `TemporalConstraintConfig` has `active_hours_start`, `active_hours_end`, `timezone`, `blackout_periods`
- **Tests**: Agent action outside active hours → BLOCKED. Agent action during blackout → BLOCKED. Agent action within hours → passes.
- **Scope**: L1 (kailash-pact)

### TODO-02: Enforce Communication dimension in verify_action()

- **File**: Same as TODO-01
- **What**: Check `internal_only` (block external), `allowed_channels` (block if channel not in set), `external_requires_approval` (HELD for external).
- **Schema**: `CommunicationConstraintConfig` has `internal_only`, `allowed_channels`, `external_requires_approval`
- **Context**: Action context must include `channel` and `is_external` fields for this to work. Define the context contract.
- **Tests**: Internal-only agent sending external message → BLOCKED. Agent using forbidden channel → BLOCKED. External with requires_approval → HELD.
- **Scope**: L1 (kailash-pact)

### TODO-03: Enforce Data Access paths in verify_action()

- **File**: Same as TODO-01
- **What**: Check `read_paths` and `write_paths` from `DataAccessConstraintConfig`. BLOCK if action's resource path is not in allowed set.
- **Schema**: `DataAccessConstraintConfig` has `read_paths`, `write_paths`, `denied_paths`
- **Context**: Action context must include `resource_path` and `access_type` (read/write) fields.
- **Note**: Classification-based access (`can_access()`) already works. This adds path-level constraints.
- **Tests**: Read from allowed path → passes. Write to denied path → BLOCKED. Read from unlisted path → BLOCKED.
- **Scope**: L1 (kailash-pact)

---

## M1: EATP Record Mapping (L1 + L3)

Section 5.7 of the PACT thesis says this mapping is normative. Currently only 3/9 actions produce proper EATP records.

### TODO-04: Wire set_role_envelope() to create EATP DelegationRecord

- **File**: L1 `engine.py` → `set_role_envelope()`
- **What**: After saving envelope, create a `DelegationRecord` with `constraint_subset` referencing the envelope dimensions. This is the "authority delegates constrained capability" record.
- **Scope**: L1 (kailash-pact)

### TODO-05: Wire grant_clearance() to create EATP CapabilityAttestation

- **File**: L1 `engine.py` → `grant_clearance()`
- **What**: After granting clearance, create a `CapabilityAttestation` with `scope` set to the clearance level and compartments.
- **Scope**: L1 (kailash-pact)

### TODO-06: Wire create_bridge() to create two cross-referencing DelegationRecords

- **File**: L1 `engine.py` → `create_bridge()`
- **What**: For bilateral bridges, create two DelegationRecords (A→B and B→A) with cross-references. For unilateral, create one.
- **Scope**: L1 (kailash-pact)

---

## M2: Emergency Bypass (L3)

PACT thesis Section 9. No implementation exists.

### TODO-07: Implement EmergencyBypass with 4 tiers

- **File**: New `src/pact_platform/engine/emergency_bypass.py`
- **What**: Create `EmergencyBypass` class with 4 tiers:
  - Tier 1 (4h): Direct supervisor approval, auto-expires
  - Tier 2 (24h): Department head approval
  - Tier 3 (72h): BOD/executive approval
  - Tier 4 (not-emergency): Full governance override (requires compliance review)
- Each bypass: temporarily expands envelope, has hard auto-expiry timer, creates audit anchor
- **Tests**: Bypass creation, auto-expiry, post-expiry action → BLOCKED, audit trail
- **Scope**: L3 (pact-platform)

### TODO-08: Implement post-incident review scheduling

- **File**: Same as TODO-07 or new `src/pact_platform/engine/incident_review.py`
- **What**: After any bypass expires, schedule a mandatory review within 7 days. Track review status.
- **Scope**: L3 (pact-platform)

---

## M3: HELD Timeout (L3)

EATP says HELD actions should auto-deny, never auto-approve.

### TODO-09: Add configurable timeout to ApprovalQueue

- **File**: `src/pact_platform/use/execution/approval.py`
- **What**: Add `timeout_seconds` config (default: 24h). HELD actions that exceed timeout are auto-denied with reason "Timeout — auto-denied per EATP guidance". Create audit anchor for timeout events.
- **Tests**: Submit HELD action, advance time past timeout, verify auto-denied.
- **Scope**: L3 (pact-platform)

---

## M4: Bridge LCA Approval (L1)

PACT thesis Section 4.4 property (4).

### TODO-10: Add lowest-common-ancestor approval check to create_bridge()

- **File**: L1 `engine.py` → `create_bridge()`
- **What**: Before creating a bridge, compute the lowest common ancestor of source and target teams in the D/T/R tree. Require approval from that ancestor's role (or a designated compliance role). If no approval, the bridge is created in PENDING state.
- **Scope**: L1 (kailash-pact)

---

## M5: Vacancy Handling (L1 + L3)

PACT thesis Section 5.5.

### TODO-11: Implement vacancy handling rules

- **File**: L1 `engine.py` or new `src/pact_platform/engine/vacancy.py`
- **What**: When a role becomes vacant:
  1. Parent role must designate acting occupant within 24h
  2. If no designation within 24h, all downstream agents are auto-suspended
  3. Acting occupant inherits the role's envelope but NOT clearance upgrades
- **Tests**: Role vacancy → 24h deadline → auto-suspension cascade
- **Scope**: L1 + L3

---

## M6: Remaining EATP Items (L1 + L3)

### TODO-12: Implement chain-level cascade revocation

- **File**: `src/pact_platform/use/execution/runtime.py`
- **What**: The `revoke_delegation_chain()` method exists but RT25 found it partial. Verify it recursively walks ALL downstream delegates (not just direct children) and revokes each with individual audit anchors.
- **Scope**: L3 (pact-platform) — may already be done, verify

### TODO-13: Populate reasoning traces on governance decisions

- **File**: L1 `engine.py` → `verify_action()`, L3 `bootstrap.py`
- **What**: Attach `ReasoningTrace` to audit anchors for HELD/BLOCKED decisions (explaining why the constraint triggered). Attach to DelegationRecords during bootstrap.
- **Scope**: L1 + L3

### TODO-14: Implement trust scoring with 5-factor weights

- **File**: New `src/pact_platform/trust/scoring.py`
- **What**: Compute trust score across: chain completeness (30%), delegation depth (15%), constraint coverage (25%), posture level (20%), chain recency (10%). Map to letter grades A-F.
- **Scope**: L3 (pact-platform)

### TODO-15: Implement dimension-scoped delegation

- **File**: L1 `DelegationRecord` / `engine.py`
- **What**: Add `dimension_scope: list[str]` to delegation. A delegation scoped to ["financial", "temporal"] only delegates authority over those two dimensions.
- **Scope**: L1 (kailash-pact)

---

## M7: Frontend Gaps (L3 — apps/web)

### TODO-16: Connect Org Builder to backend API

- **File**: `apps/web/app/org-builder/page.tsx`
- **What**: Load existing org from API. Save to API. "Deploy Org" button that POSTs to org compilation endpoint.
- **Scope**: L3 (frontend)

### TODO-17: Add verification drill-down (link to filtered audit)

- **File**: `apps/web/app/verification/page.tsx`
- **What**: Each gradient zone count should link to `/audit?level=blocked` (or flagged/held) for drill-down.
- **Scope**: L3 (frontend)

### TODO-18: Add envelope inline editing

- **File**: `apps/web/app/envelopes/[id]/page.tsx`
- **What**: Add edit mode for each constraint dimension. Save via API.
- **Scope**: L3 (frontend)

---

## Estimation

| Group                    | Todos | Sessions    | Dependency              |
| ------------------------ | ----- | ----------- | ----------------------- |
| M0 Dimension Enforcement | 01-03 | 1 session   | None — highest priority |
| M1 EATP Record Mapping   | 04-06 | 1 session   | After M0                |
| M2 Emergency Bypass      | 07-08 | 1 session   | Independent             |
| M3 HELD Timeout          | 09    | 0.5 session | Independent             |
| M4 Bridge LCA            | 10    | 0.5 session | Independent             |
| M5 Vacancy Handling      | 11    | 1 session   | Independent             |
| M6 EATP Items            | 12-15 | 1 session   | After M1                |
| M7 Frontend              | 16-18 | 1 session   | After M0                |

**Total: ~6 autonomous sessions** to reach full Quartet conformance.
