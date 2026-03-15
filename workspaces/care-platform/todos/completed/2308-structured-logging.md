# Todo 2308: Structured Logging with Correlation IDs

**Milestone**: M23 — Security Hardening: Production Readiness
**Priority**: High
**Effort**: Medium
**Source**: I1
**Dependencies**: 2101 (.env loading wired — log level configuration via env vars)

## What

Replace ad-hoc Python `logging` calls with structured JSON logging using `structlog`. Every log event must include a correlation ID that ties together the full lifecycle of a single action: submission, verification, hold/approval (if applicable), execution, and audit anchor creation. This makes the governance trail readable in log aggregators without querying the database.

**Correlation ID propagation**:

- Generated at action submission time (UUID)
- Passed through verification, hold queue, execution, and audit stages as a bound context variable
- Included in every log event produced during that action's lifecycle

**Log levels per component**:

- Configurable via env vars: `CARE_LOG_LEVEL` (global default), `CARE_LOG_LEVEL_TRUST`, `CARE_LOG_LEVEL_CONSTRAINT`, `CARE_LOG_LEVEL_AUDIT`, `CARE_LOG_LEVEL_API`
- Falls back to `CARE_LOG_LEVEL` then `INFO` if component-specific var not set

**Output**:

- JSON format in production (when `CARE_DEV_MODE` is false)
- Human-readable format in development (when `CARE_DEV_MODE` is true)

## Where

- `src/care_platform/logging/` — new module: `structlog` configuration, correlation ID context var, log level resolver
- All modules that currently use `logging` — replace with `structlog.get_logger()` and bind correlation ID where available

## Evidence

- [ ] Log output is valid JSON in production mode
- [ ] Log output is human-readable in dev mode (`CARE_DEV_MODE=true`)
- [ ] A single action's full lifecycle (submit, verify, execute, audit) is traceable by a single correlation ID across all log lines
- [ ] `CARE_LOG_LEVEL_TRUST` controls verbosity of trust module independently
- [ ] `CARE_LOG_LEVEL_CONSTRAINT` controls verbosity of constraint module independently
- [ ] Log level defaults to INFO when no env var is set
- [ ] No raw `logging.getLogger` calls remain in production modules (use structlog)
- [ ] Unit test confirms correlation ID is present in log output for a verification call
- [ ] Unit test confirms log level env vars are respected
