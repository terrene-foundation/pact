# M14-T03: Workspace lifecycle state machine

**Status**: ACTIVE
**Priority**: High
**Milestone**: M14 — CARE Formal Specifications
**Dependencies**: 1301-1304

## What

Add `WorkspaceState` enum (PROVISIONING, ACTIVE, ARCHIVED, DECOMMISSIONED) alongside existing `WorkspacePhase` (ANALYZE, PLAN, IMPLEMENT, VALIDATE, CODIFY). Phase tracks CO methodology cycle; State tracks operational lifecycle.

Valid transitions: PROVISIONING→ACTIVE, ACTIVE→ARCHIVED, ARCHIVED→ACTIVE (reactivation), ACTIVE→DECOMMISSIONED, ARCHIVED→DECOMMISSIONED. Phase cycling only allowed when state is ACTIVE.

## Where

- Modify: `src/care_platform/workspace/models.py`

## Evidence

- Unit tests for workspace state transitions; existing workspace tests still pass
