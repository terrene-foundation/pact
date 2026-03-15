# Todo 2101: Wire .env Loading Across Server/CLI/Bootstrap

**Milestone**: M21 — Hardening and Operational Readiness
**Priority**: High
**Effort**: Small
**Source**: RT10-A2 (implied)
**Dependencies**: None

## What

Add `load_dotenv()` from python-dotenv to the three process entry points: `server.py` `get_app()`, CLI `main()`, and `bootstrap.py`. The python-dotenv package is already declared in `pyproject.toml` but is never imported at any entry point, so environment variables in `.env` are silently ignored unless the caller exports them manually. The fix is a single import and call at the top of each entry point, executed before any configuration is read.

## Where

- `src/care_platform/api/server.py` — `get_app()` function (server entry point)
- `src/care_platform/cli/__init__.py` — `main()` function (CLI entry point)
- `src/care_platform/bootstrap.py` — module top-level or `bootstrap()` function (initialization entry point)

## Evidence

- [ ] Server reads `CARE_API_TOKEN` from a `.env` file on startup without requiring shell export
- [ ] CLI reads configuration values from `.env` without requiring shell export
- [ ] Unit test confirms `load_dotenv` is called before config reads in each entry point
- [ ] Existing tests continue to pass (no regression from adding dotenv loading)
