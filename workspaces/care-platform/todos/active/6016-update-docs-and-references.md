# Task 6016: Update CLAUDE.md, Documentation, and Path References

**Milestone**: M38
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

After the module restructure, all documentation that references file paths or module import paths must be updated. This includes CLAUDE.md (the primary developer context file), any docs/ pages, the README, and any scripts or config files that reference source paths.

## Acceptance Criteria

- [ ] `CLAUDE.md` updated to reflect new `trust/`, `build/`, `use/` package structure and module locations
- [ ] `README.md` updated if it references module paths or package structure
- [ ] `docs/` pages updated for any import examples or architecture diagrams showing module paths
- [ ] Any shell scripts or Makefile targets that reference source paths updated
- [ ] `conftest.py` files updated if they reference old import paths
- [ ] Architecture overview section in CLAUDE.md reflects the Fractal Dual Plane structure explicitly
- [ ] No stale references to old paths remain (grep check: `grep -r "care_platform\." docs/ CLAUDE.md` shows only new paths)

## Dependencies

- Tasks 6014, 6015 (restructure and import updates complete, so documentation reflects final state)
