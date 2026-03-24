# Repivot Analysis Synthesis

**Date**: 2026-03-21
**Inputs**: Deep analysis (#18), Requirements (#19), COC analysis (#20), Value audit (#21)
**Decision**: Proceed with repivot, but prerequisite work in kailash-py must happen first

---

## What We're Doing

Transitioning this repo from "the source of the governance framework" to "the canonical deployment that shows how a PACT-governed organization runs." The framework code moves to kailash-py where it can be installed via `pip install kailash-pact`. This repo keeps the API server, dashboard, execution runtime, examples, and deployment config.

## Who It's For

Three audiences:

1. **Vertical developers** (Astra finance, Arbor HRIS) — They `pip install kailash-pact` from kailash-py and configure it for their domain. This repo is their reference: "here's what a complete PACT deployment looks like."

2. **Enterprise evaluators** — They clone this repo, run `docker compose up`, and see governance in action: the dashboard, the D/T/R tree, the verification gradient, the audit trail. This is the product surface they judge.

3. **Foundation contributors** — They work on the governance framework in kailash-py, and use this repo to validate their changes in a real deployment context.

## What Makes This Approach Sound

The "structure IS architecture" insight (from the Astra paradigm shift document) means PACT replaces five separate cross-cutting concerns (permissions, audit, approval workflows, rate limits, data classification) with one coherent model. The framework handles the model. This repo demonstrates the model working.

**The ecosystem role is clear**: kailash-pact is the engine; this repo is the car. Evaluators judge cars, not engines on stands. Verticals buy engines to build their own cars.

## The Blocker

**The migration to kailash-py is incomplete.** The 31 governance files copied there have 30+ dangling imports — they reference `pact.build.config.schema`, `pact.build.org.builder`, `pact.trust.constraint.envelope`, and `pact.use.api.events`, none of which exist in kailash-py. Running `pip install kailash-pact` from kailash-py would fail immediately.

The root cause: `pact.build.config.schema` (528 lines) is the gravitational center of the entire codebase. It defines `ConfidentialityLevel`, `TrustPostureLevel`, `ConstraintEnvelopeConfig`, and 12 other core types imported by 58 of 156 source files (37%). It was classified as "platform code" during migration, but it's actually foundational vocabulary that the governance layer cannot function without.

**This must be fixed in kailash-py before the repivot can begin here.**

## The Plan

### Phase 0: Complete the Migration in kailash-py (PREREQUISITE)

This work happens in `~/repos/kailash/kailash-py`, not here.

1. Extract core types from `pact.build.config.schema` into kailash-pact (likely as `pact.governance.types` or `pact.types`)
2. Move `OrgDefinition` from `pact.build.org.builder` into kailash-pact
3. Decouple `governance/api/events.py` from the platform event bus
4. Make `envelope_adapter.py`'s trust import optional
5. Rewrite kailash-pact's `__init__.py` to export only governance types
6. Migrate the 230 governance tests (kailash-py currently has zero)
7. Verify: `pip install kailash-pact && python -c "from pact.governance import GovernanceEngine"`

### Phase 1: Repivot This Repo

1. Change pyproject.toml: stop publishing as `kailash-pact`, depend on it instead
2. Delete local `src/pact/governance/` (now comes from the installed package)
3. Update `src/pact/__init__.py` to export platform types only
4. Fix the 153 test collection errors
5. Add backward-compatibility import shims if needed

### Phase 2: Trust Layer Disposition

The 58-file trust layer is the hardest call. Three categories:

- **EATP SDK code** (~20 files) — becomes dead code when EATP merges into kailash core
- **Constraint evaluation engine** (~15 files) — legitimate framework code, may need to move to kailash-pact
- **Platform-specific** (~15 files) — posture scoring, shadow enforcer, resilience patterns

Pragmatic approach: keep in place, mark EATP code as deprecated, let the EATP absorption handle lifecycle. The 135 internal imports make aggressive extraction high-risk for low immediate value.

### Phase 3: Cleanup

1. Delete `build/verticals/` (dead re-export shims)
2. Update CLAUDE.md, README.md for new identity
3. Update 3 rule files that reference moved code
4. Dashboard API contract validation
5. Preserve red team knowledge (26 reports — the most valuable artifacts in the repo)

## Key Risks

| Risk                                                       | Severity | Mitigation                                                        |
| ---------------------------------------------------------- | -------- | ----------------------------------------------------------------- |
| kailash-py package can't import (dangling deps)            | CRITICAL | Must fix before anything else                                     |
| `pact.*` namespace collision (two packages, one namespace) | CRITICAL | Delete local governance/ so kailash-pact owns `pact.governance.*` |
| Security patterns silently disappear                       | HIGH     | Catalog the 11 hardened patterns before removing any trust/ code  |
| Convention drift (rules reference dead code)               | HIGH     | Audit and update rule files during Phase 1                        |
| Test rot (230 governance tests here, 0 in kailash-py)      | HIGH     | Migrate tests in Phase 0                                          |

## Decisions Needed From You

1. **Repo identity after repivot** — The value auditor suggests "PACT Operations Center" over "reference platform." The deep analyst recommends keeping the name `pact` with no PyPI publish (it's a deployment artifact, not a library). What feels right?

2. **Where should `schema.py` types land in kailash-py?** Options:
   - `pact.governance.types` (keeps everything under governance)
   - `pact.types` (signals they're cross-cutting)
   - `pact.config` (preserves current mental model)

3. **Is the constraint evaluation engine framework or platform?** If framework, `constraint/envelope.py` and `constraint/gradient.py` move to kailash-py alongside governance. If platform, they stay here and kailash-pact is purely policy (no runtime evaluation).

4. **Dashboard** — Keep here as the reference frontend? Move to its own repo? Or treat as deprecated?

5. **Should we start with Phase 0 in kailash-py now?** That's the blocker for everything else. Or would you prefer to handle the repivot differently — for example, by not separating at all (keeping everything in one repo and just publishing a subset to PyPI)?

## Success Criteria

- `pip install kailash-pact` works and `from pact.governance import GovernanceEngine` succeeds
- This repo depends on kailash-pact, doesn't publish it
- No duplicate governance source code
- All tests pass (0 collection errors)
- Dashboard loads and renders
- `docker compose up` starts all services
- Examples (university, foundation) execute cleanly
- CLAUDE.md and README reflect reality
