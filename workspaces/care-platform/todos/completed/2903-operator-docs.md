# Todo 2903: Operator Documentation

**Milestone**: M29 — Deployment and Operations
**Priority**: High
**Effort**: Medium
**Source**: Phase 3 requirement
**Dependencies**: 2901, 2902, 2601, 2604

## What

Write a comprehensive operator guide covering everything a self-hosting operator needs to deploy, run, and maintain the CARE Platform. Sections required: deployment (prerequisites, step-by-step Docker Compose setup), configuration (all environment variables with required/optional status, defaults, and valid values), monitoring (health probe endpoints, structured log fields to watch, recommended alerting thresholds), backup and restore (procedure using the `care backup` and `care restore` CLI commands, recommended backup schedule), key rotation (procedure for rotating `CARE_API_TOKEN` and cryptographic signing keys without downtime), incident response (what to do when health checks fail, trust chain corruption detected, database unreachable), and upgrade procedures (how to apply schema migrations during a version upgrade).

## Where

- `docs/operator-guide.md`

## Evidence

- [ ] A new operator with no prior knowledge of the platform can deploy it using only the guide
- [ ] All environment variables described in the guide match those in `.env.example`
- [ ] Health probe endpoint paths in the guide match the actual FastAPI routes
- [ ] Backup and restore procedure is accurate and produces a working restore
- [ ] Key rotation procedure is tested and does not cause downtime
- [ ] Upgrade procedure correctly describes running schema migrations
- [ ] Documentation-validator agent confirms all CLI commands in the guide execute without error
