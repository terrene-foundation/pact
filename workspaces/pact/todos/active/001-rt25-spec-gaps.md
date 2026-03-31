# RT25 Spec Compliance Gaps — Implementation Todos

Based on RT25 Quartet compliance audit. 7 MISSING + 9 PARTIAL findings.
Organized by priority (dependency order), estimated in autonomous sessions.

**Last updated**: 2026-03-30 — TODOs 01-09, 13-14 completed.

---

## M0: Dimension Enforcement (L1 — kailash-pact engine) — DONE

All 5 constraint dimensions now enforced in kailash-pact 0.4.1 GovernanceEngine.\_evaluate_against_envelope().

### ~~TODO-01: Enforce Temporal dimension in verify_action()~~ — DONE (kailash-pact 0.4.1)

Implemented in `kailash.trust.pact.engine` lines 492-540. Checks active_hours_start/end, blackout_periods (with overnight range support), timezone-aware.

### ~~TODO-02: Enforce Communication dimension in verify_action()~~ — DONE (kailash-pact 0.4.1)

Implemented in `kailash.trust.pact.engine` lines 584-614. Checks internal_only, external_requires_approval (→HELD), allowed_channels. Context keys: `is_external`, `channel`.

### ~~TODO-03: Enforce Data Access paths in verify_action()~~ — DONE (kailash-pact 0.4.1)

Implemented in `kailash.trust.pact.engine` lines 542-582. Checks read_paths, write_paths, denied_paths, blocked_data_types. Path traversal protection. Context keys: `resource_path`, `access_type`, `data_type`.

---

## M1: EATP Record Mapping (L1 + L3) — DONE

### ~~TODO-04: Wire set_role_envelope() to create EATP DelegationRecord~~ — DONE (kailash-pact 0.4.1)

Engine emits EATP audit anchor with PactAuditAction.ENVELOPE_CREATED (lines 863-897). Audit chain converts to DelegationRecord.

### ~~TODO-05: Wire grant_clearance() to create EATP CapabilityAttestation~~ — DONE (kailash-pact 0.4.1)

Engine emits EATP audit anchor with PactAuditAction.CLEARANCE_GRANTED (lines 782-801). Audit chain converts to CapabilityAttestation.

### ~~TODO-06: Wire create_bridge() to create two cross-referencing DelegationRecords~~ — DONE (kailash-pact 0.4.1)

Engine emits EATP audit anchor with PactAuditAction.BRIDGE_ESTABLISHED (lines 821-840). Supports bilateral and unilateral bridges.

---

## M2: Emergency Bypass (L3) — DONE

### ~~TODO-07: Implement EmergencyBypass with 4 tiers~~ — DONE (v0.3.0)

Implemented in `src/pact_platform/engine/emergency_bypass.py`. 4-tier bypass with auto-expiry timers and audit anchors.

### ~~TODO-08: Implement post-incident review scheduling~~ — DONE (v0.3.0)

Implemented in emergency_bypass.py — review scheduling on bypass expiry.

---

## M3: HELD Timeout (L3) — DONE

### ~~TODO-09: Add configurable timeout to ApprovalQueue~~ — DONE (v0.3.0)

Implemented in approval.py — configurable timeout (default 24h), auto-deny on expiry.

---

## M4: Bridge LCA Approval (L1 + L3) — DONE

PACT thesis Section 4.4 property (4).

### ~~TODO-10: Add lowest-common-ancestor approval check to create_bridge()~~ — DONE

