# Task 6013: Move Use-Plane Modules into use/

**Milestone**: M38
**Priority**: Critical
**Effort**: Large
**Status**: Active

## Description

Move all Use Plane source modules into the new `src/care_platform/use/` package. Use Plane modules are those for running and observing the governed organization at runtime — API, execution engine, and observability.

Modules to move:

- `api/` — FastAPI/Nexus routes, PlatformAPI class, endpoint definitions
- `execution/` — agent execution wiring, runner classes
- `observability/` — metrics, structured logging, health check logic

This task covers only the file moves and within-module relative imports. Cross-module imports are updated in task 6014.

## Acceptance Criteria

- [ ] All use-plane source files are under `src/care_platform/use/`
- [ ] Each moved module has its own `__init__.py` with `__all__`
- [ ] Relative imports within the `use/` subtree are correct
- [ ] `src/care_platform/use/__init__.py` re-exports the primary public API (PlatformAPI, etc.)
- [ ] FastAPI application factory still importable and runnable after move
- [ ] Docker entrypoint command (uvicorn path) updated if module path changed
- [ ] Git history preserved (use `git mv`)

## Dependencies

- Task 6010 (directory structure must exist)
- Can be done in parallel with 6011 and 6012

## Risk

The Docker entrypoint references the FastAPI app module path directly. If the path changes, the Dockerfile CMD must be updated in the same commit to prevent a broken image.
