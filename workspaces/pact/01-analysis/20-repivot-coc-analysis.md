# Repivot COC Analysis: Institutional Knowledge Preservation

**Date**: 2026-03-21
**Methodology**: COC (Cognitive Orchestration for Codegen) five-layer architecture analysis
**Subject**: PACT repo transition from "framework builder" to "reference platform importing kailash-pact"
**Thesis**: Major restructurings are where institutional knowledge dies. The repivot must be treated as an architectural migration of _knowledge_, not just code.

---

## Situation Summary

The PACT repo has undergone a significant transition:

- **31 governance source files** (the `src/pact/governance/` package) and 37 test files (968 tests) were migrated to `kailash-py/packages/kailash-pact/`
- **125 source files remain** in this repo across `trust/` (58 files), `build/` (29 files), `use/` (25 files), and `examples/` (13 files)
- **214 test files** remain, with 153 collection errors already present (stale imports from pre-migration era)
- **26 red team reports** document security findings, convergence patterns, and architectural decisions
- **17 analysis documents** capture requirements, gaps, thesis alignment, and competitive landscape
- **23 rule files** encode institutional conventions
- **30+ agent definitions**, **30 skill directories**, **23 command files**, **13 hook scripts** form the COC layer
- **Two frontends** (Next.js dashboard, Flutter mobile) consume APIs that will need re-wiring

The repo must transition from "the place where kailash-pact is built" to "a reference platform that imports kailash-pact and demonstrates governed agent orchestration." This is architecturally analogous to a company reorganization where the R&D lab becomes a showcase factory.

---

## 1. Anti-Amnesia Assessment

### What Institutional Knowledge Is at Risk

COC's anti-amnesia mechanism (the `user-prompt-rules-reminder.js` hook that fires on every prompt) protects within a session. The repivot threat is _cross-session amnesia_ -- knowledge that exists in artifacts tied to code that will be removed, archived, or reorganized.

#### 1.1 Knowledge Embedded in Code (HIGH RISK)

The `trust/` layer (58 files) contains institutional knowledge that is NOT documented anywhere else:

| Knowledge                                                                          | Location                                                                             | Risk                                                                                   |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| 11 hardened security patterns (O_NOFOLLOW, atomic_write, constant-time comparison) | `trust/store/`, `trust/constraint/`, `trust/integrity.py`                            | **CRITICAL** -- if trust/ is removed, the security patterns skill references dead code |
| Store Security Contract (6 requirements)                                           | `trust/store/store.py` docstring + `skills/project/trust-plane-security-patterns.md` | **HIGH** -- contract is split between code and skill file                              |
| Constraint envelope intersection semantics                                         | `trust/constraint/envelope.py`, `trust/constraint/enforcement.py`                    | **HIGH** -- the formal intersection rules for all 5 dimensions live only in code       |
| Shadow enforcer calibration logic                                                  | `trust/shadow_enforcer.py`, `trust/shadow_enforcer_live.py`                          | **MEDIUM** -- this is being superseded by governance layer but patterns are reusable   |
| Bridge trust cross-boundary verification                                           | `trust/bridge_trust.py`, `trust/bridge_posture.py`                                   | **HIGH** -- 200+ LOC of trust chain walking that governance layer depends on           |
| Circuit breaker and resilience patterns                                            | `trust/resilience/`, `trust/constraint/circuit_breaker.py`                           | **MEDIUM** -- production patterns not captured in any analysis document                |
| SD-JWT selective disclosure                                                        | `trust/sd_jwt.py`                                                                    | **LOW** -- specialist capability, well-documented by IETF spec                         |

The fundamental risk: **the trust/ layer was built through 10+ rounds of red teaming.** Every line of code in that layer represents a finding that was discovered, attacked, and hardened. Removing the code without preserving the _reasoning behind the patterns_ means the next session that reimplements similar logic will repeat the same security mistakes.

