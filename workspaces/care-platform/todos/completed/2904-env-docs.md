# Todo 2904: Environment Configuration Documentation

**Milestone**: M29 — Deployment and Operations
**Priority**: Medium
**Effort**: Small
**Source**: Phase 3 requirement
**Dependencies**: 2101, 2102

## What

Write complete documentation for every environment variable consumed by the CARE Platform. For each variable record: the variable name, whether it is required or optional, the default value (if any), the set of valid values or expected format, and the security implications (for example, whether it is a secret that must be managed via a secrets manager, or a non-sensitive configuration value). Group variables by subsystem: core/bootstrap, LLM backends, persistence, API server, frontend, observability. Keep `docs/environment.md` and `.env.example` in sync: every variable documented must appear in `.env.example` with a placeholder or default value, and every variable in `.env.example` must be documented.

## Where

- `docs/environment.md`

## Evidence

- [ ] Every environment variable read by the platform is documented in `docs/environment.md`
- [ ] Every documented variable appears in `.env.example` with a placeholder or default
- [ ] Every variable in `.env.example` is documented in `docs/environment.md`
- [ ] Required vs optional status is explicit for every variable
- [ ] Security implications are documented for every variable that is a secret
- [ ] A grep for `os.environ` and `os.getenv` across `src/` confirms no undocumented variables
