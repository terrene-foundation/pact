# M16-T04: Deployment state persistence — OrgBuilder state to store

**Status**: ACTIVE
**Priority**: High
**Milestone**: M16 — Gap Closure: Runtime Enforcement
**Dependencies**: 1301-1304

## What

`OrgBuilder` state is in-memory only. Persist `OrgDefinition` to TrustStore so platform can resume from persisted state after restart.

## Where

- Modify: `src/care_platform/org/builder.py` (add `save()` / `load()`)
- Modify: `src/care_platform/persistence/store.py` (add `store_org_definition()` / `get_org_definition()`)
- Implement in `MemoryStore`, `FilesystemStore`, `SQLiteTrustStore`

## Evidence

- Test: build org, save, load, verify roundtrip equality
- Test: bootstrap from persisted org definition
