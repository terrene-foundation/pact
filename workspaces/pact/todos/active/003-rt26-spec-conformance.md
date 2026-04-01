# RT26 Spec-Conformance Fixes

Based on journal/0007-GAP-spec-conformance-red-team.md. 22 findings from 5 parallel
red team agents auditing PACT-Core-Thesis.md against L1 kailash-pact v0.5.0 + L3
pact-platform v0.3.0.

**Created**: 2026-03-31
**Source**: 5 parallel spec-conformance red team agents
**Updated**: 2026-03-31 — M0 DONE; L1 issues filed on kailash-py

## Upstream Issues (kailash-py)

| Issue                                                                                            | Title                                 | TODOs | Status |
| ------------------------------------------------------------------------------------------------ | ------------------------------------- | ----- | ------ |
| [terrene-foundation/kailash-py#199](https://github.com/terrene-foundation/kailash-py/issues/199) | EATP record types at runtime          | 05-09 | Open   |
| [terrene-foundation/kailash-py#200](https://github.com/terrene-foundation/kailash-py/issues/200) | Write-time tightening + gradient      | 10-13 | Open   |
| [terrene-foundation/kailash-py#201](https://github.com/terrene-foundation/kailash-py/issues/201) | Vacant heads + bridge consent + scope | 14-17 | Open   |
| [terrene-foundation/kailash-py#202](https://github.com/terrene-foundation/kailash-py/issues/202) | Vacancy interim envelope + deadline   | 19-20 | Open   |

**kailash-rs**: No issues needed — feature-complete and aligned across all 10 PACT features.

---

## M0: Emergency Bypass Fixes (L3 — C2, H2, H3, M4)

All changes in `src/pact_platform/engine/emergency_bypass.py`. No L1 dependency.

### TODO-01: Fix Tier 4 bypass to reject >72h (C2 — CRITICAL)

**Spec**: Section 9 — ">72 hours: Not emergency. Not permitted via bypass."
**Current**: Tier 4 is open-ended with COMPLIANCE approval and no auto-expiry.
**Fix**: Remove Tier 4 as a valid bypass tier. Any bypass request >72h must go through
normal governance re-authorization. Existing Tier 3 (72h max) becomes the ceiling.
If an emergency genuinely exceeds 72h, the operator re-authorizes through Tier 3
every 72 hours with escalating authority — matching military ROE, MAS BCM guidelines,
and every mature governance system's pattern.

**Files**: `emergency_bypass.py`, tests
**Tests**: Verify Tier 4 creation raises error; verify >72h duration rejected

### TODO-02: Validate bypass scope against approver's envelope (H2 — HIGH)

**Spec**: Section 9 — "Bypass cannot widen beyond approver's own envelope."
**Current**: `create_bypass()` accepts arbitrary `expanded_envelope` without validation.
**Fix**: Before persisting, compute the approver's effective envelope via
`GovernanceEngine.compute_effective_envelope(approver_address)`. Verify every dimension
of `expanded_envelope` is within the approver's envelope. Reject with specific
dimension violation if wider.

**Dependency**: Needs GovernanceEngine reference in EmergencyBypass (pass at construction)
**Files**: `emergency_bypass.py`, tests
**Tests**: Bypass with scope wider than approver's envelope rejected; bypass within scope accepted

### TODO-03: Validate bypass authority via D/T/R relationship (H3 — HIGH)

**Spec**: Section 9 — Tier 1 requires "immediate supervisor", Tier 2 "two levels up",
Tier 3 "C-Suite or equivalent."
**Current**: Uses abstract `AuthorityLevel` enum (SUPERVISOR, DEPARTMENT_HEAD, EXECUTIVE)
without verifying actual D/T/R relationship between approver and target role.
**Fix**: Validate that the approver's D/T/R address is an ancestor of the target role's
address at the correct depth:

- Tier 1: approver is immediate parent in accountability chain
- Tier 2: approver is 2+ levels up in accountability chain
- Tier 3: approver is in the top-level D/R positions (C-Suite equivalent)

Use `Address.accountability_chain` to verify depth relationship.

**Dependency**: Needs CompiledOrg reference to resolve addresses
**Files**: `emergency_bypass.py`, tests
**Tests**: Tier 1 with non-supervisor rejected; Tier 2 with only 1 level up rejected

### TODO-04: Add bypass rate limiting (M4 — MEDIUM)

**Spec**: Section 9 — "Rate limiting prevents bypass from becoming governance workaround."
**Current**: No rate limiting. Sequential Tier 1 bypasses can maintain perpetual bypass.
**Fix**: Add per-role bypass frequency limits:

- Max 3 bypasses per role per rolling 7 days
- Min 4h cooling-off between consecutive bypasses for the same role
- After 3rd bypass in 7 days, escalate: next bypass requires Tier 2+ authority
- Emit alert when bypass frequency exceeds threshold

**Files**: `emergency_bypass.py`, tests
**Tests**: 4th bypass in 7 days rejected; bypass during cooling-off rejected

---

## M1: EATP Record Types at Runtime (L1 — C1 — CRITICAL)

The L1 GovernanceEngine must produce real EATP types, not just PACT-specific audit
anchors. This is the largest structural gap. The spec (Section 5.7) says
"This mapping is normative."

**Repo**: kailash-py (`~/repos/loom/kailash-py/packages/kailash-pact/`)
**Upstream issue**: File on terrene-foundation/kailash-py

### TODO-05: GovernanceEngine emits GenesisRecord on org creation (C1a)

**Current**: `__init__()` compiles org but creates no Genesis Record.
**Fix**: When `GovernanceEngine` initializes with a new org (no existing genesis),
create a `kailash.trust.chain.GenesisRecord` and persist it to the audit chain.
L3 bootstrap already does this — extract the pattern and move it into L1 engine.

**Files**: `engine.py`, `audit.py`, tests

### TODO-06: GovernanceEngine emits DelegationRecord on envelope ops (C1b)

**Current**: `set_role_envelope()` and `set_task_envelope()` emit PACT audit anchors.
**Fix**: In addition to the PACT audit anchor, create a
`kailash.trust.chain.DelegationRecord` with the envelope attached. Distinguish
`ENVELOPE_CREATED` from `ENVELOPE_MODIFIED` (modify = set when one already exists).
Task envelope DelegationRecord must include expiry metadata.

**Files**: `engine.py`, tests

### TODO-07: GovernanceEngine emits CapabilityAttestation on clearance grant (C1c)

**Current**: `grant_clearance()` emits PACT audit anchor.
**Fix**: Also create a `kailash.trust.chain.CapabilityAttestation` recording the
clearance grant with max_clearance, compartments, and vetting_status.

**Files**: `engine.py`, tests

### TODO-08: GovernanceEngine emits bilateral DelegationRecords on bridge creation (C1d)

**Current**: `create_bridge()` emits a single PACT audit anchor.
**Fix**: Create two cross-referencing `DelegationRecord` instances (A grants B, B grants A),
each referencing the other's record ID. Both created atomically.

**Files**: `engine.py`, `access.py`, tests

### TODO-09: Emit BARRIER_ENFORCED and ENVELOPE_MODIFIED audit subtypes (C1e)

**Current**: `BARRIER_ENFORCED` and `ENVELOPE_MODIFIED` defined in enum but never emitted.
**Fix**: `check_access()` emits `BARRIER_ENFORCED` when access denied. `set_role_envelope()`
checks whether an envelope already exists and emits `ENVELOPE_MODIFIED` (not CREATED)
when overwriting. Include effective envelope snapshot in verify_action audit anchor metadata.

**Files**: `engine.py`, `access.py`, `audit.py`, tests

---

## M2: Envelope & Gradient (L1 — H4, H6, M5, M8)

**Repo**: kailash-py (`~/repos/loom/kailash-py/packages/kailash-pact/`)

### TODO-10: Write-time tightening for Temporal, Data Access, Communication (H4 — HIGH)

**Spec**: Section 5.3 — "for every dimension d: E_child.d is at most E_parent.d"
and "Enforced at write time."
**Current**: `validate_tightening()` only checks Financial, Confidentiality, Operational,
and delegation depth. Temporal, Data Access, Communication skip write-time validation.
**Fix**: Extend `validate_tightening()` in `envelopes.py` to check:

- Temporal: child active_hours within parent's; child blackout_periods superset of parent's
- Data Access: child read_paths subset of parent's; child write_paths subset; child
  blocked_data_types superset of parent's
- Communication: child allowed_channels subset of parent's; child internal_only >= parent's

**Files**: `envelopes.py`, tests
**Tests**: Each dimension violation produces `MonotonicTighteningError` with dimension identified

### TODO-11: Per-dimension gradient configuration in RoleEnvelope (H6 — HIGH)

**Spec**: Section 5.6 — supervisor sets gradient thresholds within each Role Envelope,
per-dimension, per-role. Example: Financial auto-approved up to $20K, flagged $20K-$50K,
held $50K-$100K, blocked >$100K.
**Current**: `RoleEnvelope` has no gradient field. Single `requires_approval_above_usd`
threshold. 80% flagging is hardcoded.
**Fix**:

1. Add `DimensionGradientConfig` dataclass with `auto_approve_threshold`,
   `flag_threshold`, `hold_threshold` (block is everything above hold)
2. Add `GradientConfig` mapping `ConstraintDimension -> DimensionGradientConfig`
3. Add `gradient: GradientConfig | None` field to `RoleEnvelope`
4. Update `_evaluate_against_envelope()` to use configured thresholds instead of
   hardcoded 80% and `requires_approval_above_usd`
5. Validate gradient thresholds are within envelope limits (auto < flag < hold < max)

**Files**: `config.py`, `envelopes.py`, `engine.py`, tests
**Tests**: Per-dimension gradient evaluation; gradient validation against envelope limits

### TODO-12: Gradient dereliction detection (M5 — MEDIUM)

**Spec**: Section 5.4 — monitor ratio of auto-approved to held actions per supervisor.
Detect when supervisors set auto-approve near effective envelope boundary.
**Fix**: Add `check_gradient_dereliction(role_envelope, effective_envelope) -> list[str]`
that flags when auto_approve_threshold >= 90% of the effective envelope limit for any
dimension. Also add action-level ratio tracking to the audit system: count
auto-approved vs held per supervisor address in a bounded rolling window.

**Files**: `envelopes.py`, `engine.py`, tests

### TODO-13: Pass-through envelope detection (M8 — MEDIUM)

**Spec**: Section 12.1, 12.9.1 — detect when child envelope is identical to parent.
**Current**: Documented gap in `test_adversarial.py`.
**Fix**: Add `check_passthrough_envelope(child, parent) -> bool` that returns True when
all dimension values are identical. Call it from `set_role_envelope()` and emit a
WARNING-level audit anchor (not block — pass-through is a governance smell, not a
hard violation). Update `validate_org_detailed()` to surface pass-through warnings.

**Files**: `envelopes.py`, `engine.py`, tests
**Tests**: Identical child/parent detected; slightly narrowed child passes

---

## M3: Grammar & Bridges (L1 — H1, H7, M1, L2)

**Repo**: kailash-py (`~/repos/loom/kailash-py/packages/kailash-pact/`)

### TODO-14: Auto-create vacant head roles in compile_org() (H1 — HIGH)

**Spec**: Section 4.2 — "When a D or T is created without an R, the system auto-creates
a vacant head role."
**Current**: `compile_org()` silently drops headless units from the compiled org.
**Fix**: After building `unit_head_map`, iterate all departments and teams. For any unit
not in `unit_head_map`, synthesize a `RoleDefinition(role_id=f"{unit_id}-head-vacant",
name=f"{unit_name} Head (Vacant)", is_primary_for_unit=unit_id, is_vacant=True)`.
Insert into the roles list. Also update `yaml_loader.py` to warn (not error) when a
unit has no head.

**Files**: `compilation.py`, `yaml_loader.py`, tests
**Tests**: Headless department gets auto-created vacant head; compiled org contains the unit

### TODO-15: Bridge bilateral consent at L1 (H7 — HIGH)

**Spec**: Section 4.4 property 3 — "requires bilateral establishment (both roles must agree)."
**Current**: `create_bridge()` requires LCA approval but not consent from both endpoints.
**Fix**: Add `consent_bridge(role_address, bridge_id)` method to GovernanceEngine.
Before `create_bridge()` succeeds, both `role_a` and `role_b` must have registered
consent via `consent_bridge()`. Store consents with 24h TTL (matching approval TTL).
`create_bridge()` checks for both consents before persisting.

**Files**: `engine.py`, tests
**Tests**: Bridge without bilateral consent rejected; bridge with both consents succeeds

### TODO-16: Bridge scope validation against role envelopes (M1 — MEDIUM)

**Spec**: Section 4.4 — "A bridge cannot grant access broader than either party's
own envelope permits."
**Current**: `create_bridge()` does not validate bridge scope against role envelopes.
**Fix**: Before persisting, compute effective envelopes for both roles. Validate:

- `bridge.max_classification <= min(env_a.confidentiality, env_b.confidentiality)`
- `bridge.operational_scope` subset of both envelopes' allowed_actions (if applicable)
  Reject with specific violation if wider.

**Files**: `engine.py`, tests

### TODO-17: Compliance role as alternative bridge approver (L2 — LOW)

**Spec**: Section 4.4 property 4 — "or from a designated compliance role."
**Fix**: Add `register_compliance_role(role_address)` to GovernanceEngine. In
`approve_bridge()`, accept approval from either LCA or a registered compliance role.

**Files**: `engine.py`, tests

---

## M4: Vacancy & Posture (L1 + L3 — H5, M2, M3)

### TODO-18: Independent assessor for posture changes (H5 — HIGH)

**Spec**: Section 12.9.4 — "Should involve independent assessor" to prevent posture gaming.
**Current**: Posture is caller-supplied at every layer. No conflict-of-interest check.
**Fix (L3)**: In `PostureEligibilityChecker` or a new `PostureGovernance` module:

- Require that `changed_by` is NOT the agent itself and NOT the agent's direct supervisor
  (who benefits from higher autonomy)
- The assessor must be either: a peer supervisor, a compliance role, or an ancestor
  2+ levels up
- Validate via D/T/R address relationship using `Address.accountability_chain`

**Files (L3)**: `pact_platform/trust/store/posture_history.py` or new module, tests

### TODO-19: Vacancy interim envelope — degraded-but-operational (M2 — MEDIUM)

**Spec**: Section 5.5 Rule 2 — "Until an acting role is designated, the vacant role's
direct reports operate under the more restrictive of their own Role Envelope or the
parent's envelope for the vacant role."
**Current**: Implementation skips to full block — no degraded middle state.
**Fix (L1)**: In `_check_vacancy()`, when a vacancy exists without designation but
within the 24h deadline: instead of returning a blocking error, compute
`min(own_envelope, parent_envelope_for_vacant_role)` and return it as the interim
effective envelope. Only block after deadline expires.

**Repo**: kailash-py
**Files**: `engine.py`, tests

### TODO-20: Vacancy deadline configurable (M3 — MEDIUM)

**Spec**: Section 5.5 — "configurable deadline (default: 24 hours)."
**Current**: Hardcoded `timedelta(hours=24)`.
**Fix (L1)**: Add `vacancy_deadline_hours: int = 24` parameter to `GovernanceEngine.__init__()`.
Pass through to `designate_acting_occupant()` and `_check_vacancy()`.

**Repo**: kailash-py
**Files**: `engine.py`, tests

---

## M5: L1->L3 Wiring (MEDIUM — quick wins)

### TODO-21: Wire check_degenerate_envelope() in L3 (M6)

**Spec**: Section 12.3 — "Implementation MUST include degenerate envelope detection."
**Current**: `check_degenerate_envelope()` exists in L1 but L3 never calls it.
**Fix**: Call `check_degenerate_envelope()` in:

1. `validate_org_detailed()` in `builder.py` — check after computing effective envelopes
2. CLI `pact validate` command — surface degenerate warnings
3. Runtime `_verify_governance()` — warn (not block) when operating under degenerate envelope

**Files**: `builder.py`, `cli.py`, `runtime.py`, tests

### TODO-22: Wire pact.mcp in L3 platform (M7)

**Spec**: Disclosure — "PACT for MCP provides governance middleware for any MCP-compatible
agent, enabling PACT envelope enforcement and EATP record generation within MCP
tool-use sessions."
**Current**: `pact.mcp` sub-module exists in L1 with enforcer, middleware, audit. Zero
imports from L3.
**Fix**: Create `src/pact_platform/use/mcp/` integration module that:

1. Imports `McpGovernanceMiddleware` from `pact.mcp`
2. Wires it to the platform's GovernanceEngine and org config
3. Exposes configuration via `OrgDefinition.mcp_governance: McpGovernanceConfig | None`
4. Adds CLI `pact mcp` command group for MCP governance management
5. Adds API endpoint `POST /api/v1/mcp/evaluate` for MCP tool governance queries

**Files**: New `src/pact_platform/use/mcp/` module, `cli.py`, `routers/`, `config/schema.py`, tests

---

## M6: Tooling & Observability (LOW)

### TODO-23: Platform-level shadow mode toggle (L3)

**Spec**: Disclosure — "shadow mode for simulation."
**Fix**: Add `enforcement_mode: Literal["enforce", "shadow", "disabled"]` to platform config.
When `shadow`, all governance runs through `ShadowEnforcer` instead of `HookEnforcer`.
Add CLI `pact config set enforcement-mode shadow` command.

**Files**: Platform config, `runtime.py`, `cli.py`, tests

### TODO-24: pact calibrate CLI command (L4)

**Spec**: Section 12.1 — "Initial deployments should target at least 10% held events."
**Fix**: Add `pact calibrate` command that:

1. Takes an org definition + optional synthetic action set
2. Runs actions through governance in shadow mode
3. Reports per-supervisor held ratio
4. Flags supervisors below 10% held (potential constraint theater)
5. Flags supervisors above 50% held (potential over-restriction)

**Files**: `cli.py`, new calibration module, tests

### TODO-25: Post-execution TOCTOU comparison (L5)

**Spec**: Section 12.9.5 — "Post-execution audit comparison."
**Current**: Envelope version hash recorded in audit but never re-checked.
**Fix**: Add batch audit process `audit_toctou_check()` that:

1. Reads recent audit anchors with envelope_version
2. Re-computes effective envelope for each role at current org state
3. Compares current version hash against recorded version hash
4. Flags divergences (org changed between decision and now)

**Files**: New audit module, `cli.py` (`pact audit toctou`), tests

### TODO-26: Bilateral delegation atomicity wrapper (L1)

**Spec**: Section 4.4 — "both records are created atomically or neither is."
**Dependency**: Blocked by TODO-08 (bilateral DelegationRecords)
**Fix**: Wrap the two DelegationRecord creations in a `BilateralDelegation` transactional
pattern that rolls back on partial failure.

**Repo**: kailash-py
**Files**: `engine.py` or new `bilateral.py`, tests

---

## Summary

| Group                  | Todos | Layer | Priority      | Dependency                |
| ---------------------- | ----- | ----- | ------------- | ------------------------- |
| M0 Emergency Bypass    | 01-04 | L3    | CRITICAL+HIGH | None                      |
| M1 EATP Records        | 05-09 | L1    | CRITICAL      | None                      |
| M2 Envelope & Gradient | 10-13 | L1    | HIGH+MEDIUM   | None                      |
| M3 Grammar & Bridges   | 14-17 | L1    | HIGH+MEDIUM   | None                      |
| M4 Vacancy & Posture   | 18-20 | L1+L3 | HIGH+MEDIUM   | None                      |
| M5 L1->L3 Wiring       | 21-22 | L3    | MEDIUM        | M1 for MCP audit          |
| M6 Tooling             | 23-26 | L3+L1 | LOW           | M2 for gradient calibrate |

**L1 items (kailash-py)**: 05-17, 19-20, 26 (16 todos)
**L3 items (this repo)**: 01-04, 18, 21-25 (10 todos)

**Estimated**: 3-4 autonomous sessions for M0-M4 (CRITICAL+HIGH).
M5-M6 (MEDIUM+LOW) can follow in 1-2 sessions.