#### 1.2 Knowledge in Workspace Artifacts (MODERATE RISK)

The workspace contains three categories of knowledge:

**Analysis documents (17 files)** -- These capture _why_ decisions were made:

- `14-pact-framework-deep-analysis.md` -- The "Structure IS Architecture" insight
- `15-thesis-alignment-check.md` -- 6 gaps between thesis and implementation
- `16-thesis-gaps.md` -- Envelope intersection never formally defined (3 critical gaps)
- `17-thesis-gaps-eatp.md` -- EATP alignment gaps

These remain valid after repivot. No action needed beyond ensuring the analysis directory is not accidentally cleaned up during restructuring.

**Red team reports (26 files)** -- These capture _what was attacked and how defenses evolved_:

- Convergence trend: 34 -> 31 -> 18 -> 15 -> 10 -> 12 -> 33 -> 0 actionable findings
- RT21 governance report documents 40 adversarial tests across 10 attack categories
- Security findings from RT11 document specific vulnerability classes

These are the most valuable artifacts in the repo. They are the institutional memory of every security pattern. If a future session needs to understand _why_ `math.isfinite()` guards exist on every numeric field, the answer is in RT21, not in any comment.

**Plans and todos (100+ files)** -- These are historical. They document what was planned and completed. Low risk of loss; low value for future sessions.

#### 1.3 Knowledge in COC Layer (LOW RISK if COC layer persists)

The `.claude/` directory contains:

- **23 rule files** encoding conventions
- **30+ agent definitions** with specialist knowledge
- **30 skill directories** with implementation patterns
- **13 hook scripts** for enforcement

This is COC's strength: the knowledge is already _externalized_ from the code into the orchestration layer. As long as the `.claude/` directory survives the repivot (it should -- it is repo-level, not code-level), this knowledge persists.

**However**: Several rule files reference code that will change or disappear:

- `trust-plane-security.md` references `trustplane._locking` functions, `trustplane/store/__init__.py`
- `governance.md` references `src/pact/governance/` paths that now live in kailash-py
- `boundary-test.md` references `src/pact/` paths
- `infrastructure-sql.md` references dialect patterns from the trust store

#### 1.4 Knowledge in Memory Files (LOW RISK)

The auto-memory system (`~/.claude/projects/.../memory/`) contains 15 memory files with architectural decisions, build order, migration status, and user preferences. These survive repo changes because they live outside the repo.

### Anti-Amnesia Recommendations

| #   | Action                                                                                                                                                                                 | Priority | Preserves                           |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----------------------------------- |
| A1  | Create `docs/architecture/security-patterns-catalog.md` extracting all 11 security patterns from code and red team reports into a standalone document                                  | CRITICAL | Trust layer security knowledge      |
| A2  | Create `docs/architecture/red-team-synthesis.md` summarizing all 26 red team reports into a single narrative of how the security posture evolved                                       | HIGH     | Attack/defense institutional memory |
| A3  | Create `docs/architecture/constraint-intersection-semantics.md` formally documenting the per-dimension intersection rules currently embedded only in code                              | HIGH     | Envelope computation knowledge      |
| A4  | Create `docs/architecture/trust-layer-disposition.md` documenting what happens to each of the 58 trust files: archived, moved to kailash core, superseded by governance layer, or kept | HIGH     | Migration decision trail            |
| A5  | Add `archive/` directory with git-preserved trust layer code rather than deleting it                                                                                                   | MEDIUM   | Rollback capability                 |

---

## 2. Convention Drift Risk Assessment

Convention drift is the second COC fault line: AI follows internet conventions instead of yours. During a repivot, the risk is different -- it is _internal_ convention drift, where the repo's own rules become stale or contradictory.

### 2.1 Rules That Must Be Updated

