# COC Analysis: Restructuring Risk Assessment

**Date**: 2026-03-24
**Methodology**: COC five-layer architecture (anti-amnesia, convention drift, security blindness)
**Subject**: src/pact/ to src/pact_platform/ rename, governance deletion, trust triage, import rewrite, new surfaces (DataFlow, GovernedSupervisor, webhooks)
**Predecessor**: #20 (repivot COC analysis, 2026-03-21)
**Inputs**: All 26 rule files, 58 trust/ source files, 31 governance/ source files, 26 red team reports, 33 analysis documents, 2 integration briefs, pyproject.toml

---

## Executive Summary

This is the largest structural change in the repo's history. The previous COC analysis (#20) correctly identified the three fault lines but was written before M0 scope was finalized. This analysis is the operational version: exact file dispositions, exact rule updates, exact knowledge to preserve, exact new security surfaces.

The restructuring simultaneously triggers all three COC fault lines:

1. **Amnesia**: 10+ red team rounds of security knowledge are embedded in ~22 trust/ files being deleted. The knowledge must be extracted before the code disappears.
2. **Convention drift**: 13 of 26 rule files reference code being moved or deleted. Without updates, every future session will follow stale rules.
3. **Security blindness**: Six new attack surfaces emerge (DataFlow SQL injection, GovernedSupervisor self-modification, webhook SSRF, approval queue bypass, pool flooding, CLI injection). No existing rule covers them.

---

## 1. Anti-Amnesia Audit

### 1.1 Knowledge Source Inventory

Every institutional knowledge source in this repo, mapped to post-restructuring status.

#### 1.1.1 Analysis Documents (33 files) -- ALL SURVIVE

| File Range | Content                                                            | Post-Restructuring Status                                    |
| ---------- | ------------------------------------------------------------------ | ------------------------------------------------------------ |
| #01-#13    | Original PACT analysis (research, synthesis, UI/UX, Flutter)       | SAFE -- workspace artifacts, not touched                     |
| #14-#17    | Thesis alignment, gaps (PACT, EATP)                                | SAFE -- captures architectural decisions that transcend code |
| #18-#22    | Repivot analysis (deep, requirements, COC, value audit, synthesis) | SAFE -- the reasoning behind the restructuring itself        |
| #23-#24    | Open/commercial boundary analysis                                  | SAFE                                                         |
| #25-#33    | Delegate integration analysis (5 rounds)                           | SAFE -- captures L1/L2/L3 architecture decisions             |

**Risk**: NONE for analysis docs. They live in `workspaces/` which is untouched.

#### 1.1.2 Red Team Reports (26 files) -- ALL SURVIVE

Location: `workspaces/pact/04-validate/`

These are the most valuable artifacts in the repo. They contain:

| Report                                | Key Knowledge                                                       | Post-Restructuring Relevance                                                                     |
| ------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `red-team-report.md` (RT-01 to RT-39) | 10 CRITICAL + 12 HIGH + 11 MEDIUM + 6 LOW findings                  | Still relevant -- findings apply to governance patterns now in kailash-pact AND to platform code |
| `rt21-governance-report.md`           | 40 adversarial tests, NaN/Inf bypass, self-modification attacks     | CRITICAL -- these attack patterns apply to GovernedSupervisor wiring (M4)                        |
| `rt21-convergence-report.md`          | Convergence to 0 actionable findings                                | Historical but validates the security posture baseline                                           |
| `redteam-round1-report.md`            | First-round systemic patterns (defined-but-not-wired, dual-systems) | Still relevant -- M4 wiring must not repeat Pattern A                                            |
| `rt11-security-findings.md`           | Specific vulnerability classes                                      | Applies to any new code writing to trust stores                                                  |
| `rt18-lifecycle-analysis.md`          | Integration seam findings                                           | DIRECTLY relevant to M4 (GovernedSupervisor is the new integration seam)                         |
| `rt19-entry-points-and-boundaries.md` | Attack surface mapping                                              | Must be updated post-M0 (boundaries change)                                                      |

**Risk**: NONE for red team reports. All survive in workspace. The risk is not loss but **disconnection** -- future sessions may not know these reports exist or that they apply to the new architecture.

**Mitigation**: The CLAUDE.md rewrite (Section 6) must reference red team reports as mandatory pre-reading for security-sensitive milestones.

#### 1.1.3 Integration Decisions (1 file) -- SURVIVES, NEEDS UPDATE

File: `workspaces/pact/briefs/integration-decisions.md`

Contains 13 numbered architectural decisions. Post-restructuring status:

| Decision                                           | Status                      | Update Needed                                                                                            |
| -------------------------------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------- |
| #1 Option B Architecture                           | COMPLETED -- migration done | Mark as historical                                                                                       |
| #2 Package Name: kailash-pact                      | COMPLETED                   | Add: pact-platform is the platform package                                                               |
| #3 D/T/R Grammar Invariant                         | PERMANENT                   | None                                                                                                     |
| #4 Five-Step Access Algorithm                      | PERMANENT                   | None                                                                                                     |
| #5 Three-Layer Envelope Model                      | PERMANENT                   | None                                                                                                     |
| #6 Frozen Dataclass Pattern                        | PERMANENT                   | None                                                                                                     |
| #7 Bounded Stores (maxlen=10,000)                  | PERMANENT                   | None                                                                                                     |
| #8 University as Canonical Example                 | PERMANENT                   | None                                                                                                     |
| #9 Governance to build.config Dependency Direction | SUPERSEDED                  | Rewrite: governance is now in kailash-pact; dependency direction is pact_platform -> pact (kailash-pact) |
| #10 GovernanceEngine as Facade                     | PERMANENT                   | None                                                                                                     |
| #11 Security Baked In                              | PERMANENT                   | None                                                                                                     |
| #12 EATP Merging into Kailash Core                 | IN PROGRESS                 | Update status                                                                                            |
| #13 Transitional Dependency Model                  | ACTIVE                      | Update: pyproject.toml now depends on kailash[trust] and kailash-pact directly                           |

#### 1.1.4 Rule Files (26 files) -- SEE SECTION 2 (CONVENTION DRIFT)

#### 1.1.5 Trust Layer Code (58 files) -- HIGH RISK

This is the primary anti-amnesia concern. The trust/ layer was built through 10+ red team rounds. Each file embodies security knowledge that is NOT documented anywhere else.

**Files being deleted (~22) and their embedded knowledge:**

