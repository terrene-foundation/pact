# Task 6014: Update All Source Imports Across the Codebase

**Milestone**: M38
**Priority**: Critical
**Effort**: Large
**Status**: Active

## Description

After tasks 6011-6013 have moved all modules into their new planes, every cross-module import in the source tree will be broken. This task does a systematic find-and-replace of all import paths across `src/` to reflect the new `trust/`, `build/`, `use/` structure.

Examples of what changes:

- `from care_platform.constraint import ...` → `from care_platform.trust.constraint import ...`
- `from care_platform.org import ...` → `from care_platform.build.org import ...`
- `from care_platform.api import ...` → `from care_platform.use.api import ...`

## Acceptance Criteria

- [ ] All `from care_platform.X import` statements updated to `from care_platform.{plane}.X import`
- [ ] All `import care_platform.X` statements updated
- [ ] No remaining references to old module paths in `src/` (verified by grep)
- [ ] `python -c "import care_platform"` executes without ImportError
- [ ] FastAPI application starts without ImportError
- [ ] CLI `care --help` works without ImportError
- [ ] All existing source-level import sanity checks pass

## Dependencies

- Tasks 6011, 6012, 6013 (all module moves must be complete)

## Approach

Use systematic grep + sed or a script to find all old import paths, then update them. Commit the import updates as a single atomic commit separate from the file moves, so git history clearly shows "moved files" vs "updated imports."