| Rule File                 | Current State                                                                   | Post-Repivot State                                                                                          | Action                                                                                                                                     |
| ------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `trust-plane-security.md` | References `trustplane._locking`, `safe_read_json`, `safe_open`, `atomic_write` | These imports no longer exist in this repo if trust/ is archived                                            | **REWRITE** -- extract the patterns into framework-agnostic security rules; point implementation references to kailash-py                  |
| `governance.md`           | References `src/pact/governance/` as the location of governance code            | Governance code is now in `kailash-py/packages/kailash-pact/`                                               | **REWRITE** -- rules now apply to the _downstream consumer_ pattern (how this repo uses kailash-pact), not the _framework builder_ pattern |
| `boundary-test.md`        | Blacklists domain vocabulary in `src/pact/` excluding `examples/`               | After repivot, the entire repo IS an example/reference platform -- the boundary test no longer applies here | **ARCHIVE or REMOVE** -- this rule moves to kailash-py with the framework                                                                  |
| `infrastructure-sql.md`   | SQL safety patterns for trust stores                                            | Trust stores move to kailash-py; this repo may not have SQL code                                            | **CONDITIONALLY ARCHIVE** -- keep if the reference platform has its own persistence                                                        |
| `connection-pool.md`      | DataFlow pool safety                                                            | Still relevant if dashboard connects to DB                                                                  | **KEEP**                                                                                                                                   |
| `patterns.md`             | Kailash execution patterns                                                      | Still relevant -- reference platform uses Kailash                                                           | **KEEP**                                                                                                                                   |
| `eatp.md`                 | EATP SDK conventions                                                            | Still relevant -- reference platform uses EATP                                                              | **KEEP**                                                                                                                                   |
| `zero-tolerance.md`       | Pre-existing failures, no stubs, no workarounds                                 | Still relevant but scope changes (fewer files to enforce against)                                           | **KEEP, adjust scope**                                                                                                                     |

### 2.2 Rules That Remain Unchanged

These rules are repo-agnostic and survive any restructuring:

- `communication.md` -- Plain language communication style
- `agents.md` -- Agent orchestration and review workflow
- `git.md` -- Conventional commits, branch naming
- `security.md` -- Global security rules (no hardcoded secrets, parameterized queries)
- `deployment.md` -- Production deployment requirements
- `independence.md` -- Foundation independence (no commercial coupling)
- `terrene-naming.md` -- Naming conventions and terminology
- `documentation.md` -- Version accuracy
- `no-stubs.md` -- No placeholders in production code
- `branch-protection.md` -- Git branch protection
- `cross-sdk-inspection.md` -- Cross-SDK alignment (still relevant for kailash-py/kailash-rs)

### 2.3 New Rules Needed Post-Repivot

| New Rule                | Purpose                                                                                                                                                         |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `import-boundary.md`    | This repo MUST NOT modify `kailash-pact` primitives. All governance code comes via `import kailash_pact`. If a bug is found, fix it upstream in kailash-py.     |
| `reference-platform.md` | This repo's purpose is demonstration and reference. Every change should make the platform more useful as a learning resource, not add framework-level features. |
| `api-contract.md`       | The dashboard and mobile app consume governance APIs. API contracts between the reference platform and kailash-pact must be versioned and documented.           |

### 2.4 Convention Drift in Agent Definitions

Several agent definitions reference code paths that will change:

- `dataflow-specialist` -- references DataFlow patterns that may not apply to a reference platform
- `pattern-expert` -- references workflow patterns for framework building
- `tdd-implementer` -- references test patterns for the trust layer

These agents do not need removal but should have their system prompts updated to reflect the reference platform context. The risk is low because agents are consulted, not autonomous -- a stale agent prompt degrades quality but does not break anything.

### 2.5 Convention Drift in Skills

Skills in `project/` are tightly coupled to the pre-migration codebase:

- `trust-plane-security-patterns.md` -- references code now in kailash-py
- `trust-layer-patterns.md` -- same
- `store-backend-implementation.md` -- same
- `dashboard-patterns.md` -- still relevant (dashboard stays)

