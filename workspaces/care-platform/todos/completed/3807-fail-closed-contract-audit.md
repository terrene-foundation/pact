# 3807: Fail-Closed Contract Audit

**Milestone**: 10 — Systematic Quality (Tier 3)
**Item**: 3.1
**Priority**: After Tier 2 (3804-3806) — audit should cover newly enhanced modules

## What

Systematically audit all trust layer files for fail-closed compliance and add CI enforcement to prevent regressions.

### What "fail-closed" means

Every error path in the trust layer must deny/block/restrict — never silently allow. Specifically:

- Exception during verification → BLOCKED (not approved)
- Missing agent_id → BLOCKED (not ignored)
- Service unavailable → BLOCKED (not bypassed)
- Unknown posture → PSEUDO_AGENT (most restrictive)
- Exception in constraint evaluation → DENIED (not allowed)
- Timeout during trust chain lookup → BLOCKED (not cached stale result)

The one exception: ShadowEnforcer, which by design never blocks (it's observational).

### Audit scope

**Every `.py` file** under these directories (use glob, not a hardcoded list):

- `src/care_platform/trust/**/*.py`
- `src/care_platform/constraint/**/*.py`
- `src/care_platform/audit/**/*.py`
- `src/care_platform/persistence/**/*.py`

**Exempt from blocking requirement**: `shadow_enforcer.py` (observational by design — never blocks).

### Deliverables

#### 1. Audit report

For each file, verify every `except` block, `if/else` branch, and error return:

- Does the error path deny?
- Is there a bare `except: pass` that silently allows?
- Are there `return None` paths that could be interpreted as "allowed"?
- Document findings as a checklist in the audit report

#### 2. Fix any violations

Any fail-open patterns found during the audit must be fixed immediately (not deferred).

#### 3. CI lint rule

Create a custom ruff/pylint rule or pre-commit script that:

- Scans `src/care_platform/trust/` and `src/care_platform/constraint/` directories
- Flags `except` blocks that `return True`, `return None`, or `pass` without logging
- Flags `except Exception` without re-raise or deny action
- Exempts `shadow_enforcer.py` (which has intentional fail-open for observation)
- Runs as part of CI pipeline

#### 4. Fail-closed contract document

Add `docs/architecture/fail-closed-contract.md` documenting:

- The fail-closed requirement for trust/constraint layers
- Why ShadowEnforcer is exempt
- How to add new trust layer code that complies
- How the CI lint rule enforces it

## Where

- **Audit report**: `workspaces/care-platform/04-validate/fail-closed-audit.md`
- **Fixes**: Various files under `src/care_platform/trust/` and `src/care_platform/constraint/`
- **CI script**: `scripts/lint_fail_closed.py`
- **Contract doc**: `docs/architecture/fail-closed-contract.md`
- **Tests**: `tests/unit/test_fail_closed_lint.py`

## Evidence

- [ ] Audit report covers every trust/constraint file
- [ ] All fail-open violations fixed (zero remaining)
- [ ] CI lint script created and tested
- [ ] Lint script correctly exempts ShadowEnforcer
- [ ] Lint script catches known fail-open patterns
- [ ] Fail-closed contract documented
- [ ] Unit tests: lint script detects intentional bad patterns
- [ ] Unit tests: lint script passes on compliant code
- [ ] Security review: no trust layer code silently allows on error

## Dependencies

- 3804, 3805, 3806 (audit should cover the newly enhanced modules)
- 3801, 3802, 3803 (audit should cover the new decorator and enforcement pipeline)
