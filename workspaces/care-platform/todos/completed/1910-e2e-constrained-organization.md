# M19-T10: E2E — CARE Platform IS a Constrained Organization

**Status**: ACTIVE
**Priority**: High
**Milestone**: M19 — Constrained Organization Validation
**Dependencies**: 1901-1909

## What

Single comprehensive E2E test proving the CARE Platform is a Constrained Organization: bootstrap full org → execute agent actions → verify all five properties and three behavioral tests hold simultaneously.

## Where

- New: `tests/integration/test_constrained_organization.py`

## Evidence

- Bootstrap → agent execution → constraint enforcement → trust verification → audit chain → knowledge compounding — all pass