**Recommendation**: Move `trust-*` and `store-*` skills to kailash-py's COC layer. Keep `dashboard-patterns.md`.

---

## 3. Security Blindness Assessment

Security blindness is the third COC fault line: AI takes the shortest path, which is never the secure path. During a repivot, the risk is that security patterns silently disappear when the code that embodies them is removed.

### 3.1 Security Patterns at Risk of Silent Disappearance

The trust layer has 11 hardened security patterns validated through 14 red team rounds:

| #   | Pattern                                        | Where It Lives Now                   | Risk During Repivot                                                                 |
| --- | ---------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------- |
| 1   | `validate_id()` before filesystem/SQL          | `trust/store/`, governance stores    | **MEDIUM** -- pattern exists in both layers; governance copy migrated to kailash-py |
| 2   | `O_NOFOLLOW` via `safe_read_json()`            | `trustplane._locking` (external dep) | **LOW** -- lives in trust-plane package, not in this repo                           |
| 3   | `atomic_write()` for all record writes         | `trustplane._locking` (external dep) | **LOW** -- same                                                                     |
| 4   | `math.isfinite()` on numeric constraints       | Both trust/ and governance/ layers   | **MEDIUM** -- governance copy migrated; trust copy at risk                          |
| 5   | Bounded collections (`deque(maxlen=)`)         | Both layers                          | **MEDIUM** -- same pattern                                                          |
| 6   | Monotonic escalation only                      | Both layers                          | **LOW** -- fundamental to PACT architecture, well-documented in thesis              |
| 7   | `hmac.compare_digest()` for hash comparison    | `trust/integrity.py`                 | **HIGH** -- if trust/ is archived, future code in this repo might use `==`          |
| 8   | Key material zeroization                       | `trust/credentials.py`               | **HIGH** -- specialist pattern, easy to forget                                      |
| 9   | `frozen=True` on security-critical dataclasses | Both layers                          | **LOW** -- enforced by governance.md rule (which moves to kailash-py)               |
| 10  | `from_dict()` validates all fields             | Both layers                          | **MEDIUM** -- pattern exists in governance code now in kailash-py                   |
| 11  | Fail-closed on all error paths                 | Both layers                          | **LOW** -- enforced by rule file, fundamental to PACT philosophy                    |

### 3.2 The Real Security Risk: The Integration Seam

RT18 identified the core finding: "The governance primitives are solid. The integration layer is the gap." The trust/ layer and governance/ layer were built at different times and represent two parallel systems.

During repivot, the reference platform must integrate:

- `kailash-pact` (imported governance primitives)
- The legacy trust/ layer (EATP trust chains, constraint evaluation, shadow enforcer)
- The use/ layer (agent execution, approval queues, sessions)
- The build/ layer (org builder, config, workspace)

The security risk is that the **integration code** (the adapter between these layers) will be written in a new session that lacks awareness of the security patterns from the trust layer's 10 red team rounds. This is exactly the "brilliant new hire with no onboarding" scenario that COC was designed to prevent.

### 3.3 Specific Security Gaps to Watch

| Gap                         | Description                                                                                                                                                                            | Mitigation                                                                                                                              |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Envelope adapter bypass** | `governance/envelope_adapter.py` bridges governance envelopes to trust-layer constraint envelopes. If this adapter is rewritten during repivot, it must preserve fail-closed behavior. | Rule: envelope adapter returns BLOCKED if governance engine fails. No fallback to legacy. (Already in `governance.md` MUST NOT Rule 3.) |
| **Store isolation loss**    | `trust/store_isolation/` (3 files) enforces cross-project record isolation. If trust/ is archived, new persistence code must re-implement isolation.                                   | Extract the isolation protocol into a test fixture that can be applied to any store backend.                                            |
| **Auth token handling**     | `trust/auth/firebase_admin.py` handles SSO token verification. If archived, the reference platform needs its own auth -- and auth is where security mistakes concentrate.              | Keep auth/ as a thin shim or replace with standard library (e.g., `python-jose`).                                                       |
| **Rate limiting state**     | `use/api/server.py` has SlowAPI rate limiting. Restructuring the API layer risks losing rate limit configuration.                                                                      | Document rate limit config in deployment-config.md.                                                                                     |