- **L1**: `GovernanceEngine.approve_bridge()` implemented in kailash 2.3.1 (kailash-py#168 closed)
- **L3 wiring**: CLI `pact bridge approve` command + `POST /api/v1/org/bridges/approve` endpoint
- **Files**: `cli.py` (bridge approve command), `routers/org.py` (approve endpoint), `endpoints.py` (existing approve_bridge wiring)
- **Tests**: `test_cli.py` (TestBridgeApproveCLI), `test_org_router.py` (TestBridgeLCAApproval)

---

## M5: Vacancy Handling (L1 + L3) — DONE

PACT thesis Section 5.5.

### ~~TODO-11: Implement vacancy handling rules~~ — DONE

- **L1**: `GovernanceEngine.designate_acting_occupant()` + `get_vacancy_designation()` + `_check_vacancy()` in verify_action() — all implemented in kailash 2.3.1 (kailash-py#169 closed)
- **L3 wiring**: CLI `pact role designate-acting` + `pact role vacancy-status` commands + `POST /api/v1/org/roles/{role}/designate-acting` + `GET /api/v1/org/roles/{role}/vacancy` endpoints
- **Files**: `cli.py` (2 commands), `routers/org.py` (2 endpoints)
- **Tests**: `test_cli.py` (TestRoleDesignateActingCLI, TestRoleVacancyStatusCLI), `test_org_router.py` (TestVacancyDesignation, TestVacancyStatus)

---

## M6: Remaining EATP Items (L1 + L3)

### ~~TODO-12: Implement chain-level cascade revocation~~ — DONE (v0.3.0, verified)

Cascade revocation walks all downstream delegates with individual audit anchors.

### ~~TODO-13: Populate reasoning traces on governance decisions~~ — DONE (v0.3.0)

Reasoning traces attached to HELD/BLOCKED verdicts in runtime.py (lines 1238-1246).

### ~~TODO-14: Implement trust scoring with 5-factor weights~~ — DONE (v0.3.0)

Implemented in `src/pact_platform/trust/scoring.py`. 5-factor scoring (A-F grades).

### ~~TODO-15: Implement dimension-scoped delegation~~ — DONE

- **L1**: `DelegationRecord.dimension_scope: frozenset[str]` + `intersect_envelopes(dimension_scope=...)` implemented in kailash 2.3.1 (kailash-py#170 closed)
- **L3 wiring**: Runtime extracts `dimension_scope` from delegation records and passes to verify_action() context. CLI `envelope show` displays dimension scope when present.
- **Files**: `runtime.py` (dimension_scope context injection), `cli.py` (envelope show display)
- **Tests**: Existing governance tests cover L1; L3 integration verified via test suite (2079 pass)

---

## M7: Frontend Gaps (L3 — apps/web) — DONE

### ~~TODO-16: Connect Org Builder to backend API~~ — DONE

Frontend: `useOrgStructure()` (GET) + `useDeployOrg()` (POST) with full tree builder UI already existed.
Backend: New `routers/org.py` implements `GET /api/v1/org/structure` and `POST /api/v1/org/deploy` with GovernanceEngine integration, YAML compilation, and governance spec application.

### ~~TODO-17: Add verification drill-down (link to filtered audit)~~ — DONE (already implemented)

GradientChart component already links each zone (bar + summary card) to `/audit?level=...`. Verified in code review.

### ~~TODO-18: Add envelope inline editing~~ — DONE (already implemented)

EnvelopeEditSheet component with all 5 constraint dimensions, Zod validation, `useUpdateEnvelope()` mutation, and query cache invalidation. Verified in code review.

---

## M8: L3 Wiring — NEW (post kailash-pact 0.4.1)

### ~~TODO-19: Wire dimension context keys into runtime verify_action()~~ — DONE

Implemented in `runtime.py:1218-1228`. Forwards `resource_path`, `access_type`, `data_type`, `is_external`, `channel` from task.metadata into governance context dict.

### ~~TODO-20: Wire audit_chain into GovernanceEngine construction~~ — DONE

Implemented in `cli.py:62-73`. `_make_audit_chain()` creates AuditChain and passes to `GovernanceEngine(audit_chain=...)`.

---

## M9: Hardening Fixes (H5/H6/M1-M3) — DONE

### ~~H5: Tier-based authorization for emergency bypass~~ — DONE

Added `AuthorityLevel` enum and `_authority_sufficient()` check in `emergency_bypass.py`. Tier 1=Supervisor, 2=Dept Head, 3=Executive, 4=Compliance. Backwards-compatible (authority_level=None skips check).

### ~~H6: Envelope snapshot redaction in reasoning traces~~ — DONE

Added `_redact_envelope_snapshot()` in `runtime.py`. Redacts sensitive fields (max_budget, paths, allowed_channels) before persisting in task metadata. Structure preserved.

### ~~M1: Chain recency sort~~ — DONE

Fixed `_score_chain_recency()` in `scoring.py` to sort inbound delegations by timestamp descending before picking the most recent.

### ~~M2: Immutable weights~~ — DONE

Changed `FACTOR_WEIGHTS` and `POSTURE_SCORES` in `scoring.py` from mutable `dict` to `MappingProxyType` — runtime mutation now raises `TypeError`.

### ~~M3: Deep-copy mutable dict in frozen BypassRecord~~ — DONE

Added `__post_init__` to `BypassRecord` that deep-copies `expanded_envelope` via `object.__setattr__`. External mutation of source dict no longer affects the record.

---

## Summary

| Group                    | Todos | Status                          |
| ------------------------ | ----- | ------------------------------- |
| M0 Dimension Enforcement | 01-03 | **DONE** (kailash-pact 0.4.1)   |
| M1 EATP Record Mapping   | 04-06 | **DONE** (kailash-pact 0.4.1)   |
| M2 Emergency Bypass      | 07-08 | **DONE** (pact-platform v0.3.0) |
| M3 HELD Timeout          | 09    | **DONE** (pact-platform v0.3.0) |
| M4 Bridge LCA            | 10    | **DONE** (kailash 2.3.1 + L3)   |
| M5 Vacancy Handling      | 11    | **DONE** (kailash 2.3.1 + L3)   |
| M6 EATP Items            | 12-15 | **DONE** (kailash 2.3.1 + L3)   |
| M7 Frontend              | 16-18 | **DONE**                        |
| M8 L3 Wiring             | 19-20 | **DONE**                        |
| M9 Hardening             | H5-M3 | **DONE**                        |

**Completed**: 25/25 — ALL DONE (kailash 2.3.1 L1 + pact-platform L3)
