# M14-T02: Bridge lifecycle state machine

**Status**: ACTIVE
**Priority**: High
**Milestone**: M14 — CARE Formal Specifications
**Dependencies**: 1301-1304

## What

Formalize existing `BridgeStatus` enum transitions into proper `BridgeStateMachine` class with explicit transition table and enforcement. Consolidate scattered transition logic from `Bridge._activate()`, `BridgeManager.suspend_bridge()`, etc.

## Where

- New: `src/care_platform/workspace/bridge_lifecycle.py`
- Modify: `src/care_platform/workspace/bridge.py`

## Evidence

- Unit tests for all valid/invalid transitions; existing bridge tests still pass