### 3.4 Security Blindness Recommendations

| #   | Action                                                                                                                                                                                                                                                       | Priority |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------- |
| S1  | Before archiving ANY trust/ file, run the security pattern checklist (11 patterns) against the file and verify each pattern either (a) lives in kailash-py now, (b) lives in trust-plane package, or (c) is explicitly documented for the reference platform | CRITICAL |
| S2  | Create a "security seam test" that verifies the integration between kailash-pact imports and any remaining trust/ code preserves fail-closed behavior at every boundary                                                                                      | HIGH     |
| S3  | The `hmac.compare_digest()` and key zeroization patterns must be captured in a rule file that survives regardless of which code layer persists                                                                                                               | HIGH     |
| S4  | Any new API endpoints in the reference platform must go through the security-reviewer agent before commit -- no exceptions during repivot                                                                                                                    | MEDIUM   |

---

## 4. Knowledge Continuity Plan

### 4.1 Three-Phase Knowledge Migration

**Phase 1: Catalog (before any code changes)**

Create a disposition map for every source file in the repo:

| Layer                    | Files                                     | Disposition                                                                                                      |
| ------------------------ | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `governance/` (30 files) | Already migrated to kailash-py            | **REMOVE** from this repo; import from kailash-pact                                                              |
| `trust/` (58 files)      | Pre-governance EATP implementation        | **TRIAGE**: some move to kailash core, some are superseded by governance layer, some are reference-platform-only |
| `build/` (29 files)      | Org builder, config, workspace, verticals | **KEEP partially**: org builder and config may move to kailash-pact; workspace stays; verticals stay             |
| `use/` (25 files)        | Execution runtime, API, observability     | **KEEP**: this IS the reference platform                                                                         |
| `examples/` (13 files)   | Foundation and university examples        | **KEEP**: these demonstrate how to use kailash-pact                                                              |

**Phase 2: Extract (concurrent with code changes)**

For every file being archived or removed:

1. Check the security pattern checklist (11 items)
2. Check if any analysis document (17 files) or red team report (26 files) references the file
3. If referenced, add a cross-reference note to the analysis/report: "Code moved to [kailash-py path]"
4. If the file contains novel patterns not documented elsewhere, extract them into `docs/architecture/`

**Phase 3: Verify (after code changes)**

1. Run all remaining tests -- zero collection errors, zero failures
2. Run `ruff check` -- zero lint errors
3. Verify every rule file references only files that exist
4. Verify every skill file references only patterns that are accessible (either in this repo or via imports)
5. Verify the anti-amnesia hook (`user-prompt-rules-reminder.js`) still references valid rule files

### 4.2 Specific Documents to Create

| Document                                         | Content                                                                                         | Why                                                         |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `docs/architecture/REPIVOT-ADR.md`               | Architecture Decision Record for the repivot: what moved, what stayed, why                      | Future sessions need to understand the repo's current shape |
| `docs/architecture/security-patterns-catalog.md` | All 11 security patterns with rationale, red team report references, and current code locations | Prevents security pattern amnesia                           |
| `docs/architecture/trust-layer-disposition.md`   | File-by-file disposition of all 58 trust/ files                                                 | Traceability for the migration                              |
| `docs/architecture/red-team-synthesis.md`        | Narrative synthesis of 26 red team rounds                                                       | Institutional memory of adversarial validation              |
| Updated `CLAUDE.md`                              | New architecture overview reflecting reference platform identity                                | Session orientation                                         |
| Updated `pyproject.toml`                         | New identity, dependencies (kailash-pact as requirement), adjusted entry points                 | Package identity                                            |

