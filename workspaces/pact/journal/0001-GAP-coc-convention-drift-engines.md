---
type: GAP
date: 2026-03-30
project: pact
topic: COC convention drift — artifacts teach primitives, not engine APIs
phase: analyze
tags:
  [coc, convention-drift, dataflow, express, patterns, institutional-knowledge]
---

# COC Convention Drift: Artifacts Teach Primitives Instead of Engine APIs

## The Gap

The COC artifacts (CLAUDE.md, rules/patterns.md, skills/02-dataflow/quickstart) all teach low-level SDK primitives (`WorkflowBuilder` → `add_node()` → `runtime.execute(workflow.build())`) as the primary and default pattern for DataFlow operations.

The SDK evolved to provide engine-level APIs — specifically `DataFlow.express` (23x faster, simpler API) — but the COC artifacts were never updated. This caused pact-platform to accumulate 83 primitive call sites across 15 files when Express API calls would have been correct, simpler, and 23x faster.

## Root Cause

**Convention drift (COC Fault Line 2)**: The SDK evolved but institutional knowledge (COC artifacts) didn't keep pace.

The hierarchy of influence on agent behavior:

1. CLAUDE.md "Critical Execution Rules" (every turn) → teaches primitives
2. rules/patterns.md (every .py edit) → teaches primitives
3. skills/02-dataflow/quickstart (DataFlow questions) → teaches primitives
4. skills/02-dataflow/express (only if specifically asked) → teaches engine

The express skill exists but is buried under 3 layers of primitive-teaching artifacts. No agent would discover it through normal workflow.

## Impact

- 83 unnecessary primitive call sites in pact-platform
- 23x slower database operations than necessary
- ~200 lines of boilerplate workflow construction that could be single-line express calls
- Every future USE repo will inherit the same pattern

## Required Actions

1. Update CLAUDE.md "Critical Execution Rules" — lead with Express, keep workflow as fallback
2. Update rules/patterns.md — add DataFlow Express section before workflow section
3. Update skills/02-dataflow/quickstart — lead with Express
4. File codify proposal to kailash-coc-claude-py for upstream distribution
5. Migrate pact-platform from primitives to Express (Phase 1-2 in migration plan)

## Cross-Reference

- `workspaces/pact/01-analysis/42-engine-migration-analysis.md` — Full analysis
- `feedback_engine_over_primitives.md` — Memory record for future sessions