| File                               | Security Knowledge Embedded                                                                        | Where Knowledge Must Go                       |
| ---------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| `trust/attestation.py`             | Capability attestation validation, type checking                                                   | kailash[trust] (already there)                |
| `trust/delegation.py`              | Delegation chain walking, tightening validation                                                    | kailash[trust] (already there)                |
| `trust/genesis.py`                 | Write-once genesis semantics, authority validation                                                 | kailash[trust] (already there)                |
| `trust/posture.py`                 | 5 trust posture levels, NEVER_DELEGATED actions, upgrade requirements                              | kailash-pact GovernanceEngine (already there) |
| `trust/scoring.py`                 | Trust score computation                                                                            | kailash[trust]                                |
| `trust/lifecycle.py`               | Agent lifecycle state machine                                                                      | kaizen-agents (already there)                 |
| `trust/revocation.py`              | Cascade revocation, certificate invalidation                                                       | kailash[trust]                                |
| `trust/decorators.py`              | Trust-aware function decorators                                                                    | kaizen-agents governed_tool (already there)   |
| `trust/messaging.py`               | **RT-06: SHA-256 forgery vulnerability** -- the FIX (Ed25519 signing) is the knowledge to preserve | Security patterns catalog (create)            |
| `trust/integrity.py`               | **hmac.compare_digest() pattern**, content hash verification                                       | Security patterns catalog (create)            |
| `trust/credentials.py`             | **Key material zeroization pattern**, private key lifecycle                                        | Security patterns catalog (create)            |
| `trust/sd_jwt.py`                  | SD-JWT selective disclosure implementation                                                         | Low priority -- IETF spec is the source       |
| `trust/shadow_enforcer.py`         | Shadow enforcement calibration (observes without blocking)                                         | kaizen-agents BudgetTracker + AuditTrail      |
| `trust/shadow_enforcer_live.py`    | Live shadow enforcement with actual API calls                                                      | kaizen-agents                                 |
| `trust/reasoning.py`               | **RT-07: EATP-compliant reasoning traces** (structured fields, dual-binding)                       | kailash[trust] + security patterns catalog    |
| `constraint/gradient.py`           | **Verification gradient engine** (4 zones, pattern matching, thoroughness)                         | kailash-pact GradientEngine (already there)   |
| `constraint/envelope.py`           | **5-dimension constraint evaluation**, fail-closed expiry, RT-08 fix                               | kailash-pact (already there)                  |
| `constraint/enforcement.py`        | **Pipeline composition** (GradientEngine + StrictEnforcer), RT adapter                             | kailash-pact (already there)                  |
| `constraint/verification_level.py` | Verification thoroughness enum                                                                     | kailash-pact (already there)                  |
| `constraint/signing.py`            | **Ed25519 envelope signing**, JCS canonical serialization, RT-08 fix                               | kailash-pact (already there)                  |
| `constraint/enforcer.py`           | Enforcement action execution                                                                       | kailash-pact envelope_adapter (already there) |

**Files in the "evaluate" category (~8) -- must check dependency before deleting:**

| File                            | Content                                                                           | Disposition                                                                                                                                                                                                 |
| ------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `constraint/cache.py`           | Verification result caching with TTL                                              | CHECK: used by middleware.py. If middleware is kept, cache is kept.                                                                                                                                         |
| `constraint/resolution.py`      | Hierarchy intersection algorithm (per-dimension)                                  | CHECK: the formal intersection semantics. kailash-pact has `compute_effective_envelope()` but this may contain edge-case knowledge.                                                                         |
| `constraint/middleware.py`      | **THE central enforcement pipeline** -- 26 RT fixes documented in header comments | CHECK: this is 1,000+ lines of battle-hardened code. It references RT-03, RT-05, RT-08, RT-09, RT-30, RT2-01, RT2-03, RT2-06, RT2-14, RT2-33, RT2-19, RT2-34, RT2-36. Every line has a red team provenance. |
| `constraint/circuit_breaker.py` | Fail-safe BLOCKED on verification system failure                                  | CHECK: production resilience pattern.                                                                                                                                                                       |
| `constraint/bridge_envelope.py` | Cross-team bridge envelope intersection, information sharing modes                | CHECK: bridge constraint computation. kailash-pact has bridge support but verify this specific intersection logic.                                                                                          |
| `audit/anchor.py`               | **AuditChain with HMAC + Ed25519 signing** -- RT-13 fix                           | CHECK: kailash-pact has AuditChain. Verify it includes the RT-13 signing fix.                                                                                                                               |
| `audit/pipeline.py`             | Per-agent audit chain management                                                  | CHECK: may be platform-specific (per-agent chains).                                                                                                                                                         |
| `audit/bridge_audit.py`         | Cross-bridge audit trail                                                          | CHECK: platform-specific bridge audit.                                                                                                                                                                      |
| `resilience/failure_modes.py`   | 5 CARE failure modes (detection, mitigation, recovery)                            | KEEP: platform-specific operational resilience.                                                                                                                                                             |

**CRITICAL ANTI-AMNESIA ACTION**: Before deleting ANY file in the "evaluate" category, verify that:

1. Every RT-tagged fix in the file header exists in the kailash-pact or kailash[trust] equivalent.
2. Every `math.isfinite()` guard is preserved.
3. Every `hmac.compare_digest()` usage is preserved.
4. Every `frozen=True` dataclass is preserved.
5. Every fail-closed error path is preserved.

#### 1.1.6 Governance Layer Code (31 files) -- SAFE TO DELETE

Analysis #30 confirmed 1:1 correspondence between local governance/ and kailash-pact exports (88 symbols). The governance layer code is fully duplicated.

**Exception files** (do NOT delete without migration):

| File                            | Reason                                                                   |
| ------------------------------- | ------------------------------------------------------------------------ |
| `governance/cli.py`             | Has platform-specific CLI commands -- migrate to `pact_platform.cli`     |
| `governance/stores/sqlite.py`   | Verify exists in kailash-pact before deleting                            |
| `governance/stores/backup.py`   | Verify exists in kailash-pact before deleting                            |
| `governance/api/*.py` (5 files) | Platform-specific API layer -- migrate to `pact_platform.api.governance` |

#### 1.1.7 COC Layer (.claude/) -- LOW RISK IF UPDATED

The .claude/ directory survives the restructuring. The risk is stale references, not deletion. See Section 2.

#### 1.1.8 Memory Files (~/.claude/projects/) -- SAFE

15 memory files live outside the repo. They capture architectural decisions, user preferences, and build order. No restructuring impact.

### 1.2 Knowledge Continuity Actions (Ordered by Priority)