### 4.3 CLAUDE.md Update Requirements

The CLAUDE.md is the single most important knowledge document for COC. It is the first thing every session reads. Post-repivot, it must reflect:

1. **New identity**: "This repo is the PACT reference platform -- it imports kailash-pact and demonstrates governed agent orchestration with a dashboard, API, CLI, and mobile app."
2. **New architecture table**: Framework layer (kailash-pact, imported) vs Platform layer (this repo, API + dashboard + examples)
3. **Updated component status**: Mark governance as "imported from kailash-pact"; update trust layer status
4. **Updated dependency direction**: `pact-platform` depends on `kailash-pact` depends on `kailash` depends on `eatp`
5. **Preserved framework-first directive**: Still valid -- check Kailash before coding from scratch
6. **Preserved workspace commands**: Still valid -- the workspace workflow is platform-level

---

## 5. Five-Layer Architecture Mapping

### Layer 1: Intent (Agents)

| Aspect                | Pre-Repivot                       | Post-Repivot                                     | Action                                                              |
| --------------------- | --------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------- |
| **Agent count**       | 30+ agents across 7 phases        | Same agents, but some change scope               | Update framework specialist prompts                                 |
| **Key specialists**   | dataflow, nexus, kaizen, mcp      | Same, plus new "platform-integration" specialist | Add agent for platform integration patterns                         |
| **Governance agents** | Build governance primitives       | Consume governance primitives                    | Update system prompts from "implement" to "configure and integrate" |
| **Standards experts** | CARE, EATP, CO, COC, constitution | Unchanged                                        | No action                                                           |

**Risk**: LOW. Agent definitions are in `.claude/agents/` which persists through repivot. System prompts may reference stale code paths, but this degrades quality, it does not break anything.

**Recommendation**: After repivot, do a single pass through all agent `.md` files and update code path references. This can be done in one session.

### Layer 2: Context (Skills and Library)

| Aspect                          | Pre-Repivot                                     | Post-Repivot                                         | Action                                                                                               |
| ------------------------------- | ----------------------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **SDK skills (01-05)**          | Core, DataFlow, Nexus, Kaizen, MCP              | Unchanged -- still using Kailash                     | No action                                                                                            |
| **Architecture decisions (13)** | Framework building patterns                     | Some decisions no longer apply locally               | Review and annotate which are "framework-level (now in kailash-py)" vs "platform-level (still here)" |
| **Project skills**              | Trust-plane security, store backends, dashboard | Trust-plane and store skills reference migrated code | Move trust/store skills to kailash-py COC; keep dashboard skill                                      |
| **Standards reference (26-29)** | EATP, CARE, COC, constitution                   | Unchanged                                            | No action                                                                                            |
| **Progressive disclosure**      | CLAUDE.md -> SKILL.md -> topics -> docs         | Still works, but CLAUDE.md content needs updating    | Update CLAUDE.md (see Section 4.3)                                                                   |

**Risk**: MEDIUM. The context layer has the most stale references. The progressive disclosure hierarchy still works architecturally, but individual files point to code that has moved.

**Recommendation**: Create a script that scans all `.md` files in `.claude/` for references to `src/pact/trust/`, `src/pact/governance/`, and `src/pact/build/` paths, and flags any that reference files no longer in this repo.

### Layer 3: Guardrails (Rules and Hooks)

| Aspect                | Pre-Repivot                                               | Post-Repivot                                       | Action                                               |
| --------------------- | --------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------- |
| **Rule files**        | 23 rules, 9 scoped to trust/governance code               | ~8 rules need updating (see Section 2.1)           | Rewrite 3, archive 2, add 3 new                      |
| **Hook scripts**      | 13 hooks, all functional                                  | Most hooks are generic (format, validate, session) | Verify `validate-hierarchy-grammar.js` still applies |
| **Anti-amnesia hook** | `user-prompt-rules-reminder.js` re-injects critical rules | Must reference updated rule files                  | Update hook if rule files change names               |
| **Defense in depth**  | 5+ enforcement layers per critical rule                   | Some layers reference trust code                   | Verify each layer's code references                  |

