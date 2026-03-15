# 1203: Bootstrap and Initialization Flow

**Priority**: Critical
**Effort**: Medium
**Source**: RT3 Theme D
**Dependencies**: 1201 (persistence), 1202 (workspace discovery)

## Problem

No `care init` or bootstrap sequence exists. A fresh Foundation repo has no way to establish the trust root, create genesis records, delegate to workspace teams, or set up constraint envelopes.

## Implementation

Create `care_platform/bootstrap.py`:

- Bootstrap from an organization definition (YAML)
- Create genesis record for the organization
- Discover workspaces from disk
- Create delegation chains for each workspace team
- Generate constraint envelopes per the org definition
- Persist all trust state via TrustStore
- Idempotent: re-running bootstrap updates without duplicating

## Acceptance Criteria

- [ ] Can bootstrap from org definition YAML
- [ ] Creates complete trust hierarchy
- [ ] Idempotent (safe to re-run)
- [ ] Tests verify bootstrap creates correct trust chain