| #   | Action                                                                                                                                                                                                     | Priority | What It Preserves                    | When                                     |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------------------ | ---------------------------------------- |
| K1  | **Create `docs/architecture/security-patterns-catalog.md`** extracting all 11 hardened security patterns from trust/ code + red team reports into a standalone, code-independent document                  | CRITICAL | Trust layer security knowledge       | BEFORE any trust/ deletion               |
| K2  | **Create `docs/architecture/trust-file-disposition.md`** documenting the fate of every trust/ file (deleted, kept, migrated) with the reasoning                                                            | CRITICAL | Migration decision trail             | During M0                                |
| K3  | **Verify RT-fix parity** between constraint/middleware.py header (12 RT fixes) and kailash-pact GovernanceEngine                                                                                           | CRITICAL | Red team fix continuity              | BEFORE deleting constraint/middleware.py |
| K4  | **Archive trust/ to `archive/trust-v0.2/`** rather than deleting                                                                                                                                           | HIGH     | Rollback capability + code reference | During M0                                |
| K5  | **Update integration-decisions.md** with new decisions (#14-#18) covering: platform rename, namespace boundary, trust triage disposition, DataFlow security profile, GovernedSupervisor wiring constraints | HIGH     | Architectural decision continuity    | During M0                                |
| K6  | **Create `docs/architecture/red-team-index.md`** mapping each RT finding to its current location (kailash-pact, kailash[trust], platform, or archived)                                                     | HIGH     | Red team knowledge navigability      | After M0                                 |
| K7  | **Update CLAUDE.md** with restructured architecture, milestone index, and mandatory red-team-report references for security-sensitive work                                                                 | HIGH     | Session-start context                | During M0                                |

---

## 2. Convention Drift: All 26 Rule Files Audited

### 2.1 Rules Requiring Rewrite

#### `trust-plane-security.md` -- REWRITE

**Current state**: References `kailash.trust._locking` functions (`safe_read_json`, `safe_open`, `atomic_write`, `validate_id`), `trustplane/store/` paths.

**Post-restructuring**: Trust store code stays as `pact_platform.trust.*` for platform-specific stores. kailash-pact handles governance stores. kailash[trust] handles primitives.

**Required changes**:

- Scope: Change from `trust/` files to `src/pact_platform/trust/**` and any files using trust store operations
- Rule 1 (No bare `open()`): Keep as-is -- still applies to platform trust stores
- Rule 2 (`validate_id()`): Keep. Update import path: `from kailash.trust._locking import validate_id` becomes wherever the platform stores import it from
- Rule 3 (`math.isfinite()`): Keep unchanged -- universally applicable
- Rule 4 (Bounded collections): Keep unchanged
- Rule 5 (Parameterized SQL): Keep unchanged
- Rule 6 (SQLite file permissions): Keep unchanged
- Rule 7 (`atomic_write()`): Keep. Note that platform stores may use their own implementation
- MUST NOT Rule 7 (RecordNotFoundError): Update import path reference

**Add new rule**: Rule 9 -- `normalize_resource_path()` for all constraint pattern storage (currently last rule, keep it)

#### `governance.md` -- MAJOR REWRITE

**Current state**: References `src/pact/governance/**`, `src/pact/build/org/**`, `src/pact/build/config/schema.py` as scoped files.

**Post-restructuring**: Governance code is in kailash-pact (pip install). Platform code that USES governance is in `src/pact_platform/`.

**Required changes**:

- **Scope**: Remove `src/pact/governance/**` and `src/pact/build/config/schema.py`. Add `src/pact_platform/**` files that import from `pact.*` (kailash-pact)
- **Rule 1 (GovernanceEngine single entry point)**: KEEP -- now applies to how platform code uses the imported engine. Update example imports: `from pact.governance.engine import GovernanceEngine` becomes `from pact import GovernanceEngine`
- **Rule 2 (Audit anchors)**: KEEP -- now applies to platform-level mutations that must emit audit events through the engine
- **Rule 3 (Frozen dataclasses)**: KEEP -- applies to any new platform-level governance record types
- **Rule 4 (math.isfinite)**: KEEP unchanged
- **Rule 5 (Thread-safe stores)**: KEEP -- platform's DataFlow-backed stores still need thread safety
- **Rule 6 (Fail-closed)**: KEEP unchanged
- **Rule 7 (Bounded collections)**: KEEP unchanged
- **Rule 8 (Compilation limits)**: KEEP -- platform may expose org compilation through CLI/API
- **Rule 9 (Address validation)**: KEEP unchanged
- **Rule 10 (Boundary test compliance)**: REVISE -- `src/pact_platform/` is the platform, not the framework. Domain vocabulary is allowed in platform examples. Boundary test only applies to code in kailash-pact now.
- **MUST NOT Rule 1 (No governance imports in trust layer)**: REVISE -- dependency direction is now `pact_platform` -> `pact` (kailash-pact). Platform code must not modify governance primitives.
- **MUST NOT Rule 2 (No mutable state to agents)**: KEEP unchanged
- **MUST NOT Rule 3 (No legacy envelope path)**: UPDATE -- legacy path no longer exists in this repo
- **MUST NOT Rule 4 (Thread safety from day 1)**: KEEP unchanged
- **MUST NOT Rule 5 (Default-deny tool registration)**: KEEP unchanged

#### `pact-governance.md` -- MAJOR REWRITE

**Current state**: References PACT governance files and supplements trust-plane-security.md.

**Post-restructuring**: PACT governance primitives are in kailash-pact. This rule now applies to how the platform USES those primitives.

**Required changes**:

- **Scope**: Change to `src/pact_platform/**` files that interact with governance
- **Rule 1 (Frozen GovernanceContext)**: KEEP unchanged -- still applies when platform creates contexts for agents
- **Rule 2 (Monotonic tightening)**: KEEP unchanged
- **Rule 3 (D/T/R grammar)**: KEEP unchanged
- **Rule 4 (Fail-closed)**: KEEP unchanged
- **Rule 5 (Default-deny tool registration)**: KEEP unchanged
- **Rule 6 (NaN/Inf)**: KEEP unchanged
- **Rule 7 (Compilation limits)**: KEEP unchanged
- **Rule 8 (Thread safety)**: KEEP unchanged
- **Rule 9 (NaN/Inf on context values)**: KEEP unchanged -- DIRECTLY applies to M2 API routers that accept context dicts from HTTP requests
- **MUST NOT Rule 1 (No engine exposure to agents)**: KEEP unchanged
- **MUST NOT Rule 2 (No monotonic tightening bypass)**: KEEP unchanged
- **MUST NOT Rule 3 (Structured governance errors)**: UPDATE -- errors should use `PactPlatformError` base, not `PactError` from kailash-pact (platform has its own error hierarchy)
- **MUST NOT Rule 4 (No GovernanceContext from external data)**: KEEP unchanged -- CRITICAL for M2 API routers

#### `boundary-test.md` -- ARCHIVE OR REVISE

**Current state**: Blacklists domain vocabulary in `src/pact/` excluding `examples/`.

**Post-restructuring**: The framework is in kailash-pact. This repo IS the platform -- it will contain domain vocabulary in examples, demo configs, and documentation.

**Required changes**:

- **Option A (ARCHIVE)**: Move this rule to kailash-py's COC layer where it protects the actual framework package.
- **Option B (REVISE)**: Narrow scope to `src/pact_platform/trust/**` and `src/pact_platform/execution/**` (framework-adjacent code that should remain domain-agnostic). Allow domain vocabulary in `examples/`, `api/`, `cli/`, `workspace/`.
- **Recommendation**: Option B. The platform's core execution and trust layers should remain domain-agnostic even if the platform ships with domain-specific examples.

#### `infrastructure-sql.md` -- REVISE SCOPE

**Current state**: Applies to infrastructure SQL in trust stores and dialect code.

**Post-restructuring**: Trust stores that remain in `pact_platform.trust` still use SQL. New DataFlow models (M1) generate SQL automatically. The rule is still relevant but scope changes.

**Required changes**:

- **Scope**: Add `src/pact_platform/models/**` (new DataFlow models), keep `src/pact_platform/trust/**` (surviving stores)
- All MUST rules remain valid
- Add note: DataFlow-generated SQL is auto-parameterized; these rules apply to custom queries and store implementations

### 2.2 Rules Requiring Minor Updates

#### `connection-pool.md` -- UPDATE EXAMPLES

**Current state**: DataFlow pool safety rules with examples referencing generic app patterns.

**Post-restructuring**: M1 introduces DataFlow models. M2 introduces API routers. These are the primary consumers.

**Required changes**:

- Add M1/M2 context to examples
- Rule 2 (no DB per-request in middleware): Directly applicable to M2 API routers
- Rule 3 (health checks): Directly applicable to M2 server

#### `dataflow-pool.md` -- KEEP, ADD M1 CONTEXT

**Current state**: Pool configuration rules for DataFlow.

**Post-restructuring**: M1 creates 11 DataFlow models. This rule becomes directly operational.

**Required changes**:

- Add note referencing M1 models as the primary governed surface
- Otherwise unchanged

#### `patterns.md` -- UPDATE IMPORT PATHS

**Current state**: References `from pact.build.config.schema import ...` in examples.

**Required changes**:

- Update all `pact.build.*` import paths to either `pact.*` (kailash-pact) or `pact_platform.*`
- Otherwise unchanged

#### `eatp.md` -- KEEP, MINOR NOTE

**Current state**: EATP SDK conventions.

**Post-restructuring**: EATP is merging into kailash core. This rule still applies to any platform code that creates EATP records.

**Required changes**:

- Add note: "EATP types are now imported from `kailash.trust.*` (kailash[trust] extra)"

#### `documentation.md` -- UPDATE REPO REFERENCES

**Current state**: References kailash-py monorepo URLs.

**Required changes**:

- Add pact-platform specific documentation requirements (CLAUDE.md accuracy, architecture docs)
- Keep all existing rules

#### `testing.md` -- UPDATE SCOPE PATHS

**Current state**: Test paths reference the pre-restructuring layout.

**Required changes**:

- Update any paths that reference `pact.governance.*` or `pact.trust.*` in test examples
- Add DataFlow testing patterns for M1 models
- Keep all existing rules

### 2.3 Rules Requiring No Changes (11 files)

| Rule File                 | Why It Survives Unchanged                                                 |
| ------------------------- | ------------------------------------------------------------------------- |
| `agents.md`               | Agent orchestration rules are code-agnostic                               |
| `autonomous-execution.md` | Execution model rules are architectural, not code-specific                |
| `branch-protection.md`    | Git protection rules are repo-level                                       |
| `communication.md`        | Communication style is universal                                          |
| `cross-sdk-inspection.md` | Cross-SDK rules apply to kailash-py/kailash-rs, not this repo's internals |
| `deployment.md`           | Release rules are process-level                                           |
| `e2e-god-mode.md`         | E2E testing rules apply to any UI                                         |
| `env-models.md`           | .env rules are universal                                                  |
| `git.md`                  | Git workflow rules are universal                                          |
| `independence.md`         | Foundation independence is structural                                     |
| `terrene-naming.md`       | Naming conventions are permanent                                          |

### 2.4 Rules Requiring Deletion or Archival

| Rule File              | Disposition                                                                 |
| ---------------------- | --------------------------------------------------------------------------- |
| `learned-instincts.md` | AUTO-GENERATED -- regenerated by session-end hook. No manual action needed. |

### 2.5 New Rules Needed

| New Rule               | Purpose                                                                                                                   | When |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------- | ---- |
| `import-boundary.md`   | Platform MUST NOT modify kailash-pact primitives. Governance code comes via pip. Bugs found = upstream fix in kailash-py. | M0   |
| `dataflow-security.md` | DataFlow model validation, input sanitization, SQL injection prevention for auto-generated nodes                          | M1   |
| `delegate-wiring.md`   | GovernedSupervisor wiring constraints: frozen context, adapter-only, no direct engine exposure, event bridge validation   | M4   |
| `webhook-security.md`  | SSRF prevention, URL allowlisting, request signing, timeout enforcement for webhook adapters                              | M6   |

### 2.6 Convention Drift in Agent Definitions

Several agents reference code paths that will change:

| Agent                    | Issue                                                                | Action                                     |
| ------------------------ | -------------------------------------------------------------------- | ------------------------------------------ |
| `pact-specialist.md`     | New agent -- verify it references pact_platform, not pact.governance | Update during M0                           |
| `dataflow-specialist.md` | Generic -- no pact-specific paths                                    | No change                                  |
| `security-reviewer.md`   | References trust-plane-security.md rules                             | Will auto-update when rule file is updated |
| `kaizen-specialist.md`   | References kaizen patterns                                           | No change                                  |

### 2.7 Convention Drift in Skills

| Skill                    | Issue                                              | Action           |
| ------------------------ | -------------------------------------------------- | ---------------- |
| `29-pact/` (new)         | Verify references point to pact_platform namespace | Update during M0 |
| `project/pool-safety.md` | References deployment patterns                     | No change needed |

---

## 3. Security Blindness: Existing Patterns

### 3.1 The 11 Hardened Security Patterns -- Full Catalog

Each pattern was forged through red team rounds. This catalog maps each pattern to its current enforcement location and post-restructuring status.

| #   | Pattern                                                                                                   | Origin RT                                | Current Location(s)                                      | Post-Restructuring Location                                                                 | Status                                                                                                                         |
| --- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 1   | **validate_id()** -- regex `^[a-zA-Z0-9_-]+$` before any filesystem/SQL path construction                 | RT-19                                    | `trust/store/`, governance stores                        | kailash-pact stores + pact_platform.trust stores                                            | SAFE -- exists in both                                                                                                         |
| 2   | **O_NOFOLLOW** via `safe_read_json()` / `safe_open()` -- prevent symlink attacks on record files          | RT-19                                    | `trustplane._locking` (external)                         | kailash[trust] (external)                                                                   | SAFE -- external dep                                                                                                           |
| 3   | **atomic_write()** -- temp + fsync + os.replace for crash-safe record writes                              | RT-19                                    | `trustplane._locking` (external)                         | kailash[trust] (external)                                                                   | SAFE -- external dep                                                                                                           |
| 4   | **math.isfinite()** on ALL numeric constraint fields -- NaN/Inf bypass prevention                         | RT-21 governance, kailash-rs RT2         | governance/ (NaN checks), trust/constraint/ (NaN checks) | kailash-pact GovernanceEngine + pact_platform rules                                         | SAFE -- exists in kailash-pact. **Must verify platform's new DataFlow models also validate.**                                  |
| 5   | **Bounded collections** (`deque(maxlen=10000)`) -- prevent OOM in long-running processes                  | RT-23, governance rules                  | Both trust/ and governance/ layers                       | kailash-pact stores + pact_platform stores                                                  | SAFE -- exists in kailash-pact. **Must apply to M1 DataFlow model collections.**                                               |
| 6   | **Monotonic escalation only** -- trust state can only escalate (AUTO_APPROVED -> BLOCKED), never relax    | RT-02                                    | trust/posture.py, governance/envelopes.py                | kailash-pact (inherent to architecture)                                                     | SAFE                                                                                                                           |
| 7   | **hmac.compare_digest()** for all hash/signature comparison -- prevent timing attacks                     | RT-21, security rules                    | trust/integrity.py, trust/audit/anchor.py                | kailash[trust] + **must enforce in any new platform signing code**                          | AT RISK -- if integrity.py is deleted and platform writes new hash comparison code. **Captured in security-patterns-catalog.** |
| 8   | **Key material zeroization** -- `del private_key` immediately after registration, overwrite on revocation | trust-plane-security.md                  | trust/credentials.py                                     | **AT RISK** -- credentials.py may be deleted. Pattern must be in security-patterns-catalog. |
| 9   | **frozen=True** on all security-critical dataclasses -- prevent post-construction mutation                | RT-21, governance.md, pact-governance.md | Both layers                                              | kailash-pact (frozen dataclasses) + platform rules                                          | SAFE                                                                                                                           |
| 10  | **from_dict() validates all fields** -- no blind deserialization of governance state                      | pact-governance.md MUST NOT Rule 4       | governance/context.py                                    | kailash-pact GovernanceContext                                                              | SAFE -- GovernanceContext blocks from_dict()                                                                                   |
| 11  | **Fail-closed on all error paths** -- deny on error, never permit                                         | RT-09, governance.md Rule 6              | Both layers                                              | kailash-pact + pact_platform rules                                                          | SAFE                                                                                                                           |

### 3.2 Per-File Security Knowledge in Files Being Deleted

#### Files Superseded by kailash[trust] (~12 files)

| File                   | Security Knowledge                                             | Preserved In                                                        |
| ---------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------- |
| `trust/attestation.py` | Capability type validation, attestation format checks          | kailash[trust] CapabilityAttestation                                |
| `trust/delegation.py`  | Delegation chain walking, tightening validation (RT-02 fix)    | kailash[trust] DelegationRecord                                     |
| `trust/genesis.py`     | Write-once semantics, authority validation                     | kailash[trust] GenesisRecord                                        |
| `trust/posture.py`     | NEVER_DELEGATED actions list (RT-03 fix), upgrade requirements | kailash-pact GovernanceEngine                                       |
| `trust/scoring.py`     | Trust score computation with bounds                            | kailash[trust]                                                      |
| `trust/lifecycle.py`   | Agent lifecycle state machine                                  | kaizen-agents                                                       |
| `trust/revocation.py`  | Cascade revocation with EATP chain invalidation (RT-14 fix)    | kailash[trust]                                                      |
| `trust/decorators.py`  | Trust-aware function decorators                                | kailash-pact governed_tool                                          |
| `trust/messaging.py`   | **RT-06 fix**: Ed25519 message signing (was SHA-256 forgery)   | **NOT YET in kailash-pact** -- capture in security patterns catalog |
| `trust/integrity.py`   | **hmac.compare_digest()** for hash comparison (RT-21 fix)      | **PARTIALLY** in kailash[trust]. Capture pattern in catalog.        |
| `trust/credentials.py` | **Key material zeroization** pattern                           | **NOT in kailash-pact** -- capture in security patterns catalog     |
| `trust/sd_jwt.py`      | SD-JWT selective disclosure                                    | Specialist feature -- IETF spec is source of truth                  |

**Gaps found**: Three security patterns (messaging signing, constant-time comparison, key zeroization) are NOT confirmed to exist in kailash-pact or kailash[trust]. These MUST be captured in the security patterns catalog before the files are deleted.

#### Files Superseded by kailash-pact (~5 files)

| File                               | Security Knowledge                                                                     | Preserved In                            |
| ---------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------- |
| `constraint/gradient.py`           | 4-zone verification gradient, pattern matching, thoroughness                           | kailash-pact GradientEngine (confirmed) |
| `constraint/envelope.py`           | 5-dimension evaluation, fail-closed expiry (RT-08), active envelope selection (RT7-06) | kailash-pact (confirmed)                |
| `constraint/enforcement.py`        | GradientEngine + StrictEnforcer pipeline, CARE-to-EATP adapter                         | kailash-pact (confirmed)                |
| `constraint/verification_level.py` | Thoroughness enum                                                                      | kailash-pact (confirmed)                |
| `constraint/signing.py`            | Ed25519 envelope signing, JCS canonical serialization (RT-08, M15/1504 fixes)          | kailash-pact (confirmed)                |

**Gaps found**: None. All 5 constraint-layer files have confirmed kailash-pact equivalents.

#### Files Superseded by kaizen-agents (~3 files)

| File                            | Security Knowledge                                                           | Preserved In                                                    |
| ------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `trust/shadow_enforcer.py`      | Shadow evaluation (observe without blocking)                                 | kaizen-agents AuditTrail                                        |
| `trust/shadow_enforcer_live.py` | Live shadow enforcement with real API calls                                  | kaizen-agents                                                   |
| `trust/reasoning.py`            | RT-07 fix: EATP-compliant reasoning traces (structured fields, dual-binding) | kailash[trust] reasoning + **verify dual-binding is preserved** |

**Gaps found**: Verify dual-binding from trust/dual_binding.py is preserved in kailash[trust].

#### Files in "Evaluate" Category (~8 files)

These files need dependency analysis before disposition:

| File                            | Used By (in kept code)                           | Disposition                                                                                                                                                                |
| ------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `constraint/cache.py`           | constraint/middleware.py (if kept)               | If middleware is kept: KEEP. If middleware is deleted: DELETE.                                                                                                             |
| `constraint/resolution.py`      | Standalone (hierarchy intersection)              | kailash-pact has `compute_effective_envelope()`. **VERIFY** resolution.py's per-dimension intersection rules are fully captured. DELETE if confirmed.                      |
| `constraint/middleware.py`      | execution/runtime.py, execution/hook_enforcer.py | **THE HARDEST CALL**. 1,000+ lines, 12 RT fixes. If execution runtime uses GovernedSupervisor (M4), middleware becomes redundant. KEEP until M4 is complete, then archive. |
| `constraint/circuit_breaker.py` | constraint/middleware.py                         | Same disposition as middleware.                                                                                                                                            |
| `constraint/bridge_envelope.py` | execution/kaizen_bridge.py                       | kailash-pact has bridge support. VERIFY bridge intersection is fully captured.                                                                                             |
| `audit/anchor.py`               | Multiple files (audit chain)                     | kailash-pact has AuditChain. VERIFY RT-13 signing fix is present.                                                                                                          |
| `audit/pipeline.py`             | execution/runtime.py                             | Per-agent audit chain management -- may be platform-specific. KEEP if execution runtime needs it.                                                                          |
| `audit/bridge_audit.py`         | execution/kaizen_bridge.py                       | Bridge-specific audit. KEEP if bridges are platform-managed.                                                                                                               |
| `resilience/failure_modes.py`   | Standalone (5 CARE failure modes)                | **KEEP** -- operational resilience is platform-specific.                                                                                                                   |

---

## 4. Security Blindness: New Attack Surfaces

### M0: Platform Rename and Cleanup

**New surfaces**: None introduced. M0 is structural (rename, delete, rewrite imports).

**Security concerns**:

- **Import confusion attack**: After rename, ensure no residual `import pact.governance.*` in platform code tries to import from kailash-pact's governance layer and accidentally gets different behavior than expected.
- **Stale test imports**: 153 collection errors may mask actual test failures. Fix all collection errors before proceeding.

**Rules that apply**: `security.md` (no secrets in committed files), `git.md` (atomic commits)

### M1: Work Management Models (DataFlow)

**New surfaces**:

| Surface                               | Attack Vector                                                                                                                           | Applicable Rule                                                                        | New Rule Needed?                                                                                                      |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **SQL injection via DataFlow**        | DataFlow auto-generates queries from model definitions. Custom queries (filters, aggregations) may be injectable.                       | `infrastructure-sql.md` Rule 1 (validate identifiers), Rule 5 (use `dialect.upsert()`) | YES -- `dataflow-security.md` must cover: model field validation, custom query patterns, auto-generated node security |
| **Model field validation bypass**     | DataFlow silently ignores unknown parameters. A malformed `AgenticDecision` could bypass approval workflow by omitting required fields. | `testing.md` State Persistence Verification                                            | NO -- existing rule covers read-back verification                                                                     |
| **Unbounded model collections**       | 11 models x unlimited records = OOM potential                                                                                           | `pact-governance.md` Rule 7 (bounded collections), `infrastructure-sql.md` Rule 7      | NO -- existing rules cover this                                                                                       |
| **AgenticObjective injection**        | User-supplied title/description fields injected into LLM prompts                                                                        | `security.md` Rule 3 (input validation)                                                | YES -- add prompt injection prevention to `dataflow-security.md`                                                      |
| **AgenticPool membership escalation** | Agent adds itself to a pool with higher capabilities                                                                                    | `pact-governance.md` Rule 5 (default-deny tool registration)                           | YES -- pool membership must go through GovernanceEngine                                                               |

### M2: Work Management API (FastAPI Routers)

**New surfaces**:

| Surface                                     | Attack Vector                                                                 | Applicable Rule                                         | New Rule Needed?                                                |
| ------------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------- |
| **NaN/Inf in context dicts**                | HTTP POST with `{"transaction_amount": NaN}` bypasses all budget checks       | `pact-governance.md` Rule 9 (NaN/Inf on context values) | NO -- rule exists, must be enforced in every router             |
| **Unauthenticated approval**                | RT-04 fix must be applied to new decision endpoints                           | `security.md` Rule 3 (input validation)                 | NO -- existing RT-04 fix pattern applies                        |
| **IDOR (Insecure Direct Object Reference)** | `/api/v1/objectives/{id}` without ownership check                             | `security.md` Rule 3                                    | YES -- add IDOR prevention to API router security rules         |
| **Rate limiting bypass**                    | Governance API has slowapi. New routers need it too.                          | `connection-pool.md`                                    | NO -- existing pattern, must be applied                         |
| **Mass assignment**                         | POST body includes fields that should not be user-settable (status, cost_usd) | `security.md` Rule 3                                    | YES -- add mass assignment prevention to `dataflow-security.md` |

### M3: Admin CLI

**New surfaces**:

| Surface                          | Attack Vector                                                             | Applicable Rule                                                                | New Rule Needed?                                                                          |
| -------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| **YAML deserialization**         | `pact org create <yaml>` with malicious YAML (yaml.load with Loader=None) | `security.md` Rule 1                                                           | NO -- must use `yaml.safe_load()`. Existing YAML loader in kailash-pact already does.     |
| **CLI argument injection**       | `pact role assign "D1-R1; DROP TABLE"`                                    | `trust-plane-security.md` Rule 2 (validate_id), `infrastructure-sql.md` Rule 1 | NO -- address validation via Address.parse() + validate_id() handles this                 |
| **Clearance escalation via CLI** | `pact clearance grant <address> TOP_SECRET` by unauthorized user          | `pact-governance.md` Rule 4 (fail-closed)                                      | YES -- CLI must authenticate caller. Add to `delegate-wiring.md` or new `cli-security.md` |
| **Audit export data leakage**    | `pact audit export json` includes sensitive metadata                      | RT-34 (existing LOW finding)                                                   | NO -- existing finding, implement redaction                                               |

### M4: GovernedSupervisor Wiring

**New surfaces -- THE HIGHEST RISK MILESTONE**:

| Surface                                 | Attack Vector                                                                                                                                  | Applicable Rule                                           | New Rule Needed?                                                                                                                  |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Agent self-modification**             | GovernedSupervisor holds reference to GovernanceEngine. If wiring is wrong, agent can call engine.update_envelope() on itself.                 | `pact-governance.md` MUST NOT Rule 1 (no engine exposure) | YES -- `delegate-wiring.md` must mandate: DelegateBridge receives GovernanceContext (frozen), NEVER GovernanceEngine              |
| **Envelope adapter type confusion**     | ConstraintEnvelopeConfig (Pydantic, NaN-safe) to ConstraintEnvelope (dataclass, dict-based). Dict fields can contain NaN.                      | `pact-governance.md` Rule 6 (NaN/Inf)                     | YES -- `delegate-wiring.md` must mandate: adapter validates math.isfinite() on EVERY numeric dict value during conversion         |
| **Event bridge injection**              | PlanEvent -> WebSocket. Malicious PlanEvent content reaches dashboard without sanitization.                                                    | `security.md` Rule 4 (output encoding)                    | YES -- `delegate-wiring.md` must mandate: event bridge sanitizes all user-derived content before WebSocket emit                   |
| **HELD verdict bypass**                 | GovernedSupervisor's BudgetTracker emits HELD. Bridge to AgenticDecision (DataFlow) loses the HELD state. Agent continues executing.           | `pact-governance.md` Rule 4 (fail-closed)                 | YES -- `delegate-wiring.md` must mandate: HELD verdict from GovernedSupervisor BLOCKS execution until AgenticDecision is resolved |
| **execute_node callback escape**        | The callback provided to GovernedSupervisor.run() wraps BackendRouter. If callback is not governance-gated, agent bypasses envelope checks.    | `pact-governance.md` (overall)                            | YES -- `delegate-wiring.md` must mandate: execute_node callback routes through engine.verify_action()                             |
| **Stale context after envelope update** | GovernanceContext is frozen at wiring time. If envelope is updated mid-execution, agent operates on stale (possibly more permissive) envelope. | Not covered                                               | YES -- `delegate-wiring.md` must address context refresh strategy                                                                 |

### M5: Frontend Updates

**New surfaces**:

| Surface                               | Attack Vector                                           | Applicable Rule                                                          | New Rule Needed?                            |
| ------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------- |
| **XSS in objective/request display**  | User-created objective titles rendered without escaping | `security.md` Rule 4 (output encoding)                                   | NO -- existing rule applies                 |
| **CSRF on approval actions**          | Approval button submits without CSRF token              | `security.md`                                                            | NO -- existing security review should catch |
| **Interactive org builder injection** | D/T/R names from user input injected into compilation   | `pact-governance.md` Rule 3 (D/T/R grammar), Rule 9 (address validation) | NO -- Address.parse() validates             |

### M6: Integration Layer (Webhooks)

**New surfaces**:

| Surface                                | Attack Vector                                                                        | Applicable Rule                                              | New Rule Needed?                                                                                                |
| -------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| **SSRF (Server-Side Request Forgery)** | Webhook URL set to `http://169.254.169.254/latest/meta-data/` (AWS metadata)         | Not covered                                                  | YES -- `webhook-security.md` must mandate: URL allowlisting, private IP rejection, DNS rebinding prevention     |
| **Webhook replay**                     | Captured webhook payload replayed to trigger duplicate actions                       | Not covered                                                  | YES -- `webhook-security.md` must mandate: request signing (HMAC), nonce/timestamp validation, idempotency keys |
| **Webhook flooding**                   | External service sends 10,000 events/second                                          | `connection-pool.md` (rate limiting)                         | YES -- `webhook-security.md` must mandate: rate limiting per source, circuit breaker on webhook ingestion       |
| **Notification injection**             | Slack/Discord/Teams message content includes user-generated text                     | `security.md` Rule 4 (output encoding)                       | NO -- existing rule applies, but `webhook-security.md` should explicitly require platform-specific encoding     |
| **LLM provider API key theft**         | BYO API keys stored in platform. Webhook adapter or notification service leaks them. | `security.md` Rule 1 (no hardcoded secrets), `env-models.md` | NO -- existing rules apply. Keys must stay in .env, never in DataFlow models.                                   |

---

## 5. Knowledge Continuity Plan

### 5.1 Actions BEFORE M0 Starts

| #   | Action                                     | Deliverable                                                                                                                             | Who                                      |
| --- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| P1  | **Create security patterns catalog**       | `docs/architecture/security-patterns-catalog.md` -- all 11 patterns with code examples, RT provenance, and platform applicability notes | Before any trust/ deletion               |
| P2  | **Verify RT-fix parity for middleware.py** | Checklist of 12 RT fixes, each confirmed present in kailash-pact                                                                        | Before deleting constraint/middleware.py |
| P3  | **Verify dual-binding preservation**       | Confirm kailash[trust] has dual_binding.py equivalent                                                                                   | Before deleting trust/dual_binding.py    |
| P4  | **Verify messaging.py Ed25519 fix**        | Confirm kailash[trust] has Ed25519 message signing (not SHA-256)                                                                        | Before deleting trust/messaging.py       |

### 5.2 Actions DURING M0

| #   | Action                                    | Deliverable                                            | When                          |
| --- | ----------------------------------------- | ------------------------------------------------------ | ----------------------------- |
| P5  | **Archive trust/ to archive/trust-v0.2/** | Git-preserved trust layer code for reference           | When trust/ files are deleted |
| P6  | **Create trust-file-disposition.md**      | Table of all 58 trust files with fate + reasoning      | During trust triage           |
| P7  | **Update integration-decisions.md**       | Add decisions #14-#18                                  | After rename is complete      |
| P8  | **Rewrite CLAUDE.md**                     | See Section 6                                          | After rename is complete      |
| P9  | **Update 13 rule files**                  | Per Section 2 analysis                                 | After rename is complete      |
| P10 | **Create import-boundary.md rule**        | Prevents platform from modifying governance primitives | After rename is complete      |

### 5.3 Actions DURING M1-M3

| #   | Action                                        | Deliverable                                                                                                  | When                         |
| --- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------- |
| P11 | **Create dataflow-security.md rule**          | DataFlow model validation, SQL injection prevention, mass assignment prevention, prompt injection prevention | Before M1 models are created |
| P12 | **Apply NaN/Inf validation to all M1 models** | Every numeric field in every DataFlow model validated                                                        | During M1                    |
| P13 | **Apply rate limiting to all M2 routers**     | slowapi on every new endpoint                                                                                | During M2                    |
| P14 | **Add authentication to M3 CLI**              | CLI caller verification before state-mutating commands                                                       | During M3                    |

### 5.4 Actions DURING M4

| #   | Action                                | Deliverable                                                                   | When                          |
| --- | ------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------- |
| P15 | **Create delegate-wiring.md rule**    | GovernedSupervisor wiring constraints (see Section 4, M4 table)               | Before M4 wiring starts       |
| P16 | **Verify adapter NaN safety**         | PlatformEnvelopeAdapter validates math.isfinite() on every numeric dict value | During adapter implementation |
| P17 | **Re-run red team on DelegateBridge** | Focus on self-modification, context staleness, callback escape                | After M4 wiring is complete   |

### 5.5 Actions DURING M6

| #   | Action                              | Deliverable                                                               | When                       |
| --- | ----------------------------------- | ------------------------------------------------------------------------- | -------------------------- |
| P18 | **Create webhook-security.md rule** | SSRF prevention, replay prevention, flooding prevention                   | Before M6 webhook adapters |
| P19 | **SSRF test suite**                 | Tests for private IP rejection, DNS rebinding, metadata endpoint blocking | During M6                  |

---

## 6. CLAUDE.md Rewrite -- Key Sections

The current CLAUDE.md describes this repo as publishing kailash-pact. It needs a complete rewrite for the pact-platform identity. Here are the key sections that must change:

### 6.1 "What This Is" -- Complete Rewrite

**Current**: "A framework and reference implementation of PACT... publishes the domain-agnostic governance framework..."

**New**:

```
## What This Is

**PACT Platform** is the Terrene Foundation's human judgment surface for governed AI operations. It sits on top of two layers from kailash-py:

- **kailash-pact** (Layer 1): GovernanceEngine, D/T/R grammar, envelopes, clearance, bridges -- the governance primitives
- **kaizen-agents** (Layer 2): GovernedSupervisor, TAOD loop, planning, recovery, 7 governance subsystems -- the autonomous agent core

This repo (Layer 3) provides:
- **Org definition**: YAML + CLI + interactive builder for organizational structures
- **Approval UX**: Human decision points for HELD actions, approval queues, review workflows
- **Work management**: Objectives, requests, sessions, artifacts, decisions (DataFlow-backed)
- **Dashboard**: 18 Next.js pages for real-time governance monitoring
- **Mobile**: 14 Flutter screens for on-the-go approval and monitoring
- **Admin CLI**: org create/list, role assign, clearance grant, bridge create, envelope show, audit export
- **Example vertical**: University domain proving the full stack

**The boundary test**: kailash-pact knows nothing about universities, finance, or any domain. PACT Platform ships with domain-specific examples but its core execution and trust layers remain domain-agnostic.

**What it is NOT**: A governance framework (that is kailash-pact). Not an agent orchestrator (that is kaizen-agents). It is the **entrypoint** -- the place where humans and AI agents meet under governed autonomy.
```

### 6.2 "Architecture Overview" -- Rewrite Product Stack

**New**:

```
### Product Stack

| Layer           | Package           | Purpose                                                  |
| --------------- | ----------------- | -------------------------------------------------------- |
| L1 Primitives   | kailash-pact      | GovernanceEngine, D/T/R, envelopes, clearance, bridges   |
| L1 Primitives   | kailash[trust]    | EATP trust operations, audit anchors, trust postures     |
| L1 Primitives   | kailash-dataflow  | Zero-config database operations                          |
| L1 Primitives   | kailash-kaizen    | AI agent framework, L3 orchestration                     |
| L2 Autonomous   | kaizen-agents     | GovernedSupervisor, governance subsystems, plan DAG      |
| **L3 Platform** | **pact-platform** | **Human judgment surface (this repo)**                   |
```

### 6.3 "PACT Framework Components" -- Replace with Platform Components

**New**:

```
### Platform Components

| Component           | What                                                          | Status        |
| ------------------- | ------------------------------------------------------------- | ------------- |
| Org Builder         | YAML loader + CLI + interactive D/T/R construction            | Functional    |
| Approval UX         | HELD action queues, review workflows, decision points         | Building (M2) |
| Work Management     | DataFlow-backed objectives, requests, sessions, artifacts     | Building (M1) |
| Admin CLI           | 8 Click commands for operators                                | Building (M3) |
| GovernedSupervisor  | Delegate wiring (L2 -> L3 bridge)                             | Planned (M4)  |
| Dashboard           | 18 Next.js pages + 4 new pages                                | Functional    |
| Mobile              | 14 Flutter screens + 3 new screens                            | Functional    |
| Webhook Adapters    | Slack, Discord, Teams                                         | Planned (M6)  |
| Trust Stores        | SQLite + PostgreSQL persistence for platform trust state      | Production    |
| Execution Runtime   | Agent execution with governance gate                          | Functional    |
```

### 6.4 "Absolute Directives" -- Update Directive 1

**Current**: Directive 1 is "Framework-First" -- check Kailash frameworks before coding from scratch.

**New Directive 1**:

```
### 1. Framework-First + Library-First

Never write code from scratch before checking:
- Whether **kailash-pact** already provides the governance primitive (GovernanceEngine, envelopes, clearance, bridges)
- Whether **kaizen-agents** already provides the agent capability (GovernedSupervisor, planning, recovery)
- Whether **kailash-dataflow** already provides the persistence pattern
- Whether **kailash-nexus** already provides the API/deployment pattern

This repo USES these packages. It does not reimplement them.
```

### 6.5 "Rules Index" -- Update File Paths and Add New Rules

Add:

- `import-boundary.md` -- Platform MUST NOT modify governance primitives
- `dataflow-security.md` -- DataFlow model security (when created)
- `delegate-wiring.md` -- GovernedSupervisor constraints (when created)
- `webhook-security.md` -- Webhook adapter security (when created)

Update scope paths for: `governance.md`, `pact-governance.md`, `trust-plane-security.md`, `boundary-test.md`, `infrastructure-sql.md`

### 6.6 "Critical Execution Rules" -- Add Import Pattern

**Add**:

```python
# Governance primitives come from kailash-pact (pip install)
from pact import GovernanceEngine, GovernanceContext, GovernanceVerdict
from pact import Address, RoleEnvelope, TaskEnvelope, compute_effective_envelope
from pact.governance.config import ConstraintEnvelopeConfig

# Platform code lives in pact_platform
from pact_platform.execution.runtime import ExecutionRuntime
from pact_platform.api.server import create_app
from pact_platform.trust.store import SQLiteTrustStore
```

### 6.7 New Section: "Milestone Index"

```
## Milestones

| Milestone | What | Security Rules | Red Team Reports to Read |
|---|---|---|---|
| M0 | Rename + cleanup | security.md, trust-plane-security.md | red-team-report.md (all RTs) |
| M1 | DataFlow models | dataflow-security.md, infrastructure-sql.md, connection-pool.md | rt21-governance-report.md (NaN) |
| M2 | API routers | pact-governance.md Rule 9 (NaN), security.md Rule 3 (input validation) | rt-04 (approval auth) |
| M3 | Admin CLI | security.md, pact-governance.md Rule 4 | rt-19 (path traversal) |
| M4 | GovernedSupervisor | delegate-wiring.md, pact-governance.md | rt21-governance-report.md, rt18-lifecycle-analysis.md |
| M5 | Frontend | security.md Rule 4 (output encoding), e2e-god-mode.md | rt14-flutter-app-report.md |
| M6 | Integration | webhook-security.md | rt19-entry-points-and-boundaries.md |
```

### 6.8 New Section: "Security Knowledge Locations"

```
## Security Knowledge

Security patterns in this repo were forged through 10+ red team rounds (26 reports in workspaces/pact/04-validate/).

| Knowledge | Primary Location | Backup Location |
|---|---|---|
| 11 hardened security patterns | docs/architecture/security-patterns-catalog.md | Rule files + red team reports |
| NaN/Inf bypass prevention | pact-governance.md Rule 6, Rule 9 | rt21-governance-report.md |
| Approval authentication | rt-04 fix in kailash-pact | red-team-report.md RT-04 |
| Envelope signing | kailash-pact constraint/signing.py | rt-08 fix documentation |
| Trust file disposition | docs/architecture/trust-file-disposition.md | analysis #36 |
| Attack surface per milestone | analysis #36 Section 4 | CLAUDE.md milestone index |
```

---

## 7. Summary of All Required Actions

### BEFORE M0 (4 actions)

- P1: Create security-patterns-catalog.md
- P2: Verify RT-fix parity for middleware.py (12 fixes)
- P3: Verify dual-binding preservation in kailash[trust]
- P4: Verify messaging.py Ed25519 fix in kailash[trust]

### DURING M0 (6 actions)

- P5: Archive trust/ to archive/trust-v0.2/
- P6: Create trust-file-disposition.md
- P7: Update integration-decisions.md (#14-#18)
- P8: Rewrite CLAUDE.md
- P9: Update 13 rule files (Section 2)
- P10: Create import-boundary.md rule

### DURING M1-M3 (4 actions)

- P11: Create dataflow-security.md rule
- P12: Apply NaN/Inf validation to all DataFlow models
- P13: Apply rate limiting to all API routers
- P14: Add authentication to CLI

### DURING M4 (3 actions)

- P15: Create delegate-wiring.md rule
- P16: Verify adapter NaN safety
- P17: Re-run red team on DelegateBridge

### DURING M6 (2 actions)

- P18: Create webhook-security.md rule
- P19: SSRF test suite

**Total**: 19 knowledge continuity actions across 7 milestones. 10 before or during M0 (critical path). 9 during M1-M6 (parallel with implementation).

---

## Appendix A: Rule File Quick Reference

| #   | Rule File                 | Update Status                    | Section |
| --- | ------------------------- | -------------------------------- | ------- |
| 1   | `agents.md`               | NO CHANGE                        | 2.3     |
| 2   | `autonomous-execution.md` | NO CHANGE                        | 2.3     |
| 3   | `boundary-test.md`        | REVISE (narrow scope)            | 2.1     |
| 4   | `branch-protection.md`    | NO CHANGE                        | 2.3     |
| 5   | `communication.md`        | NO CHANGE                        | 2.3     |
| 6   | `connection-pool.md`      | MINOR UPDATE (add M1/M2 context) | 2.2     |
| 7   | `cross-sdk-inspection.md` | NO CHANGE                        | 2.3     |
| 8   | `dataflow-pool.md`        | MINOR UPDATE (add M1 context)    | 2.2     |
| 9   | `deployment.md`           | NO CHANGE                        | 2.3     |
| 10  | `documentation.md`        | MINOR UPDATE (add platform docs) | 2.2     |
| 11  | `e2e-god-mode.md`         | NO CHANGE                        | 2.3     |
| 12  | `eatp.md`                 | MINOR UPDATE (import path note)  | 2.2     |
| 13  | `env-models.md`           | NO CHANGE                        | 2.3     |
| 14  | `git.md`                  | NO CHANGE                        | 2.3     |
| 15  | `governance.md`           | MAJOR REWRITE                    | 2.1     |
| 16  | `independence.md`         | NO CHANGE                        | 2.3     |
| 17  | `infrastructure-sql.md`   | REVISE SCOPE                     | 2.1     |
| 18  | `learned-instincts.md`    | AUTO-GENERATED                   | 2.4     |
| 19  | `no-stubs.md`             | NO CHANGE                        | 2.3     |
| 20  | `pact-governance.md`      | MAJOR REWRITE                    | 2.1     |
| 21  | `patterns.md`             | MINOR UPDATE (import paths)      | 2.2     |
| 22  | `security.md`             | NO CHANGE                        | 2.3     |
| 23  | `terrene-naming.md`       | NO CHANGE                        | 2.3     |
| 24  | `testing.md`              | MINOR UPDATE (scope paths)       | 2.2     |
| 25  | `trust-plane-security.md` | REWRITE                          | 2.1     |
| 26  | `zero-tolerance.md`       | NO CHANGE                        | 2.3     |
| --  | `import-boundary.md`      | NEW                              | 2.5     |
| --  | `dataflow-security.md`    | NEW                              | 2.5     |
| --  | `delegate-wiring.md`      | NEW                              | 2.5     |
| --  | `webhook-security.md`     | NEW                              | 2.5     |