**Risk**: MEDIUM-HIGH. Rules that reference non-existent code silently degrade from "enforcement" to "aspiration." A rule that says "use `atomic_write()` from `trustplane._locking`" but the import path has changed means the rule is ignored or confusing. This is the most insidious form of convention drift.

**Recommendation**: After updating rule files, run the validate-workflow hook manually against a test file to verify enforcement still works. The hooks are the deterministic enforcement layer -- they must be correct.

### Layer 4: Instructions (Workflow and Operating Procedures)

| Aspect                        | Pre-Repivot                                                          | Post-Repivot                                | Action                                       |
| ----------------------------- | -------------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------- |
| **Workspace commands**        | `/analyze`, `/todos`, `/implement`, `/redteam`, `/codify`, `/deploy` | All still valid for reference platform work | No action                                    |
| **Quality gates**             | 4 gates: Planning, Implementation, Pre-commit, Pre-push              | Still valid                                 | No action                                    |
| **Evidence-based completion** | File-and-line proof required                                         | Still valid, but file paths change          | Naturally adapts -- references current files |
| **Mandatory delegation**      | Code review after changes, security review before commit             | Still valid                                 | No action                                    |

**Risk**: LOW. The workflow layer is the most stable through a repivot because it operates at the process level, not the code level. "Review code before committing" does not depend on which code you are reviewing.

### Layer 5: Learning (Observation and Evolution)

| Aspect                | Pre-Repivot                                     | Post-Repivot                                           | Action                                                            |
| --------------------- | ----------------------------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------- |
| **Observations**      | `observations.jsonl` with workflow pattern data | Historical observations reference pre-repivot patterns | Clear or archive; new observations will reflect platform patterns |
| **Instincts**         | 2 instincts (workflow_builder pattern)          | workflow_builder may not apply to reference platform   | Let instincts naturally evolve                                    |
| **Evolved artifacts** | None yet                                        | N/A                                                    | No action                                                         |
| **Checkpoints**       | Session checkpoints                             | Historical                                             | Archive with session notes                                        |

**Risk**: LOW. The learning layer is designed to be ephemeral and self-correcting. Stale observations naturally decay (recency weighting at 20%). New sessions generate new observations that reflect the current codebase.

**Recommendation**: After repivot, run one `/codify` session to capture the new platform patterns. This seeds the learning layer with post-repivot knowledge.

---

## 6. Prioritized Execution Plan

Based on the analysis above, here is the recommended execution sequence:

### Phase 0: Knowledge Preservation (Before Any Code Changes)

1. Create `docs/architecture/security-patterns-catalog.md` (Action A1)
2. Create `docs/architecture/trust-layer-disposition.md` (Action A4)
3. Create `docs/architecture/REPIVOT-ADR.md` (Section 4.2)
4. Ensure all 26 red team reports are preserved in workspace

### Phase 1: Code Restructuring

1. Remove `src/pact/governance/` (now in kailash-py) -- replace with `from kailash_pact import ...`
2. Triage `src/pact/trust/` per disposition document:
   - Files superseded by governance layer: archive
   - Files moving to kailash core: document and archive
   - Files needed by reference platform: keep
3. Update `pyproject.toml`: add `kailash-pact>=0.2.0` as dependency
4. Fix test collection errors (153 currently) by updating imports

### Phase 2: COC Layer Update

1. Rewrite `trust-plane-security.md`, `governance.md`, `boundary-test.md` rules
2. Add `import-boundary.md`, `reference-platform.md`, `api-contract.md` rules
3. Update agent system prompts referencing stale code paths
4. Move trust/store skills to kailash-py COC
5. Update CLAUDE.md to reflect reference platform identity

