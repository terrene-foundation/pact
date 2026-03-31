# L1 Upstream Analysis: kailash-py + kailash-rs

**Date**: 2026-03-31
**Source**: RT26 spec-conformance red team (journal/0007)

## kailash-py (terrene-foundation/kailash-py)

15 L1 changes needed across 4 GitHub issues:

| Issue                                                               | Title                                 | TODOs | Severity | Files                              |
| ------------------------------------------------------------------- | ------------------------------------- | ----- | -------- | ---------------------------------- |
| [#199](https://github.com/terrene-foundation/kailash-py/issues/199) | EATP record types at runtime          | 05-09 | CRITICAL | engine.py, audit.py                |
| [#200](https://github.com/terrene-foundation/kailash-py/issues/200) | Write-time tightening + gradient      | 10-13 | HIGH+MED | envelopes.py, config.py, engine.py |
| [#201](https://github.com/terrene-foundation/kailash-py/issues/201) | Vacant heads + bridge consent + scope | 14-17 | HIGH+MED | compilation.py, engine.py          |
| [#202](https://github.com/terrene-foundation/kailash-py/issues/202) | Vacancy interim envelope + deadline   | 19-20 | MEDIUM   | engine.py                          |

### Key Files

All changes in `/packages/kailash-pact/src/pact/`:

- `engine.py` — GovernanceEngine (11 of 15 changes touch this file)
- `envelopes.py` — RoleEnvelope, validate_tightening, degenerate detection
- `config.py` — ConstraintDimension, new DimensionGradientConfig
- `compilation.py` — compile_org() auto-vacant heads
- `audit.py` — PactAuditAction enum (BARRIER_ENFORCED, ENVELOPE_MODIFIED)

### EATP Types Available (kailash.trust.chain)

| Type                  | Constructor                                                              | Key Fields                                      |
| --------------------- | ------------------------------------------------------------------------ | ----------------------------------------------- |
| GenesisRecord         | `(id, agent_id, authority_id, authority_type, created_at, signature)`    | metadata dict                                   |
| DelegationRecord      | `(id, delegator_id, delegatee_id, task_id, capabilities_delegated, ...)` | constraint_subset, expires_at, delegation_chain |
| CapabilityAttestation | `(id, capability, capability_type, constraints, attester_id, ...)`       | scope dict, expires_at                          |

## kailash-rs (esperie/kailash-rs)

**Result: No issues needed.** Feature-complete and aligned.

The Rust SDK has comprehensive PACT governance across two crates:

- `kailash-governance` (v0.1.0) — core primitives
- `kailash-pact` (v0.1.0) — higher-level frameworks

All 10 PACT features are implemented:

1. D/T/R grammar with state machine validation
2. GovernanceEngine with verify_action, can_access, export_rbac_matrix
3. Monotonic tightening with FiniteF64 type
4. Emergency bypass (7 never-delegated actions → Held zone)
5. Bridge creation with LCA approval + bilateral directionality
6. Vacancy handling with configurable duration + acting designations
7. EATP record mapping via explain module + serializable GovernanceContext
8. 4-zone verification gradient (AutoApproved, Flagged, Held, Blocked)
9. Knowledge clearance (5 levels + posture ceiling)
10. PACT for MCP middleware (feature-gated)

Notable Rust-ahead features:

- `FiniteF64` type (rejects NaN/Inf at construction)
- `VacancyCheckResult` enum (Active/ActingDesignation/Blocked)
- `BridgeApprovalStatus` enum (Pending/Approved/Rejected)
- RBAC matrix export (CSV, JSON, Markdown)
- SQLite persistence (feature-gated)