### Phase 3: Verification

1. Zero test collection errors, zero test failures
2. All rule files reference existing code
3. All skill files reference accessible patterns
4. Anti-amnesia hook references valid rules
5. One `/redteam` session against the restructured platform

---

## 7. The COC Thesis Applied

This repivot is a textbook case for why COC exists.

**Without COC**: A developer (or AI) restructures the repo. Code moves, tests break, they fix the tests. Some rule files become stale. Some security patterns disappear. Three sessions later, a new feature is implemented without `math.isfinite()` guards because the rule file that enforced it references a module that no longer exists. The security pattern was lost not because anyone chose to remove it, but because it was coupled to code structure instead of institutional knowledge structure.

**With COC**: The five-layer analysis performed here identifies exactly which knowledge is at risk (Layer 2 and Layer 3), which enforcement mechanisms need updating (Layer 3 hooks and rules), and which workflow patterns remain stable (Layer 4). The anti-amnesia assessment ensures that security patterns are extracted from code into standalone documents before the code is archived. The convention drift assessment ensures that rule files are updated atomically with code changes.

The competitive advantage is not in the code that was migrated to kailash-py. It is in the 26 red team reports, 11 security patterns, 23 rule files, and 17 analysis documents that represent the _institutional knowledge_ of how to build governed systems. That knowledge must survive the repivot intact.

**Bainbridge's Irony applies directly**: The more the framework is automated (imported as a package), the more critical it is that the platform team maintains deep understanding of the governance primitives. The reference platform team must understand _why_ `frozen=True` is required on all governance dataclasses, even though they never write that code themselves. The COC layer -- rules, agents, skills -- is the mechanism for preserving that understanding.

---

## Appendix: File Inventory

### Source Files by Layer

| Layer         | Files   | LOC (est.)  | Post-Repivot Disposition                               |
| ------------- | ------- | ----------- | ------------------------------------------------------ |
| `governance/` | 30      | ~5,500      | REMOVE (migrated to kailash-py)                        |
| `trust/`      | 58      | ~12,000     | TRIAGE (archive most, keep auth and bridge)            |
| `build/`      | 29      | ~6,000      | KEEP partially (org builder may move; workspace stays) |
| `use/`        | 25      | ~5,000      | KEEP (this IS the reference platform)                  |
| `examples/`   | 13      | ~1,200      | KEEP (demonstration code)                              |
| **Total**     | **155** | **~29,700** | ~80 files remain post-repivot                          |

### COC Artifacts

| Category           | Count | Post-Repivot Action                      |
| ------------------ | ----- | ---------------------------------------- |
| Rule files         | 23    | Rewrite 3, archive 2, add 3              |
| Agent definitions  | 30+   | Update system prompts                    |
| Skill directories  | 30    | Move 3 trust/store skills to kailash-py  |
| Command files      | 23    | No change (workflow-level)               |
| Hook scripts       | 13    | Verify references                        |
| Analysis documents | 17    | Preserve (add cross-references)          |
| Red team reports   | 26    | Preserve (critical institutional memory) |
| Memory files       | 15    | Naturally persists (outside repo)        |

### Test Files

| Category            | Files    | Tests (est.) | Post-Repivot Action             |
| ------------------- | -------- | ------------ | ------------------------------- |
| Governance tests    | 37       | 968          | REMOVE (migrated to kailash-py) |
| Trust tests         | ~60      | ~1,500       | TRIAGE with trust/ source       |
| Build tests         | ~30      | ~500         | KEEP partially                  |
| Use/execution tests | ~40      | ~600         | KEEP                            |
| Integration tests   | ~20      | ~200         | KEEP and update                 |
| **Total**           | **~187** | **~3,770**   | ~110 files remain               |
